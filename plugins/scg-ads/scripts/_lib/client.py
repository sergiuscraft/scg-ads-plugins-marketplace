"""Google Ads client factory. Mirrors the auth used by the google-ads MCP fork
(ads_mcp/utils.py): Application Default Credentials + env vars. No secrets on disk here.

Env:
  GOOGLE_APPLICATION_CREDENTIALS   ADC json (authorized_user) with the adwords scope
  GOOGLE_ADS_DEVELOPER_TOKEN       optional here, required for Keyword Planner etc.
  GOOGLE_ADS_LOGIN_CUSTOMER_ID     manager account id (overridable with --login-customer)
"""

from __future__ import annotations

import os
import re

ADS_SCOPE = "https://www.googleapis.com/auth/adwords"


def clean_id(value) -> str:
    return re.sub(r"\D", "", str(value))


def get_client(login_customer_id=None):
    import google.auth
    from google.ads.googleads.client import GoogleAdsClient

    credentials, _ = google.auth.default(scopes=[ADS_SCOPE])
    args = {"credentials": credentials, "use_proto_plus": True}
    token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    if token:
        args["developer_token"] = token
    login = login_customer_id or os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    if login:
        args["login_customer_id"] = clean_id(login)
    return GoogleAdsClient(**args)


def gaql(client, customer_id: str, query: str):
    """Run a GAQL query, return list of rows."""
    service = client.get_service("GoogleAdsService")
    rows = []
    for batch in service.search_stream(customer_id=clean_id(customer_id), query=query):
        rows.extend(batch.results)
    return rows


def format_error(exc) -> str:
    """Readable text for GoogleAdsException, else str(exc)."""
    failure = getattr(exc, "failure", None)
    if failure is None:
        return str(exc)
    parts = []
    for err in failure.errors:
        parts.append(f"{err.error_code}: {err.message}")
    return "\n".join(parts) or str(exc)
