#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Customer Match: create a CRM-based user list and/or upload hashed members. Dry run by default.

  user_lists.py list   --customer C
  user_lists.py create --customer C --name "Newsletter 2026" --life-span 540 [--description ...]
  user_lists.py upload --customer C --csv contacts.csv (--list-id 123 | --create-name "New list")
                       --consent-confirmed [--default-country-code 380]

contacts CSV: email, phone, (optional) first_name, last_name, country, zip  -- only email/phone used here.
PII is normalised and SHA-256 hashed locally; plain values are never sent, printed or logged.

LEGAL: Customer Match requires that you collected the data with the consent Google's policy
demands. Upload refuses to run without --consent-confirmed, and the human must say yes in chat.
The account also needs Customer Match eligibility (history/spend); the API rejects otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.csvio import read_rows  # noqa: E402
from _lib.hashing import hash_email, hash_phone  # noqa: E402

MAX_MEMBERS = 100_000  # per run; the API allows 100k operations per request


def parse_members(rows, default_cc=None):
    """-> (members, stats). member = {'emails': [hash], 'phones': [hash]} (one row = one person)."""
    members, seen, bad, dup = [], set(), 0, 0
    for r in rows:
        he = hash_email(r["email"]) if r.get("email") else None
        hp = hash_phone(r["phone"], default_cc) if r.get("phone") else None
        if not (he or hp):
            bad += 1
            continue
        key = (he, hp)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        members.append({"he": he, "hp": hp})
    return members, {"rows": len(rows), "usable": len(members), "invalid": bad, "duplicates": dup}


def build_user_list_op(client, name, description, life_span):
    op = client.get_type("UserListOperation")
    ul = op.create
    ul.name = name
    if description:
        ul.description = description
    ul.membership_life_span = life_span
    ul.crm_based_user_list.upload_key_type = client.enums.CustomerMatchUploadKeyTypeEnum.CONTACT_INFO
    ul.crm_based_user_list.data_source_type = client.enums.UserListCrmDataSourceTypeEnum.FIRST_PARTY
    return op


def build_user_data_ops(client, members):
    ops = []
    for m in members:
        op = client.get_type("OfflineUserDataJobOperation")
        ud = op.create
        for attr, h in (("hashed_email", m["he"]), ("hashed_phone_number", m["hp"])):
            if h:
                u = client.get_type("UserIdentifier")
                setattr(u, attr, h)
                ud.user_identifiers.append(u)
        ops.append(op)
    return ops


def main(argv=None, client=None) -> int:
    from _lib.client import clean_id, format_error, get_client, gaql
    from _lib.safety import SafetyError, add_safety_args, run_mutation

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["list", "create", "upload"])
    add_safety_args(p)
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--life-span", type=int, default=540, help="Days a member stays (max 540; 10000 = no expiry)")
    p.add_argument("--csv")
    p.add_argument("--list-id")
    p.add_argument("--create-name", help="Create a new list with this name, then upload into it")
    p.add_argument("--consent-confirmed", action="store_true")
    p.add_argument("--default-country-code")
    args = p.parse_args(argv)

    cid = clean_id(args.customer)

    if args.action == "list":
        client = client or get_client(args.login_customer)
        for r in gaql(client, cid, "SELECT user_list.id, user_list.name, user_list.type, user_list.size_for_search, "
                      "user_list.size_for_display, user_list.membership_status, user_list.eligible_for_search "
                      "FROM user_list ORDER BY user_list.name"):
            u = r.user_list
            print(f"{u.id}\t{u.name}\t{u.type_.name}\tsearch={u.size_for_search}\tdisplay={u.size_for_display}"
                  f"\t{u.membership_status.name}\teligible_for_search={u.eligible_for_search}")
        return 0

    if args.action == "create" and not args.name:
        print("--name required", file=sys.stderr)
        return 2
    if args.action == "upload":
        if not args.csv or bool(args.list_id) == bool(args.create_name):
            print("upload needs --csv and exactly one of --list-id / --create-name", file=sys.stderr)
            return 2
        if not args.consent_confirmed:
            print("REFUSED: pass --consent-confirmed only after the human confirms the contacts gave "
                  "consent that meets Google's Customer Match policy.", file=sys.stderr)
            return 3
    if not 1 <= args.life_span <= 540 and args.life_span != 10000:
        print("--life-span must be 1..540 or 10000", file=sys.stderr)
        return 2

    client = client or get_client(args.login_customer)
    ul_svc = client.get_service("UserListService")

    try:
        if args.action == "create":
            op = build_user_list_op(client, args.name, args.description, args.life_span)
            items = [{"operation": "CREATE", "entity": "UserList (CRM based)", "name": args.name,
                      "life_span_days": args.life_span}]
            def validate():
                ul_svc.mutate_user_lists(customer_id=cid, operations=[op], validate_only=True)
            def commit():
                return {"resource": ul_svc.mutate_user_lists(customer_id=cid, operations=[op]).results[0].resource_name}
            run_mutation(customer_id=cid, operations=[op], change_items=items, apply=args.apply,
                         checksum=args.checksum, validate_fn=validate, commit_fn=commit)
            return 0

        members, stats = parse_members(read_rows(args.csv), args.default_country_code)
        if not members:
            print(f"No usable contacts: {stats}", file=sys.stderr)
            return 2
        if len(members) > MAX_MEMBERS:
            print(f"Max {MAX_MEMBERS} contacts per run.", file=sys.stderr)
            return 2
        data_ops = build_user_data_ops(client, members)
        create_op = build_user_list_op(client, args.create_name, args.description, args.life_span) \
            if args.create_name else None
        operations = ([create_op] if create_op else []) + data_ops
        target = f"new list '{args.create_name}'" if create_op else f"list {args.list_id}"
        items = [{"operation": "UPLOAD", "entity": "CustomerMatchMembers", "target": target,
                  **stats, "hashed_only": True, "consent_confirmed": True}]

        def validate():
            if create_op:
                ul_svc.mutate_user_lists(customer_id=cid, operations=[create_op], validate_only=True)
            # Offline user data jobs have no validate_only: structure/hash checks are done locally.

        def commit():
            if create_op:
                list_rn = ul_svc.mutate_user_lists(customer_id=cid, operations=[create_op]).results[0].resource_name
            else:
                list_rn = ul_svc.user_list_path(cid, clean_id(args.list_id))
            job_svc = client.get_service("OfflineUserDataJobService")
            job = client.get_type("OfflineUserDataJob")
            job.type_ = client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            job.customer_match_user_list_metadata.user_list = list_rn
            job.customer_match_user_list_metadata.consent.ad_user_data = client.enums.ConsentStatusEnum.GRANTED
            job.customer_match_user_list_metadata.consent.ad_personalization = client.enums.ConsentStatusEnum.GRANTED
            job_rn = job_svc.create_offline_user_data_job(customer_id=cid, job=job).resource_name
            req = client.get_type("AddOfflineUserDataJobOperationsRequest")
            req.resource_name = job_rn
            req.enable_partial_failure = True
            req.operations.extend(data_ops)
            job_svc.add_offline_user_data_job_operations(request=req)
            job_svc.run_offline_user_data_job(resource_name=job_rn)
            return {"user_list": list_rn, "job": job_rn, "members_sent": len(members),
                    "note": "Processing is async; list size updates in 6-48h. Check with: user_lists.py list"}

        run_mutation(customer_id=cid, operations=operations, change_items=items, apply=args.apply,
                     checksum=args.checksum, validate_fn=validate, commit_fn=commit)
        return 0
    except SafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {format_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
