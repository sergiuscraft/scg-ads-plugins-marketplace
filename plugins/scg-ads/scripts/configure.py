#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-ads>=33", "google-auth", "google-auth-oauthlib"]
# ///
"""Set up scg-ads WITHOUT the agent: keys and accounts never pass through the chat.

  configure.py init                       interactive wizard (does everything below in order)
  configure.py login --client-secret FILE sign in with Google in your browser; writes adc.json (mode 600)
  configure.py accounts                   (optional) discover accessible accounts from the API and save labels
  configure.py check                      verify file modes, credentials, MCP server, one read call
  configure.py show                       print the config (it holds no secrets, only paths and ids)
  configure.py list                       accounts table (label, id, login id) - contains no secrets
  configure.py use [LABEL|ID]             choose the account you work with now (id need not be in the config)
  configure.py workspace [--customer X]   create/print that account's folder (briefs, CSVs, changelog)
  configure.py path                       print the config file location

Config: ~/.config/scg-ads/config.toml (override with SCG_ADS_CONFIG). Created with mode 600
outside any git repository. See docs/CREDENTIALS.md for how to obtain every value.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import config as cfgmod  # noqa: E402

ADS_SCOPE = "https://www.googleapis.com/auth/adwords"


# ---------------- helpers ----------------
def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default and not secret else (" [keep current]" if default and secret else "")
    text = (getpass.getpass if secret else input)(f"{prompt}{suffix}: ").strip()
    return text or default


def yes(prompt: str, default: bool = True) -> bool:
    ans = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not ans else ans.startswith("y")


def load_cfg() -> dict:
    cfg = cfgmod.load()
    for sec in ("mcp", "credentials", "defaults"):
        cfg.setdefault(sec, {})
    cfg.setdefault("accounts", [])
    return cfg


def save_cfg(cfg: dict) -> None:
    p = cfgmod.save(cfg)
    print(f"Saved {p} (mode 600)")


# ---------------- login ----------------
def write_adc(client_secret_file: Path, out: Path, port: int = 0) -> Path:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes=[ADS_SCOPE])
    creds = flow.run_local_server(port=port, access_type="offline", prompt="consent",
                                  authorization_prompt_message="Open this URL if the browser did not open:\n{url}\n")
    if not creds.refresh_token:
        raise SystemExit("Google returned no refresh token. Revoke the app at "
                         "https://myaccount.google.com/permissions and run login again.")
    payload = dict(type="authorized_user", client_id=creds.client_id,
                   client_secret=creds.client_secret, refresh_token=creds.refresh_token)
    cfgmod.write_private(out, json.dumps(payload, indent=2) + "\n")
    return out


def cmd_login(args) -> int:
    src = Path(args.client_secret).expanduser()
    if not src.is_file():
        print(f"Not found: {src}. Download the OAuth client JSON first (docs/CREDENTIALS.md step 3).", file=sys.stderr)
        return 2
    out = Path(args.out).expanduser() if args.out else cfgmod.default_adc_path()
    write_adc(src, out)
    cfg = load_cfg()
    cfg["credentials"]["adc_file"] = str(out)
    save_cfg(cfg)
    print(f"Credentials written to {out} (mode 600).")
    print("You can now delete the downloaded client_secret file; it is not needed any more.")
    return 0


# ---------------- accounts ----------------
def discover(client_factory) -> tuple[list[dict], list[str]]:
    """Return (accounts, errors). client_factory(login_id|None) -> GoogleAdsClient."""
    found: dict[str, dict] = {}
    errors: list[str] = []
    base = client_factory(None)
    ids = [cfgmod.digits(r.split("/")[-1]) for r in
           base.get_service("CustomerService").list_accessible_customers().resource_names]
    q = ("SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, "
         "customer_client.level, customer_client.currency_code, customer_client.time_zone, "
         "customer_client.status FROM customer_client WHERE customer_client.status = 'ENABLED'")
    for top in ids:
        try:
            cl = client_factory(top)
            svc = cl.get_service("GoogleAdsService")
            for batch in svc.search_stream(customer_id=top, query=q):
                for row in batch.results:
                    c = row.customer_client
                    cid = str(c.id)
                    entry = {"customer_id": cid, "name": c.descriptive_name, "currency": c.currency_code,
                             "time_zone": c.time_zone, "manager": bool(c.manager),
                             "login_customer_id": top}  # direct access => the account's own id
                    # prefer reaching a client through its manager over direct access
                    if cid not in found or (found[cid]["login_customer_id"] == cid and top != cid):
                        found[cid] = entry
        except Exception as exc:  # noqa: BLE001
            msg = getattr(getattr(exc, "failure", None), "errors", None)
            errors.append(f"{top}: {msg[0].message if msg else exc}")
    return list(found.values()), errors


def slug(name: str, taken: set[str]) -> str:
    import re
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "account"
    out, i = base, 2
    while out in taken:
        out, i = f"{base}-{i}", i + 1
    return out


def cmd_accounts(args) -> int:
    from _lib.client import get_client
    cfg = load_cfg()
    print("Discovering accounts via the Google Ads API...")
    accs, errors = discover(lambda login: get_client(login))
    for e in errors:
        print(f"  skipped {e}")
    if not accs:
        print("No accounts found. Check credentials: configure.py check", file=sys.stderr)
        return 1
    clients = [a for a in accs if not a["manager"]] or accs
    print("\nReachable accounts:")
    for i, a in enumerate(accs, 1):
        kind = "manager" if a["manager"] else "client "
        print(f"  {i:>2}. {a['customer_id']}  {kind}  {a['name'] or '(no name)'}  {a['currency']} {a['time_zone']}"
              f"{'  via ' + a['login_customer_id'] if a['login_customer_id'] != a['customer_id'] else '  direct'}")
    raw = ask("\nNumbers to save (comma separated, Enter = all client accounts)", "")
    chosen = [accs[int(x) - 1] for x in raw.replace(" ", "").split(",") if x.isdigit() and 0 < int(x) <= len(accs)] \
        if raw else clients
    labels = {a.get("label") for a in cfg["accounts"] if a.get("label")}
    existing = {cfgmod.digits(a["customer_id"]): a for a in cfg["accounts"]}
    for a in chosen:
        old = existing.get(a["customer_id"])
        if old:
            old.update({k: a[k] for k in ("name", "currency", "time_zone", "login_customer_id")})
        else:
            label = ask(f"Label for {a['customer_id']} ({a['name']})", slug(a["name"], labels))
            labels.add(label)
            cfg["accounts"].append({"label": label, "customer_id": a["customer_id"],
                                    "login_customer_id": a["login_customer_id"], "name": a["name"],
                                    "currency": a["currency"], "time_zone": a["time_zone"], "notes": ""})
    mgrs = [a for a in accs if a["manager"] and not a["login_customer_id"]]
    if not cfg["credentials"].get("login_customer_id") and len(mgrs) == 1:
        cfg["credentials"]["login_customer_id"] = mgrs[0]["customer_id"]
        print(f"Login (manager) id set to {mgrs[0]['customer_id']}")
    if cfg["accounts"]:
        labels_list = [a["label"] for a in cfg["accounts"]]
        cur = cfg["defaults"].get("account") or labels_list[0]
        cfg["defaults"]["account"] = ask(f"Default account {labels_list}", cur)
    save_cfg(cfg)
    return 0


# ---------------- check ----------------
def cmd_check(args) -> int:
    ok = True

    def line(good: bool, msg: str, fix: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} {msg}" + (f"\n       -> {fix}" if not good and fix else ""))

    p = cfgmod.config_path()
    line(p.exists(), f"config file {p}", "run: configure.py init")
    if not p.exists():
        return 1
    line(cfgmod.mode_ok(p), "config file is private (mode 600)", f"chmod 600 {p}")
    cfg = load_cfg()
    adc = Path(str(cfg["credentials"].get("adc_file", ""))).expanduser()
    line(adc.is_file(), "OAuth credentials file (adc_file)", "run: configure.py login --client-secret <file>")
    if adc.is_file():
        line(cfgmod.mode_ok(adc), "adc.json is private (mode 600)", f"chmod 600 {adc}")
    line(bool(cfgmod.digits(cfg["credentials"].get("login_customer_id"))), "login (manager) customer id set",
         "your manager (MCC) id, digits: edit config.toml or run configure.py init")
    fork = Path(str(cfg["mcp"].get("fork_dir", ""))).expanduser()
    line((fork / "ads_mcp").is_dir(), f"MCP fork directory has ads_mcp/ ({fork})",
         "git clone https://github.com/sergiuscraft/google-ads-mcp.git and set [mcp].fork_dir")
    if not ok:
        print("\nFix the items above, then run check again.")
        return 1
    try:
        from _lib.client import get_client
        ids = get_client(None).get_service("CustomerService").list_accessible_customers().resource_names
        line(True, f"Google Ads API read works ({len(ids)} accessible customers)")
    except Exception as exc:  # noqa: BLE001
        failure = getattr(exc, "failure", None)
        text = failure.errors[0].message if failure and failure.errors else str(exc)
        line(False, f"Google Ads API read: {text[:200]}", "see docs/CREDENTIALS.md > Troubleshooting")
        return 1
    if args.mcp:
        smoke = Path(__file__).resolve().parents[3] / "tools" / "smoke_mcp.py"
        if smoke.exists():
            r = subprocess.run([str(smoke)], capture_output=True, text=True)
            line(r.returncode == 0, "MCP server starts and answers (tools/smoke_mcp.py)", r.stdout[-300:] + r.stderr[-300:])
    print("\nAll good." if ok else "")
    return 0 if ok else 1


# ---------------- show / path ----------------
def cmd_show(args) -> int:
    cfg = load_cfg()
    shown = json.loads(json.dumps(cfg))
    print(f"# {cfgmod.config_path()}")
    print(cfgmod.render(shown), end="")
    return 0


def known_accounts(cfg: dict) -> list[dict]:
    """Accounts from config.toml (optional) PLUS every account that already has a workspace folder."""
    from _lib import workspace
    out = [dict(a) for a in cfg["accounts"]]
    seen = {cfgmod.digits(a["customer_id"]) for a in out}
    root = workspace.root(cfg)
    if root.is_dir():
        for d in sorted(root.iterdir()):
            meta = d / "account.toml"
            if d.is_dir() and meta.is_file():
                m = workspace.read_meta(d.name, cfg) if d.name.isdigit() else _read_toml(meta)
                cid = cfgmod.digits(m.get("customer_id") or d.name)
                if cid and cid not in seen:
                    seen.add(cid)
                    out.append({"label": cid, "customer_id": cid, "login_customer_id": m.get("login_customer_id", ""),
                                "name": m.get("name", ""), "currency": "", "time_zone": ""})
    return out


def _read_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return cfgmod.tomllib.load(f)


def cmd_list(args) -> int:
    """Non-secret account table for humans AND the agent: label, id, login id to pass to MCP tools."""
    cfg = load_cfg()
    accs = known_accounts(cfg)
    default = cfgmod.find_account(cfg, None)
    default_id = cfgmod.digits(default["customer_id"]) if default else cfgmod.digits(cfgmod.get(cfg, "defaults", "account"))
    if not accs:
        print("No accounts yet. Choose one by its 10-digit id: configure.py use 123-456-7890", file=sys.stderr)
        return 1
    print("label\tcustomer_id\tlogin_customer_id\tcurrency\ttime_zone\tname\tdefault")
    for a in accs:
        cid = cfgmod.digits(a["customer_id"])
        login = cfgmod.digits(a.get("login_customer_id")) or cfgmod.login_for(cid, cfg) or ""
        print("\t".join([a.get("label", ""), cid, login, a.get("currency", ""), a.get("time_zone", ""),
                         a.get("name", ""), "yes" if cid == default_id else ""]))
    return 0


def cmd_use(args) -> int:
    """Choose the account you are working with. Works for accounts that are NOT in the config too."""
    from _lib import workspace
    cfg = load_cfg()
    ref = args.account
    if not ref:
        cmd_list(args)
        ref = ask("\nAccount label or any customer id")
    try:
        folder, cid = workspace.folder_name(ref, cfg)
    except cfgmod.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    known = cfgmod.find_account(cfg, ref)
    login = args.login or ""
    if not known and not login and sys.stdin.isatty():
        login = ask("Manager (login) id for this account, digits (Enter = use [credentials].login_customer_id)", "")
    base = workspace.ensure(ref, cfg, name=args.name or "", login=login)
    cfg["defaults"]["account"] = folder if known else cid
    save_cfg(cfg)
    print(f"Working account: {folder} ({cid}){'' if known else '  [not in config - fine]'}")
    print(f"Workspace folder: {base}")
    return 0


def cmd_workspace(args) -> int:
    from _lib import workspace
    cfg = load_cfg()
    ref = args.customer or cfgmod.get(cfg, "defaults", "account")
    if not ref:
        print("No account given and no default. Run: configure.py use", file=sys.stderr)
        return 2
    try:
        print(workspace.ensure(ref, cfg, name=args.name or "", login=args.login or ""))
    except cfgmod.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_path(args) -> int:
    print(cfgmod.config_path())
    return 0


# ---------------- init wizard ----------------
def cmd_init(args) -> int:
    cfg = load_cfg()
    print(f"scg-ads setup. Config file: {cfgmod.config_path()}\nNothing you type here goes to any chat.\n")
    print("Step 1/4 - MCP server (fork)")
    cur = cfg["mcp"].get("fork_dir", "")
    fork = Path(ask("Path to your clone of google-ads-mcp", cur)).expanduser()
    if fork and not (fork / "ads_mcp").is_dir():
        print("  That folder has no ads_mcp/. Clone first:\n    git clone https://github.com/sergiuscraft/google-ads-mcp.git")
        if not yes("  Continue anyway?", False):
            return 1
    cfg["mcp"]["fork_dir"] = str(fork)

    print("\nStep 2/4 - Google sign-in (OAuth)")
    adc = Path(str(cfg["credentials"].get("adc_file") or cfgmod.default_adc_path())).expanduser()
    if adc.is_file() and not yes(f"  {adc} exists. Sign in again?", False):
        cfg["credentials"]["adc_file"] = str(adc)
    else:
        cs = ask("  Path to the downloaded OAuth client JSON (Enter to skip)", "")
        if cs:
            write_adc(Path(cs).expanduser(), adc)
            cfg["credentials"]["adc_file"] = str(adc)
            print(f"  Saved {adc}")
        else:
            print("  Skipped. Later: configure.py login --client-secret <file>   (docs/CREDENTIALS.md)")

    print("\nStep 3/4 - Manager (MCC) customer id")
    cfg["credentials"]["login_customer_id"] = cfgmod.digits(ask(
        "  Manager account id, digits (Enter to detect later)", cfg["credentials"].get("login_customer_id", "")))
    save_cfg(cfg)

    print("\nStep 4/4 - Accounts (optional; keys above are the important part)")
    ids = ask("  10-digit customer id(s) you work with, comma separated (Enter = skip)", "")
    for raw in [x for x in ids.split(",") if cfgmod.digits(x)]:
        ns = argparse.Namespace(account=raw.strip(), name="", login="")
        cmd_use(ns)
    if not ids and cfg["credentials"].get("adc_file") and yes("  Or discover accounts from the API now?", False):
        cmd_accounts(args)
    print("\nDone. Verify with:  configure.py check --mcp")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("init")
    lg = sub.add_parser("login")
    lg.add_argument("--client-secret", required=True)
    lg.add_argument("--out")
    sub.add_parser("accounts")
    ck = sub.add_parser("check")
    ck.add_argument("--mcp", action="store_true", help="also start the MCP server and call it")
    sub.add_parser("show")
    sub.add_parser("list", help="accounts table without secrets (safe to show the agent)")
    sub.add_parser("path")
    us = sub.add_parser("use", help="choose the account you work with now (any id; config entry optional)")
    us.add_argument("account", nargs="?")
    us.add_argument("--name")
    us.add_argument("--login", help="manager id for an account that is not in the config")
    ws = sub.add_parser("workspace", help="create/print the folder for an account (prints only the path)")
    ws.add_argument("--customer")
    ws.add_argument("--name")
    ws.add_argument("--login")
    args = p.parse_args(argv)
    handlers = {"init": cmd_init, "login": cmd_login, "accounts": cmd_accounts,
                "check": cmd_check, "show": cmd_show, "list": cmd_list, "use": cmd_use, "workspace": cmd_workspace, "path": cmd_path, None: cmd_init}
    try:
        return handlers[args.cmd](args)
    except cfgmod.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
