---
name: new-campaign
description: Stage 2 of the scg-ads pipeline - build a new Google Ads Search campaign with a human: brief, keyword sources, budget, targeting, schedule, audiences, ads, creatives. Everything is created PAUSED and goes through propose-confirm.
argument-hint: "[optional free-text brief or path to account-brief.md / campaign-brief.md]"
---

# Stage 2 - New campaign

Load `propose-confirm` first. `$ARGUMENTS` is free context; **no required syntax**. Discover options from the account and let the human select (AskUserQuestion, with "Other" for custom input). End each step with a one-paragraph summary the human confirms.

## 1. Context
- If `account-brief.md` exists in the working directory, read it; otherwise suggest `/scg-ads:setup` (or continue with a minimal interview).
- Pick the account: `customers_list_accessible_customers` + `search_search` on `customer` -> pick-list.
- Create `campaign-brief.md` from `${CLAUDE_PLUGIN_ROOT}/templates/campaign-brief.md` and fill it as you go.

## 2. Brief (interview)
Goal (leads/sales/calls), offer and landing page(s) (WebFetch the page; extract value props, prices, proof, constraints), geo (use `targeting_suggest_geo_targets`, show matches, confirm), language, **schedule** (always ask: days, hours, time zone, phone coverage; propose windows), **audience** (who; compare with existing user lists from the audit; propose OBSERVATION by default), competitors to avoid/mention, brand/policy rules.

## 3. Keywords
Run the `keywords` skill. It asks for the sources every run and produces `out/keywords.csv` (ad groups, keywords, match types, negatives) that the human edits and approves.

## 4. Budget
Run the `budget` skill: prices -> forecast -> three scenarios -> select top -> chosen daily budget and bidding strategy.

## 5. Ad copy
For each ad group draft one RSA (3 variants for the human to pick/merge): 12-15 headlines (<= 30 chars), 4 descriptions (<= 90), paths (<= 15), mix of keyword themes, benefits, proof, offer, CTA; pin only when required (legal text). Use only facts from the brief/landing page. Save to `out/ads.csv` (template `${CLAUDE_PLUGIN_ROOT}/templates/ads.csv`). Lint offline: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/create_ads.py --csv out/ads.csv --lint-only`. Apply the policy check from the `budget` skill (step 6). Human edits the CSV and approves.

## 6. Creatives (optional)
If images/video are wanted, run `creatives`.

## 7. Build (all via propose-confirm; one proposal per bullet; everything PAUSED)
1. Campaign: `campaigns_create_campaign` (budget + bidding from step 4; Search only, display network off). Record the campaign id.
2. Locations/languages: `targeting_add_campaign_locations` (+ exclusions), `targeting_add_campaign_languages`.
3. Schedule: `scheduling_add_campaign_ad_schedule` (MCP) with the agreed windows and bid adjustments; device modifiers via `scheduling_set_campaign_device_bid_modifier` if agreed. To edit/remove windows later use `scripts/ad_schedule.py`.
4. Settings the MCP cannot do (start/end date, tracking template, URL suffix, partner network, EU political flag): `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/campaign_settings.py ...`.
5. Ad groups + keywords + negatives: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/import_csv.py --customer <id> --campaign <id> --csv out/keywords.csv` (dry run, approve, `--apply --checksum`). Shared negative list: `shared_sets_*` tools, then attach.
6. Ads: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/create_ads.py --customer <id> --campaign <id> --csv out/ads.csv` (not the MCP ad tools).
7. Assets: sitelinks/callouts/snippets via `assets_create_asset` + `asset_links_link_asset` at campaign level.
8. Audiences: `audiences_add_campaign_audience` in OBSERVATION mode with existing lists (custom segments are rejected on Search).
9. Conversion goals: confirm the campaign uses the primary conversion actions from setup.

## 8. Verify and hand over
Read everything back with `search_search` (campaign, budget, criteria, ad groups, ads, assets) and show a final checklist table: status, budget, bidding, geo, schedule, audiences, number of ad groups/keywords/negatives/ads, policy flags. Ask whether to **enable** (separate proposal via `campaigns_set_campaign_status`, then enable ad groups/ads). Append everything to `changelog.md`. Remind the human to review the Policy/approval status in the UI after 24h.
