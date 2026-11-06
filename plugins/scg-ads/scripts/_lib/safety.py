"""Propose-and-confirm for scripts, same contract as the MCP fork
(ads_mcp/propose_and_confirm.py): dry run by default, checksum bound to
customer_id + exact operations, commit only with --apply --checksum <hash>.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import struct
import sys
from typing import Any, Sequence


def _op_bytes(op: Any) -> bytes:
    # proto-plus message
    if hasattr(type(op), "pb") and callable(getattr(type(op), "pb")):
        return type(op).pb(op).SerializeToString(deterministic=True)
    # raw protobuf message
    if hasattr(op, "SerializeToString"):
        return op.SerializeToString(deterministic=True)
    return json.dumps(op, sort_keys=True, separators=(",", ":"), default=str).encode()


def _prefixed(digest, chunk: bytes) -> None:
    digest.update(struct.pack(">Q", len(chunk)))
    digest.update(chunk)


def compute_checksum(customer_id: str, operations: Sequence[Any]) -> str:
    digest = hashlib.sha256()
    _prefixed(digest, str(customer_id).encode())
    digest.update(struct.pack(">Q", len(operations)))
    for op in operations:
        _prefixed(digest, _op_bytes(op))
    return digest.hexdigest()


class SafetyError(RuntimeError):
    pass


def run_mutation(
    *,
    customer_id: str,
    operations: Sequence[Any],
    change_items: Sequence[dict],
    apply: bool,
    checksum: str | None,
    validate_fn,
    commit_fn,
    out=sys.stdout,
) -> dict:
    """Two-phase mutation.

    validate_fn(): run the API with validate_only=True (raise on failure -> no checksum).
    commit_fn(): perform the real mutate, return a JSON-serialisable result.
    """
    expected = compute_checksum(customer_id, operations)
    if not apply:
        validate_fn()
        result = {
            "status": "PROPOSED",
            "validate_only": True,
            "customer_id": customer_id,
            "operations": len(operations),
            "checksum": expected,
            "change_items": list(change_items),
            "message": (
                "Validation succeeded. Nothing was changed. Show change_items to the "
                "human; on explicit approval re-run with the same inputs plus "
                "--apply --checksum <checksum>."
            ),
        }
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write("\n")
        return result

    if not checksum or not hmac.compare_digest(checksum.strip().lower().encode(), expected.encode()):
        raise SafetyError(
            "Checksum missing or does not match these exact inputs. Run without --apply "
            "first and use the checksum it prints."
        )
    outcome = commit_fn()
    result = {"status": "COMMITTED", "customer_id": customer_id, "result": outcome}
    json.dump(result, out, indent=2, ensure_ascii=False, default=str)
    out.write("\n")
    return result


def _customer_arg(value: str) -> str:
    """Accept a config label or any id format. Also picks the account's own login (manager) id."""
    import os
    from . import config
    cfg = config.load()
    cid = config.resolve_customer(value, cfg)
    if not cid:
        raise argparse.ArgumentTypeError(f"unknown account {value!r} (see `configure.py accounts`)")
    login = config.login_for(cid, cfg)
    if login and not os.environ.get("SCG_ADS_LOGIN_PINNED"):
        os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = login
    return cid


def add_safety_args(parser) -> None:
    from . import config
    default = config.resolve_customer(None) if config.get(config.load(), "defaults", "account") else None
    parser.add_argument("--customer", type=_customer_arg, default=default, required=default is None,
                        help="Account label from config.toml, or customer id (default: [defaults].account)")
    parser.add_argument("--login-customer", help="Manager id; default: account/config login_customer_id")
    parser.add_argument("--apply", action="store_true", help="Commit. Requires --checksum from a dry run.")
    parser.add_argument("--checksum", help="Checksum printed by the dry run")
