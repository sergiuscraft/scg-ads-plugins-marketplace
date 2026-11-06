---
name: update
description: Stage 3 of the scg-ads pipeline - review and update an existing Google Ads campaign with a human (performance read, search terms, negatives, keywords, ads, budget/bidding, schedule, audiences), applying only approved batches.
argument-hint: "[optional: what you want to improve, e.g. 'wasted spend', 'more leads']"
---

# Stage 3 - Update a campaign

Load `propose-confirm`. `$ARGUMENTS` is free context. Discover, then let the human select.

## 1. Pick scope
`customers_list_accessible_customers` -> account pick-list -> GAQL campaign list (name, status, channel, budget, last-30d cost/clicks/conversions) -> campaign pick-list (multi-select ok). Ask the period (7/30/90 days, custom) and the goal for this round (waste, volume, CPA, new angles, structure, seasonality).

## 2. Read (all read-only)
- Campaign/ad group/keyword/ad performance, device, hour x day-of-week, geo, audience segments.
- `search_term_view` (search term, status, clicks, cost, conversions).
- Impression share & lost-IS (budget / rank), quality score components, ad strength, disapprovals/policy status, recommendations-like signals.
- For deeper diagnosis load the `google-ads-api-account-diagnostics` skill.
- Optionally refresh ideas: `keywords` skill (sources asked again - never reuse last time's choice).

## 3. Findings -> proposed change list
Write `out/update-<date>.md`: numbered findings with evidence (numbers), the proposed action, expected effect, risk, and which tool/script applies it. Group by type:
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

Prioritise by impact; flag anything that resets learning (big bid strategy/budget changes, many ad swaps at once) and suggest staging.

## 4. Approve and apply in batches
Human approves per batch (by number). Apply each approved batch via propose-confirm (dry run -> show -> yes -> commit). Never bundle unapproved items. After applying, read back and compare with the expectation.

## 5. Log and follow up
Append to `changelog.md`: date, campaign, what/why, expected effect, review date. Suggest when to re-check (typically 7-14 days, longer for smart bidding) and what metric decides success.
