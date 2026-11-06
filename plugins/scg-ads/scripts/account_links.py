#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-ads>=33", "google-auth"]
# ///
"""Inspect account links and invite a Merchant Center account. Dry run by default.

  account_links.py list   --customer C
  account_links.py invite-merchant --customer C --merchant-id 1234567 [--apply --checksum H]
  account_links.py ga4-howto

What the Google Ads API can and cannot do:
  * Merchant Center: Ads sends an invitation; the Merchant Center admin must APPROVE it
    (or send the invite from Merchant Center and approve it here in the Ads UI).
  * GA4: links are created from the GA4 side (Admin > Product links > Google Ads links, or the
    Analytics Admin API). The Ads API can only read them. `ga4-howto` prints the steps.
  * Approval of any invitation is always a human action in the partner product.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

GA4_HOWTO = """GA4 -> Google Ads link (human steps)
1. In GA4: Admin > Product links > Google Ads links > Link.
2. Choose the Google Ads account (you need Admin on the GA4 property and Admin on the Ads account).
3. Enable personalized advertising and auto-tagging in Google Ads (Admin > Account settings).
4. In Google Ads: Admin > Data manager (or Linked accounts) - confirm status is Linked.
5. Import GA4 key events as conversions only if you are not already tracking them natively
   (avoid double counting); imported GA4 goals cannot be edited through the API.
Verify afterwards:  account_links.py list --customer <id>
"""


def list_links(client, cid):
    from _lib.client import gaql
    out = []
    for r in gaql(client, cid, "SELECT product_link.resource_name, product_link.type, "
                  "product_link.product_link_id FROM product_link"):
        pl = r.product_link
        out.append(("linked", pl.type_.name, pl.resource_name))
    for r in gaql(client, cid, "SELECT product_link_invitation.resource_name, product_link_invitation.status, "
                  "product_link_invitation.type FROM product_link_invitation"):
        pi = r.product_link_invitation
        out.append((f"invitation:{pi.status.name}", pi.type_.name, pi.resource_name))
    return out


def main(argv=None, client=None) -> int:
    if argv and argv[0] == "ga4-howto":
        print(GA4_HOWTO)
        return 0

    from _lib.client import clean_id, format_error, get_client
    from _lib.safety import SafetyError, add_safety_args, run_mutation

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["list", "invite-merchant", "ga4-howto"])
    add_safety_args(p)
    p.add_argument("--merchant-id")
    args = p.parse_args(argv)
    if args.action == "ga4-howto":
        print(GA4_HOWTO)
        return 0

    client = client or get_client(args.login_customer)
    cid = clean_id(args.customer)
    if args.action == "list":
        rows = list_links(client, cid)
        for state, kind, rn in rows:
            print(f"{state}\t{kind}\t{rn}")
        if not rows:
            print("No product links or invitations found.")
        return 0

    if not args.merchant_id or not clean_id(args.merchant_id):
        print("--merchant-id required (digits)", file=sys.stderr)
        return 2
    req = client.get_type("CreateProductLinkInvitationRequest")
    req.customer_id = cid
    req.product_link_invitation.merchant_center.merchant_center_id = int(clean_id(args.merchant_id))
    req.product_link_invitation.type_ = client.enums.LinkedProductTypeEnum.MERCHANT_CENTER
    svc = client.get_service("ProductLinkInvitationService")
    items = [{"operation": "CREATE", "entity": "ProductLinkInvitation", "type": "MERCHANT_CENTER",
              "merchant_id": clean_id(args.merchant_id),
              "note": "Merchant Center admin must approve before the link is active"}]
    try:
        run_mutation(customer_id=cid, operations=[req], change_items=items, apply=args.apply,
                     checksum=args.checksum, validate_fn=lambda: None,  # this endpoint has no validate_only
                     commit_fn=lambda: {"invitation": svc.create_product_link_invitation(request=req)
                                        .product_link_invitation.resource_name})
        return 0
    except SafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {format_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
