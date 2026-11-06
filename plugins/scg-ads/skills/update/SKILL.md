---
name: update
description: Stage 3 of the scg-ads pipeline - review and update an existing Google Ads campaign with a human (performance read, search terms, negatives, keywords, ads, budget/bidding, schedule, audiences), applying only approved batches.
argument-hint: "[optional: what you want to improve, e.g. 'wasted spend', 'more leads']"
---

# Stage 3 - Update a campaign

Load `propose-confirm`. `$ARGUMENTS` is free context. Discover, then let the human select.

## 0. Pick the account and its workspace (no secrets involved)
1. Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py list` - a table of saved accounts: label, customer id, **login id**, currency, time zone, name, default. If it reports no config, tell the human to run `configure.py init` in their own terminal (never ask them to paste keys or tokens here).
2. AskUserQuestion: the saved accounts (default first) plus "Other - any customer id (does not need to be in the config)". Several accounts are normal: always confirm which one this session works on.
3. Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py use <label-or-id> [--login <manager id>]` then `... configure.py workspace --customer <label-or-id>`; the last prints the **workspace folder** (`<root>/<label or id>/` with `account-brief.md`, `changelog.md`, `out/`, `campaigns/`, `creatives/`). For an account that is not saved, ask the human for its manager (login) id or "none/direct" and pass it with `--login`.
4. From now on: every file this skill writes (briefs, CSVs, reports, changelog) goes into that folder, by absolute path; say the folder path to the human once. Pass the table's **login id** as `login_customer_id` on every MCP tool call, and `--customer <label-or-id>` to scripts (they resolve labels and the login id themselves).

## 1. Pick scope
GAQL campaign list for this account (name, status, channel, budget, last-30d cost/clicks/conversions; pass the login id) -> campaign pick-list (multi-select ok). Ask the period (7/30/90 days, custom) and the goal for this round (waste, volume, CPA, new angles, structure, seasonality). Work inside `<workspace>/campaigns/<campaign>/` when it exists.

## 2. Read (all read-only)
- Campaign/ad group/keyword/ad performance, device, hour x day-of-week, geo, audience segments.
- `search_term_view` (search term, status, clicks, cost, conversions).
- Impression share & lost-IS (budget / rank), quality score components, ad strength, disapprovals/policy status, recommendations-like signals.
- For deeper diagnosis load the `google-ads-api-account-diagnostics` skill.
- Optionally refresh ideas: `keywords` skill (sources asked again - never reuse last time's choice).

## 3. Findings -> proposed change list
Write `<workspace>/out/update-<date>.md`: numbered findings with evidence (numbers), the proposed action, expected effect, risk, and which tool/script applies it. Group by type:
| Type | How |
|---|---|
| Wasted search terms -> negatives | `keywords_add_negative_keywords` / `shared_sets_add_list_negative_keywords` |
| New high-intent terms -> keywords | `import_csv.py` (CSV round-trip) |
| Keyword pause/bid | `keywords_update_keyword`, `keywords_remove_keywords` (second confirm) |
| Ads: new variants / replace weak RSA | `create_ads.py` (new ad PAUSED, enable on approval), pause old via `ads_update_ad_group_ad` |
| Budget / bidding | `budget` skill -> `campaigns_update_campaign_budget`, `campaigns_update_campaign` |
| Schedule / device / geo bid modifiers | `scheduling_*`, `ad_schedule.py list|remove|replace`, `targeting_*` |
| Dates, tracking, partner network | `campaign_settings.py` |
| Audiences | `audiences_*` (OBSERVATION first) |
| Assets | `assets_create_asset`, `asset_links_*`; images via `creatives` |
| Offline conversions to improve bidding | `conversion_upload.py clicks|calls` (CSV with gclid or hashed email/phone) |
| Audience lists refresh | `user_lists.py upload` (consent confirmation required) |

Prioritise by impact; flag anything that resets learning (big bid strategy/budget changes, many ad swaps at once) and suggest staging.

## 4. Approve and apply in batches
Human approves per batch (by number). Apply each approved batch via propose-confirm (dry run -> show -> yes -> commit). Never bundle unapproved items. After applying, read back and compare with the expectation.

## 5. Log and follow up
Append to the workspace `changelog.md`: date, campaign, what/why, expected effect, review date. Suggest when to re-check (typically 7-14 days, longer for smart bidding) and what metric decides success.
