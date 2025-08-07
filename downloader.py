#!/usr/bin/env python3
import argparse
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from tqdm import tqdm
import sys

# Version
VERSION = "1.2.0"

# Optional station code used in filenames (e.g., 'BSR')
STATION_CODE = ""

# Globals set at runtime
BASE_URL = ""
OUTPUT_DIR = Path()

# Show schedules: (start_date, end_date, weekday_index, [hours])
#   start_date, end_date   – “YYYY-MM-DD” strings
#   weekday_index          – Python weekday (0=Monday … 6=Sunday)
#   hours                  – list of hours (0–23) to download segments for each date
SCHEDULES = [
    ("2023-09-01", "2023-12-10", 2, [22, 23, 0]),  # Wednesdays 10pm–1am
    ("2024-02-01", "2024-05-05", 1, [22, 23, 0]),  # Tuesdays 10pm–1am
    ("2024-09-01", "2025-05-01", 0, [22, 23, 0]),  # Mondays 10pm–1am
]

def login_session(base_url, username, password):
    """Log in and finalize session state for all future requests."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Chrome/117.0.5938.150 Safari/605.1.15")
    })
    # 1) GET login form
    s.get(f"{base_url}?pp=1").raise_for_status()
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    # 2) POST credentials
    resp = s.post(
        base_url,
        data={"pp": "1", "pn": username, "ps": password},
        headers={"Referer": f"{base_url}?pp=1", "Origin": origin},
        allow_redirects=True
    )
    resp.raise_for_status()
    # 3) Finalize login by visiting landing page
    s.get(f"{base_url}?pc=3").raise_for_status()
    print("✅ Logged in successfully")
    return s


def gen_show_dates(start_after=None):
    """Yield (date, hours) pairs matching the configured schedules."""
    for start, end, wd, hours in SCHEDULES:
        cur = datetime.strptime(start, "%Y-%m-%d").date()
        last = datetime.strptime(end,   "%Y-%m-%d").date()
        while cur <= last:
            if cur.weekday() == wd:
                if not start_after or cur >= start_after:
                    yield cur, hours
            cur += timedelta(days=1)


def build_urls_for_date(dt, hours):
    """Return list of (filename, url, headers) for a show’s segments."""
    entries = []
    for hour in hours:
        date_for = dt if hour != 0 else dt + timedelta(days=1)
        fn = f"{STATION_CODE}-{date_for.strftime('%y-%m-%d')}-{hour:02d}-00.mp3"
        url = f"{BASE_URL}?f={fn}&action=10"
        hdr = {
            "Referer": (
                f"{BASE_URL}"
                f"?c=0&d={date_for.day:02d}"
                f"&m={date_for.month:02d}"
                f"&y={date_for.year}"
                f"&p={hour:02d}"
            )
        }
        entries.append((fn, url, hdr))
    return entries


def verify_mpeg(path: Path) -> bool:
    """Return True if ffmpeg can decode the file without errors."""
    try:
        res = subprocess.run(
            ["ffmpeg","-v","error","-i",str(path),"-f","null","-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        return res.returncode == 0
    except Exception:
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Download and concat radio shows from DJB platform.")
    parser.add_argument(
        "--start-date", "-s",
        help="YYYY-MM-DD to start processing from (inclusive)",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Base URL for the archive site (will prompt if omitted)"
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory to save downloaded shows (will prompt if omitted)"
    )
    parser.add_argument(
        "--username",
        help="Username"
    )
    parser.add_argument(
        "--password",
        help="Password"
    )
    parser.add_argument(
        "--station-code",
        default="",
        help="Station code for filename prefix (e.g., BSR). If omitted, will attempt to extract after login."
    )
    return parser.parse_args()


def main():
    import getpass

    args = parse_args()
    # Upfront configuration checks
    missing = []
    if not args.base_url:
        missing.append("No Archive Base URL detected. Use --base-url or set it in the script.")
    if not args.username:
        missing.append("No Username detected. Use --username or set it in the script.")
    if not (args.password):
        missing.append("No Password detected. Use --password or set it in the script.")
    if missing:
        for m in missing:
            print(f"⚠️ {m}")
        print()
    # Verify that show schedules are configured
    if not SCHEDULES:
        print("⚠️ No show schedules detected. Please configure the SCHEDULES list at the top of the script.")
        sys.exit(1)
    # Print header
    print(f"\033[1m\033[34mDJBdownloader v{VERSION}\033[0m")
    print("©2025 Micah Beck\n")
    global BASE_URL, OUTPUT_DIR
    # Prompt and sanitize base URL
    raw_url = args.base_url.strip() or input("Please input the archive's Base URL: ").strip()
    # Prepend scheme if missing
    if not raw_url.lower().startswith(("http://", "https://")):
        raw_url = "https://" + raw_url
    # Ensure URL ends with index.php
    if not raw_url.lower().endswith("index.php"):
        raw_url = raw_url.rstrip("/") + "/index.php"
    BASE_URL = raw_url
    # Prompt for output directory or use provided
    od = args.output_dir.strip() or input("Output directory for shows: ").strip()
    OUTPUT_DIR = Path(od).expanduser()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    USERNAME = args.username or input("Username: ")
    if args.password:
        PASSWORD = args.password
    else:
        PASSWORD = getpass.getpass("Password: ")

    global STATION_CODE
    STATION_CODE = args.station_code or ""

    if not STATION_CODE:
        print("ℹ️ No station callsign provided. Attempting to auto-detect after login...")

    try:
        session = login_session(BASE_URL, USERNAME, PASSWORD)
    except Exception as e:
        print(f"🚨 Login failed: {e}")
        sys.exit(1)

    if not STATION_CODE:
        import re
        today = datetime.today()
        index_url = (
            f"{BASE_URL}"
            f"?c=0&d={today.day:02d}"
            f"&m={today.month:02d}"
            f"&y={today.year}"
        )
        index_page = session.get(index_url)
        index_page.raise_for_status()
        html = index_page.text
        from tqdm import tqdm

        # Debug output already printed above
        # Auto-detect station callsigns via matching index.php?d=...&c=...
        codes = re.findall(
            r'<a[^>]+href=["\\\']index\.php\?d=\d+&m=\d+&y=\d+&c=\d+["\\\'][^>]*>([^<]+)</a>',
            html
        )
        # Deduplicate while preserving order
        seen = set()
        codes = [c for c in codes if not (c in seen or seen.add(c))]

        if codes:
            if len(codes) == 1:
                STATION_CODE = codes[0]
                print(f"✅ Auto-detected station callsign: {STATION_CODE}")
            else:
                print("⚠️ Multiple station callsigns detected:")
                for idx, code in enumerate(codes, 1):
                    print(f"  [{idx}] {code}")
                sel = input("Enter the number of the callsign to use: ").strip()
                try:
                    STATION_CODE = codes[int(sel) - 1]
                except Exception:
                    print("❌ Invalid selection.")
                    sys.exit(1)
        else:
            # Fallback: parse first table row "Group"
            row_match = re.search(r'<tr[^>]*>\\s*<td>(\\w+)</td>', html)
            if row_match:
                STATION_CODE = row_match.group(1)
                print(f"✅ Station callsign from first table row: {STATION_CODE}")
            else:
                print("⚠️ Could not auto-detect station callsign.")
                print("You can find it in your browser at:")
                print(f"\n📎 Click to open in browser:\n{index_url}\n")
                STATION_CODE = input("Please enter your station callsign: ").strip()

    # Build flat task list
    tasks = []
    for dt, hours in gen_show_dates(start_after=args.start_date):
        segs = build_urls_for_date(dt, hours)
        for idx, (fn, url, hdr) in enumerate(segs, start=1):
            tasks.append({
                "type":     "download",
                "date":      dt,
                "segment":   idx,
                "total":     len(segs),
                "filename":  fn,
                "url":       url,
                "headers":   hdr
            })
        tasks.append({"type": "concat", "date": dt})

    pbar = tqdm(total=len(tasks), desc="Starting...", unit="task")
    for task in tasks:
        try:
            if task["type"] == "download":
                dt = task["date"]
                fn, url, hdr = task["filename"], task["url"], task["headers"]
                seg, tot = task["segment"], task["total"]
                # Prime index page for this segment’s date
                hour = int(fn.split('-')[4])
                prime_date = dt if hour != 0 else dt + timedelta(days=1)
                prime_url = (
                    f"{BASE_URL}"
                    f"?c=0&d={prime_date.day:02d}"
                    f"&m={prime_date.month:02d}"
                    f"&y={prime_date.year}"
                )
                session.get(prime_url, timeout=30).raise_for_status()
                pbar.set_description(f"⬇️ Downloading {fn} (Seg {seg}/{tot})")
                tmp = OUTPUT_DIR / "tmp" / dt.isoformat()
                tmp.mkdir(parents=True, exist_ok=True)
                dest = tmp / fn
                r = session.get(url, headers=hdr, timeout=60)
                ct = r.headers.get("Content-Type","")
                if r.status_code == 200 and ct.startswith("audio"):
                    dest.write_bytes(r.content)
                    pbar.set_description(f"🛡 Verifying {fn}")
                    if not verify_mpeg(dest):
                        tqdm.write(f"⚠️ Warning: {fn} may be corrupted, keeping it for concat")
                else:
                    tqdm.write(f"⚠️ Skipped {fn} ({r.status_code} {ct})")

            else:  # concat
                dt = task["date"]
                pbar.set_description(f"🔗 Concatenating {dt.isoformat()}.mp3")
                tmp = OUTPUT_DIR / "tmp" / dt.isoformat()
                parts = sorted(tmp.glob("*.mp3"))
                if parts:
                    listf = tmp / "file_list.txt"
                    listf.write_text("\n".join(f"file '{p}'" for p in parts))
                    out = OUTPUT_DIR / f"{dt.isoformat()}.mp3"
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-hide_banner","-loglevel","error",
                            "-y",
                            "-f","concat","-safe","0",
                            "-i",str(listf),
                            "-t","9000",
                            "-c","copy",
                            str(out)
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                    tqdm.write(f"🎉 Created {out.name}")
                    listf.unlink()
                for f in tmp.iterdir():
                    f.unlink()
                tmp.rmdir()

        except Exception as e:
            tqdm.write(f"🚨 Error on {task}: {e}")
        finally:
            pbar.update(1)

    pbar.set_description("✅ All done!")
    pbar.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"🚨 Unexpected error: {e}")
        sys.exit(1)