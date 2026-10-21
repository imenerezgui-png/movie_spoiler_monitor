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
CONFIG = os.path.join(HERE, "tiktok_config.local")
COLUMNS = ["platform", "platform_id", "url", "creator", "published_at", "title", "text"]


def load_local_config():
    """Load KEY=VALUE secrets from tiktok_config.local into the environment (without overriding)."""
    if not os.path.exists(CONFIG):
        return
    for line in open(CONFIG, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and not os.getenv(key):
            os.environ[key] = value


def load_app_namespace():
    """Load the app's helper functions without starting the Streamlit UI."""
    src = open(APP, encoding="utf-8").read().split("\nensure_db()\n")[0]
    ns = {}
    exec(compile(src, APP, "exec"), ns)
    return ns


def main():
    p = argparse.ArgumentParser(description="Scrape TikTok hashtags for BAKMA spoilers -> CSV + DB")
    p.add_argument("--hashtags", default="bakmafilm,bakmamovie,filmbakma,بكمة,بكما,bakma",
                   help="Comma-separated hashtags (without #).")
    p.add_argument("--count", type=int, default=30, help="Videos per hashtag.")
    p.add_argument("--browser", default="webkit", choices=["webkit", "chromium", "firefox"])
    p.add_argument("--proxy", default="", help="Optional proxy URL (overrides TIKTOK_PROXY).")
    p.add_argument("--headless", action="store_true",
                   help="Hide the browser window (visible is less likely to be blocked).")
    p.add_argument("--keep-turkish", action="store_true", help="Do not drop Turkish-language videos.")
    p.add_argument("--no-db", action="store_true", help="Only write CSV, do not update the dashboard DB.")
    p.add_argument("--out", default=None, help="Output CSV path.")
    args = p.parse_args()

    load_local_config()
    sessionid = os.getenv("TIKTOK_SESSIONID") or ""
    ms_token = os.getenv("TIKTOK_MS_TOKEN") or os.getenv("ms_token") or ""
    proxy = args.proxy or os.getenv("TIKTOK_PROXY", "")
    if not sessionid and not ms_token:
        print("WARNING: no TIKTOK_SESSIONID or TIKTOK_MS_TOKEN set — scrapes are much more likely to be blocked.")
        print("  Add them to tiktok_config.local, or set env vars.\n")

    ns = load_app_namespace()
    tiktok_search = ns["tiktok_search"]
    is_turkish = ns["is_turkish"]

    hashtags = [h.strip() for h in args.hashtags.replace("\n", ",").split(",") if h.strip()]
    print(f"Scraping {len(hashtags)} hashtag(s) with {args.browser}: {', '.join(hashtags)}")

    rows = tiktok_search(ms_token, hashtags, args.count, proxy, args.browser, args.headless, sessionid)
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

    if not args.no_db and videos:
        ns["ensure_db"]()
        cfg = ns["DEFAULT_CONFIG"]
        split_terms = ns["split_terms"]
        upsert_post = ns["upsert_post"]
        movie_terms = split_terms(cfg["movie_title"]) + split_terms(cfg["aliases"])
        characters = split_terms(cfg["characters"])
        saved = sum(1 for v in videos if upsert_post(v, movie_terms, characters) == "saved")
        print(f"Updated dashboard database: {saved} candidate record(s).")

    for e in errors:
        print("ERROR:", e)
    if not videos and not errors:
        print("\nNo videos returned — TikTok likely blocked the request.")
        print("Try: run without --headless, keep --browser webkit, or add --proxy.")


if __name__ == "__main__":
    main()
