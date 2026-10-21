import os
import re
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
import streamlit as st

APP_TITLE = "Movie Spoiler Monitor"
DB_PATH = os.getenv("SPOILER_DB_PATH", "spoiler_monitor.db")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide")

# Starter multilingual lexicon. Customize it for the actual movie and its characters.
# Scores are signals, not proof that a post contains a real spoiler.
SPOILER_TERMS = {
    "high": [
        # English
        "dies at the end", "he dies", "she dies", "they die", "the killer is",
        "the murderer is", "the twist is", "plot twist", "secret identity",
        "the ending reveals", "final scene", "post credit scene", "post-credits scene",
        "is actually the", "turns out to be",
        # French
        "il meurt à la fin", "elle meurt à la fin", "ils meurent", "le tueur est",
        "la tueuse est", "le twist", "retournement de situation", "la fin révèle",
        "scène finale", "scène post-générique", "en fait c'est",
        # Arabic (Modern Standard / common variants)
        "يموت في النهاية", "تموت في النهاية", "القاتل هو", "النهاية تكشف",
        "المفاجأة هي", "في المشهد الأخير", "يتضح أنه", "تتضح أنها",
        # Tunisian / Arabizi common spellings (starter examples)
        "yemout fel lekher", "t emout fel lekher", "el 9atel howa",
        "fil ekher", "twist mta3 el film", "yطلع howa"
    ],
    "medium": [
        "ending explained", "spoiler review", "full plot", "whole story",
        "who dies", "death scene", "ending explained",
        "explication de la fin", "résumé complet", "qui meurt",
        "mort du personnage", "la vraie identité", "la fin du film",
        "حرق", "حرق الفيلم", "شرح النهاية", "ملخص الفيلم", "من هو القاتل",
        "spoiler", "spoilers", "spoilers alert", "spoil",
        "7ra9", "7ra9 el film", "chkon yemout", "chkoun howa el 9atel"
    ],
    "low": [
        "movie review", "film review", "trailer", "teaser", "official trailer",
        "critique du film", "bande annonce", "avis sur le film",
        "فيلم", "film", "movie", "cinema", "سينما"
    ],
}

DEFAULT_CONFIG = {
    "movie_title": "BAKMA",
    "aliases": "BAKMA, باكما, #BAKMA, #BakmaFilm, #Bakma, Bakma film, Bakma movie, film Bakma, فيلم باكما",
    "characters": "",
    "youtube_queries": "BAKMA film\nBAKMA spoiler\nBAKMA ending\nفيلم باكما\nباكما حرق\nBAKMA 7ra9\nBakma fin du film\n#BAKMA",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower().replace("’", "'").replace("ـ", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def split_terms(value: str):
    return [x.strip() for x in re.split(r"[\n,;|]+", value or "") if x.strip()]

def make_url(platform: str, video_id: str, supplied_url: str = "") -> str:
    if supplied_url and supplied_url.strip():
        return supplied_url.strip()
    if platform.lower() == "youtube" and video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    if platform.lower() == "tiktok" and video_id:
        return f"https://www.tiktok.com/video/{video_id}"
    return ""

def ensure_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                platform_id TEXT,
                url TEXT,
                creator TEXT,
                published_at TEXT,
                title TEXT,
                text TEXT,
                matched_terms TEXT,
                score INTEGER,
                risk TEXT,
                status TEXT DEFAULT 'Needs review',
                reviewer_notes TEXT,
                collected_at TEXT,
                UNIQUE(platform, platform_id, url)
            )
        """)
        con.commit()

def score_post(title: str, body: str, movie_terms: list[str], characters: list[str]):
    combined = norm(f"{title} {body}")
    matched = []
    score = 0

    # Movie/alias match is required to reduce unrelated keyword hits.
    movie_hits = [t for t in movie_terms if norm(t) and norm(t) in combined]
    character_hits = [t for t in characters if norm(t) and norm(t) in combined]

    if movie_terms and not movie_hits:
        # If a character is mentioned, still allow a candidate; otherwise don't flag.
        if not character_hits:
            return 0, "Not scored", []

    if movie_hits:
        score += min(25, 10 + 5 * (len(movie_hits) - 1))
        matched.extend([f"movie:{x}" for x in movie_hits])

    if character_hits:
        score += min(20, 5 * len(character_hits))
        matched.extend([f"character:{x}" for x in character_hits])

    for term in SPOILER_TERMS["high"]:
        t = norm(term)
        if t and t in combined:
            score += 35
            matched.append(f"high:{term}")
    for term in SPOILER_TERMS["medium"]:
        t = norm(term)
        if t and t in combined:
            score += 18
            matched.append(f"medium:{term}")
    for term in SPOILER_TERMS["low"]:
        t = norm(term)
        if t and t in combined:
            score += 2
            matched.append(f"context:{term}")

    # Context clues suggesting a warning rather than an actual reveal are weak evidence.
    if any(x in combined for x in ["no spoilers", "sans spoiler", "pas de spoiler", "بدون حرق"]):
        score -= 12
        matched.append("context:spoiler-warning")

    score = max(0, min(100, score))
    if score >= 65:
        risk = "High"
    elif score >= 30:
        risk = "Medium"
    elif score > 0:
        risk = "Low"
    else:
        risk = "Not scored"
    return score, risk, sorted(set(matched))

def upsert_post(row: dict, movie_terms: list[str], characters: list[str]):
    title = str(row.get("title", "") or "")
    body = str(row.get("text", "") or row.get("description", "") or row.get("caption", "") or "")
    platform = str(row.get("platform", "Manual import") or "Manual import").strip()
    platform_id = str(row.get("platform_id", row.get("video_id", row.get("id", ""))) or "").strip()
    url = make_url(platform, platform_id, str(row.get("url", "") or ""))
    creator = str(row.get("creator", row.get("channel_title", row.get("username", ""))) or "")
    published = str(row.get("published_at", row.get("publishedAt", "")) or "")
    score, risk, matched = score_post(title, body, movie_terms, characters)
    if score == 0:
        return False

    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            INSERT INTO posts(platform, platform_id, url, creator, published_at, title, text,
                              matched_terms, score, risk, status, collected_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(platform, platform_id, url) DO UPDATE SET
                creator=excluded.creator,
                published_at=excluded.published_at,
                title=excluded.title,
                text=excluded.text,
                matched_terms=excluded.matched_terms,
                score=excluded.score,
                risk=excluded.risk,
                collected_at=excluded.collected_at
        """, (
            platform, platform_id, url, creator, published, title, body,
            json.dumps(matched, ensure_ascii=False), score, risk, "Needs review", now_iso()
        ))
        con.commit()
    return True

def youtube_search(api_key: str, query: str, max_results: int = 25):
    """Search public YouTube video metadata. This does not fetch arbitrary video transcripts."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(50, max(1, int(max_results))),
        "order": "date",
        "key": api_key,
    }
    response = requests.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=30)
    if response.status_code != 200:
        try:
            message = response.json().get("error", {}).get("message", response.text)
        except Exception:
            message = response.text
        raise RuntimeError(f"YouTube API error {response.status_code}: {message}")
    payload = response.json()
    rows = []
    for item in payload.get("items", []):
        snippet = item.get("snippet", {})
        vid = item.get("id", {}).get("videoId", "")
        rows.append({
            "platform": "YouTube",
            "platform_id": vid,
            "url": make_url("YouTube", vid),
            "creator": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "title": snippet.get("title", ""),
            "text": snippet.get("description", ""),
        })
    return rows

def load_posts():
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query("SELECT * FROM posts ORDER BY score DESC, published_at DESC", con)
    if not df.empty:
        df["matched_terms"] = df["matched_terms"].apply(
            lambda x: ", ".join(json.loads(x)) if isinstance(x, str) and x else ""
        )
    return df

ensure_db()
st.title("🎬 Movie Spoiler Monitor")
st.caption("Public-content discovery and spoiler-risk triage. Scores are heuristic signals, not proof.")

with st.sidebar:
    st.header("Movie configuration")
    movie_title = st.text_input("Official movie title", value=DEFAULT_CONFIG["movie_title"], placeholder="Enter the title")
    aliases_text = st.text_area("Alternate titles / hashtags (comma-separated)", value=DEFAULT_CONFIG["aliases"], placeholder="title in French, Arabic title, #MovieName")
    characters_text = st.text_area("Character names / aliases (comma-separated)", value=DEFAULT_CONFIG["characters"], placeholder="Character A, Character B")
    st.caption("Use exact names and common spellings. Include Arabic script and Arabizi variants when relevant.")
    st.divider()
    st.header("YouTube collection")
    yt_key = st.text_input("YouTube Data API key", type="password", value=os.getenv("YOUTUBE_API_KEY", ""))
    yt_queries_text = st.text_area("Search queries (one per line)", value=DEFAULT_CONFIG["youtube_queries"])
    yt_max = st.slider("Results per query", min_value=5, max_value=50, value=25, step=5)
    run_yt = st.button("Search YouTube", type="primary", use_container_width=True)
    st.divider()
    st.header("TikTok collection")
    st.info("No TikTok credentials configured? Import a CSV exported by an approved social-listening tool or collected through approved access.")
    uploaded = st.file_uploader("Import TikTok / other public-post CSV", type=["csv"])
    import_btn = st.button("Import CSV", use_container_width=True)

movie_terms = split_terms(movie_title) + split_terms(aliases_text)
characters = split_terms(characters_text)
if movie_title.strip() and movie_title.strip() not in movie_terms:
    movie_terms.insert(0, movie_title.strip())

if run_yt:
    if not yt_key:
        st.error("Add a YouTube Data API key in the sidebar or set YOUTUBE_API_KEY.")
    else:
        queries = split_terms(yt_queries_text)
        if not queries:
            queries = [movie_title.strip()] if movie_title.strip() else []
        if not queries:
            st.error("Enter the movie title and at least one search query.")
        else:
            discovered = []
            errors = []
            progress = st.progress(0)
            for i, query in enumerate(queries):
                try:
                    discovered.extend(youtube_search(yt_key, query, yt_max))
                except Exception as e:
                    errors.append(f"{query}: {e}")
                progress.progress((i + 1) / len(queries))
            saved = sum(1 for row in discovered if upsert_post(row, movie_terms, characters))
            st.success(f"Retrieved {len(discovered)} YouTube videos; saved/updated {saved} candidate records.")
            for err in errors:
                st.warning(err)

if import_btn:
    if uploaded is None:
        st.error("Choose a CSV file first.")
    else:
        try:
            imported = pd.read_csv(uploaded).fillna("")
            # Supported columns: platform, platform_id/id/video_id, url, creator/username/channel_title,
            # published_at/publishedAt, title, text/description/caption.
            count = sum(1 for _, r in imported.iterrows() if upsert_post(r.to_dict(), movie_terms, characters))
            st.success(f"Read {len(imported)} rows; saved/updated {count} candidate records.")
        except Exception as e:
            st.error(f"Could not import CSV: {e}")

df = load_posts()
if df.empty:
    st.info("No candidate posts yet. Configure the movie, search YouTube, or import a CSV to populate the dashboard.")
else:
    total = len(df)
    high = int((df["risk"] == "High").sum())
    pending = int((df["status"] == "Needs review").sum())
    reviewed = int((df["status"] != "Needs review").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidate posts", total)
    c2.metric("High risk", high)
    c3.metric("Awaiting review", pending)
    c4.metric("Reviewed", reviewed)

    st.subheader("Flagged posts")
    f1, f2, f3 = st.columns(3)
    risk_filter = f1.multiselect("Risk", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    platform_filter = f2.multiselect("Platform", sorted(df["platform"].dropna().unique().tolist()), default=sorted(df["platform"].dropna().unique().tolist()))
    status_filter = f3.multiselect("Review status", sorted(df["status"].dropna().unique().tolist()), default=sorted(df["status"].dropna().unique().tolist()))
    filtered = df[df["risk"].isin(risk_filter) & df["platform"].isin(platform_filter) & df["status"].isin(status_filter)].copy()

    show_cols = ["risk", "score", "platform", "creator", "published_at", "title", "url", "matched_terms", "status"]
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True,
                 column_config={"url": st.column_config.LinkColumn("Post URL"),
                                "score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%d")})

    st.subheader("Review a candidate")
    choices = filtered["id"].tolist()
    if choices:
        chosen_id = st.selectbox("Select record ID", choices, format_func=lambda x: f"#{x} · {filtered.loc[filtered.id == x, 'risk'].iloc[0]} · {filtered.loc[filtered.id == x, 'title'].iloc[0][:70]}")
        selected = df[df["id"] == chosen_id].iloc[0]
        st.markdown(f"**{selected['title']}**")
        st.write(selected["text"])
        if selected["url"]:
            st.markdown(f"[Open original post]({selected['url']})")
        st.caption(f"Matched signals: {selected['matched_terms']}")
        with st.form("review_form"):
            new_status = st.selectbox("Decision", ["Needs review", "Confirmed spoiler", "Not a spoiler", "Escalated to legal/platform"], index=["Needs review", "Confirmed spoiler", "Not a spoiler", "Escalated to legal/platform"].index(selected["status"]) if selected["status"] in ["Needs review", "Confirmed spoiler", "Not a spoiler", "Escalated to legal/platform"] else 0)
            notes = st.text_area("Reviewer notes", value=selected["reviewer_notes"] or "")
            submitted = st.form_submit_button("Save review")
            if submitted:
                with sqlite3.connect(DB_PATH) as con:
                    con.execute("UPDATE posts SET status=?, reviewer_notes=? WHERE id=?", (new_status, notes, int(chosen_id)))
                    con.commit()
                st.success("Review saved. Refresh the page to update the table.")
                st.rerun()

    st.subheader("Export")
    export_df = filtered.copy()
    csv_data = export_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Download filtered candidates as CSV", csv_data, file_name="movie_spoiler_candidates.csv", mime="text/csv")

with st.expander("Scoring notes and limitations"):
    st.markdown("""
    - High risk is a rule-based score based on keyword/context matches; it is not an AI-verified probability.
    - Add the film title, localized title variants, character names, nicknames, and common misspellings before searching.
    - YouTube search covers indexed public video metadata. The official captions endpoints do not grant unrestricted access to transcripts for arbitrary third-party videos.
    - TikTok collection is not built as an unofficial scraper. Import data from an approved social-listening vendor or a platform-authorized integration.
    - Search results are incomplete by nature; repeat searches with localized title variants and different spoiler phrases.
    - Review content manually before escalation. Preserve only data your company is authorized to collect and retain.
    """)
