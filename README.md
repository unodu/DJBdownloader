# 🎧 DJBdownloader

**DJBdownloader** is a command-line utility to automate the downloading and concatenation of radio show segments from web-based archives using the [DJB Radio File Viewer platform](https://www.djbroadcast.com/). This has been specifically tested on **DJB File Viewer v0.90.2**.

This tool is useful for DJs, station archivists, or content curators who need to automatically pull and stitch together program audio files from known airing schedules. I created this program to catalog recordings of each weekly radio show I aired on my college's radio station, [Black Squirrel Radio](https://blacksquirrelradio.com). 

---

## Features

- Logs in to DJB File Viewer with session persistence
- Supports configurable schedules (day-of-week and hours)
- Detects station callsign if none provided
- Downloads audio segments (typically hourly MP3s)
- Concatenates segments via `ffmpeg` into one long MP3 (programmed at 150 minutes, but can be customized for your specific needs)
- Verifies audio files with `ffmpeg`
- Cleans up temporary files after processing
- Supports partial retries with `--start-date` argument, continuing from that point in the schedule sequence that was set (eg. if you drop network connection).
- Friendly progress bar using `tqdm` with task descriptions and emojis
- Interactive or CLI-based configuration

---

## Requirements

- Python 3.7+
- `ffmpeg` installed and available on the system path
- Python packages: `requests`, `tqdm`

To install the requirements, activate your virtual environment and run:

```bash
pip install -r requirements.txt
```

---

## Installation

Clone the repo or copy the script, then create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

```bash
python downloader.py [--start-date YYYY-MM-DD] [--base-url URL] [--username USER] [--password PASS] [--output-dir PATH]
```

If values are missing, you will be prompted to enter them interactively.

---

## Station Callsign Detection

DJBdownloader needs your station’s callsign code to construct valid file URLs. It will:

1. **Auto-detect** from the second `<div class="menuBar">` on the archive index page (e.g. `<a href="index.php?d=7&m=8&y=2025&c=0">BSR</a>`).  
2. If **multiple callsigns** are found (which may be the case when DJB is logging multiple stations at once), you will be prompted to select one.  
3. If none or detection fails, it will **fall back** to parsing the first table’s **Group** column.  
4. Finally, if still not found, you will be prompted to enter it manually.  
5. A **link** to the index page (e.g. `https://station.example.com/index.php?c=0&d=7&m=8&y=2025`) is provided to the user to manually input for convenience.

**Tip:** Log in to your archive and look just below the date picker to see your station code in the menu bar.

---

## Formatting Schedules

The `SCHEDULES` list is at the top of the script and defines the shows to fetch. Each item should be a tuple:

```python
SCHEDULES = [
    # (start_date, end_date, weekday_index, hours_list)
    ("2023-09-01", "2023-12-10", 2, [22, 23, 0]),  # Wednesdays at 10PM–12:30AM
    ("2024-02-01", "2024-05-05", 1, [22, 23, 0]),  # Tuesdays
    ("2024-09-01", "2025-05-01", 0, [22, 23, 0]),  # Mondays
]
```

- `start_date` and `end_date`: The inclusive range of dates.
- `weekday_index`: 0 = Monday, 6 = Sunday.
- `hours_list`: List of 24-hour format integers (e.g. `[22, 23, 0]` for 10PM to 12:30AM).

> The downloader will **automatically fetch midnight from the _next calendar day_** if `0` is included in the `hours_list`, in the case that your show runs over the turn of the day.

---

## Output

Each final file will be saved in the output directory with this naming convention:

```
YYYY-MM-DD.mp3
```

Intermediate downloaded segments are stored in a temporary subdirectory and cleaned up after successful concatenation.

- Internally, filenames are prefixed with your station callsign (e.g., `BSR-YY-MM-DD-HH-00.mp3`) to match the server schema, but the final merged files are saved as `YYYY-MM-DD.mp3`.

---


## Error Handling

- Failed downloads or decode verification are logged.
- Concatenation will still proceed if only some segments are valid.
- The script prints friendly warnings and summaries throughout.
- The script prints debug output of the fetched index page HTML when station code detection fails, so you can inspect why auto-detection missed your callsign.

---

- This tool is designed for use with DJB File Viewer-based archive platforms (e.g. `https://station.example.com/index.php`). **It is critical to understand:** DJB File Viewer seems to require a sort of “priming” request to the index listing page for a specific day _before_ the corresponding MP3s for that day are accessible via direct URL. We emulate this by automatically sending a `GET` to the proper index URL (e.g. `?c=0&d=10&m=3&y=2025`) before requesting the audio. If this is not done, requesting an mp3 URL will return a 200 blank HTML page.

---

## Credits

- Built by **Micah Beck**, 2025
- Version: **1.2.0**
- Tested on DJB File Viewer **v0.90.2**

---
