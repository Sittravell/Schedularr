# Schedularr

Schedularr is an intelligent automation tool that syncs your MDBlist with Radarr and Sonarr based on Real-Debrid capacity. It automatically rotates through your curated lists every hour, ensuring optimal download management and content discovery.

## Features

- **Smart Capacity Management**: Automatically calculates available download slots based on Real-Debrid usage
- **Hourly List Rotation**: Cycles through your MDBList to ensure balanced content discovery
- **Duplicate Prevention**: Checks existing libraries before adding content
- **Separate Movie/Show Logic**: Different handling for movies and TV shows based on capacity
- **Flexible Blackout Periods**: Schedule time ranges when the script should not run (daily or one-time)

## Prerequisites

- Python 3.8 or higher
- Active accounts for:
  - [Real-Debrid](https://real-debrid.com/) (Premium)
  - [MDBlist](https://mdblist.com/) (Free or VIP)
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
    "token": "YOUR_REAL_DEBRID_TOKEN_HERE"
  },
  "mdbList": {
    "api_key": "YOUR_MDBLIST_API_KEY"
  },
  "blackout_periods": [
    {
      "name": "Daily Peak Hours",
      "enabled": true,
      "recurring": "daily",
      "start_time": "18:00",
      "end_time": "23:00"
    },
    {
      "name": "Daily Maintenance Window",
      "enabled": true,
      "recurring": "daily",
      "start_time": "02:00",
      "duration": "2h"
    }
  ],
  "movies": [
    {
      "id": 6452,
      "name": "Movie List 1",
      "qualityProfileId": 1,
      "rootFolderPath": "/path/to/root"
    }
  ],
  "shows": [
    {
      "id": 2442,
      "name": "Show List 1",
      "qualityProfileId": 1,
      "rootFolderPath": "/path/to/root"
    }
  ],
  "radarr": {
    "base_url": "https://your-radarr-url.com",
    "port": "7878",
    "api_key": "YOUR_RADARR_API_KEY"
  },
  "sonarr": {
    "base_url": "https://your-sonarr-url.com",
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

#### MDBList API Credentials

1. Go to https://mdblist.com
2. Sign in or create an account
3. Go to your preferences → API Access

#### Radarr/Sonarr API Keys

1. Open Radarr/Sonarr web interface
2. Go to **Settings** → **General**
3. Copy the **API Key**

#### MDBList List IDs

1. Find or create a list on https://mdblist.com
2. Call the List by Name endpoint to retrieve the list ID:

```text
https://mdblist.com/lists/username/slug-name
```

3. In the response JSON, copy the "id" value
4. Add that ID to your movies or shows arrays in config.json

### Configuring Blackout Periods

Blackout periods allow you to prevent the script from running during specific times. This is useful for:

- Avoiding peak internet usage hours
- Scheduled maintenance windows
- Preventing downloads during specific events
- Managing bandwidth during work hours

#### Daily Recurring Blackouts

Block the script from running every day at specific times:

```json
{
  "name": "Peak Hours",
  "enabled": true,
  "recurring": "daily",
  "start_time": "18:00",
  "end_time": "23:00"
}
```

With duration instead of end time:

```json
{
  "name": "Maintenance Window",
  "enabled": true,
  "recurring": "daily",
  "start_time": "02:00",
  "duration": "2h"
}
```

**Overnight periods work correctly:**

```json
{
  "name": "Overnight Blackout",
  "enabled": true,
  "recurring": "daily",
  "start_time": "23:00",
  "end_time": "06:00"
}
```

#### One-Time Blackouts

Block the script for a specific date/time:

```json
{
  "name": "Holiday Break",
  "enabled": true,
  "recurring": "once",
  "start": "2025-12-25T00:00:00",
  "end": "2025-12-26T00:00:00"
}
```

With duration:

```json
{
  "name": "Server Migration",
  "enabled": true,
  "recurring": "once",
  "start": "2025-11-10T14:00:00",
  "duration": "4h 30m"
}
```

#### Duration Format

Durations support multiple time units that can be combined:

- `s` - seconds
- `m` - minutes
- `h` - hours
- `d` - days
- `w` - weeks
- `y` - years (approximated as 365 days)

**Examples:**

- `"30s"` - 30 seconds
- `"5m"` - 5 minutes
- `"2h"` - 2 hours
- `"1d"` - 1 day
- `"2w"` - 2 weeks
- `"1y"` - 1 year
- `"1d 2h 30m"` - 1 day, 2 hours, and 30 minutes

#### Blackout Period Fields

| Field        | Required  | Description                                        |
| ------------ | --------- | -------------------------------------------------- |
| `name`       | Yes       | Descriptive name for the blackout period           |
| `enabled`    | Yes       | `true` to activate, `false` to temporarily disable |
| `recurring`  | Yes       | `"daily"` for recurring or `"once"` for one-time   |
| `start_time` | For daily | Time in 24-hour format (e.g., `"18:00"`)           |
| `end_time`   | For daily | Time in 24-hour format (e.g., `"23:00"`)           |
| `start`      | For once  | ISO datetime (e.g., `"2025-12-25T00:00:00"`)       |
| `end`        | For once  | ISO datetime (e.g., `"2025-12-26T00:00:00"`)       |
| `duration`   | Optional  | Duration string (alternative to end_time/end)      |

#### Blackout Period Tips

- **Multiple periods**: You can have multiple blackout periods active simultaneously
- **Temporary disable**: Set `"enabled": false` to disable without deleting
- **Script behavior**: If ANY enabled blackout period is active, the script will skip execution
- **Remove feature**: Delete the entire `blackout_periods` array or set it to `[]` to disable the feature
- **Cron still runs**: The cron job will execute, but the script will exit early during blackout periods

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
2. Fetches items from MDBList in rotation
3. Filters out movies already in Radarr
4. Looks up movie metadata in Radarr
5. Adds movies up to the calculated capacity limit

### Show Processing

1. Only processes if capacity allows (≥10 slots available)
2. Selects one list based on current hour
3. Adds one show per run
4. Ensures controlled growth of TV library

### Blackout Period Checking

Before processing any content, the script:

1. Checks all configured blackout periods
2. Evaluates if the current time falls within any active blackout
3. Skips execution if in a blackout period
4. Logs the blackout period name and continues normal execution otherwise

## Logging

Logs are written to both console and file:

```bash
# View real-time logs
tail -f cronjob.log

# View last 50 lines
tail -n 50 cronjob.log

# Search for errors
grep ERROR cronjob.log

# Check blackout period skips
grep "blackout period" cronjob.log
```

## Troubleshooting

### Movies/shows not being added

- Check that lists are public or you have access
- Verify TMDB IDs are available in MDBList data
- Ensure Radarr/Sonarr are accessible from the script's host
- Check if execution is being blocked by blackout periods

### Script not running during expected hours

- Verify blackout periods configuration
- Check if `enabled: true` for relevant blackout periods
- Ensure time formats are correct (24-hour format for daily, ISO format for one-time)
- Review logs for "blackout period" messages

### Cron not running

- Verify cron service is active: `systemctl status cron`
- Check crontab syntax: `crontab -l`
- Ensure script paths are absolute

### Permission denied errors

- Make script executable: `chmod +x media_sync.py`
- Check config file permissions: `chmod 644 config.json`

### Blackout periods not working

- Verify JSON syntax in config.json
- Check that datetime formats match requirements
- Ensure system time is correct: `date`
- Review logs for parsing errors

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

The script will still respect blackout periods when run manually.

### Testing Blackout Periods

To test if your blackout configuration is working:

1. Set a blackout period for the current time
2. Run the script manually: `python3 media_sync.py`
3. Check the log output - you should see: `"Skipping execution - currently in blackout period"`

### Multiple Configurations

Run multiple instances with different configs:

```bash
python3 media_sync.py --config /path/to/alternate-config.json
```

(Note: This requires modifying the script to accept command-line arguments)

## 📋 Example Blackout Scenarios

### Scenario 1: Avoid Peak Internet Hours

```json
{
  "name": "Peak Hours",
  "enabled": true,
  "recurring": "daily",
  "start_time": "18:00",
  "end_time": "23:00"
}
```

### Scenario 2: Maintenance Every Night

```json
{
  "name": "Nightly Maintenance",
  "enabled": true,
  "recurring": "daily",
  "start_time": "02:00",
  "duration": "1h"
}
```

### Scenario 3: Work Hours (Multi-period)

```json
[
  {
    "name": "Morning Work Hours",
    "enabled": true,
    "recurring": "daily",
    "start_time": "09:00",
    "end_time": "12:00"
  },
  {
    "name": "Afternoon Work Hours",
    "enabled": true,
    "recurring": "daily",
    "start_time": "13:00",
    "end_time": "17:00"
  }
]
```

### Scenario 4: Holiday Vacation

```json
{
  "name": "Christmas Vacation",
  "enabled": true,
  "recurring": "once",
  "start": "2025-12-24T00:00:00",
  "duration": "2w"
}
```
