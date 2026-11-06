# scg-ads-plugins-marketplace

Claude Code plugin marketplace. Currently one plugin: **`scg-ads`** - a human + AI Google Ads pipeline.

## Install
Requires [`uv`](https://docs.astral.sh/uv/) and Claude Code.

```bash
# 1. get both repos
git clone https://github.com/sergiuscraft/google-ads-mcp.git
git clone https://github.com/sergiuscraft/scg-ads-plugins-marketplace.git

# 2. configure in YOUR terminal (nothing goes through the chat): sign-in, developer token, accounts
./scg-ads-plugins-marketplace/plugins/scg-ads/scripts/configure.py init
#    where to get each key/id: plugins/scg-ads/docs/CREDENTIALS.md

# 3. verify: file modes, API read, and that the MCP server starts
./scg-ads-plugins-marketplace/plugins/scg-ads/scripts/configure.py check --mcp

# 4. add the MCP tools and skills to Claude Code
claude plugin marketplace add ./scg-ads-plugins-marketplace
claude plugin install scg-ads@scg-ads-plugins
```
Config lives in `~/.config/scg-ads/` (private, outside any repo). The plugin starts the MCP server itself from that config, so there is nothing to export. Restart Claude Code and run `/scg-ads:setup`. If you registered a `google-ads` MCP server by hand, remove it to avoid duplicate tools.

Config = keys and tokens only. Accounts are just 10-digit ids: `configure.py use 123-456-7890` picks the one you work on (no registration needed), `configure.py list` shows the ones you have used. Each account gets its own folder (`~/ads-workspaces/<id>/`) with briefs, CSVs and the changelog.

Contributors: `./scg-ads-plugins-marketplace/tools/install-hooks.sh` blocks commits containing secrets or personal data.

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
`plugins/scg-ads/` - `docs/CREDENTIALS.md` (how to get keys), `config.example.toml`, `skills/` (setup, new-campaign, update, keywords, budget, creatives, propose-confirm), `commands/`, `scripts/` (Python via `uv run`: configure, run_mcp, keyword_ideas, import_csv, create_ads, ad_schedule, campaign_settings, conversion_upload, user_lists, account_links), `templates/`, `docs/`, `tests/`.

## Tests
```bash
cd plugins/scg-ads && uv run --with pytest --with google-ads --with google-auth python -m pytest tests -q
```

## Roadmap
P3: `campaign_create_other.py` (Display, PMax, Demand Gen, Shopping, Video). See `docs/TOOL-MAP.md`.
