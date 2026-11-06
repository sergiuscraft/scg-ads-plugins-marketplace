---
name: keywords
description: Keyword research pipeline for scg-ads - ask which sources to use every run, ingest CSV/Keyword Planner/search terms, clean, cluster into ad groups, propose match types and negatives, round-trip a CSV with the human.
argument-hint: "[optional seed ideas, URL, or path to CSV]"
---

# Keywords: sources -> CSV -> ad groups + negatives

Used by `new-campaign`, `update`, or alone. First do step 0 of `new-campaign` (pick the account, get its workspace folder). Output files go to `<workspace>/out/` (or the campaign folder when called from `new-campaign`/`update`).

## 1. Ask for the sources - EVERY run (never assume last time's choice)
AskUserQuestion (multi-select): 
1. **I bring a CSV** (Keyword Planner UI, Ahrefs, Semrush, Ubersuggest...).
2. **Account search terms** (AI pulls `search_term_view` via `search_search`).
3. **Keyword Planner via script** (`keyword_ideas.py`) - works only after developer-token Basic access; if it exits 4 say so and drop to 1/2.
4. **I'll research on my own** - show the sources sheet `${CLAUDE_PLUGIN_ROOT}/docs/KEYWORD-SOURCES.md` (links + the CSV format to bring back) and propose 10-20 seed phrases from the brief/landing page; pause until the human returns with a file.

## 2. Collect
- CSV: read with the tolerant reader (`scripts/_lib/csvio.py` semantics): any delimiter, any header casing. Map columns (keyword, volume, cpc, competition) and confirm the mapping with the human.
- Search terms: GAQL `search_term_view` last 30-90 days: `search_term_view.search_term, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions` for the chosen campaign/account. Ask the date range.
- Script: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/keyword_ideas.py --customer <id> --seeds "..." --geo <geo ids> --language <id> --out <workspace>/out/ideas.csv` (geo ids from `targeting_suggest_geo_targets`; language id from the human's target language).

## 3. Clean
Normalise (lowercase, trim, collapse whitespace, strip punctuation that Google ignores), dedupe (including word-order and plural variants that are the same intent), drop: brand/competitor terms (ask first - they may be a separate campaign), irrelevant intents (jobs, free, DIY, wikis, reviews if not wanted), too-low volume, other-language/geo junk, policy-risk terms. Report counts at each step; keep dropped terms in `dropped.csv` next to the keywords file with a reason so the human can rescue some.

## 4. Cluster into ad groups
Group by intent/theme so each ad group can have one tight RSA (aim 5-30 keywords, one landing page per group). Name groups plainly. Propose match types: EXACT for high-intent head terms, PHRASE for most, BROAD only when smart bidding with conversion data exists. Do not put the same keyword in two groups.

## 5. Negatives
- Campaign-level negatives from junk intents (jobs, free, DIY, torrent, etc.) and from wasted search terms (clicks, no conversions).
- Cross-group negatives to stop ad groups competing (exact-match negatives for sibling head terms).
- Reusable ones go in a shared list: `shared_sets_create_negative_keyword_list` / `shared_sets_add_list_negative_keywords` (via propose-confirm).

## 6. Write the working CSV and let the human edit it
`keywords.csv` with columns `ad_group,keyword,match_type,negative,cpc_bid` (+ extra info columns like `volume`, `cpc_est`, `note` are fine and ignored by the importer). Template: `${CLAUDE_PLUGIN_ROOT}/templates/keywords.csv`. Tell the human to edit it freely and say "ready"; re-read the file after every edit (the file, not memory, is the truth).

## 7. Hand off
When approved: `new-campaign` runs `import_csv.py` (dry run -> approve -> apply). Shared-list negatives go through the MCP tools. Always dry-run the importer first.
