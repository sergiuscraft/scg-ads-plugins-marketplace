#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Create non-Search campaigns from a TOML spec: pmax | display | shopping | demand-gen | video.

  campaign_create_other.py pmax        --spec my-pmax.toml --customer ID            # dry run
  campaign_create_other.py pmax        --spec my-pmax.toml --lint-only              # offline checks, no credentials
  campaign_create_other.py display     --spec ...  [--apply --checksum H]
  campaign_create_other.py shopping|demand-gen|video  --spec ...

Templates: templates/specs/<type>.toml. Everything (budget, campaign, assets, asset group / ad group,
ads, location + language criteria) is ONE atomic GoogleAdsService.mutate, created PAUSED. Image files in
the spec are uploaded in the same request; `asset:<id>` reuses an existing asset; `youtube:<VIDEO_ID>`
creates a YouTube video asset. Limits and image ratios are linted locally first; the API dry run
(validate_only) is the final judge. Targeting beyond location/language (audiences, topics, placements,
asset-group signals) is added afterwards with the audiences_* MCP tools or in the UI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import imagesize  # noqa: E402

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

TYPES = ("pmax", "display", "shopping", "demand-gen", "video")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
BIDDING = {"MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE", "MAXIMIZE_CLICKS", "TARGET_CPA", "TARGET_ROAS", "MANUAL_CPC"}
ALLOWED_BIDDING = {
    "pmax": {"MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE"},
    "display": {"MAXIMIZE_CONVERSIONS", "MAXIMIZE_CLICKS", "TARGET_CPA", "MANUAL_CPC"},
    "shopping": {"MANUAL_CPC", "MAXIMIZE_CLICKS", "TARGET_ROAS"},
    "demand-gen": {"MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE", "MAXIMIZE_CLICKS", "TARGET_CPA", "TARGET_ROAS"},
    "video": {"MAXIMIZE_CONVERSIONS", "TARGET_CPA"},
}
# (field, min, max, per-item max chars). Limits as documented at the time of writing; the API is authoritative.
TEXT_RULES = {
    "pmax": {"headlines": (3, 15, 30), "long_headlines": (1, 5, 90), "descriptions": (2, 5, 90)},
    "display": {"headlines": (1, 5, 30), "long_headlines": (1, 1, 90), "descriptions": (1, 5, 90)},
    "demand-gen": {"headlines": (1, 5, 40), "descriptions": (1, 5, 90)},
    "video": {"headlines": (1, 5, 30), "long_headlines": (1, 5, 90), "descriptions": (1, 5, 90)},
}
IMAGE_RULES = {   # field -> (aspect ratio, min w, min h)
    "marketing_images": (1.91, 600, 314),
    "square_marketing_images": (1.0, 300, 300),
    "portrait_marketing_images": (0.8, 480, 600),
    "logo_images": (1.0, 128, 128),
    "landscape_logo_images": (4.0, 512, 128),
}
REQUIRED_IMAGES = {
    "pmax": ["marketing_images", "square_marketing_images", "logo_images"],
    "display": ["marketing_images", "square_marketing_images"],
    "demand-gen": ["marketing_images", "square_marketing_images"],
    "video": [],
}


# ------------------------------------------------------------------ lint
def load_spec(path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _asset_ref_kind(ref: str) -> str:
    return "asset" if ref.startswith("asset:") else "youtube" if ref.startswith("youtube:") else "file"


def lint(kind: str, spec: dict, base: Path | None = None) -> list[str]:
    errs: list[str] = []
    camp, cr = spec.get("campaign", {}), spec.get("creative", {})
    if not camp.get("name"):
        errs.append("campaign.name is required")
    try:
        if float(camp.get("daily_budget", 0)) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        errs.append("campaign.daily_budget must be a positive number (account currency)")
    strat = str(camp.get("bidding", "")).upper()
    if strat not in ALLOWED_BIDDING[kind]:
        errs.append(f"campaign.bidding must be one of {sorted(ALLOWED_BIDDING[kind])} for {kind}")
    if strat in ("TARGET_CPA",) and not camp.get("target_cpa"):
        errs.append("target_cpa required for TARGET_CPA")
    if strat in ("TARGET_ROAS",) and not camp.get("target_roas"):
        errs.append("target_roas required for TARGET_ROAS")
    if "eu_political_ads" not in camp:
        errs.append("campaign.eu_political_ads must be set explicitly (true/false)")
    if not camp.get("locations"):
        errs.append("campaign.locations needs at least one geo target id (targeting_suggest_geo_targets)")

    if kind == "shopping":
        sh = spec.get("shopping", {})
        if not str(sh.get("merchant_id", "")).strip().isdigit():
            errs.append("shopping.merchant_id (Merchant Center id, digits) is required")
        if not sh.get("feed_label"):
            errs.append("shopping.feed_label is required (usually the 2-letter country, e.g. UA)")
        if sh.get("priority", 0) not in (0, 1, 2):
            errs.append("shopping.priority must be 0, 1 or 2")
        if not spec.get("ad_group", {}).get("name"):
            errs.append("ad_group.name is required")
        return errs

    if kind != "pmax" and not spec.get("ad_group", {}).get("name"):
        errs.append("ad_group.name is required")
    if kind == "pmax" and not spec.get("asset_group", {}).get("name"):
        errs.append("asset_group.name is required")
    if not str(cr.get("final_url", "")).startswith(("http://", "https://")):
        errs.append("creative.final_url must start with http(s)://")
    if not cr.get("business_name"):
        errs.append("creative.business_name is required")
    elif len(cr["business_name"]) > 25:
        errs.append("creative.business_name max 25 characters")

    for field, (lo, hi, mx) in TEXT_RULES[kind].items():
        vals = [v.strip() for v in cr.get(field, []) if str(v).strip()]
        if not lo <= len(vals) <= hi:
            errs.append(f"creative.{field}: need {lo}..{hi}, got {len(vals)}")
        errs += [f"creative.{field}: too long ({len(v)}>{mx}): {v}" for v in vals if len(v) > mx]
        if len({v.lower() for v in vals}) != len(vals):
            errs.append(f"creative.{field}: duplicates")
    if kind == "pmax":
        short = [d for d in cr.get("descriptions", []) if len(d) <= 60]
        if cr.get("descriptions") and not short:
            errs.append("creative.descriptions: at least one must be <= 60 characters")

    for field in REQUIRED_IMAGES[kind]:
        if not cr.get(field):
            errs.append(f"creative.{field}: at least one image required")
    for field, (ratio, mw, mh) in IMAGE_RULES.items():
        for ref in cr.get(field, []):
            if _asset_ref_kind(ref) != "file":
                if _asset_ref_kind(ref) == "youtube":
                    errs.append(f"creative.{field}: youtube: refs are only valid in creative.videos")
                continue
            p = Path(ref).expanduser()
            p = p if p.is_absolute() or base is None else base / p
            if not p.is_file():
                errs.append(f"creative.{field}: file not found: {ref}")
                continue
            data = p.read_bytes()
            if len(data) > MAX_IMAGE_BYTES:
                errs.append(f"creative.{field}: {ref} is over 5 MB")
            dim = imagesize.dimensions(data)
            if not dim:
                errs.append(f"creative.{field}: {ref} is not a readable PNG/JPEG/GIF")
            elif not imagesize.ratio_ok(dim[0], dim[1], ratio) or dim[0] < mw or dim[1] < mh:
                errs.append(f"creative.{field}: {ref} is {dim[0]}x{dim[1]}; need ratio {ratio}:1, min {mw}x{mh}")
    if kind == "video" and not cr.get("videos"):
        errs.append("creative.videos: at least one `youtube:<VIDEO_ID>` or `asset:<id>`")
    for v in cr.get("videos", []):
        if _asset_ref_kind(v) == "file":
            errs.append(f"creative.videos: {v!r} must be youtube:<VIDEO_ID> or asset:<id> (upload videos with assets_upload_video_asset first)")
    return errs


# ------------------------------------------------------------------ builder
class Builder:
    def __init__(self, client, customer_id: str, base: Path | None = None):
        self.c, self.cid, self.base = client, customer_id, base
        self.ops, self.items = [], []
        self._n = 0
        self._cache: dict[str, str] = {}

    def tmp(self) -> int:
        self._n -= 1
        return self._n

    def op(self):
        o = self.c.get_type("MutateOperation")
        self.ops.append(o)
        return o

    # --- generic pieces
    def budget(self, camp: dict) -> str:
        rn = self.c.get_service("CampaignBudgetService").campaign_budget_path(self.cid, self.tmp())
        b = self.op().campaign_budget_operation.create
        b.resource_name = rn
        b.name = f"{camp['name']} - budget"
        b.amount_micros = int(round(float(camp["daily_budget"]) * 1_000_000))
        b.delivery_method = self.c.enums.BudgetDeliveryMethodEnum.STANDARD
        b.explicitly_shared = False
        self.items.append({"operation": "CREATE", "entity": "CampaignBudget", "name": b.name,
                           "daily_amount": float(camp["daily_budget"])})
        return rn

    def bidding(self, camp_msg, camp: dict) -> None:
        s = str(camp["bidding"]).upper()
        c = self.c
        if s == "MAXIMIZE_CONVERSIONS":
            c.copy_from(camp_msg.maximize_conversions, c.get_type("MaximizeConversions"))
            if camp.get("target_cpa"):
                camp_msg.maximize_conversions.target_cpa_micros = int(round(float(camp["target_cpa"]) * 1e6))
        elif s == "MAXIMIZE_CONVERSION_VALUE":
            c.copy_from(camp_msg.maximize_conversion_value, c.get_type("MaximizeConversionValue"))
            if camp.get("target_roas"):
                camp_msg.maximize_conversion_value.target_roas = float(camp["target_roas"])
        elif s == "MAXIMIZE_CLICKS":
            c.copy_from(camp_msg.target_spend, c.get_type("TargetSpend"))
            if camp.get("max_cpc"):
                camp_msg.target_spend.cpc_bid_ceiling_micros = int(round(float(camp["max_cpc"]) * 1e6))
        elif s == "TARGET_CPA":
            camp_msg.target_cpa.target_cpa_micros = int(round(float(camp["target_cpa"]) * 1e6))
        elif s == "TARGET_ROAS":
            camp_msg.target_roas.target_roas = float(camp["target_roas"])
        elif s == "MANUAL_CPC":
            camp_msg.manual_cpc.enhanced_cpc_enabled = False

    def campaign(self, kind: str, camp: dict, budget_rn: str, shopping: dict | None = None) -> str:
        c = self.c
        rn = c.get_service("CampaignService").campaign_path(self.cid, self.tmp())
        m = self.op().campaign_operation.create
        m.resource_name = rn
        m.name = camp["name"]
        m.status = c.enums.CampaignStatusEnum.PAUSED
        m.campaign_budget = budget_rn
        m.contains_eu_political_advertising = (
            c.enums.EuPoliticalAdvertisingStatusEnum.CONTAINS_EU_POLITICAL_ADVERTISING if camp["eu_political_ads"]
            else c.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
        ch = c.enums.AdvertisingChannelTypeEnum
        m.advertising_channel_type = {"pmax": ch.PERFORMANCE_MAX, "display": ch.DISPLAY, "shopping": ch.SHOPPING,
                                      "demand-gen": ch.DEMAND_GEN, "video": ch.VIDEO}[kind]
        if kind == "video":
            m.advertising_channel_sub_type = c.enums.AdvertisingChannelSubTypeEnum.VIDEO_ACTION
        if kind == "display":
            m.network_settings.target_content_network = True
        if kind == "shopping":
            m.network_settings.target_google_search = True
            m.network_settings.target_search_network = False
            m.network_settings.target_content_network = False
        if kind == "shopping":
            m.shopping_setting.merchant_id = int(shopping["merchant_id"])
            m.shopping_setting.feed_label = shopping["feed_label"]
            m.shopping_setting.campaign_priority = int(shopping.get("priority", 0))
        if camp.get("final_url_suffix"):
            m.final_url_suffix = camp["final_url_suffix"]
        self.bidding(m, camp)
        self.items.append({"operation": "CREATE", "entity": f"Campaign ({kind})", "name": camp["name"],
                           "status": "PAUSED", "bidding": camp["bidding"]})
        return rn

    def criteria(self, camp_rn: str, camp: dict) -> None:
        c = self.c
        geo = c.get_service("GeoTargetConstantService")
        for gid, neg in [(g, False) for g in camp.get("locations", [])] + [(g, True) for g in camp.get("exclude_locations", [])]:
            cc = self.op().campaign_criterion_operation.create
            cc.campaign = camp_rn
            cc.location.geo_target_constant = geo.geo_target_constant_path(gid)
            cc.negative = neg
            self.items.append({"operation": "CREATE", "entity": "Location" + (" (excluded)" if neg else ""), "geo_target_id": gid})
        for lid in camp.get("languages", []):
            cc = self.op().campaign_criterion_operation.create
            cc.campaign = camp_rn
            cc.language.language_constant = c.get_service("GoogleAdsService").language_constant_path(lid)
            self.items.append({"operation": "CREATE", "entity": "Language", "language_id": lid})

    # --- assets
    def text_asset(self, text: str) -> str:
        key = f"t:{text}"
        if key not in self._cache:
            rn = self.c.get_service("AssetService").asset_path(self.cid, self.tmp())
            a = self.op().asset_operation.create
            a.resource_name = rn
            a.text_asset.text = text
            self._cache[key] = rn
        return self._cache[key]

    def media_asset(self, ref: str, label: str) -> str:
        if ref in self._cache:
            return self._cache[ref]
        svc = self.c.get_service("AssetService")
        k = _asset_ref_kind(ref)
        if k == "asset":
            rn = svc.asset_path(self.cid, ref.split(":", 1)[1])
        else:
            rn = svc.asset_path(self.cid, self.tmp())
            a = self.op().asset_operation.create
            a.resource_name = rn
            if k == "youtube":
                a.youtube_video_asset.youtube_video_id = ref.split(":", 1)[1]
                a.name = f"{label} youtube {ref.split(':', 1)[1]}"
            else:
                p = Path(ref).expanduser()
                p = p if p.is_absolute() or self.base is None else self.base / p
                a.image_asset.data = p.read_bytes()
                a.name = f"{label} {p.name}"
                self.items.append({"operation": "UPLOAD", "entity": "ImageAsset", "file": p.name})
        self._cache[ref] = rn
        return rn

    def ad_text(self, text: str):
        t = self.c.get_type("AdTextAsset")
        t.text = text
        return t

    def ad_image(self, ref: str, label: str):
        i = self.c.get_type("AdImageAsset")
        i.asset = self.media_asset(ref, label)
        return i

    def ad_video(self, ref: str):
        v = self.c.get_type("AdVideoAsset")
        v.asset = self.media_asset(ref, "video")
        return v


def build(client, kind: str, spec: dict, customer_id: str, base: Path | None = None):
    b = Builder(client, customer_id, base)
    camp, cr = spec["campaign"], spec.get("creative", {})
    c = client
    camp_rn = b.campaign(kind, camp, b.budget(camp), spec.get("shopping"))
    b.criteria(camp_rn, camp)

    if kind == "pmax":
        ag = spec["asset_group"]
        ag_rn = c.get_service("AssetGroupService").asset_group_path(customer_id, b.tmp())
        m = b.op().asset_group_operation.create
        m.resource_name, m.campaign, m.name = ag_rn, camp_rn, ag["name"]
        m.final_urls.append(cr["final_url"])
        m.status = c.enums.AssetGroupStatusEnum.PAUSED
        for k in ("path1", "path2"):
            if cr.get(k):
                setattr(m, k, cr[k])
        b.items.append({"operation": "CREATE", "entity": "AssetGroup", "name": ag["name"], "status": "PAUSED"})
        F = c.enums.AssetFieldTypeEnum
        links = ([(t, F.HEADLINE) for t in cr["headlines"]] + [(t, F.LONG_HEADLINE) for t in cr["long_headlines"]]
                 + [(t, F.DESCRIPTION) for t in cr["descriptions"]] + [(cr["business_name"], F.BUSINESS_NAME)])
        link_ops = [(b.text_asset(t), ft) for t, ft in links]
        media = [("marketing_images", F.MARKETING_IMAGE), ("square_marketing_images", F.SQUARE_MARKETING_IMAGE),
                 ("portrait_marketing_images", F.PORTRAIT_MARKETING_IMAGE), ("logo_images", F.LOGO),
                 ("landscape_logo_images", F.LANDSCAPE_LOGO), ("videos", F.YOUTUBE_VIDEO)]
        for field, ft in media:
            link_ops += [(b.media_asset(r, field), ft) for r in cr.get(field, [])]
        for rn, ft in link_ops:
            l = b.op().asset_group_asset_operation.create
            l.asset_group, l.asset, l.field_type = ag_rn, rn, ft
        b.items.append({"operation": "LINK", "entity": "AssetGroupAsset", "count": len(link_ops),
                        "summary": {f: len(cr.get(f, [])) for f in ("headlines", "long_headlines", "descriptions", "marketing_images",
                                                                    "square_marketing_images", "logo_images", "videos")}})
        return b.ops, b.items

    # ad-group based types
    agc = spec["ad_group"]
    ag_rn = c.get_service("AdGroupService").ad_group_path(customer_id, b.tmp())
    g = b.op().ad_group_operation.create
    g.resource_name, g.campaign, g.name = ag_rn, camp_rn, agc["name"]
    g.status = c.enums.AdGroupStatusEnum.PAUSED
    T = c.enums.AdGroupTypeEnum
    if kind == "display":
        g.type_ = T.DISPLAY_STANDARD
    elif kind == "shopping":
        g.type_ = T.SHOPPING_PRODUCT_ADS
    elif kind == "video":
        g.type_ = T.VIDEO_RESPONSIVE
    if agc.get("cpc_bid") and kind in ("display", "shopping"):
        g.cpc_bid_micros = int(round(float(agc["cpc_bid"]) * 1e6))
    b.items.append({"operation": "CREATE", "entity": f"AdGroup ({kind})", "name": agc["name"], "status": "PAUSED"})

    if kind == "shopping":
        sh = spec["shopping"]
        ad = b.op().ad_group_ad_operation.create
        ad.ad_group, ad.status = ag_rn, c.enums.AdGroupAdStatusEnum.PAUSED
        c.copy_from(ad.ad.shopping_product_ad, c.get_type("ShoppingProductAdInfo"))
        crit = b.op().ad_group_criterion_operation.create
        crit.ad_group = ag_rn
        crit.status = c.enums.AdGroupCriterionStatusEnum.ENABLED
        crit.listing_group.type_ = c.enums.ListingGroupTypeEnum.UNIT
        if agc.get("cpc_bid"):
            crit.cpc_bid_micros = int(round(float(agc["cpc_bid"]) * 1e6))
        b.items.append({"operation": "CREATE", "entity": "ShoppingProductAd + all-products listing group", "status": "PAUSED",
                        "merchant_id": sh["merchant_id"], "feed_label": sh["feed_label"]})
        return b.ops, b.items

    # Create every asset BEFORE the ad op: temp asset ids must exist earlier in the same mutate.
    texts = lambda f: [b.ad_text(t) for t in cr.get(f, [])]                                   # noqa: E731
    imgs = {f: [b.ad_image(r, f) for r in cr.get(f, [])]
            for f in ("marketing_images", "square_marketing_images", "portrait_marketing_images", "logo_images")}
    vids = [b.ad_video(v) for v in cr.get("videos", [])]
    ad = b.op().ad_group_ad_operation.create
    ad.ad_group, ad.status = ag_rn, c.enums.AdGroupAdStatusEnum.PAUSED
    ad.ad.final_urls.append(cr["final_url"])
    if kind == "display":
        r = ad.ad.responsive_display_ad
        r.headlines.extend(texts("headlines"))
        r.long_headline = b.ad_text(cr["long_headlines"][0])
        r.descriptions.extend(texts("descriptions"))
        r.business_name = cr["business_name"]
        r.marketing_images.extend(imgs["marketing_images"])
        r.square_marketing_images.extend(imgs["square_marketing_images"])
        r.logo_images.extend(imgs["logo_images"])
        if cr.get("call_to_action"):
            r.call_to_action_text = cr["call_to_action"]
    elif kind == "demand-gen":
        r = ad.ad.demand_gen_multi_asset_ad
        r.headlines.extend(texts("headlines"))
        r.descriptions.extend(texts("descriptions"))
        r.business_name = cr["business_name"]
        r.marketing_images.extend(imgs["marketing_images"])
        r.square_marketing_images.extend(imgs["square_marketing_images"])
        r.portrait_marketing_images.extend(imgs["portrait_marketing_images"])
        r.logo_images.extend(imgs["logo_images"])
        if cr.get("call_to_action"):
            r.call_to_action_text = cr["call_to_action"]
    elif kind == "video":
        r = ad.ad.video_responsive_ad
        r.headlines.extend(texts("headlines"))
        r.long_headlines.extend(texts("long_headlines"))
        r.descriptions.extend(texts("descriptions"))
        r.videos.extend(vids)
        r.business_name = b.ad_text(cr["business_name"])
        r.logo_images.extend(imgs["logo_images"])
        if cr.get("call_to_action"):
            r.call_to_actions.append(b.ad_text(cr["call_to_action"]))
    b.items.append({"operation": "CREATE", "entity": f"Ad ({kind})", "status": "PAUSED", "final_url": cr["final_url"],
                    "summary": {f: len(cr.get(f, [])) for f in ("headlines", "long_headlines", "descriptions", "marketing_images",
                                                                "square_marketing_images", "logo_images", "videos")}})
    return b.ops, b.items


def main(argv=None, client=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=TYPES)
    p.add_argument("--spec", required=True)
    p.add_argument("--lint-only", action="store_true")
    p.add_argument("--customer")
    p.add_argument("--login-customer")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--checksum")
    args = p.parse_args(argv)

    spec_path = Path(args.spec).expanduser()
    spec = load_spec(spec_path)
    errs = lint(args.kind, spec, spec_path.parent)
    if errs:
        print("Spec problems:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    if args.lint_only:
        print(f"OK: {args.kind} spec passes local checks (the API dry run is the final check).")
        return 0

    from _lib.client import clean_id, get_client
    from _lib.mutate import execute
    from _lib.safety import _customer_arg
    if not args.customer:
        from _lib import config
        args.customer = config.resolve_customer(None)
    if not args.customer:
        print("--customer is required (label or 10-digit id)", file=sys.stderr)
        return 2
    args.customer = _customer_arg(args.customer)
    client = client or get_client(args.login_customer)
    ops, items = build(client, args.kind, spec, clean_id(args.customer), spec_path.parent)
    return execute(args, ops, items, client=client)


if __name__ == "__main__":
    sys.exit(main())
