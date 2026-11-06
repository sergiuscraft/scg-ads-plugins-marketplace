# scg-ads-plugins-marketplace

Claude Code plugin marketplace. Currently one plugin: **`scg-ads`** - a human + AI Google Ads pipeline.

## Install
```bash
export GOOGLE_ADS_MCP_FORK_DIR=~/GitHub/google-ads-mcp/google-ads-mcp-fork   # see plugins/scg-ads/docs/PREREQS.md
claude plugin marketplace add ~/GitHub/scg-ads-plugins-marketplace
claude plugin install scg-ads@scg-ads-plugins
```

## Use
| Command | Stage |
|---|---|
| `/scg-ads:setup` | 1. Account: audit, conversions, shared assets, audiences/links checklist, `account-brief.md` |
| `/scg-ads:new-campaign` | 2. Brief -> keywords (sources asked each run) -> budget -> ads -> build PAUSED -> verify |
| `/scg-ads:update` | 3. Read performance -> findings -> approved batches -> apply -> changelog |
| `/scg-ads:keywords` | Standalone keyword research / cleaning / clustering / negatives |

No parameter syntax: commands discover accounts, campaigns and options from the API and ask you to pick (or type your own). Optional free text after the command is just context.

## How human and AI split the work
- **You**: business facts, prices/margins, schedule, audience decisions, keyword research if you prefer (see `docs/KEYWORD-SOURCES.md`), approving every change, enabling campaigns.
- **Claude**: reads the account, drafts keyword clusters/negatives/ads/budgets, runs dry runs, shows diffs, applies only approved changes, reads back, logs.
- **Safety**: dry run -> checksum -> explicit yes -> commit; new objects PAUSED. Same contract for MCP tools and scripts.

## Layout
`plugins/scg-ads/` - `skills/` (setup, new-campaign, update, keywords, budget, creatives, propose-confirm), `commands/`, `scripts/` (Python via `uv run`: keyword_ideas, import_csv, create_ads, ad_schedule, campaign_settings, conversion_upload, user_lists, account_links), `templates/`, `docs/`, `tests/`.

## Tests
```bash
cd plugins/scg-ads && uv run --with pytest --with google-ads --with google-auth python -m pytest tests -q
```

## Roadmap
P3: `campaign_create_other.py` (Display, PMax, Demand Gen, Shopping, Video). See `docs/TOOL-MAP.md`.
