#!/usr/bin/env python3
"""
Media Sync Cronjob
Synchronizes movies and shows from Trakt lists to Radarr/Sonarr
Based on Real-Debrid capacity
"""

import json
import requests
import logging
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from typing import Dict, List, Optional
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MediaSyncManager:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the manager with config file path"""
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.current_hour = datetime.now().hour
        
    def load_config(self) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def save_config(self):
        """Save updated configuration back to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Config saved successfully")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
    
    def is_in_blackout_period(self) -> bool:
        """Check if current time is within any configured blackout period"""
        blackout_periods = self.config.get('blackout_periods', [])
        
        if not blackout_periods:
            return False
        
        now = datetime.now()
        
        for period in blackout_periods:
            if not period.get('enabled', True):
                continue
            
            try:
                recurring = period.get('recurring', 'once')
                
                if recurring == 'daily':
                    # Daily recurring blackout - only check time, not date
                    if self._is_in_daily_blackout(period, now):
                        logger.info(f"In daily blackout period: {period.get('name', 'Unnamed')}")
                        return True
                
                elif recurring == 'once':
                    # One-time blackout period
                    if self._is_in_onetime_blackout(period, now):
                        logger.info(f"In blackout period: {period.get('name', 'Unnamed')}")
                        return True
                
            except Exception as e:
                logger.warning(f"Error parsing blackout period {period.get('name', 'Unnamed')}: {e}")
                continue
        
        return False
    
    def _is_in_daily_blackout(self, period: Dict, now: datetime) -> bool:
        """Check if current time is within a daily recurring blackout"""
        start_time_str = period.get('start_time')
        end_time_str = period.get('end_time')
        duration_str = period.get('duration')
        
        if start_time_str and end_time_str:
            # Time range mode (e.g., 18:00 to 23:00)
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
            current_time = now.time()
            
            # Handle overnight periods (e.g., 23:00 to 02:00)
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time
        
        elif start_time_str and duration_str:
            # Start time + duration mode
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            delta = self._parse_duration(duration_str)
            
            # Create datetime objects for today
            start_datetime = datetime.combine(now.date(), start_time)
            end_datetime = start_datetime + delta
            
            # If duration spans multiple days, adjust comparison
            if end_datetime.date() > now.date():
                # Check if we're between start today and end tomorrow
                return now >= start_datetime
            elif end_datetime.date() < now.date():
                # Check if we're before end time (carried over from yesterday)
                yesterday_start = start_datetime - timedelta(days=1)
                yesterday_end = yesterday_start + delta
                return now <= yesterday_end
            else:
                # Same day
                return start_datetime <= now <= end_datetime
        
        return False
    
    def _is_in_onetime_blackout(self, period: Dict, now: datetime) -> bool:
        """Check if current time is within a one-time blackout period"""
        start_str = period.get('start')
        end_str = period.get('end')
        duration_str = period.get('duration')
        
        if start_str and end_str:
            # Time range mode
            start_time = datetime.fromisoformat(start_str)
            end_time = datetime.fromisoformat(end_str)
            return start_time <= now <= end_time
        
        elif start_str and duration_str:
            # Start + duration mode
            start_time = datetime.fromisoformat(start_str)
            delta = self._parse_duration(duration_str)
            end_time = start_time + delta
            return start_time <= now <= end_time
        
        return False
    
    def _parse_duration(self, duration_str: str) -> timedelta:
        """
        Parse duration string to timedelta
        Supports formats like: "2h", "30m", "1d", "2w", "1y"
        Can combine: "1d 2h 30m"
        """
        duration_map = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days',
            'w': 'weeks'
        }
        
        total_delta = timedelta()
        parts = duration_str.strip().split()
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Extract number and unit
            unit = part[-1].lower()
            try:
                value = int(part[:-1])
            except ValueError:
                logger.warning(f"Invalid duration part: {part}")
                continue
            
            if unit == 'y':
                # Approximate year as 365 days
                total_delta += timedelta(days=value * 365)
            elif unit in duration_map:
                kwargs = {duration_map[unit]: value}
                total_delta += timedelta(**kwargs)
            else:
                logger.warning(f"Unknown duration unit: {unit}")
        
        return total_delta

    def get_rd_active_count(self) -> Dict:
        """Get active torrents count from Real-Debrid"""
        url = "https://api.real-debrid.com/rest/1.0/torrents/activeCount"
        headers = {
            "Authorization": f"Bearer {self.config['rd']['token']}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get RD active count: {e}")
            raise
    
    def calculate_download_capacity(self, rd_data: Dict) -> tuple:
        """Calculate how many movies and whether shows can be downloaded"""
        nb = rd_data['nb']
        limit = rd_data['limit']
        
        half_download = limit // 2  # Integer division for cleaner logic
        download_left = limit - nb
        # Calculate total movie downloads, ensuring non-negative
        total_movie_ddl = max(0, download_left - half_download)
        can_download_show = download_left >= 10
        
        logger.info(f"Download capacity - Movies: {total_movie_ddl}, Shows: {can_download_show}")
        return total_movie_ddl, can_download_show
    
    def get_list_items(self, list_meta: Dict) -> List[Dict]:
        """Fetch items from a MDBlist"""
        apiKey = self.config['mdbList']['api_key']
        url = f"https://api.mdblist.com/lists/{list_meta['id']}/items?apikey={apiKey}&unified=true"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get MDBlist list {list_meta['name']}: {e}")
            return []
    
    def get_radarr_existing_movies(self) -> List[int]:
        """Get list of existing TMDB IDs from Radarr"""
        base_url = self.config['radarr']['base_url']
        port = self.config['radarr'].get('port')
        api_key = self.config['radarr']['api_key']
        
        # Build URL with optional port
        if port:
            url = f"{base_url}:{port}/api/v3/movie"
        else:
            url = f"{base_url}/api/v3/movie"
        
        headers = {"X-Api-Key": api_key}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            movies = response.json()
            
            # Extract TMDB IDs
            return [movie['tmdbId'] for movie in movies if 'tmdbId' in movie]
        except Exception as e:
            logger.error(f"Failed to get Radarr movies: {e}")
            return []
    
    def radarr_lookup_movie(self, tmdb_id: int) -> Optional[Dict]:
        """Look up movie details in Radarr by TMDB ID"""
        base_url = self.config['radarr']['base_url']
        port = self.config['radarr'].get('port')
        api_key = self.config['radarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/movie/lookup?term=tmdb%3A{tmdb_id}"
        else:
            url = f"{base_url}/api/v3/movie/lookup?term=tmdb%3A{tmdb_id}"
        
        headers = {"X-Api-Key": api_key}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            results = response.json()
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to lookup movie {tmdb_id}: {e}")
            return None
    
    def radarr_add_movie(self, movie_data: Dict, list_meta: Dict) -> bool:
        """Add a movie to Radarr"""
        base_url = self.config['radarr']['base_url']
        port = self.config['radarr'].get('port')
        api_key = self.config['radarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/movie"
        else:
            url = f"{base_url}/api/v3/movie"
        
        headers = {"X-Api-Key": api_key}
        
        payload = {
            "tmdbId": movie_data['tmdbId'],
            "qualityProfileId": list_meta['qualityProfileId'],
            "rootFolderPath": list_meta['rootFolderPath'],
            "addOptions": {
                "monitor": "movieOnly",
                "searchForMovie": True
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Added movie: {movie_data.get('title', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to add movie: {e}")
            return False
    
    def process_movies(self, total_movie_ddl: int):
        """Process movie lists and add to Radarr"""
        movie_list = self.config.get('movies', [])
        
        if not movie_list:
            logger.info("No movie lists configured")
            return
        
        # Calculate starting index based on current hour
        list_count = len(movie_list)
        start_index = self.current_hour % list_count
        
        logger.info(f"Processing movies starting from index {start_index}")
        
        list_in_order = []

        for i in range(total_movie_ddl):
            list_in_order.append(movie_list[(start_index + i) % list_count])
            
        # Fetch all list items
        list_item_dictionary = {}
        for list_meta in movie_list:
            items = self.get_list_items(list_meta)
            list_item_dictionary[list_meta['id']] = items
            logger.info(f"Fetched {len(items)} items from list {list_meta['name']}")
        
        # Get existing movies from Radarr
        existing_tmdb_ids = self.get_radarr_existing_movies()
        logger.info(f"Found {len(existing_tmdb_ids)} existing movies in Radarr")
        
        # Process each list
        movies_added = 0
        for idx, list_meta in enumerate(list_in_order):
            # Cycle through lists if we've added more than total_movie_ddl
            if movies_added >= total_movie_ddl:
                break
            
            items = list_item_dictionary[list_meta['id']]
            
            # Filter for movies only and not already in Radarr
            for item in items:
                if movies_added >= total_movie_ddl:
                    break
                
                if item.get('mediatype') != 'movie':
                    continue
                
                tmdb_id = item.get('id')
                
                if not tmdb_id or tmdb_id in existing_tmdb_ids:
                    continue
                
                movie_data = self.radarr_lookup_movie(tmdb_id)
        
                if movie_data:
                    if self.radarr_add_movie(movie_data, list_meta):
                        movies_added += 1
                        existing_tmdb_ids.append(tmdb_id)  # Prevent duplicates in this run
                        break;
        
        logger.info(f"Added {movies_added} movies to Radarr")
    
    def get_sonarr_existing_series(self) -> List[int]:
        """Get list of existing TMDB IDs from Sonarr"""
        base_url = self.config['sonarr']['base_url']
        port = self.config['sonarr'].get('port')
        api_key = self.config['sonarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/series"
        else:
            url = f"{base_url}/api/v3/series"
        
        headers = {"X-Api-Key": api_key}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            series = response.json()
            return [show['tmdbId'] for show in series if 'tmdbId' in show]
        except Exception as e:
            logger.error(f"Failed to get Sonarr series: {e}")
            return []
    
    def sonarr_lookup_series(self, tmdb_id: int) -> Optional[Dict]:
        """Look up series details in Sonarr by TMDB ID"""
        base_url = self.config['sonarr']['base_url']
        port = self.config['sonarr'].get('port')
        api_key = self.config['sonarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/series/lookup?term=tmdb%3A{tmdb_id}"
        else:
            url = f"{base_url}/api/v3/series/lookup?term=tmdb%3A{tmdb_id}"
        
        headers = {"X-Api-Key": api_key}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            results = response.json()
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to lookup series {tmdb_id}: {e}")
            return None
    
    def sonarr_add_series(self, series_data: Dict, list_meta: Dict) -> bool:
        """Add a series to Sonarr"""
        base_url = self.config['sonarr']['base_url']
        port = self.config['sonarr'].get('port')
        api_key = self.config['sonarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/series"
        else:
            url = f"{base_url}/api/v3/series"
        
        headers = {"X-Api-Key": api_key}
        
        payload = {
            "title": series_data['title'], 
            "tvdbId": series_data['tvdbId'],
            "qualityProfileId": list_meta['qualityProfileId'],
            "rootFolderPath": list_meta['rootFolderPath'],
            "addOptions": {
                "monitor": "all",
                "searchForMissingEpisodes": True,
                "searchForCutoffUnmetEpisodes": True
            },
            "monitored": True
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Added series: {series_data.get('title', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to add series: {e}")
            return False
    
    def process_shows(self, can_download_show: bool):
        """Process show lists and add to Sonarr"""
        if not can_download_show:
            logger.info("Insufficient capacity for shows, skipping")
            return
        
        show_list = self.config.get('shows', [])
        
        if not show_list:
            logger.info("No show lists configured")
            return
        
        # Pick one list based on current hour
        list_count = len(show_list)
        index = self.current_hour % list_count
        selected_list_meta = show_list[index]
        
        logger.info(f"Processing shows from list {selected_list_meta['name']}")
        
        # Fetch list items
        items = self.get_list_items(selected_list_meta)
        
        # Get existing series from Sonarr
        existing_tmdb_ids = self.get_sonarr_existing_series()
        logger.info(f"Found {len(existing_tmdb_ids)} existing series in Sonarr")
        
        # Process shows
        shows_added = 0
        for item in items:
            if item.get('mediatype') != 'show':
                continue
            
            tmdb_id = item.get('id')
            
            if not tmdb_id or tmdb_id in existing_tmdb_ids:
                continue
            
            # Lookup and add series
            series_data = self.sonarr_lookup_series(tmdb_id)
            if series_data:
                if self.sonarr_add_series(series_data, selected_list_meta):
                    shows_added += 1
                    existing_tmdb_ids.append(tmdb_id)
                    break  # Only add one show per run
        
        logger.info(f"Added {shows_added} shows to Sonarr")
    
    def run(self):
        """Main execution flow"""
        logger.info("=== Starting Media Sync ===")
        
        # Check blackout periods first
        if self.is_in_blackout_period():
            logger.info("Skipping execution - currently in blackout period")
            return
        
        try:
            rd_data = self.get_rd_active_count()
            total_movie_ddl, can_download_show = self.calculate_download_capacity(rd_data)
            
            if total_movie_ddl > 0:
                self.process_movies(total_movie_ddl)
            else:
                logger.info("No capacity for movies")

            self.process_shows(can_download_show)
            
            logger.info("=== Media Sync Completed Successfully ===")
            
        except Exception as e:
            logger.error(f"Media sync failed: {e}")
            raise


if __name__ == "__main__":
    # You can specify a different config path if needed
    manager = MediaSyncManager("config.json")
    manager.run()