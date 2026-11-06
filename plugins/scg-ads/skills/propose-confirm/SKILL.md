---
name: propose-confirm
description: Shared safety protocol for every Google Ads write (MCP tools and Python scripts). Load before any mutation in the scg-ads pipeline.
---

# Propose & confirm

Every write in scg-ads is two-phase. No exceptions, including "small" changes.

## MCP tools (google-ads server)
1. Call the tool with `validate_only=True` (default). The server runs a real API dry run and returns `change_items` + `checksum`.
2. Show the human `change_items` as a short table (entity, field, before -> after). Say what is NOT changing if it could be assumed.
3. Wait for an explicit yes in chat. Silence, "ok so", or approval of a *different* batch does not count.
4. Re-call with the exact same parameters, `validate_only=False`, and the returned `checksum`.
5. Read back with `search_search` and tell the human what is now live.

## Python scripts (`${CLAUDE_PLUGIN_ROOT}/scripts/*.py`)
1. Run without `--apply`. Output is JSON with `change_items` and `checksum` (identical contract).
2. Show, wait for explicit yes.
3. Re-run with identical inputs plus `--apply --checksum <hash>`. A changed input invalidates the checksum - re-propose.
4. Read back via GAQL.

## Rules
- New campaigns, ad groups and ads are created **PAUSED**. Enabling is its own proposal and its own approval.
- Removals/detachments: after the normal approval, ask once more ("This removes X. Confirm?").
- Batch related operations into one proposal so the human reviews one coherent change, not 40 fragments. Keep each batch <= 100 operations (the API access level may limit daily operations).
- If a dry run fails, show the API error verbatim, fix the input, re-propose. Never "try the commit anyway".
- Tools never run live before: `shared_sets_detach_negative_keyword_list`, `budgets_set_campaign_budget`, `ads_replace_responsive_search_ad`, ad-group-level `keywords_add_negative_keywords`. Tell the human it is a first live use and re-check by read-back.
- Never print, paste or ask for credentials or refresh tokens; setup is done by the human in a terminal with `configure.py` (the agent only runs `configure.py list|use|workspace`, which hold no secrets). Do not read `config.toml` or `adc.json`.
- Keep an append-only `changelog.md` in the account's workspace folder (`configure.py workspace`): date, customer, what changed, who approved (the human).
