---
name: setup
description: Stage 1 of the scg-ads pipeline - account-level setup for a Google Ads customer (audit, conversions, budget baseline, shared assets, negatives list, links and audiences checklist). Produces account-brief.md.
argument-hint: "[optional free-text context or path to a brief]"
---

# Stage 1 - Account setup

Goal: a reviewed `account-brief.md` (template: `${CLAUDE_PLUGIN_ROOT}/templates/account-brief.md`) plus the account-level objects the campaigns will reuse. Follow `propose-confirm` for every write.

`$ARGUMENTS` is free context only (a brief, a path, a sentence). Read it, but **never require a syntax**; discover everything else and let the human pick.

## 0. Pick the account (discover, then ask)
1. `customers_list_accessible_customers`, then `search_search` on `customer` (`customer.descriptive_name`, `customer.id`, `customer.currency_code`, `customer.time_zone`, `customer.manager`) for each id.
2. AskUserQuestion pick-list of accounts. Skip manager accounts unless asked. Confirm currency and time zone back to the human - they drive budgets and schedules.

## 1. Audit what already exists (read-only, `search_search`)
Campaigns (status, budget), conversion actions (status, primary, category), shared negative lists, assets by type, user lists (type, size, status), labels, linked accounts visible via resources, last 30d spend. Summarise in 10 lines; flag problems (no primary conversion, tag inactive, duplicate actions, budgets limited, empty lists).

## 2. Interview the human (AskUserQuestion, one topic at a time, offer discovered options + "Other")
- Business: offer, who buys, geo, languages, landing pages (ask for URLs; if a URL is given, WebFetch it and propose the value propositions it supports).
- Prices, margin/LTV, target CPA/ROAS -> hand to the `budget` skill for numbers and scenarios.
- **Schedule**: working days/hours, time zone, phone availability, lead-handling hours.
- **Audience**: who we want and who we don't; existing lists/contacts; any first-party data. Verify against the audit: which lists exist, are they big enough (Search lists need >= 1,000 active users), is Customer Match allowed for the vertical. Recommend OBSERVATION vs TARGETING.
- Conversion goals: what counts (calls, forms, purchases), values, counting, lookback.
- Brand rules: tone, banned claims, legal/policy constraints (regulated categories, pricing/refund claims).

## 3. Build account-level objects (each via propose-confirm)
| Need | Tool |
|---|---|
| Conversion actions | `conversions_create_conversion_action`, `conversions_update_conversion_action` (imported GA4 goals cannot be mutated by API) |
| Shared budget (if used) | `budgets_create_campaign_budget` |
| Sitelinks, callouts, snippets, call, images | `assets_create_asset` then `asset_links_link_asset` (customer level) |
| Geo ids | `targeting_suggest_geo_targets` (confirm matches with the human before use) |
| Labels | `labels_manage_labels` |
| Negative list skeleton | `shared_sets_create_negative_keyword_list` (see `keywords` skill for content) |

Not covered by MCP - use the scripts (same dry run -> approve -> `--apply --checksum` contract):
- **User lists / Customer Match**: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/user_lists.py list|create|upload`. Before `upload`, ask the human in chat to confirm the contacts gave consent that meets Google's Customer Match policy; only then pass `--consent-confirmed`. Contacts CSV: `email`, `phone`. PII is hashed locally; never print or paste contact data into the chat.
- **Offline conversions / enhanced conversions**: `scripts/conversion_upload.py clicks|calls` (the conversion action must be UPLOAD_CLICKS / UPLOAD_CALLS, created with `conversions_create_conversion_action`).
- **Account links**: `scripts/account_links.py list` to see status; `invite-merchant --merchant-id` sends a Merchant Center invitation (the Merchant Center admin must approve it); GA4 links can only be created on the GA4 side - run `account_links.py ga4-howto` and give the human the steps. Re-run `list` afterwards to confirm the link is active.

## 4. Write `account-brief.md`
Fill the template with confirmed answers and the IDs of everything created. Show it, get approval, save in the working directory. This file is the input to `/scg-ads:new-campaign` and `/scg-ads:update`.

## 5. Checklist for the human (always print at the end)
Billing set up; auto-tagging on; conversion tags firing (Tag Assistant); account links approved on the partner side; policy-sensitive categories declared; who gets notifications.
