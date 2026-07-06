"""
Monitors public Telegram channels — and, optionally, RSS feeds from
job boards — for postings matching your keywords.

How it works:
1. Telegram channels (config.json -> "channels"): fetch each channel's
   public web preview page (https://t.me/s/<channel>) — works without
   login and without the Telegram API, because the channel is public.
2. RSS/Atom feeds (config.json -> "feeds", optional): fetch and parse
   each feed with the standard library (no extra dependency). This is
   meant for legitimate job boards that publish official public RSS
   feeds (e.g. remote-work boards) — NOT for scraping mainstream sites
   like LinkedIn or Indeed, which prohibit scraping in their terms of
   service. Leave "feeds" empty (or omit it) if you only want Telegram
   channels — the rest of the script behaves exactly as before.
3. Filter each post/item: it must contain at least one of the
   include_keywords and none of the exclude_keywords.
4. Send new (not yet seen) matches to your personal Telegram bot.
5. Store progress in seen_ids.json, so nothing is sent twice and
   nothing is skipped between runs.
6. At the end of every run, ALWAYS send a summary status message, even
   if zero new matches were found.

This script does not store or use any payment data — only the bot token
and chat_id, passed in as environment variables (in GitHub Actions, via
Secrets).
"""

import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CONFIG_PATH = Path(__file__).parent / "config.json"
SEEN_PATH = Path(__file__).parent / "seen_ids.json"

TELEGRAM_PREVIEW_URL = "https://t.me/s/{channel}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
ATOM_NS = "{http://www.w3.org/2005/Atom}"
MAX_SEEN_FEED_IDS = 500  # cap per feed, so seen_ids.json doesn't grow forever
MAX_SENT_HASHES = 1000  # cap for cross-source dedup hashes


def content_hash(text: str) -> str:
    """Hash of normalized post text, used to deduplicate the same vacancy
    reposted across multiple channels/feeds. Normalization strips URLs,
    @mentions, hashtags, punctuation and whitespace differences, so
    near-identical reposts collapse into the same hash."""
    normalized = text.lower()
    normalized = re.sub(r"https?://\S+", "", normalized)  # links differ per repost
    normalized = re.sub(r"[@#]\w+", "", normalized)  # channel tags differ per repost
    normalized = re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)  # keep letters/digits only
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seen() -> dict:
    if SEEN_PATH.exists():
        with open(SEEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen(seen: dict) -> None:
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def matches_filters(text: str, include_keywords: list[str], exclude_keywords: list[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(bad.lower() in lowered for bad in exclude_keywords):
        return False
    return any(good.lower() in lowered for good in include_keywords)


def send_telegram_message(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] BOT_TOKEN / CHAT_ID not set — message not sent.")
        print(text)
        return
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            api_url,
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[WARN] Failed to send Telegram message: {e}")


# --- Telegram channels ---


def fetch_channel_posts(channel: str) -> list[dict]:
    """Returns a list of channel posts: [{id, text, url}, ...], oldest to newest."""
    url = TELEGRAM_PREVIEW_URL.format(channel=channel)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[WARN] Failed to load channel {channel}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = []
    for msg in soup.select("div.tgme_widget_message"):
        post_id_attr = msg.get("data-post")  # format "channel/1234"
        if not post_id_attr:
            continue
        post_id = post_id_attr.split("/")[-1]

        text_el = msg.select_one(".tgme_widget_message_text")
        text = text_el.get_text(separator="\n").strip() if text_el else ""

        posts.append(
            {
                "id": int(post_id),
                "text": text,
                "url": f"https://t.me/{channel}/{post_id}",
            }
        )

    if not posts:
        print(f"[WARN] {channel}: 0 posts received (channel not found, private, or preview disabled)")

    posts.sort(key=lambda p: p["id"])
    return posts


def process_channel(channel: str, seen: dict, include_keywords: list[str], exclude_keywords: list[str]) -> int:
    posts = fetch_channel_posts(channel)
    if not posts:
        return 0

    last_seen_id = seen.get(channel)

    if last_seen_id is None:
        # First run for this channel: just record the current max post id
        # as a baseline, so we don't dump a pile of old posts on you.
        max_id = max(p["id"] for p in posts)
        seen[channel] = max_id
        print(f"[INFO] {channel}: baseline set (id={max_id})")
        return 0

    new_posts = [p for p in posts if p["id"] > last_seen_id]

    matches = 0
    for post in new_posts:
        if matches_filters(post["text"], include_keywords, exclude_keywords):
            h = content_hash(post["text"])
            sent_hashes = seen.setdefault("_sent_hashes", [])
            if h in sent_hashes:
                print(f"[INFO] {channel}: skipping duplicate of an already-sent vacancy")
                continue
            message = f"🎯 New match in @{channel}\n\n{post['text'][:800]}\n\n{post['url']}"
            send_telegram_message(message)
            sent_hashes.append(h)
            del sent_hashes[:-MAX_SENT_HASHES]
            matches += 1
            time.sleep(1)  # avoid hammering the Telegram API

    if new_posts:
        seen[channel] = max(p["id"] for p in new_posts)

    return matches


# --- RSS / Atom feeds (job boards that publish an official public feed) ---


def fetch_feed_items(feed_url: str) -> list[dict]:
    """Returns a list of feed items: [{id, text, url}, ...]. Supports both
    RSS 2.0 (<item>) and Atom (<entry>) formats."""
    try:
        resp = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[WARN] Failed to load feed {feed_url}: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"[WARN] Feed {feed_url} is not valid XML: {e}")
        return []

    items = []

    # RSS 2.0: <rss><channel><item>...
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        if guid:
            items.append({"id": guid, "text": f"{title}\n{description}", "url": link or guid})

    # Atom: <feed><entry>...
    for entry in root.findall(f".//{ATOM_NS}entry"):
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        summary = (
            entry.findtext(f"{ATOM_NS}summary") or entry.findtext(f"{ATOM_NS}content") or ""
        ).strip()
        link_el = entry.find(f"{ATOM_NS}link")
        link = link_el.get("href", "") if link_el is not None else ""
        entry_id = (entry.findtext(f"{ATOM_NS}id") or link).strip()
        if entry_id:
            items.append({"id": entry_id, "text": f"{title}\n{summary}", "url": link or entry_id})

    if not items:
        print(f"[WARN] {feed_url}: 0 items parsed (unsupported feed format, or feed is empty)")

    return items


def process_feed(feed_url: str, name: str, seen: dict, include_keywords: list[str], exclude_keywords: list[str]) -> int:
    items = fetch_feed_items(feed_url)
    if not items:
        return 0

    feeds_seen = seen.setdefault("_feeds", {})
    seen_ids = feeds_seen.get(feed_url)

    if seen_ids is None:
        # First run for this feed: record current items as baseline, don't
        # send anything yet.
        feeds_seen[feed_url] = [item["id"] for item in items][-MAX_SEEN_FEED_IDS:]
        print(f"[INFO] {name}: baseline set ({len(items)} items)")
        return 0

    seen_ids_set = set(seen_ids)
    new_items = [item for item in items if item["id"] not in seen_ids_set]

    matches = 0
    for item in new_items:
        if matches_filters(item["text"], include_keywords, exclude_keywords):
            h = content_hash(item["text"])
            sent_hashes = seen.setdefault("_sent_hashes", [])
            if h in sent_hashes:
                print(f"[INFO] {name}: skipping duplicate of an already-sent vacancy")
                continue
            message = f"🎯 New match on {name}\n\n{item['text'][:800]}\n\n{item['url']}"
            send_telegram_message(message)
            sent_hashes.append(h)
            del sent_hashes[:-MAX_SENT_HASHES]
            matches += 1
            time.sleep(1)

    updated_ids = (seen_ids + [item["id"] for item in new_items])[-MAX_SEEN_FEED_IDS:]
    feeds_seen[feed_url] = updated_ids

    return matches


def main() -> None:
    config = load_config()
    seen = load_seen()

    channels = config.get("channels", [])
    feeds = config.get("feeds", [])
    include_keywords = config["include_keywords"]
    exclude_keywords = config["exclude_keywords"]

    total_new_matches = 0

    for channel in channels:
        total_new_matches += process_channel(channel, seen, include_keywords, exclude_keywords)

    for feed in feeds:
        # A feed entry can be a plain URL string, or {"name": ..., "url": ...}
        if isinstance(feed, str):
            feed_url, name = feed, feed
        else:
            feed_url = feed["url"]
            name = feed.get("name", feed_url)
        total_new_matches += process_feed(feed_url, name, seen, include_keywords, exclude_keywords)

    save_seen(seen)
    print(f"[INFO] Done. New matching vacancies sent: {total_new_matches}")

    # Final status — always sent, even if 0 matches were found
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status_text = (
        f"✅ Check complete ({now_str})\n"
        f"Matching vacancies found: {total_new_matches}"
    )
    send_telegram_message(status_text)


if __name__ == "__main__":
    main()
