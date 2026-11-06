#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Upload offline conversions (click or call) from CSV. Dry run by default.

  conversion_upload.py clicks --customer C --conversion-action 123456 --csv leads.csv [--currency EUR]
  conversion_upload.py calls  --customer C --conversion-action 123456 --csv calls.csv

clicks CSV (tolerant headers): gclid | gbraid | wbraid | email | phone ;
   conversion_time (YYYY-MM-DD HH:MM:SS[+TZ], default tz from --tz) ; value ; currency ; order_id
   email/phone are normalised and SHA-256 hashed locally (enhanced conversions for leads);
   plain PII is never sent or printed.
calls CSV: caller_id (E.164) ; call_start_time ; conversion_time ; value ; currency

Uses partial_failure; the dry run is the API's own validate_only. The conversion action must
be of type UPLOAD_CLICKS / UPLOAD_CALLS (create it with the MCP conversions tool).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.csvio import read_rows  # noqa: E402
from _lib.hashing import hash_email, hash_phone  # noqa: E402

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\s?[+-]\d{2}:?\d{2})?$")
MAX_BATCH = 2000


def fmt_ts(value: str, tz: str) -> str | None:
    v = value.strip().replace("T", " ")
    if not TS_RE.match(v):
        return None
    if re.search(r"[+-]\d{2}:?\d{2}$", v):
        v = re.sub(r"\s?([+-]\d{2}):?(\d{2})$", r" \1:\2", v)
        return v
    return f"{v} {tz}"


def parse_clicks(rows, tz, default_cc=None, default_currency=None):
    items, errors = [], []
    for i, r in enumerate(rows, start=2):
        ids = {k: r.get(k, "").strip() for k in ("gclid", "gbraid", "wbraid")}
        he, hp = hash_email(r.get("email", "")) if r.get("email") else None, \
            hash_phone(r.get("phone", ""), default_cc) if r.get("phone") else None
        bad = False
        if r.get("email") and not he:
            errors.append(f"row {i}: invalid email")
            bad = True
        if r.get("phone") and not hp:
            errors.append(f"row {i}: invalid phone (use +E.164 or --default-country-code)")
            bad = True
        if bad:
            continue
        if not (any(ids.values()) or he or hp):
            errors.append(f"row {i}: need gclid/gbraid/wbraid or email/phone")
            continue
        ts = fmt_ts(r.get("conversion_time", ""), tz)
        if not ts:
            errors.append(f"row {i}: bad conversion_time (YYYY-MM-DD HH:MM:SS)")
            continue
        try:
            val = float(r["value"].replace(",", ".")) if r.get("value") else None
        except ValueError:
            errors.append(f"row {i}: bad value")
            continue
        items.append({"ids": ids, "he": he, "hp": hp, "ts": ts, "value": val,
                      "currency": (r.get("currency") or default_currency or "").upper() or None,
                      "order_id": r.get("order_id", "").strip() or None})
    return items, errors


def parse_calls(rows, tz, default_currency=None):
    items, errors = [], []
    for i, r in enumerate(rows, start=2):
        caller = re.sub(r"[^\d+]", "", r.get("caller_id", ""))
        if not re.match(r"^\+\d{8,15}$", caller):
            errors.append(f"row {i}: caller_id must be E.164 (+...)")
            continue
        start, conv = fmt_ts(r.get("call_start_time", ""), tz), fmt_ts(r.get("conversion_time", ""), tz)
        if not (start and conv):
            errors.append(f"row {i}: bad call_start_time/conversion_time")
            continue
        try:
            val = float(r["value"].replace(",", ".")) if r.get("value") else None
        except ValueError:
            errors.append(f"row {i}: bad value")
            continue
        items.append({"caller": caller, "start": start, "ts": conv, "value": val,
                      "currency": (r.get("currency") or default_currency or "").upper() or None})
    return items, errors


def build_clicks(client, action_rn, items):
    out = []
    for it in items:
        c = client.get_type("ClickConversion")
        c.conversion_action = action_rn
        c.conversion_date_time = it["ts"]
        for k, v in it["ids"].items():
            if v:
                setattr(c, k, v)
        if it["value"] is not None:
            c.conversion_value = it["value"]
            if it["currency"]:
                c.currency_code = it["currency"]
        if it["order_id"]:
            c.order_id = it["order_id"]
        for attr, h in (("hashed_email", it["he"]), ("hashed_phone_number", it["hp"])):
            if h:
                u = client.get_type("UserIdentifier")
                u.user_identifier_source = client.enums.UserIdentifierSourceEnum.FIRST_PARTY
                setattr(u, attr, h)
                c.user_identifiers.append(u)
        out.append(c)
    return out


def build_calls(client, action_rn, items):
    out = []
    for it in items:
        c = client.get_type("CallConversion")
        c.conversion_action = action_rn
        c.caller_id = it["caller"]
        c.call_start_date_time = it["start"]
        c.conversion_date_time = it["ts"]
        if it["value"] is not None:
            c.conversion_value = it["value"]
            if it["currency"]:
                c.currency_code = it["currency"]
        out.append(c)
    return out


def main(argv=None, client=None) -> int:
    from _lib.client import clean_id, format_error, get_client
    from _lib.safety import SafetyError, add_safety_args, run_mutation

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["clicks", "calls"])
    add_safety_args(p)
    p.add_argument("--conversion-action", required=True, help="Conversion action id")
    p.add_argument("--csv", required=True)
    p.add_argument("--tz", default="+00:00", help="Offset for timestamps without one, e.g. +02:00")
    p.add_argument("--currency")
    p.add_argument("--default-country-code", help="For phones without +, e.g. 380")
    args = p.parse_args(argv)

    rows = read_rows(args.csv)
    tz = args.tz if " " not in args.tz else args.tz.strip()
    if args.kind == "clicks":
        items, errors = parse_clicks(rows, tz, args.default_country_code, args.currency)
    else:
        items, errors = parse_calls(rows, tz, args.currency)
    if errors:
        print("CSV problems:\n  " + "\n  ".join(errors[:50]), file=sys.stderr)
        return 2
    if not items:
        print("No rows.", file=sys.stderr)
        return 2
    if len(items) > MAX_BATCH:
        print(f"Max {MAX_BATCH} rows per run.", file=sys.stderr)
        return 2

    client = client or get_client(args.login_customer)
    cid = clean_id(args.customer)
    action_rn = client.get_service("ConversionActionService").conversion_action_path(
        cid, clean_id(args.conversion_action))
    convs = (build_clicks if args.kind == "clicks" else build_calls)(client, action_rn, items)
    svc = client.get_service("ConversionUploadService")
    upload = svc.upload_click_conversions if args.kind == "clicks" else svc.upload_call_conversions

    def call(validate):
        resp = upload(customer_id=cid, conversions=convs, partial_failure=True, validate_only=validate)
        pf = getattr(resp, "partial_failure_error", None)
        if pf and pf.message:
            raise RuntimeError(f"partial failure: {pf.message}")
        return resp

    summary = [{"operation": "UPLOAD", "entity": f"{args.kind[:-1].title()}Conversion",
                "count": len(convs), "conversion_action": args.conversion_action,
                "first_time": items[0]["ts"], "uses_hashed_identifiers": any(i.get("he") or i.get("hp") for i in items)}]
    try:
        run_mutation(customer_id=cid, operations=convs, change_items=summary, apply=args.apply,
                     checksum=args.checksum, validate_fn=lambda: call(True),
                     commit_fn=lambda: {"uploaded": len(convs), "response": str(call(False))[:2000]})
        return 0
    except SafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {format_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
