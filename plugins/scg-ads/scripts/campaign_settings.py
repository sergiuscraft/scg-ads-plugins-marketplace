#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Edit campaign settings the MCP cannot: dates, networks, tracking, EU political flag.

Only flags you pass are changed. Dry run by default.

  campaign_settings.py --customer C --campaign ID --start-date 2026-12-01 --end-date 2027-01-15
  campaign_settings.py --customer C --campaign ID --tracking-template "{lpurl}?src=g" --final-url-suffix "utm_source=google"
  campaign_settings.py --customer C --campaign ID --search-partners off --display-network off
  campaign_settings.py --customer C --campaign ID --clear-end-date
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

NO_END = "2037-12-30 23:59:59"  # API sentinel for "no end date"


def onoff(v: str) -> bool:
    if v.lower() in {"on", "true", "yes"}:
        return True
    if v.lower() in {"off", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError("use on/off")


def date_arg(v: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise argparse.ArgumentTypeError("use YYYY-MM-DD")
    return v


def collect_changes(args) -> dict:
    ch = {}
    if args.start_date:
        ch["start_date_time"] = f"{args.start_date} 00:00:00"
    if args.clear_end_date:
        ch["end_date_time"] = NO_END
    elif args.end_date:
        ch["end_date_time"] = f"{args.end_date} 23:59:59"
    if args.tracking_template is not None:
        ch["tracking_url_template"] = args.tracking_template
    if args.final_url_suffix is not None:
        ch["final_url_suffix"] = args.final_url_suffix
    for flag, field in (
        (args.search_partners, "network_settings.target_partner_search_network"),
        (args.google_search, "network_settings.target_google_search"),
        (args.display_network, "network_settings.target_content_network"),
    ):
        if flag is not None:
            ch[field] = flag
    if args.eu_political is not None:
        ch["contains_eu_political_advertising"] = args.eu_political
    return ch


def main(argv=None, client=None) -> int:
    from _lib.client import clean_id, get_client
    from _lib.mutate import execute
    from _lib.safety import add_safety_args

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_safety_args(p)
    p.add_argument("--campaign", required=True)
    p.add_argument("--start-date", type=date_arg)
    p.add_argument("--end-date", type=date_arg)
    p.add_argument("--clear-end-date", action="store_true")
    p.add_argument("--tracking-template")
    p.add_argument("--final-url-suffix")
    p.add_argument("--search-partners", type=onoff)
    p.add_argument("--google-search", type=onoff)
    p.add_argument("--display-network", type=onoff)
    p.add_argument("--eu-political", type=onoff, help="on = contains EU political advertising")
    args = p.parse_args(argv)

    changes = collect_changes(args)
    if not changes:
        print("No changes requested.", file=sys.stderr)
        return 2

    client = client or get_client(args.login_customer)
    cid = clean_id(args.customer)
    op = client.get_type("MutateOperation")
    camp = op.campaign_operation.update
    camp.resource_name = client.get_service("CampaignService").campaign_path(cid, clean_id(args.campaign))
    for path, value in changes.items():
        if "." in path:
            head, leaf = path.split(".")
            setattr(getattr(camp, head), leaf, value)
        elif path == "contains_eu_political_advertising":
            enum = client.enums.EuPoliticalAdvertisingStatusEnum
            camp.contains_eu_political_advertising = (
                enum.CONTAINS_EU_POLITICAL_ADVERTISING if value
                else enum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
            )
        else:
            setattr(camp, path, value)
    op.campaign_operation.update_mask.paths.extend(changes.keys())
    items = [{"operation": "UPDATE", "entity": "Campaign", "id": args.campaign, "field": k, "value": v}
             for k, v in changes.items()]
    return execute(args, [op], items, client=client)


if __name__ == "__main__":
    sys.exit(main())
