#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Bulk import ad groups, keywords and negatives from CSV into an existing campaign.

CSV columns (case/spacing tolerant):
  ad_group    ad group name (blank + negative=yes -> campaign-level negative)
  keyword     keyword text
  match_type  EXACT | PHRASE | BROAD (default PHRASE)
  negative    yes/no (default no)
  cpc_bid     optional max CPC in account currency (ad-group default or keyword-level)

Missing ad groups are created PAUSED (same default as the MCP fork). Everything goes in
ONE atomic mutate so it is all-or-nothing. Dry run by default.
"""

from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.client import clean_id, get_client, gaql  # noqa: E402
from _lib.csvio import read_rows, truthy  # noqa: E402
from _lib.mutate import execute  # noqa: E402
from _lib.safety import add_safety_args  # noqa: E402

MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}
MAX_OPS = 5000


def parse_rows(rows):
    """Validate + normalise CSV rows. Returns (entries, errors)."""
    entries, errors, seen = [], [], set()
    for i, r in enumerate(rows, start=2):
        kw = r.get("keyword", "").strip()
        if not kw:
            errors.append(f"row {i}: empty keyword")
            continue
        mt = (r.get("match_type") or "PHRASE").strip().upper()
        if mt not in MATCH_TYPES:
            errors.append(f"row {i}: bad match_type {mt!r}")
            continue
        neg = truthy(r.get("negative", ""))
        ag = r.get("ad_group", "").strip()
        if not neg and not ag:
            errors.append(f"row {i}: positive keyword needs ad_group")
            continue
        bid = r.get("cpc_bid", "").strip()
        try:
            bid_micros = int(round(float(bid.replace(",", ".")) * 1e6)) if bid else None
        except ValueError:
            errors.append(f"row {i}: bad cpc_bid {bid!r}")
            continue
        key = (ag.lower(), kw.lower(), mt, neg)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"ad_group": ag, "keyword": kw, "match_type": mt, "negative": neg, "bid": bid_micros})
    return entries, errors


def build(client, campaign_id: str, customer_id: str, entries, existing_ad_groups: dict):
    ops, items = [], []
    svc_ag = client.get_service("AdGroupService")
    svc_c = client.get_service("CampaignService")
    campaign_rn = svc_c.campaign_path(customer_id, campaign_id)
    temp = -1
    ag_rn = {name.lower(): rn for name, rn in existing_ad_groups.items()}

    for name in OrderedDict.fromkeys(e["ad_group"] for e in entries if e["ad_group"]):
        if name.lower() in ag_rn:
            continue
        rn = svc_ag.ad_group_path(customer_id, temp)
        temp -= 1
        op = client.get_type("MutateOperation")
        ag = op.ad_group_operation.create
        ag.resource_name = rn
        ag.name = name
        ag.campaign = campaign_rn
        ag.status = client.enums.AdGroupStatusEnum.PAUSED
        ag.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        ops.append(op)
        ag_rn[name.lower()] = rn
        items.append({"operation": "CREATE", "entity": "AdGroup", "name": name, "status": "PAUSED"})

    for e in entries:
        op = client.get_type("MutateOperation")
        mt = getattr(client.enums.KeywordMatchTypeEnum, e["match_type"])
        if e["negative"] and not e["ad_group"]:
            c = op.campaign_criterion_operation.create
            c.campaign = campaign_rn
            c.negative = True
            c.keyword.text = e["keyword"]
            c.keyword.match_type = mt
            where = "campaign"
        else:
            c = op.ad_group_criterion_operation.create
            c.ad_group = ag_rn[e["ad_group"].lower()]
            c.keyword.text = e["keyword"]
            c.keyword.match_type = mt
            if e["negative"]:
                c.negative = True
            else:
                c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                if e["bid"]:
                    c.cpc_bid_micros = e["bid"]
            where = e["ad_group"]
        ops.append(op)
        items.append({
            "operation": "CREATE",
            "entity": "NegativeKeyword" if e["negative"] else "Keyword",
            "scope": where, "text": e["keyword"], "match_type": e["match_type"],
        })
    return ops, items


def main(argv=None, client=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_safety_args(p)
    p.add_argument("--campaign", required=True, help="Campaign id")
    p.add_argument("--csv", required=True)
    args = p.parse_args(argv)

    entries, errors = parse_rows(read_rows(args.csv))
    if errors:
        print("CSV problems:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 2
    if len(entries) > MAX_OPS:
        print(f"Too many rows ({len(entries)} > {MAX_OPS}); split the CSV.", file=sys.stderr)
        return 2

    client = client or get_client(args.login_customer)
    cid = clean_id(args.customer)
    rows = gaql(
        client, cid,
        f"SELECT ad_group.name, ad_group.resource_name FROM ad_group "
        f"WHERE campaign.id = {clean_id(args.campaign)} AND ad_group.status != 'REMOVED'",
    )
    existing = {r.ad_group.name: r.ad_group.resource_name for r in rows}
    ops, items = build(client, clean_id(args.campaign), cid, entries, existing)
    return execute(args, ops, items, client=client)


if __name__ == "__main__":
    sys.exit(main())
