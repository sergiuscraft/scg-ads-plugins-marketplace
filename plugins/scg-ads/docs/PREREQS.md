# Prerequisites

## 1. Google Ads MCP fork
Clone the fork and export its path:
```bash
git clone https://github.com/sergiuscraft/google-ads-mcp.git
export GOOGLE_ADS_MCP_FORK_DIR="$PWD/google-ads-mcp"
```
The plugin's `.mcp.json` starts it with `uv run --directory "$GOOGLE_ADS_MCP_FORK_DIR" -m ads_mcp.server`.
If you already registered a `google-ads` server in your own MCP config, disable one of them to avoid duplicate tool names.

## 2. Credentials (env only, never in this repo)
| Var | Purpose |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | ADC json with the `adwords` scope (keep it outside any repo, mode 600) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | manager account id |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | needed for scripts like Keyword Planner; the MCP also sends it if set |

Scripts use the same variables (`scripts/_lib/client.py`) and run with `uv run <script>`; dependencies are declared inline (PEP 723). `uv` required.

## 3. Developer-token access level (important)
- Explorer access: low daily operation limit, **Keyword Planner returns `DEVELOPER_TOKEN_NOT_APPROVED`**. `keyword_ideas.py` exits with code 4 and the skills fall back to CSV / search terms.
- To unlock Keyword Planner and higher limits: apply for **Basic access** in Google Ads (manager account) > Tools > API Center. This is a human action.

## 4. Known untested-live fork tools
`shared_sets_detach_negative_keyword_list`, `budgets_set_campaign_budget`, `ads_replace_responsive_search_ad`, ad-group-level `keywords_add_negative_keywords`. First use: verify with a read-back.

## 5. Safety defaults
Everything dry-runs first; new objects are PAUSED; commit needs the checksum of the exact approved inputs. Scripts follow the same contract: no `--apply` without `--checksum`.

## 6. Do not commit
`client_secret*.json`, `mcp-google-ads.yaml`, `adc.json`, any refresh token. The `.gitignore` covers common names; check `git status` before committing. Run `tools/install-hooks.sh` once after cloning: a pre-commit scan blocks secret files, token patterns, personal emails, absolute home paths and anything listed in your untracked `.personal-denylist`.
