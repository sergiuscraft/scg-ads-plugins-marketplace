# scg-ads-plugins-marketplace

Claude Code plugin marketplace. Currently one plugin: **`scg-ads`** - a human + AI Google Ads pipeline.

## Install
Requires [`uv`](https://docs.astral.sh/uv/) and Claude Code. Do it in order: first get the MCP server running locally, then add the plugin.

### 1. Run the Google Ads MCP server locally
```bash
git clone https://github.com/sergiuscraft/google-ads-mcp.git
git clone https://github.com/sergiuscraft/scg-ads-plugins-marketplace.git

# credentials: environment only, never in a repo (how to get them: scg-ads-plugins-marketplace/plugins/scg-ads/docs/PREREQS.md)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/adc.json
export GOOGLE_ADS_LOGIN_CUSTOMER_ID=<manager account id>
export GOOGLE_ADS_DEVELOPER_TOKEN=<developer token>
export GOOGLE_ADS_MCP_FORK_DIR="$PWD/google-ads-mcp"

# check that the server starts and can read your account (read-only)
./scg-ads-plugins-marketplace/tools/smoke_mcp.py
```
Expected: `OK: server started, 47 tools` and your accessible customer ids. If it fails, fix this before step 2 (usual causes: ADC file/scope, wrong login customer id, missing developer token).

### 2. Add the MCP tools and skills to Claude Code
```bash
claude plugin marketplace add ./scg-ads-plugins-marketplace
claude plugin install scg-ads@scg-ads-plugins
```
The plugin starts the server from step 1 itself (`uv run --directory "$GOOGLE_ADS_MCP_FORK_DIR" -m ads_mcp.server`) using the same env vars, so keep them in your shell profile. Restart Claude Code, then run `/scg-ads:setup`. If you also registered a `google-ads` server by hand, remove one of them to avoid duplicate tools.

Contributors: run `./scg-ads-plugins-marketplace/tools/install-hooks.sh` to block commits containing secrets or personal data.

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
