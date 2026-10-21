#!/usr/bin/env python
r"""Scrape TikTok hashtags for BAKMA spoilers locally and export a CSV for the cloud dashboard.

Run from the project folder (double-click scrape_tiktok.bat, or):
    $env:TIKTOK_MS_TOKEN="<your msToken cookie>"
    .\.venv\Scripts\python.exe scrape_tiktok.py

The CSV it produces can be uploaded via the dashboard's "Import CSV" button.
"""
import os
import csv
import argparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app.py")
COLUMNS = ["platform", "platform_id", "url", "creator", "published_at", "title", "text"]


def load_app_namespace():
    """Load the app's helper functions without starting the Streamlit UI."""
    src = open(APP, encoding="utf-8").read().split("\nensure_db()\n")[0]
    ns = {}
    exec(compile(src, APP, "exec"), ns)
    return ns


def main():
    p = argparse.ArgumentParser(description="Scrape TikTok hashtags for BAKMA spoilers -> CSV")
    p.add_argument("--hashtags", default="bakmafilm,bakmamovie,filmbakma,بكمة,بكما,bakma",
                   help="Comma-separated hashtags (without #).")
    p.add_argument("--count", type=int, default=30, help="Videos per hashtag.")
    p.add_argument("--browser", default="webkit", choices=["webkit", "chromium", "firefox"])
    p.add_argument("--proxy", default=os.getenv("TIKTOK_PROXY", ""), help="Optional proxy URL.")
    p.add_argument("--headless", action="store_true",
                   help="Hide the browser window (visible is less likely to be blocked).")
    p.add_argument("--keep-turkish", action="store_true", help="Do not drop Turkish-language videos.")
    p.add_argument("--out", default=None, help="Output CSV path.")
    args = p.parse_args()

    ms_token = os.getenv("TIKTOK_MS_TOKEN") or os.getenv("ms_token") or ""
    if not ms_token:
        print("WARNING: no TIKTOK_MS_TOKEN set — scrapes are much more likely to be blocked.")
        print('  Set it first:  $env:TIKTOK_MS_TOKEN="<your msToken cookie>"\n')

    ns = load_app_namespace()
    tiktok_search = ns["tiktok_search"]
    is_turkish = ns["is_turkish"]

    hashtags = [h.strip() for h in args.hashtags.replace("\n", ",").split(",") if h.strip()]
    print(f"Scraping {len(hashtags)} hashtag(s) with {args.browser}: {', '.join(hashtags)}")

    rows = tiktok_search(ms_token, hashtags, args.count, args.proxy, args.browser, args.headless)
    errors = [r["__error__"] for r in rows if "__error__" in r]
    videos = [r for r in rows if "__error__" not in r]

    if not args.keep_turkish:
        before = len(videos)
        videos = [v for v in videos if not is_turkish(v.get("title", ""), v.get("text", ""))]
        print(f"Excluded {before - len(videos)} Turkish-language video(s).")

    out = args.out or os.path.join(HERE, f"tiktok_bakma_{datetime.now():%Y%m%d_%H%M}.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for v in videos:
            writer.writerow({c: v.get(c, "") for c in COLUMNS})

    print(f"\nSaved {len(videos)} video(s) -> {out}")
    for e in errors:
        print("ERROR:", e)
    if not videos and not errors:
        print("\nNo videos returned — TikTok likely blocked the request.")
        print("Try: run without --headless, keep --browser webkit, or add --proxy.")


if __name__ == "__main__":
    main()
