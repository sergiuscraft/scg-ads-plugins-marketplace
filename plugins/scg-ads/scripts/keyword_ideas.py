#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Keyword Planner ideas -> CSV (read-only).

Needs a developer token with Basic access or higher. On Explorer/test access the API
returns DEVELOPER_TOKEN_NOT_APPROVED; this script says so and exits 4 so the skill can
fall back to CSV / search-terms sources.

Examples:
  keyword_ideas.py --customer 123-456-7890 --seeds "dental implants,teeth whitening" \
      --geo 2804 --language 1031 --out out/ideas.csv
  keyword_ideas.py --customer 1234567890 --url https://example.com --seeds-file seeds.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.client import clean_id, format_error, get_client  # noqa: E402
from _lib.safety import _customer_arg  # noqa: E402
from _lib.csvio import write_rows  # noqa: E402

FIELDS = [
    "keyword", "avg_monthly_searches", "competition", "competition_index",
    "low_top_of_page_bid", "high_top_of_page_bid", "monthly_searches_12m",
]


def build_request(client, args):
    req = client.get_type("GenerateKeywordIdeasRequest")
    req.customer_id = clean_id(args.customer)
    req.language = client.get_service("GoogleAdsService").language_constant_path(args.language)
    for geo in args.geo or []:
        req.geo_target_constants.append(
            client.get_service("GeoTargetConstantService").geo_target_constant_path(geo)
        )
    network = client.enums.KeywordPlanNetworkEnum
    req.keyword_plan_network = (
        network.GOOGLE_SEARCH_AND_PARTNERS if args.partners else network.GOOGLE_SEARCH
    )
    req.include_adult_keywords = False
    seeds = list(args.seeds or [])
    if args.seeds_file:
        seeds += [s.strip() for s in Path(args.seeds_file).read_text().splitlines() if s.strip()]
    if seeds and args.url:
        req.keyword_and_url_seed.url = args.url
        req.keyword_and_url_seed.keywords.extend(seeds)
    elif seeds:
        req.keyword_seed.keywords.extend(seeds)
    elif args.url:
        req.url_seed.url = args.url
    else:
        raise SystemExit("Provide --seeds, --seeds-file and/or --url")
    return req


def to_row(idea) -> dict:
    m = idea.keyword_idea_metrics
    return {
        "keyword": idea.text,
        "avg_monthly_searches": m.avg_monthly_searches,
        "competition": getattr(m.competition, "name", str(m.competition)),
        "competition_index": m.competition_index,
        "low_top_of_page_bid": round(m.low_top_of_page_bid_micros / 1e6, 2),
        "high_top_of_page_bid": round(m.high_top_of_page_bid_micros / 1e6, 2),
        "monthly_searches_12m": ";".join(str(v.monthly_searches) for v in m.monthly_search_volumes),
    }


def main(argv=None, client=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--customer", type=_customer_arg, required=True, help="Account label from config.toml or customer id")
    p.add_argument("--login-customer")
    p.add_argument("--seeds", type=lambda s: [x.strip() for x in s.split(",") if x.strip()])
    p.add_argument("--seeds-file")
    p.add_argument("--url")
    p.add_argument("--geo", action="append", help="Geo target constant id (repeatable); see targeting_suggest_geo_targets")
    p.add_argument("--language", default="1000", help="Language constant id (1000=English, 1031=Ukrainian)")
    p.add_argument("--partners", action="store_true", help="Include search partners")
    p.add_argument("--min-volume", type=int, default=0)
    p.add_argument("--out", help="CSV path (default: <account workspace>/out/keyword_ideas.csv)")
    args = p.parse_args(argv)

    if not args.out:
        from _lib import workspace
        args.out = str(workspace.out_dir(args.customer) / "keyword_ideas.csv")
    client = client or get_client(args.login_customer)
    try:
        service = client.get_service("KeywordPlanIdeaService")
        ideas = service.generate_keyword_ideas(request=build_request(client, args))
        rows = [to_row(i) for i in ideas]
    except Exception as exc:  # noqa: BLE001
        text = format_error(exc)
        if "DEVELOPER_TOKEN_NOT_APPROVED" in text:
            print(
                "Keyword Planner is not available: DEVELOPER_TOKEN_NOT_APPROVED. Apply for Basic "
                "access in Google Ads > Tools > API Center. Meanwhile use a CSV exported from the "
                "Keyword Planner UI / Ahrefs / Semrush, or account search terms.",
                file=sys.stderr,
            )
            return 4
        print(f"FAILED: {text}", file=sys.stderr)
        return 1

    rows = [r for r in rows if r["avg_monthly_searches"] >= args.min_volume]
    rows.sort(key=lambda r: r["avg_monthly_searches"], reverse=True)
    write_rows(args.out, rows, FIELDS)
    print(f"Wrote {len(rows)} ideas to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
