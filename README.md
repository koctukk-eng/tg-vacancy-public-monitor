# TG Vacancy Monitor

A free, self-hosted Telegram bot that watches public channels for job
postings matching your keywords and sends matches straight to your own
Telegram bot. Runs on GitHub Actions — no server, no computer that has
to stay on 24/7, no paid subscriptions.

**How it works:** the script reads the public web preview page of each
channel (`t.me/s/<channel>`), filters posts by your keywords, and sends
matches to your bot. GitHub runs the check automatically every 3 hours
(configurable).

## Before you start — limitations

- Telegram monitoring works **only with public channels**, not private
  groups/chats (groups have no public web preview page — there's no way
  to read them this way without being a member with elevated access)
- English-language Telegram channels with job postings are, in practice,
  **far less numerous** than Russian-language ones — this ecosystem
  skews heavily CIS/Russian. That's why this bot can *optionally* also
  check RSS feeds from job boards (see step 4) — useful mainly if you're
  targeting an English-speaking/international market
- Only job boards with an **official public RSS/Atom feed** are
  supported for the web side — this deliberately does NOT scrape
  mainstream sites like LinkedIn or Indeed, which prohibit scraping in
  their terms of service
- The Telegram web preview only shows the last ~20 posts per channel —
  if a channel publishes more than that between checks, some posts may
  slip through the gap
- Telegram reading is an unofficial method (not the Bot/MTProto API) —
  if Telegram changes the preview page markup, the script may need updating
- Intended for personal, non-commercial use at a reasonable check
  frequency — not for aggressive scraping

## What you'll need

- A **Telegram account** (you already have one if you're reading this on Telegram)
- A **free GitHub account** — sign up at [github.com](https://github.com) if
  you don't have one yet (~2 minutes, just an email and password)
- About **20-25 minutes** total, most of it in step 4

No credit card, no paid tools, anywhere in this process.

## Quick start (checklist)

Each step below is tagged with where it happens — 📱 **Telegram** or
🌐 **GitHub** (in your regular web browser) — since you'll be switching
back and forth a couple of times.

### 1. 📱 Create your Telegram bot
- [ ] In Telegram, find `@BotFather`
- [ ] Send `/newbot`, choose a display name and a username (must end in `bot`)
- [ ] Save the **token** you get back (a string like `123456:AAExample...`)

### 2. 📱 Find your chat_id
- [ ] Send your new bot any message (it can't see you until you message
      it first)
- [ ] Open in a browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
- [ ] Find `"chat":{"id":123456789,...}` in the response — that number is
      your **chat_id**

### 3. 🌐 Deploy the repository (back on GitHub)
This step happens on **github.com**, in your browser — not in Telegram.
If you don't have a GitHub account yet, create one now (free, just an
email and password) before continuing.

- [ ] Go to this repository's page on GitHub
- [ ] Click the green **Use this template** button near the top
      (creates a clean copy of everything under your own GitHub account,
      with no shared commit history)
- [ ] Give it a name and click **Create repository** — this creates
      *your own* copy that you'll work in for every step from here on
- [ ] Optional: make your new repo **Private** if you'd rather not let
      others see which channels/keywords you're job-hunting with

### 4. 🌐 + 💬 Set up your filters (GitHub + a Claude chat)
`config.json` ships empty on purpose — filling it in by hand from scratch
is hard (you'd also need to verify every channel/feed actually exists and
is active). Instead, use **`PROMPT.md`** — a ready-made prompt for Claude
(or another LLM with web search) that will ask you clarifying questions
(including whether you want RSS job-board feeds in addition to Telegram —
recommended for English-speaking/international markets), find and verify
suitable sources, build a keyword list, and hand you back a finished JSON.

- [ ] On GitHub, open `PROMPT.md` in **your** new repository (the copy
      from step 3, not this original template)
- [ ] Copy the prompt into a new chat with Claude (claude.ai) or another
      LLM that can search the web
- [ ] Fill in the bracketed fields for your own situation (role, market,
      language, work format, etc.) and send it — this part is a normal
      back-and-forth chat, it may take a few replies
- [ ] Once you have a finished JSON result, go back to GitHub, open
      `config.json` in your repo, and paste it in, replacing the empty
      placeholder
- [ ] Commit changes

### 5. 🌐 Add your secrets (GitHub)
- [ ] In your repo: Settings → Secrets and variables → Actions → New repository secret
- [ ] Add `BOT_TOKEN` (from step 1) and `CHAT_ID` (from step 2)

### 6. 🌐 Allow the workflow to commit changes (GitHub)
- [ ] Settings → Actions → General → Workflow permissions →
      **Read and write permissions** → Save

### 7. 🌐 Run the setup check (GitHub)
- [ ] Actions → **Test Setup** → Run workflow
- [ ] Wait for ✅, then open the log — it will clearly show: whether
      config.json is valid, whether the bot works, and which channels
      are reachable
- [ ] If anything shows ❌, see Troubleshooting below

### 8. 🌐 Start the main monitor (GitHub)
- [ ] Actions → **Monitor TG vacancies** → Run workflow
- [ ] On the first run, the bot **won't send you any vacancies** — it
      only records the current latest post of each channel as a
      baseline, so it doesn't dump a pile of old postings on you
- [ ] From the second run onward, you'll only get genuinely new posts

Done — from here it runs on its own, on schedule (`cron` in
`.github/workflows/monitor.yml`, every 3 hours by default). Check
📱 Telegram — that's where results will show up from now on, not GitHub.

## Editing your criteria later

Open `config.json` directly on GitHub (the pencil icon):
- `channels` — list of channel usernames (no `@`, just the name)
- `feeds` — optional list of RSS/Atom job board feeds, each as
  `{"name": "...", "url": "..."}` (or a plain URL string)
- `include_keywords` — at least one of these must appear in a post
- `exclude_keywords` — stop words: if even one is present, the post is discarded

Changes take effect automatically on the next run.

## Troubleshooting

**Log shows `[WARN] channel: 0 posts received`**
The channel wasn't found under that name, was renamed/deleted, or it's a
private group rather than a channel — groups have no public web preview.
Double-check the spelling or swap in a working alternative.

**Log shows `[WARN] <feed url>: 0 items parsed` or "not valid XML"**
The URL doesn't actually serve RSS/Atom (double-check it in a browser —
a real feed URL usually shows raw XML, not a normal web page), the board
changed its feed URL, or the feed is temporarily empty. Ask in the same
Claude chat that generated your config for a replacement source.

**Nothing has arrived in the bot for hours**
This is normal on the very first run (see step 8), and also normal in
general for narrow niches — matching postings might only show up every
few hours or days across all your channels combined, not as a steady
stream. To confirm the system is actually alive rather than silently
broken: Actions → Test Setup → Run workflow.

**getUpdates returns `{"ok":true,"result":[]}`**
You haven't messaged the bot yet, or you did but checked `getUpdates`
before the message actually went through. Message the bot, wait a couple
seconds, refresh the page.

**After uploading files, the `.github` folder isn't showing up**
Common issue: Mac/Windows file managers hide folders starting with a dot
during drag-and-drop uploads. Fix: create
`.github/workflows/monitor.yml` (and `test-setup.yml`) manually via
"Add file → Create new file", typing the full path with `/` — GitHub
will create the folders for you.

**Workflow fails with a push / permission denied error**
Check step 6 — Workflow permissions must be set to "Read and write",
otherwise the script can't commit the updated `seen_ids.json` back to
the repo.

## License

MIT — use, modify, and distribute freely. See `LICENSE`.
