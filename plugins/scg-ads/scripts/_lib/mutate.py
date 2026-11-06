"""Shared mutate flow: GoogleAdsService.mutate with validate_only dry run + checksum gate."""

from __future__ import annotations

import sys

from .client import clean_id, format_error, get_client
from .safety import SafetyError, run_mutation


def _to_dict(resp):
    try:
        return type(resp).to_dict(resp)
    except Exception:  # noqa: BLE001
        return {"raw": str(resp)}


def execute(args, operations, change_items, client=None) -> int:
    """operations: list of client.get_type('MutateOperation'). Returns process exit code."""
    if not operations:
        print("Nothing to do: no operations were generated.", file=sys.stderr)
        return 2
    client = client or get_client(getattr(args, "login_customer", None))
    cid = clean_id(args.customer)
    service = client.get_service("GoogleAdsService")

    def validate():
        service.mutate(customer_id=cid, mutate_operations=operations, validate_only=True)

    def commit():
        return _to_dict(service.mutate(customer_id=cid, mutate_operations=operations))

    try:
        run_mutation(
            customer_id=cid,
            operations=operations,
            change_items=change_items,
            apply=args.apply,
            checksum=args.checksum,
            validate_fn=validate,
            commit_fn=commit,
        )
        return 0
    except SafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {format_error(exc)}", file=sys.stderr)
        return 1
