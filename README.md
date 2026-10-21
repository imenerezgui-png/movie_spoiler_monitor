# Movie Spoiler Monitor

A starter Streamlit dashboard for discovering and triaging public posts that may contain movie spoilers.

## Included
- YouTube Data API `search.list` integration for public video titles/descriptions.
- CSV import for TikTok or social-listening exports from approved sources.
- Multilingual keyword/context scoring starter lexicon (English, French, Arabic, Tunisian Arabizi examples).
- SQLite storage, deduplication, review statuses, filters, and CSV export.

## Important limitations
- This is a **triage tool**, not a definitive spoiler classifier. Tune terms for your movie and review flagged items.
- YouTube API search does not provide unrestricted transcripts for arbitrary third-party videos. Caption listing/downloading is permission-scoped.
- TikTok Research API access is restricted and generally intended for eligible research purposes, not ordinary commercial monitoring. Confirm current TikTok commercial/API eligibility or use a compliant social-listening vendor. This project intentionally does not use an unofficial TikTok scraper.
- The system only analyzes fields supplied by the source (e.g., title, caption, description, transcript if your approved provider supplies one). It does not inspect video frames/audio itself.
- Follow each platform's terms, privacy rules, company policy, and applicable law.

## Run locally
1. Install Python 3.10+.
2. Create a virtual environment (recommended).
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run:

   ```bash
   streamlit run app.py
   ```

5. In the sidebar, enter the movie title, aliases/hashtags, character names, and YouTube API key.

## Set up YouTube API
1. Create/select a project in Google Cloud Console.
2. Enable YouTube Data API v3.
3. Create an API key and restrict it appropriately.
4. Paste it into the app sidebar, or set `YOUTUBE_API_KEY` as an environment variable.
5. Search using the official title and alternate titles, e.g. French title, Arabic title, transliterations, and hashtags.

API quotas and endpoint behavior can change; check current Google documentation.

## TikTok / vendor CSV format
Upload a CSV with as many of these columns as available:
- `platform` (e.g. TikTok)
- `platform_id` (or `id` / `video_id`)
- `url`
- `creator` (or `username` / `channel_title`)
- `published_at` (or `publishedAt`)
- `title`
- `text` (or `description` / `caption`)

If the provider includes transcript text, put it in `text` or append it to the caption/description before importing. Do not include data your organization is not authorized to process.

## Improving the classifier
- Add the movie's character names, nicknames, Arabic spellings, Arabizi forms, and frequent misspellings.
- Add plot-specific phrases only in an internal, access-controlled config. Avoid writing the actual ending into public dashboards or broad reports.
- Create a labeled set of confirmed spoilers and non-spoilers from human review, then evaluate precision/recall before using an ML model.
- Keep review statuses separate from risk scores. A high score means "inspect first", not "confirmed spoiler".

## Production hardening before release week
- Use a secrets manager, not a committed API key.
- Add scheduled jobs and retry/backoff with rate limits.
- Store source, query, and collection time for auditability.
- Restrict dashboard access and export permissions.
- Define retention/deletion rules and escalation procedures.
