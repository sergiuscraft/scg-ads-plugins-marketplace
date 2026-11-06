# Stage -> tool map

MCP = google-ads server (fork). SCRIPT = `${CLAUDE_PLUGIN_ROOT}/scripts/`. Status: ready / planned (P2/P3).

| Need | How | Status |
|---|---|---|
| List accounts, any read/report | MCP `customers_list_accessible_customers`, `search_search`, `metadata_get_resource_metadata` | ready |
| Keyword ideas + volumes | SCRIPT `keyword_ideas.py` (needs Basic access) or CSV / search terms | ready (live-gated) |
| Bulk ad groups / keywords / negatives from CSV | SCRIPT `import_csv.py` | ready |
| Shared negative lists | MCP `shared_sets_*` | ready |
| Create campaign (Search) | MCP `campaigns_create_campaign` | ready |
| Campaign update: name, bidding, partners | MCP `campaigns_update_campaign`, `campaigns_set_campaign_status` | ready |
| Campaign dates, networks, tracking, URL suffix, EU flag | SCRIPT `campaign_settings.py` | ready |
| Budgets | MCP `budgets_*`, `campaigns_update_campaign_budget` | ready |
| Locations / languages | MCP `targeting_*` | ready |
| Ad schedule add | MCP `scheduling_add_campaign_ad_schedule` | ready |
| Ad schedule list / edit / remove | SCRIPT `ad_schedule.py` | ready |
| Device / criterion bid modifiers | MCP `scheduling_set_*` | ready |
| Create RSAs | SCRIPT `create_ads.py` (by design, not MCP ad tools) | ready |
| Pause/enable/remove ads | MCP `ads_update_ad_group_ad`, `ads_remove_ad_group_ad` | ready |
| Assets: sitelinks, callouts, snippets, images, video | MCP `assets_*`, `asset_links_*` | ready |
| Audiences: attach existing lists | MCP `audiences_*` | ready |
| Conversion actions | MCP `conversions_*` | ready |
| Conversion uploads (offline click / call, enhanced via hashed email/phone) | SCRIPT `conversion_upload.py` | ready |
| Account links: list, Merchant Center invite (human approves in Merchant Center); GA4 link is created on the GA4 side (`ga4-howto`) | SCRIPT `account_links.py` | ready |
| User lists: list, create, Customer Match upload (local hashing, explicit consent flag) | SCRIPT `user_lists.py` | ready |
| Display / PMax / Demand Gen / Shopping / Video | SCRIPT `campaign_create_other.py` | planned P3 |
| Images / video creation | other MCPs (Higgsfield, Figma...) via `creatives` skill | ready (depends on connected MCPs) |
