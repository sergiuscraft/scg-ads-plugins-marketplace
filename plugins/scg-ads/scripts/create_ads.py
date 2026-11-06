#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Create Responsive Search Ads from CSV (replaces the MCP ad tools by design).

CSV columns (tolerant): ad_group, final_url, path1, path2, headline_1..headline_15,
description_1..description_4, [pin_headline_1 = 1|2|3 style: pin_h1.. optional]

Limits linted before any API call: headline <= 30, description <= 90, path <= 15,
3..15 headlines, 2..4 descriptions, no duplicates. Ads are created PAUSED.
Use --lint-only to check a file with no credentials. Dry run by default.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.csvio import read_rows  # noqa: E402
from _lib.safety import _customer_arg  # noqa: E402

H_MAX, D_MAX, P_MAX = 30, 90, 15


def collect(row, prefix, n):
    return [row[f"{prefix}_{i}"].strip() for i in range(1, n + 1) if row.get(f"{prefix}_{i}", "").strip()]


def lint_row(row, line):
    errs = []
    hs, ds = collect(row, "headline", 15), collect(row, "description", 4)
    if not row.get("ad_group", "").strip():
        errs.append("missing ad_group")
    if not re.match(r"^https?://", row.get("final_url", "")):
        errs.append("final_url must start with http(s)://")
    if len(hs) < 3:
        errs.append(f"needs >=3 headlines, has {len(hs)}")
    if len(ds) < 2:
        errs.append(f"needs >=2 descriptions, has {len(ds)}")
    errs += [f"headline too long ({len(h)}>{H_MAX}): {h}" for h in hs if len(h) > H_MAX]
    errs += [f"description too long ({len(d)}>{D_MAX}): {d}" for d in ds if len(d) > D_MAX]
    for k in ("path1", "path2"):
        if len(row.get(k, "")) > P_MAX:
            errs.append(f"{k} too long (>{P_MAX})")
    if len({h.lower() for h in hs}) != len(hs):
        errs.append("duplicate headlines")
    if len({d.lower() for d in ds}) != len(ds):
        errs.append("duplicate descriptions")
    return [f"row {line}: {e}" for e in errs]


def lint(rows):
    out = []
    for i, r in enumerate(rows, start=2):
        out += lint_row(r, i)
    return out


def build(client, customer_id, rows, ad_group_rns):
    ops, items = [], []
    for r in rows:
        op = client.get_type("MutateOperation")
        aga = op.ad_group_ad_operation.create
        aga.ad_group = ad_group_rns[r["ad_group"].lower()]
        aga.status = client.enums.AdGroupAdStatusEnum.PAUSED
        aga.ad.final_urls.append(r["final_url"])
        rsa = aga.ad.responsive_search_ad
        for idx, h in enumerate(collect(r, "headline", 15), start=1):
            a = client.get_type("AdTextAsset")
            a.text = h
            pin = r.get(f"pin_h{idx}", "").strip()
            if pin in {"1", "2", "3"}:
                a.pinned_field = getattr(client.enums.ServedAssetFieldTypeEnum, f"HEADLINE_{pin}")
            rsa.headlines.append(a)
        for d in collect(r, "description", 4):
            a = client.get_type("AdTextAsset")
            a.text = d
            rsa.descriptions.append(a)
        if r.get("path1"):
            rsa.path1 = r["path1"]
        if r.get("path2"):
            rsa.path2 = r["path2"]
        ops.append(op)
        items.append({
            "operation": "CREATE", "entity": "ResponsiveSearchAd", "ad_group": r["ad_group"],
            "status": "PAUSED", "headlines": collect(r, "headline", 15),
            "descriptions": collect(r, "description", 4), "final_url": r["final_url"],
        })
    return ops, items


def main(argv=None, client=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True)
    p.add_argument("--lint-only", action="store_true")
    p.add_argument("--customer", type=_customer_arg, help="Account label from config.toml or customer id")
    p.add_argument("--login-customer")
    p.add_argument("--campaign", help="Campaign id (ad groups are resolved by name inside it)")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--checksum")
    args = p.parse_args(argv)

    rows = read_rows(args.csv)
    errs = lint(rows)
    if errs:
        print("Lint problems:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    if args.lint_only:
        print(f"OK: {len(rows)} ad(s) pass limits.")
        return 0
    if not (args.customer and args.campaign):
        print("--customer and --campaign are required unless --lint-only", file=sys.stderr)
        return 2

    from _lib.client import clean_id, get_client, gaql
    from _lib.mutate import execute

    client = client or get_client(args.login_customer)
    cid = clean_id(args.customer)
    found = gaql(
        client, cid,
        f"SELECT ad_group.name, ad_group.resource_name FROM ad_group "
        f"WHERE campaign.id = {clean_id(args.campaign)} AND ad_group.status != 'REMOVED'",
    )
    rns = {r.ad_group.name.lower(): r.ad_group.resource_name for r in found}
    missing = sorted({r["ad_group"] for r in rows if r["ad_group"].lower() not in rns})
    if missing:
        print(f"Ad groups not found in campaign: {missing}. Run import_csv.py first.", file=sys.stderr)
        return 2
    ops, items = build(client, cid, rows, rns)
    return execute(args, ops, items, client=client)


if __name__ == "__main__":
    sys.exit(main())
