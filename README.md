# Schedularr

Schedularr is an intelligent automation tool that syncs your Trakt lists with Radarr and Sonarr based on Real-Debrid capacity. It automatically rotates through your curated lists every hour, ensuring optimal download management and content discovery.

## 🌟 Features

- **Smart Capacity Management**: Automatically calculates available download slots based on Real-Debrid usage
- **Hourly List Rotation**: Cycles through your Trakt lists to ensure balanced content discovery
- **Duplicate Prevention**: Checks existing libraries before adding content
- **Separate Movie/Show Logic**: Different handling for movies and TV shows based on capacity

## Prerequisites

- Python 3.8 or higher
- Active accounts for:
  - [Real-Debrid](https://real-debrid.com/) (Premium)
  - [Trakt](https://trakt.tv/) (Free or VIP)
  - [Radarr](https://radarr.video/) (for movies)
  - [Sonarr](https://sonarr.tv/) (for TV shows)

## Quick Start

### Installation

1. Clone the repository:

```bash
git clone https://github.com/Sittravell/Schedularr.git
cd Schedularr
```

2. Install dependencies:

```bash
pip3 install -r requirements.txt
```

3. Create your configuration file:

```bash
cp config.example.json config.json
```

4. Edit `config.json` with your API credentials (see [Configuration](#-configuration))

5. Test the script:

```bash
python3 media_sync.py
```

### Setting Up the Cronjob

To run Schedularr every hour:

1. Open crontab editor:

```bash
crontab -e
```

2. Add this line:

```bash
0 * * * * cd /path/to/schedularr && /usr/bin/python3 media_sync.py >> /path/to/schedularr/cronjob.log 2>&1
```

3. Save and exit. Verify with:

```bash
crontab -l
```

## ⚙️ Configuration

Create a `config.json` file with the following structure:

```json
{
  "rd": {
    "token": "YOUR_REAL_DEBRID_API_TOKEN"
  },
  "trakt": {
    "refresh_token": "YOUR_TRAKT_REFRESH_TOKEN",
    "access_token": "",
    "client_id": "YOUR_TRAKT_CLIENT_ID",
    "client_secret": "YOUR_TRAKT_CLIENT_SECRET",
    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
  },
  "movies": [131, 466, 789],
  "shows": [425, 950, 1234],
  "radarr": {
    "base_url": "http://localhost",
    "port": "7878",
    "api_key": "YOUR_RADARR_API_KEY"
  },
  "sonarr": {
    "base_url": "http://localhost",
    "port": "8989",
    "api_key": "YOUR_SONARR_API_KEY"
  }
}
```

### Getting Your API Credentials

#### Real-Debrid Token

1. Go to https://real-debrid.com/apitoken
2. Generate a new API token
3. Copy the token to `rd.token` in config.json

#### Trakt API Credentials

1. Create an application at https://trakt.tv/oauth/applications
2. Set the Redirect URI to whichever url was setup in your account
3. Copy the **Client ID** and **Client Secret** to your config
4. Get your refresh token by following [Trakt's OAuth flow](https://trakt.docs.apiary.io/#reference/authentication-oauth)

#### Radarr/Sonarr API Keys

1. Open Radarr/Sonarr web interface
2. Go to **Settings** → **General**
3. Copy the **API Key**

#### Trakt List IDs

1. Go to any Trakt list (e.g., https://trakt.tv/lists/131)
2. The number in the URL is the list ID
3. Add multiple list IDs to the `movies` and `shows` arrays

## How It Works

### Capacity Calculation

Schedularr intelligently manages your Real-Debrid downloads:

```
halfDownload = limit / 2
downloadLeft = limit - currentActive
totalMovieDownloads = max(0, downloadLeft - halfDownload)
canDownloadShows = downloadLeft >= 10
```

This ensures you always have buffer capacity while maximizing content addition.

### Hourly Rotation

The script uses the current hour to determine which list to process first:

```
startIndex = currentHour % numberOfLists
```

For example, with 3 lists:

- **1 AM**: Starts at list index 1
- **2 AM**: Starts at list index 2
- **3 AM**: Starts at list index 0
- **4 AM**: Starts at list index 1

This rotation ensures all lists get equal priority over time.

### Movie Processing

1. Calculates starting index based on current hour
2. Fetches items from Trakt lists in rotation
3. Filters out movies already in Radarr
4. Looks up movie metadata in Radarr
5. Adds movies up to the calculated capacity limit

### Show Processing

1. Only processes if capacity allows (≥10 slots available)
2. Selects one list based on current hour
3. Adds one show per run
4. Ensures controlled growth of TV library

## Logging

Logs are written to both console and file:

```bash
# View real-time logs
tail -f cronjob.log

# View last 50 lines
tail -n 50 cronjob.log

# Search for errors
grep ERROR cronjob.log
```

## Troubleshooting

### Script fails with "Token expired"

- The script automatically refreshes Trakt tokens
- If it persists, regenerate your refresh token from Trakt

### Movies/shows not being added

- Check that lists are public or you have access
- Verify TMDB IDs are available in Trakt data
- Ensure Radarr/Sonarr are accessible from the script's host

### Cron not running

- Verify cron service is active: `systemctl status cron`
- Check crontab syntax: `crontab -l`
- Ensure script paths are absolute

### Permission denied errors

- Make script executable: `chmod +x media_sync.py`
- Check config file permissions: `chmod 644 config.json`

## 📝 Advanced Usage

### Custom Schedule

To run every 2 hours instead of hourly:

```bash
0 */2 * * * cd /path/to/schedularr && python3 media_sync.py >> cronjob.log 2>&1
```

### Running Manually

You can run the script anytime without waiting for cron:

```bash
python3 media_sync.py
```

### Multiple Configurations

Run multiple instances with different configs:

```bash
python3 media_sync.py --config /path/to/alternate-config.json
```

(Note: This requires modifying the script to accept command-line arguments)
