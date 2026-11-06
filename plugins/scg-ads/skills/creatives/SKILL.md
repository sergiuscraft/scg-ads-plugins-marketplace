---
name: creatives
description: Create and attach image/video assets for Google Ads campaigns using whichever creative MCPs are connected (Higgsfield, Figma, Canva...), then upload via assets_create_asset and link with asset_links_link_asset.
argument-hint: "[optional: what the creative should show]"
---

# Creatives

1. **Detect** which creative tools exist in this session (names containing e.g. `generate_image`, `generate_video`, Figma `get_design_context`/`use_figma`/`get_screenshot`, Canva). Tell the human what is available. If none: ask for files, do not fabricate.
2. **Brief** from `campaign-brief.md` / `account-brief.md`: offer, audience, tone, brand style, banned claims, required text. Ask what asset slots are needed (marketing image 1.91:1, square 1:1, portrait 4:5, logo 1:1 and 4:1, sitelink/promotion visuals, YouTube video). Use real product facts only; no fake reviews, certifications, prices or before/after claims.
3. **Generate** 2-4 candidates per slot with the chosen tool(s); show them; the human picks or asks for changes. Save finals under `<workspace>/creatives/` with the slot in the filename.
4. **Check** dimensions, aspect ratio, file size (<= 5 MB images; the MCP asset tool caps at 20 MB), no text-heavy images, no policy-risky content. Fix or regenerate.
5. **Upload** with `assets_create_asset` (`asset_type=IMAGE`, `image_asset_path` in stdio mode or base64), then **link** with `asset_links_link_asset` (`MARKETING_IMAGE`, `SQUARE_MARKETING_IMAGE`, `LOGO`, ... at CAMPAIGN or CUSTOMER level). Both via `propose-confirm`.
6. Videos: generate/export, upload with `assets_upload_video_asset` (YouTube, stdio only), link as `YOUTUBE_VIDEO`. Warn that it is a public/unlisted YouTube upload and get explicit approval first.
7. Record asset IDs in the brief.

Search campaigns use mostly text; images attach as asset extensions and matter more for Demand Gen / PMax / Display (P3).
