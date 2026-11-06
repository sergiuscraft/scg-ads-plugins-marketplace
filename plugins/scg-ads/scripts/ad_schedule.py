#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""List / replace / remove campaign ad-schedule windows (the MCP only adds).

  ad_schedule.py list    --customer C --campaign ID
  ad_schedule.py remove  --customer C --campaign ID --criterion 111 --criterion 222 [--apply --checksum H]
  ad_schedule.py replace --customer C --campaign ID --slots "MON-FRI 09:00-18:00 +0; SAT 10:00-14:00 -20" [--apply ...]

Slot grammar: DAYS HH:MM-HH:MM [+/-percent bid adjustment]. DAYS = MON | MON-FRI | MON,WED,FRI.
Minutes must be 0/15/30/45. 'replace' removes ALL existing windows then adds the new ones in
one atomic mutate. Dry run by default.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
ABBR = {d[:3]: d for d in DAYS}
MIN_ENUM = {0: "ZERO", 15: "FIFTEEN", 30: "THIRTY", 45: "FORTY_FIVE"}


def parse_days(text: str) -> list[str]:
    out = []
    for part in text.upper().split(","):
        part = part.strip()
        if "-" in part:
            a, b = (ABBR[x.strip()[:3]] for x in part.split("-"))
            i, j = DAYS.index(a), DAYS.index(b)
            out += DAYS[i : j + 1] if i <= j else DAYS[i:] + DAYS[: j + 1]
        else:
            out.append(ABBR[part[:3]])
    return out


def parse_slots(spec: str) -> list[dict]:
    slots = []
    for chunk in filter(None, (s.strip() for s in spec.split(";"))):
        m = re.match(r"^([A-Za-z,\- ]+?)\s+(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})(?:\s+([+-]\d+))?$", chunk)
        if not m:
            raise ValueError(f"Cannot parse slot: {chunk!r}")
        d, sh, sm, eh, em, pct = m.groups()
        sh, sm, eh, em = int(sh), int(sm), int(eh), int(em)
        if sm not in MIN_ENUM or em not in MIN_ENUM or not (0 <= sh <= 24) or not (0 <= eh <= 24):
            raise ValueError(f"Bad time in {chunk!r} (minutes 0/15/30/45, hours 0-24)")
        if (eh, em) <= (sh, sm):
            raise ValueError(f"End must be after start in {chunk!r}")
        for day in parse_days(d):
            slots.append({"day": day, "sh": sh, "sm": sm, "eh": eh, "em": em, "pct": int(pct) if pct else 0})
    return slots


def list_windows(client, cid, campaign):
    from _lib.client import gaql
    return gaql(
        client, cid,
        "SELECT campaign_criterion.criterion_id, campaign_criterion.ad_schedule.day_of_week, "
        "campaign_criterion.ad_schedule.start_hour, campaign_criterion.ad_schedule.start_minute, "
        "campaign_criterion.ad_schedule.end_hour, campaign_criterion.ad_schedule.end_minute, "
        "campaign_criterion.bid_modifier, campaign_criterion.resource_name "
        f"FROM campaign_criterion WHERE campaign.id = {campaign} AND campaign_criterion.type = AD_SCHEDULE",
    )


def build_removes(client, rows, only=None):
    ops, items = [], []
    for r in rows:
        cc = r.campaign_criterion
        if only and str(cc.criterion_id) not in only:
            continue
        op = client.get_type("MutateOperation")
        op.campaign_criterion_operation.remove = cc.resource_name
        ops.append(op)
        s = cc.ad_schedule
        items.append({
            "operation": "REMOVE", "entity": "AdSchedule", "criterion_id": cc.criterion_id,
            "window": f"{s.day_of_week.name} {s.start_hour}:{s.start_minute.name}-{s.end_hour}:{s.end_minute.name}",
        })
    return ops, items


def build_adds(client, cid, campaign, slots):
    ops, items = [], []
    campaign_rn = client.get_service("CampaignService").campaign_path(cid, campaign)
    for s in slots:
        op = client.get_type("MutateOperation")
        c = op.campaign_criterion_operation.create
        c.campaign = campaign_rn
        a = c.ad_schedule
        a.day_of_week = getattr(client.enums.DayOfWeekEnum, s["day"])
        a.start_hour, a.end_hour = s["sh"], s["eh"]
        a.start_minute = getattr(client.enums.MinuteOfHourEnum, MIN_ENUM[s["sm"]])
        a.end_minute = getattr(client.enums.MinuteOfHourEnum, MIN_ENUM[s["em"]])
        if s["pct"]:
            c.bid_modifier = 1 + s["pct"] / 100
        ops.append(op)
        items.append({
            "operation": "CREATE", "entity": "AdSchedule",
            "window": f"{s['day']} {s['sh']:02d}:{s['sm']:02d}-{s['eh']:02d}:{s['em']:02d}",
            "bid_adjustment_pct": s["pct"],
        })
    return ops, items


def main(argv=None, client=None) -> int:
    from _lib.client import clean_id, get_client
    from _lib.mutate import execute
    from _lib.safety import add_safety_args

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["list", "remove", "replace"])
    add_safety_args(p)
    p.add_argument("--campaign", required=True)
    p.add_argument("--criterion", action="append", default=[])
    p.add_argument("--slots")
    args = p.parse_args(argv)

    client = client or get_client(args.login_customer)
    cid, camp = clean_id(args.customer), clean_id(args.campaign)
    rows = list_windows(client, cid, camp)

    if args.action == "list":
        for r in rows:
            cc, s = r.campaign_criterion, r.campaign_criterion.ad_schedule
            print(f"{cc.criterion_id}\t{s.day_of_week.name}\t{s.start_hour}:{s.start_minute.name}-"
                  f"{s.end_hour}:{s.end_minute.name}\tbid_modifier={cc.bid_modifier}")
        return 0
    if args.action == "remove":
        if not args.criterion:
            print("--criterion required (repeatable)", file=sys.stderr)
            return 2
        ops, items = build_removes(client, rows, only=set(clean_id(c) for c in args.criterion))
    else:
        if not args.slots:
            print("--slots required", file=sys.stderr)
            return 2
        try:
            slots = parse_slots(args.slots)
        except (ValueError, KeyError) as exc:
            print(f"Bad --slots: {exc}", file=sys.stderr)
            return 2
        rm_ops, rm_items = build_removes(client, rows)
        add_ops, add_items = build_adds(client, cid, camp, slots)
        ops, items = rm_ops + add_ops, rm_items + add_items
    return execute(args, ops, items, client=client)


if __name__ == "__main__":
    sys.exit(main())
