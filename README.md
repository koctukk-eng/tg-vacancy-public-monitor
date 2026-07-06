"""
Quick setup check — run this BEFORE relying on the main workflow
(monitor.yml).

Checks:
1. Is config.json valid, and does it have all required fields
2. Do the BOT_TOKEN / CHAT_ID secrets work (sends a test message)
3. Which Telegram channels in config.json are actually reachable
4. Which RSS/Atom feeds in config.json are actually reachable and parseable

Does not write to seen_ids.json and does not send any vacancies — safe
to run as many times as you like while setting things up.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CONFIG_PATH = Path(__file__).parent / "config.json"
TELEGRAM_PREVIEW_URL = "https://t.me/s/{channel}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
ATOM_NS = "{http://www.w3.org/2005/Atom}"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_IDS = [c.strip() for c in (os.environ.get("CHAT_ID") or "").split(",") if c.strip()]


def check_config() -> dict:
    print("== 1. Checking config.json ==")
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found next to the script")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ config.json has a JSON syntax error: {e}")
        print("   Common cause: a missing or extra comma after editing the file")
        sys.exit(1)

    missing = [k for k in ("channels", "include_keywords", "exclude_keywords") if k not in config]
    if missing:
        print(f"❌ config.json is missing required field(s): {', '.join(missing)}")
        sys.exit(1)

    n_feeds = len(config.get("feeds", []))
    print(
        f"✅ config.json is valid: {len(config['channels'])} channels, "
        f"{n_feeds} feed(s), "
        f"{len(config['include_keywords'])} include keywords, "
        f"{len(config['exclude_keywords'])} exclude keywords"
    )
    return config


def check_bot() -> None:
    print("\n== 2. Checking bot (BOT_TOKEN / CHAT_ID) ==")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN is not set.")
        print("   Check: Settings → Secrets and variables → Actions in your repo")
        sys.exit(1)

    if not CHAT_IDS:
        # CHAT_ID not set yet — try to auto-detect it from getUpdates.
        print("ℹ️  CHAT_ID is not set — trying to detect it automatically...")
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", timeout=20
            )
            data = resp.json()
        except requests.RequestException as e:
            print(f"❌ Could not reach the Telegram API: {e}")
            sys.exit(1)

        if not data.get("ok"):
            print(f"❌ Telegram API rejected the request: {data}")
            print("   Most likely the BOT_TOKEN is wrong — recheck it in your secrets.")
            sys.exit(1)

        found = {}
        for update in data.get("result", []):
            msg = update.get("message")
            if msg and msg.get("chat", {}).get("type") == "private":
                chat = msg["chat"]
                found[chat["id"]] = chat.get("first_name", "") or chat.get("username", "")

        if not found:
            print("❌ No messages found. Open Telegram, send your bot any message")
            print("   (e.g. 'hello'), then re-run this Test Setup workflow.")
            sys.exit(1)

        print("✅ Found the following chat_id(s) from messages sent to your bot:")
        for cid, name in found.items():
            print(f"   chat_id: {cid}   (from: {name})")
        print()
        if len(found) == 1:
            print("   → Add it as a CHAT_ID secret:")
        else:
            print("   → Multiple people have messaged this bot. If you want ALL of them")
            print("     to get notifications, join the numbers with commas into ONE")
            print("     CHAT_ID secret, for example:")
            print(f"     {','.join(str(c) for c in found)}")
            print("   → Or just use one of the numbers above if you only want a single recipient.")
        print("     Settings → Secrets and variables → Actions → New repository secret")
        print("   Then re-run this Test Setup workflow to confirm everything works.")
        sys.exit(1)

    print(f"Sending a test message to {len(CHAT_IDS)} recipient(s)...")
    all_ok = True
    for chat_id in CHAT_IDS:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": "✅ Test message: your bot is set up correctly and can message you!",
                },
                timeout=20,
            )
            data = resp.json()
        except requests.RequestException as e:
            print(f"❌ Could not reach the Telegram API for {chat_id}: {e}")
            all_ok = False
            continue

        if data.get("ok"):
            print(f"✅ Test message sent to {chat_id} — check that chat in Telegram")
        else:
            print(f"❌ Telegram API rejected the request for {chat_id}: {data}")
            all_ok = False

    if not all_ok:
        print("   Common causes: wrong chat_id, or that person hasn't messaged the bot first yet")
        sys.exit(1)


def check_channels(channels: list[str]) -> None:
    print(f"\n== 3. Checking {len(channels)} Telegram channel(s) ==")
    if not channels:
        print("   (none configured — skipping)")
        return

    ok, fail = [], []
    for channel in channels:
        url = TELEGRAM_PREVIEW_URL.format(channel=channel)
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            posts = soup.select("div.tgme_widget_message")
            (ok if posts else fail).append(channel)
        except requests.RequestException:
            fail.append(channel)

    print(f"✅ Working channels: {len(ok)}")
    if fail:
        print(f"❌ Problem channels: {len(fail)}")
        for ch in fail:
            print(f"   - {ch}")
        print(
            "   Possible causes: typo in the name, channel renamed/deleted, "
            "or it's a private GROUP rather than a public channel — groups "
            "don't have a public web preview, so this reading method doesn't "
            "work for them."
        )


def check_feeds(feeds: list) -> None:
    print(f"\n== 4. Checking {len(feeds)} RSS/Atom feed(s) ==")
    if not feeds:
        print("   (none configured — skipping)")
        return

    ok, fail = [], []
    for feed in feeds:
        if isinstance(feed, str):
            feed_url, name = feed, feed
        else:
            feed_url = feed["url"]
            name = feed.get("name", feed_url)

        try:
            resp = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            has_items = bool(root.findall(".//item")) or bool(root.findall(f".//{ATOM_NS}entry"))
            (ok if has_items else fail).append(name)
        except (requests.RequestException, ET.ParseError):
            fail.append(name)

    print(f"✅ Working feeds: {len(ok)}")
    if fail:
        print(f"❌ Problem feeds: {len(fail)}")
        for name in fail:
            print(f"   - {name}")
        print(
            "   Possible causes: wrong URL, the site doesn't actually offer "
            "RSS/Atom at that address, or the feed is temporarily empty."
        )


if __name__ == "__main__":
    cfg = check_config()
    check_bot()
    check_channels(cfg.get("channels", []))
    check_feeds(cfg.get("feeds", []))
    print("\nDone. If everything is ✅, you can rely on the main workflow (Monitor TG vacancies).")
