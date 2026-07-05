# Prompt to generate your own config.json

Copy the prompt below into a new chat with Claude (or another LLM with
web search access), fill in the bracketed fields for your own situation,
and send it.

Why a prompt instead of ready-made presets: a channel/keyword list tuned
for, say, marketing is useless for a QA engineer or a Data Scientist —
the communities, niches, and even the language of postings differ too
much. Instead of guessing on your behalf, this prompt reproduces the
actual research-and-verification process for whatever your criteria are.

**A heads-up on language/market:** English-language Telegram channels
with job postings are, in practice, far less numerous than Russian-language
ones — the Telegram vacancy-channel ecosystem skews heavily CIS/Russian.
That's exactly why the prompt below also asks about RSS feeds from job
boards, not just Telegram — for English-speaking/international markets,
that combination will realistically find you more than Telegram alone.

---

```
You're helping me build a configuration for a bot that monitors Telegram
channels and, optionally, RSS feeds from job boards, sending me postings
that match specific criteria. The final output must be valid JSON in
exactly this structure:

{
  "channels": ["channel_username_1", "channel_username_2"],
  "feeds": [{"name": "Board Name", "url": "https://example.com/feed.rss"}],
  "include_keywords": ["keyword or phrase 1", "..."],
  "exclude_keywords": ["stop word 1", "..."]
}

("feeds" can be an empty array if I don't want any — see my answer below.)

My criteria:
- Role/profession: [e.g. QA Engineer, Backend Developer (Python),
  Data Scientist, Product Manager...]
- Synonyms/adjacent titles that also count: [...]
- Seniority (junior/mid/senior/doesn't matter): [...]
- Work format: [remote / hybrid / office / any]
- Employment type: [full-time / part-time / contract / any]
- Target market/geography of companies: [worldwide / specific
  country or region / ...]
- Language of postings: [English / other / any]
- Niches/industries I want to AVOID, if any: [e.g. gambling,
  crypto scams, MLM, specific companies...]
- Also include RSS feeds from job boards, in addition to Telegram
  channels? [yes / no / not sure — recommend based on my market]
- Anything else worth knowing: [...]

Please do the following, step by step:

1. If anything above is missing or unclear, ask me clarifying questions
   first — don't guess on my behalf. If I said "not sure" about RSS
   feeds, recommend yes/no based on how well-covered my target market
   is likely to be on Telegram (English-speaking/international markets
   are sparser on Telegram, so RSS feeds help more there; CIS/Russian-
   language markets are usually well covered by Telegram alone).

2. Find 15-30 relevant Telegram channels via web search, searching in
   several directions:
   - channels specifically dedicated to this profession/niche
   - broad general job-vacancy aggregator channels matching the target
     market/language
   - relocation/international-jobs hub channels, if relevant to the market
   - adjacent professional communities where relevant postings might
     also appear

3. CRITICALLY IMPORTANT — verify each Telegram channel individually via
   search before adding it to the list:
   - the channel exists and is active (not abandoned or renamed)
   - it is genuinely a PUBLIC BROADCAST CHANNEL, not a group chat — groups
     do not have a public web preview (t.me/s/...), and the reading method
     this bot relies on does not work for them
   - do not add a channel "just in case" or by name-pattern guessing
     without direct confirmation it actually exists — a short list of
     working channels beats a long list that's half dead

4. If I asked for RSS feeds: find job boards relevant to my role/market
   that publish an OFFICIAL PUBLIC RSS OR ATOM FEED (many remote-work-
   focused job boards do this explicitly). For each candidate:
   - verify by fetching the feed URL directly that it returns valid
     RSS/Atom XML with real, current job listings — don't guess a
     plausible-looking URL without checking it actually works
   - do NOT include mainstream platforms like LinkedIn or Indeed — they
     prohibit automated scraping in their terms of service, and this bot
     is only meant to read sources that explicitly publish an open feed
     for this purpose

5. Build include_keywords: exact job titles + synonyms (including other
   languages, if the market is international) + terms/tools/platforms
   characteristic of the profession. Avoid overly generic single words
   that will catch a lot of irrelevant noise.

6. Build exclude_keywords: think about whether this profession has an
   adjacent-but-unwanted niche (similar to how, in marketing, there's a
   whole separate "traffic arbitrage" world involving gambling/crypto
   scams that looks similar but is usually unwanted) — and add terms
   characteristic of that niche as stop words.

7. Output the final result ONLY as valid JSON in a code block, with no
   other text inside it — I'll paste it straight into config.json.
```

---

**After you get the result:** paste the JSON into your repo's
`config.json`, commit it, and run **Test Setup** (Actions tab) — it will
show you which of the suggested channels and feeds are actually
reachable, and which aren't. If some aren't working, you can go back to
the same chat and ask for a replacement.

You can reuse this prompt later too — e.g. to expand the channel/feed
list, tune keywords after seeing the first real results, or rebuild the
whole config for a different role.
