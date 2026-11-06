---
name: new-campaign
description: Stage 2 of the scg-ads pipeline - build a new Google Ads Search campaign with a human: brief, keyword sources, budget, targeting, schedule, audiences, ads, creatives. Everything is created PAUSED and goes through propose-confirm.
argument-hint: "[optional free-text brief or path to account-brief.md / campaign-brief.md]"
---

# Stage 2 - New campaign

Load `propose-confirm` first. `$ARGUMENTS` is free context; **no required syntax**. Discover options from the account and let the human select (AskUserQuestion, with "Other" for custom input). End each step with a one-paragraph summary the human confirms.

## 0. Pick the account and its workspace (no secrets involved)
1. Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py list` - a table of saved accounts: label, customer id, **login id**, currency, time zone, name, default. If it reports no config, tell the human to run `configure.py init` in their own terminal (never ask them to paste keys or tokens here).
2. AskUserQuestion: the saved accounts (default first) plus "Other - any customer id (does not need to be in the config)". Several accounts are normal: always confirm which one this session works on.
3. Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py use <label-or-id> [--login <manager id>]` then `... configure.py workspace --customer <label-or-id>`; the last prints the **workspace folder** (`<root>/<label or id>/` with `account-brief.md`, `changelog.md`, `out/`, `campaigns/`, `creatives/`). For an account that is not saved, ask the human for its manager (login) id or "none/direct" and pass it with `--login`.
4. From now on: every file this skill writes (briefs, CSVs, reports, changelog) goes into that folder, by absolute path; say the folder path to the human once. Pass the table's **login id** as `login_customer_id` on every MCP tool call, and `--customer <label-or-id>` to scripts (they resolve labels and the login id themselves).

## 0b. Campaign type
AskUserQuestion: **Search** (default; continue below), **Performance Max**, **Display**, **Shopping**, **Demand Gen**, **Video**. For anything but Search use the spec flow in the last section of this skill (keywords/RSA steps do not apply; Shopping needs a linked Merchant Center feed, Video needs YouTube videos).

## 1. Context
- Read `account-brief.md` from the workspace; if it is still the empty template, suggest `/scg-ads:setup` (or continue with a minimal interview).
- Create the campaign folder `<workspace>/campaigns/<campaign-name>/` and `campaign-brief.md` in it from `${CLAUDE_PLUGIN_ROOT}/templates/campaign-brief.md`; keep this campaign's `keywords.csv` and `ads.csv` there instead of the account-level `out/`.

## 2. Brief (interview)
Goal (leads/sales/calls), offer and landing page(s) (WebFetch the page; extract value props, prices, proof, constraints), geo (use `targeting_suggest_geo_targets`, show matches, confirm), language, **schedule** (always ask: days, hours, time zone, phone coverage; propose windows), **audience** (who; compare with existing user lists from the audit; propose OBSERVATION by default), competitors to avoid/mention, brand/policy rules.

## 3. Keywords
Run the `keywords` skill. It asks for the sources every run and produces `<campaign folder>/keywords.csv` (ad groups, keywords, match types, negatives) that the human edits and approves.

## 4. Budget
Run the `budget` skill: prices -> forecast -> three scenarios -> select top -> chosen daily budget and bidding strategy.

## 5. Ad copy
For each ad group draft one RSA (3 variants for the human to pick/merge): 12-15 headlines (<= 30 chars), 4 descriptions (<= 90), paths (<= 15), mix of keyword themes, benefits, proof, offer, CTA; pin only when required (legal text). Use only facts from the brief/landing page. Save to `<campaign folder>/ads.csv` (template `${CLAUDE_PLUGIN_ROOT}/templates/ads.csv`). Lint offline: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/create_ads.py --csv <campaign folder>/ads.csv --lint-only`. Apply the policy check from the `budget` skill (step 6). Human edits the CSV and approves.

## 6. Creatives (optional)
If images/video are wanted, run `creatives`.

## 7. Build (all via propose-confirm; one proposal per bullet; everything PAUSED)
1. Campaign: `campaigns_create_campaign` (budget + bidding from step 4; Search only, display network off). Record the campaign id.
2. Locations/languages: `targeting_add_campaign_locations` (+ exclusions), `targeting_add_campaign_languages`.
3. Schedule: `scheduling_add_campaign_ad_schedule` (MCP) with the agreed windows and bid adjustments; device modifiers via `scheduling_set_campaign_device_bid_modifier` if agreed. To edit/remove windows later use `scripts/ad_schedule.py`.
4. Settings the MCP cannot do (start/end date, tracking template, URL suffix, partner network, EU political flag): `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/campaign_settings.py ...`.
5. Ad groups + keywords + negatives: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/import_csv.py --customer <id> --campaign <id> --csv <campaign folder>/keywords.csv` (dry run, approve, `--apply --checksum`). Shared negative list: `shared_sets_*` tools, then attach.
6. Ads: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/create_ads.py --customer <id> --campaign <id> --csv <campaign folder>/ads.csv` (not the MCP ad tools).
7. Assets: sitelinks/callouts/snippets via `assets_create_asset` + `asset_links_link_asset` at campaign level.
8. Audiences: `audiences_add_campaign_audience` in OBSERVATION mode with existing lists (custom segments are rejected on Search).
9. Conversion goals: confirm the campaign uses the primary conversion actions from setup.

## 8. Verify and hand over
Read everything back with `search_search` (campaign, budget, criteria, ad groups, ads, assets) and show a final checklist table: status, budget, bidding, geo, schedule, audiences, number of ad groups/keywords/negatives/ads, policy flags. Ask whether to **enable** (separate proposal via `campaigns_set_campaign_status`, then enable ad groups/ads). Append everything to the workspace `changelog.md`. Remind the human to review the Policy/approval status in the UI after 24h.

## Other campaign types (PMax, Display, Shopping, Demand Gen, Video)
1. Copy `${CLAUDE_PLUGIN_ROOT}/templates/specs/<type>.toml` into the campaign folder and fill it **with the human**: goal and bidding (`budget` skill for budget/targets), geo ids (`targeting_suggest_geo_targets`), languages, EU political flag (ask, never assume), landing page, and the creative: headlines / long headlines / descriptions drafted from the landing page and brand rules (`budget` skill step 6 policy check), business name (<= 25 chars), images (use `creatives`: landscape 1.91:1, square 1:1, logo 1:1, optional portrait 4:5), YouTube videos as `youtube:<ID>`. For Shopping: Merchant Center id and feed label; check the link with `account_links.py list` first.
2. Offline checks, no credentials: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/campaign_create_other.py <type> --spec <file> --lint-only`. Fix every problem it lists (text limits, image ratios and sizes, missing fields).
3. Dry run: same command without `--lint-only` and with `--customer <label-or-id>`; show the human the change items (budget, campaign, targeting, assets, ad group/asset group, ad) and the API result. If the API rejects it, show the error verbatim, fix the spec, repeat. This script has not been run live yet: say so on the first use.
4. Apply with `--apply --checksum <hash>` only after an explicit yes. Everything is created PAUSED in one atomic request.
5. Afterwards: audiences / topics / placements / PMax audience signals (`audiences_*` tools or the UI), conversion goal check, sitelinks etc. via `assets_create_asset` + `asset_links_link_asset`, schedule via `scheduling_*` / `ad_schedule.py`, dates/tracking via `campaign_settings.py`. Read back with `search_search`, then ask about enabling (separate proposal).
