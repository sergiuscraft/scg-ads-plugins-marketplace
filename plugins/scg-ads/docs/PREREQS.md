# Prerequisites

## 1. Google Ads MCP fork + credentials
Clone `https://github.com/sergiuscraft/google-ads-mcp.git`, then run `scripts/configure.py init`. The plugin's `.mcp.json` starts the server through `scripts/run_mcp.py`, which reads `~/.config/scg-ads/config.toml` and exports the credentials to the server process only. Full guide, including how to obtain every key: **`CREDENTIALS.md`**.
If you already registered a `google-ads` server in your own MCP config, disable one of them to avoid duplicate tool names.

## 2. Environment overrides
Real env vars win over the file: `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `GOOGLE_ADS_MCP_FORK_DIR`, `SCG_ADS_CONFIG` (config path). Scripts run with `uv run <script>`; dependencies are declared inline (PEP 723).

## 3. Keyword Planner availability
Keyword Planner depends on the API access level of your setup. When the API refuses it, `keyword_ideas.py` exits with code 4 and the skills fall back to CSV / search terms.

## 4. Known untested-live fork tools
`shared_sets_detach_negative_keyword_list`, `budgets_set_campaign_budget`, `ads_replace_responsive_search_ad`, ad-group-level `keywords_add_negative_keywords`. First use: verify with a read-back.

## 5. Safety defaults
Everything dry-runs first; new objects are PAUSED; commit needs the checksum of the exact approved inputs. Scripts follow the same contract: no `--apply` without `--checksum`.

## 6. Do not commit
`client_secret*.json`, `mcp-google-ads.yaml`, `adc.json`, any refresh token. The `.gitignore` covers common names; check `git status` before committing. Run `tools/install-hooks.sh` once after cloning (contributors): a pre-commit scan blocks secret files, token patterns, personal emails, absolute home paths and anything listed in your untracked `.personal-denylist`.
