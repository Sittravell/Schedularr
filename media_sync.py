#!/usr/bin/env python3
"""
Media Sync Cronjob
Synchronizes movies and shows from Trakt lists to Radarr/Sonarr
Based on Real-Debrid capacity
"""

import json
import requests
import logging
from datetime import datetime
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
    
    def refresh_trakt_token(self):
        """Refresh Trakt access token if needed"""
        trakt_config = self.config['trakt']
        is_expired = True;

        if 'expires_in' in trakt_config and 'created_at' in trakt_config :
            buffer = 300
            is_expired = time.time() >= trakt_config['created_at'] + trakt_config['expires_in'] - buffer

        if not is_expired and 'access_token' in trakt_config and trakt_config['access_token']:
            logger.info("Trakt access token exists and not expired, skipping refresh")
            return
        
        url = "https://api.trakt.tv/oauth/token"
        payload = {
            "client_id": trakt_config['client_id'],
            "client_secret": trakt_config['client_secret'],
            "redirect_uri": trakt_config['redirect_uri'],
            "refresh_token": trakt_config['refresh_token'],
            "grant_type": "refresh_token"
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            token_data = response.json()
            
            # Update config with new tokens
            self.config['trakt']['access_token'] = token_data['access_token']
            self.config['trakt']['refresh_token'] = token_data['refresh_token']
            self.config['trakt']['created_at'] = token_data['created_at']
            self.config['trakt']['expires_in'] = token_data['expires_in']
            self.save_config()
            
            logger.info("Trakt token refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh Trakt token: {e}")
            raise
    
    def get_trakt_list_items(self, list_id: int) -> List[Dict]:
        """Fetch items from a Trakt list"""
        url = f"https://api.trakt.tv/lists/{list_id}/items"
        headers = {
            "Authorization": f"Bearer {self.config['trakt']['access_token']}",
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.config['trakt']['client_id']
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get Trakt list {list_id}: {e}")
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
    
    def radarr_add_movie(self, movie_data: Dict) -> bool:
        """Add a movie to Radarr"""
        base_url = self.config['radarr']['base_url']
        port = self.config['radarr'].get('port')
        api_key = self.config['radarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/movie"
        else:
            url = f"{base_url}/api/v3/movie"
        
        headers = {"X-Api-Key": api_key}
        
        try:
            response = requests.post(url, json=movie_data, headers=headers)
            response.raise_for_status()
            logger.info(f"Added movie: {movie_data.get('title', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to add movie: {e}")
            return False
    
    def process_movies(self, total_movie_ddl: int):
        """Process movie lists and add to Radarr"""
        movie_list_ids = self.config.get('movies', [])
        
        if not movie_list_ids:
            logger.info("No movie lists configured")
            return
        
        # Calculate starting index based on current hour
        list_count = len(movie_list_ids)
        start_index = self.current_hour % list_count
        
        logger.info(f"Processing movies starting from index {start_index}")
        
        list_ids_in_order = []

        for i in range(total_movie_ddl):
            list_ids_in_order.append(movie_list_ids[(start_index + i) % list_count])
            
        # Fetch all list items
        list_id_dictionary = {}
        for list_id in movie_list_ids:
            items = self.get_trakt_list_items(list_id)
            list_id_dictionary[list_id] = items
            logger.info(f"Fetched {len(items)} items from list {list_id}")
        
        # Get existing movies from Radarr
        existing_tmdb_ids = self.get_radarr_existing_movies()
        logger.info(f"Found {len(existing_tmdb_ids)} existing movies in Radarr")
        
        # Process each list
        movies_added = 0
        for idx, list_id in enumerate(list_ids_in_order):
            # Cycle through lists if we've added more than total_movie_ddl
            if movies_added >= total_movie_ddl:
                break
            
            items = list_id_dictionary[list_id]
            
            # Filter for movies only and not already in Radarr
            for item in items:
                if movies_added >= total_movie_ddl:
                    break
                
                if item.get('type') != 'movie':
                    continue
                
                movie = item.get('movie', {})
                tmdb_id = movie.get('ids', {}).get('tmdb')
                
                if not tmdb_id or tmdb_id in existing_tmdb_ids:
                    continue
                
                # Lookup and add movie
                movie_data = self.radarr_lookup_movie(tmdb_id)
        
                if movie_data:
                    if self.radarr_add_movie(movie_data):
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
    
    def sonarr_add_series(self, series_data: Dict) -> bool:
        """Add a series to Sonarr"""
        base_url = self.config['sonarr']['base_url']
        port = self.config['sonarr'].get('port')
        api_key = self.config['sonarr']['api_key']
        
        if port:
            url = f"{base_url}:{port}/api/v3/series"
        else:
            url = f"{base_url}/api/v3/series"
        
        headers = {"X-Api-Key": api_key}
        
        try:
            response = requests.post(url, json=series_data, headers=headers)
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
        
        show_list_ids = self.config.get('shows', [])
        
        if not show_list_ids:
            logger.info("No show lists configured")
            return
        
        # Pick one list based on current hour
        list_count = len(show_list_ids)
        index = self.current_hour % list_count
        selected_list_id = show_list_ids[index]
        
        logger.info(f"Processing shows from list {selected_list_id}")
        
        # Fetch list items
        items = self.get_trakt_list_items(selected_list_id)
        
        # Get existing series from Sonarr
        existing_tmdb_ids = self.get_sonarr_existing_series()
        logger.info(f"Found {len(existing_tmdb_ids)} existing series in Sonarr")
        
        # Process shows
        shows_added = 0
        for item in items:
            if item.get('type') != 'show':
                continue
            
            show = item.get('show', {})
            tmdb_id = show.get('ids', {}).get('tmdb')
            
            if not tmdb_id or tmdb_id in existing_tmdb_ids:
                continue
            
            # Lookup and add series
            series_data = self.sonarr_lookup_series(tmdb_id)
            if series_data:
                if self.sonarr_add_series(series_data):
                    shows_added += 1
                    existing_tmdb_ids.append(tmdb_id)
                    break  # Only add one show per run
        
        logger.info(f"Added {shows_added} shows to Sonarr")
    
    def run(self):
        """Main execution flow"""
        logger.info("=== Starting Media Sync ===")
        
        try:
            # Step 1: Get Real-Debrid capacity
            rd_data = self.get_rd_active_count()
            total_movie_ddl, can_download_show = self.calculate_download_capacity(rd_data)
            
            # Step 2: Refresh Trakt token if needed
            self.refresh_trakt_token()
            
            # Step 3: Process movies
            if total_movie_ddl > 0:
                self.process_movies(total_movie_ddl)
            else:
                logger.info("No capacity for movies")
            
            # Step 4: Process shows
            self.process_shows(can_download_show)
            
            logger.info("=== Media Sync Completed Successfully ===")
            
        except Exception as e:
            logger.error(f"Media sync failed: {e}")
            raise


if __name__ == "__main__":
    # You can specify a different config path if needed
    manager = MediaSyncManager("config.json")
    manager.run()