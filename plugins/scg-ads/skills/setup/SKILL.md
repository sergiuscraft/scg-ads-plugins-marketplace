---
name: setup
description: Stage 1 of the scg-ads pipeline - account-level setup for a Google Ads customer (audit, conversions, budget baseline, shared assets, negatives list, links and audiences checklist). Produces account-brief.md.
argument-hint: "[optional free-text context or path to a brief]"
---

# Stage 1 - Account setup

Goal: a reviewed `account-brief.md` (template: `${CLAUDE_PLUGIN_ROOT}/templates/account-brief.md`) plus the account-level objects the campaigns will reuse. Follow `propose-confirm` for every write.

`$ARGUMENTS` is free context only (a brief, a path, a sentence). Read it, but **never require a syntax**; discover everything else and let the human pick.

## 0. Pick the account and its workspace (no secrets involved)
1. Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py list` - a table of saved accounts: label, customer id, **login id**, currency, time zone, name, default. If it reports no config, tell the human to run `configure.py init` in their own terminal (never ask them to paste keys or tokens here).
2. AskUserQuestion: the saved accounts (default first) plus "Other - any customer id (does not need to be in the config)". Several accounts are normal: always confirm which one this session works on.
3. Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py use <label-or-id> [--login <manager id>]` then `... configure.py workspace --customer <label-or-id>`; the last prints the **workspace folder** (`<root>/<label or id>/` with `account-brief.md`, `changelog.md`, `out/`, `campaigns/`, `creatives/`). For an account that is not saved, ask the human for its manager (login) id or "none/direct" and pass it with `--login`.
4. From now on: every file this skill writes (briefs, CSVs, reports, changelog) goes into that folder, by absolute path; say the folder path to the human once. Pass the table's **login id** as `login_customer_id` on every MCP tool call, and `--customer <label-or-id>` to scripts (they resolve labels and the login id themselves).

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
Fill the template with confirmed answers and the IDs of everything created. Show it, get approval, save it as `account-brief.md` in the account workspace. This file is the input to `/scg-ads:new-campaign` and `/scg-ads:update`.

## 5. Checklist for the human (always print at the end)
Billing set up; auto-tagging on; conversion tags firing (Tag Assistant); account links approved on the partner side; policy-sensitive categories declared; who gets notifications.
