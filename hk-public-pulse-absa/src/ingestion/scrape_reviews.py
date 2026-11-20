"""Step 1 feasibility check for HK Public Pulse.

Scrapes Google Play and App Store reviews for a few Hong Kong public-service
and utility apps, then reports how many reviews arrive per week and in which
language. The point is to decide whether trend and spike detection is viable
before any labelling or modelling starts.

Usage:
    pip install google-play-scraper pandas requests
    python scrape_reviews.py                 # scrape, save, print the report
    python scrape_reviews.py --report-only   # re-run the report on saved data

Outputs (in data/raw/):
    reviews.csv        one row per review, no usernames
    volume_weekly.csv  reviews per app per week
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import pandas as pd
import requests

OUT_DIR = Path("data/raw")

# play_id=None means "look it up by name on Google Play and print the match".
APPS = [
    {"app": "CLP",         "play_id": "com.cherrypicks.clp",    "ios_id": "450725907",  "search": "CLP HK"},
    {"app": "HK Electric", "play_id": None,                     "ios_id": "1590821640", "search": "HK Electric"},
    {"app": "Towngas",     "play_id": "com.TownGas",            "ios_id": "407750575",  "search": "Towngas"},
    {"app": "iAM Smart",   "play_id": "hk.gov.ogcio.iamsmart",  "ios_id": "1515065344", "search": "iAM Smart"},
]

PLAY_LANGS = ["zh_HK", "zh_TW", "en"]   # Play filters reviews by language, so ask for each
PLAY_MAX_PER_LANG = 5000
PAUSE = 1.0                              # seconds between requests


# ---------------------------------------------------------------- language

# Characters that are written Cantonese rather than standard written Chinese.
CANTONESE_MARKERS = set("嘅咗唔喺佢啲冇嘢咁乜哋俾畀嚟啱噉嗰咩喇囉喎㗎嘥攞諗瞓")
CANTONESE_WORDS = re.compile(r"但係|即係|係咪|就係|都係|真係|點解|點樣|邊度|而家|依家|搞掂|幾好|好耐|彈app")
CJK = re.compile(r"[㐀-䶿一-鿿]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def tag_language(text: str) -> tuple[str, bool]:
    """Return (lang, code_switched). lang is one of yue, zh, en, other."""
    text = text or ""
    n_cjk = len(CJK.findall(text))
    n_latin = len(LATIN_WORD.findall(text))
    if n_cjk == 0:
        return ("en" if n_latin else "other", False)
    is_yue = any(ch in CANTONESE_MARKERS for ch in text) or bool(CANTONESE_WORDS.search(text))
    lang = "yue" if is_yue else "zh"
    return lang, n_latin >= 1


# ---------------------------------------------------------------- scraping

def resolve_play_id(app: dict) -> str | None:
    from google_play_scraper import search

    if app["play_id"]:
        return app["play_id"]
    hits = search(app["search"], lang="en", country="hk", n_hits=5)
    if not hits:
        print(f"  [{app['app']}] no Google Play match for '{app['search']}'")
        return None
    top = hits[0]
    print(f"  [{app['app']}] Google Play lookup -> {top['appId']} "
          f"('{top['title']}' by {top.get('developer')}). Check this is right, "
          f"then hard-code it in APPS.")
    return top["appId"]


def scrape_play(app: dict) -> list[dict]:
    from google_play_scraper import Sort, reviews

    play_id = resolve_play_id(app)
    if not play_id:
        return []
    rows: dict[str, dict] = {}
    for lang in PLAY_LANGS:
        token, fetched = None, 0
        while fetched < PLAY_MAX_PER_LANG:
            batch, token = reviews(play_id, lang=lang, country="hk", sort=Sort.NEWEST,
                                   count=200, continuation_token=token)
            if not batch:
                break
            for r in batch:
                rows[r["reviewId"]] = {
                    "review_id": r["reviewId"],
                    "app": app["app"],
                    "store": "google_play",
                    "created_at": r["at"],
                    "rating": r["score"],
                    "app_version": r.get("reviewCreatedVersion"),
                    "text": (r.get("content") or "").strip(),
                }
            fetched += len(batch)
            time.sleep(PAUSE)
            if token is None or getattr(token, "token", None) is None:
                break
    return list(rows.values())


def scrape_app_store(app: dict) -> list[dict]:
    """Apple's public RSS feed: at most 10 pages x 50 most recent reviews."""
    rows = []
    for page in range(1, 11):
        url = (f"https://itunes.apple.com/hk/rss/customerreviews/page={page}"
               f"/id={app['ios_id']}/sortby=mostrecent/json")
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            break
        entries = resp.json().get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        entries = [e for e in entries if "im:rating" in e]
        if not entries:
            break
        for e in entries:
            title = e.get("title", {}).get("label", "")
            body = e.get("content", {}).get("label", "")
            rows.append({
                "review_id": "ios_" + e["id"]["label"],
                "app": app["app"],
                "store": "app_store",
                "created_at": e["updated"]["label"],
                "rating": int(e["im:rating"]["label"]),
                "app_version": e.get("im:version", {}).get("label"),
                "text": f"{title}. {body}".strip(". ").strip(),
            })
        time.sleep(PAUSE)
    return rows


def scrape_all() -> pd.DataFrame:
    rows = []
    for app in APPS:
        for store, fn in (("Google Play", scrape_play), ("App Store", scrape_app_store)):
            try:
                got = fn(app)
            except Exception as exc:  # one broken source should not stop the rest
                print(f"  [{app['app']}] {store} failed: {type(exc).__name__}: {exc}")
                got = []
            print(f"  [{app['app']}] {store}: {len(got)} reviews")
            rows.extend(got)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert("Asia/Hong_Kong")
    df = df[df["text"].str.len() > 0].drop_duplicates("review_id")
    tags = df["text"].map(tag_language)
    df["lang"] = tags.str[0]
    df["code_switched"] = tags.str[1]
    return df.sort_values("created_at").reset_index(drop=True)


# ---------------------------------------------------------------- report

def weekly_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Reviews per app per week, with empty weeks kept as zero."""
    week = df["created_at"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    counts = df.assign(week=week).groupby(["app", "week"]).size().rename("reviews").reset_index()
    full = []
    for app, g in counts.groupby("app"):
        idx = pd.date_range(g["week"].min(), g["week"].max(), freq="W-MON")
        s = g.set_index("week")["reviews"].reindex(idx, fill_value=0)
        full.append(pd.DataFrame({"app": app, "week": idx, "reviews": s.values}))
    return pd.concat(full, ignore_index=True)


def report(df: pd.DataFrame) -> pd.DataFrame:
    pd.set_option("display.width", 140)
    weekly = weekly_volume(df)
    cutoff = weekly["week"].max() - pd.Timedelta(weeks=52)
    recent = weekly[weekly["week"] > cutoff]

    print("\n=== 1. Totals and date range ===")
    print(df.groupby(["app", "store"]).agg(
        reviews=("review_id", "size"),
        first=("created_at", lambda s: s.min().date()),
        last=("created_at", lambda s: s.max().date()),
    ))

    print("\n=== 2. Reviews per week, last 52 weeks ===")
    per_app = recent.groupby("app")["reviews"].agg(
        median="median", mean="mean", max="max",
        weeks_with_10_plus=lambda s: int((s >= 10).sum()),
        empty_weeks=lambda s: int((s == 0).sum()),
    ).round(1)
    print(per_app)
    pooled = recent.groupby("week")["reviews"].sum()
    print(f"\nAll apps pooled: median {pooled.median():.0f} per week, "
          f"{int((pooled >= 30).sum())} of {len(pooled)} weeks have 30 or more.")

    print("\n=== 3. Language mix (% of reviews) ===")
    mix = (pd.crosstab(df["app"], df["lang"], normalize="index") * 100).round(1)
    mix["code_switched"] = (df.groupby("app")["code_switched"].mean() * 100).round(1)
    print(mix)

    print("\n=== 4. Review length (characters) ===")
    print(df["text"].str.len().describe()[["25%", "50%", "75%"]].round(0).to_string())

    print("\n=== Verdict ===")
    med = pooled.median()
    if med >= 30:
        print(f"Pooled median is {med:.0f} per week: weekly trends are viable; "
              "per-app trends only for apps with a median of 10 or more.")
    elif med >= 10:
        print(f"Pooled median is {med:.0f} per week: use pooled weekly or per-app monthly "
              "buckets, and consider adding higher-volume apps.")
    else:
        print(f"Pooled median is {med:.0f} per week: too thin for trend detection. "
              "Add higher-volume apps before going further.")
    return weekly


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "reviews.csv"
    if args.report_only:
        df = pd.read_csv(path, parse_dates=["created_at"])
    else:
        print("Scraping...")
        df = scrape_all()
        if df.empty:
            print("No reviews fetched. Check your network and the app IDs.")
            return
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Saved {len(df)} reviews to {path}")

    weekly = report(df)
    weekly.to_csv(OUT_DIR / "volume_weekly.csv", index=False)


if __name__ == "__main__":
    main()
