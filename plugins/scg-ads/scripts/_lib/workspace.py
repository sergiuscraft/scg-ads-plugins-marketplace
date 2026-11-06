"""Per-account workspace folders. The account does NOT have to be in config.toml.

<root>/<label or customer id>/
    account.toml        non-secret: customer_id, login_customer_id, name, created
    account-brief.md    from templates/ (created once)
    changelog.md        append-only log of approved changes
    out/                keyword CSVs, ads.csv, update reports
    campaigns/          one subfolder per campaign (campaign-brief.md etc.)
    creatives/          generated or supplied images/video

Root: [workspace].root in config.toml (default ~/ads-workspaces). Keep it outside git: it holds
business data. Contains no credentials.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import config

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
SUBDIRS = ("out", "campaigns", "creatives")


def root(cfg: dict | None = None) -> Path:
    cfg = config.load() if cfg is None else cfg
    return Path(config.get(cfg, "workspace", "root", "~/ads-workspaces")).expanduser()


def folder_name(ref: str | None, cfg: dict) -> tuple[str, str]:
    """-> (folder name, customer_id). Configured account -> its label; otherwise the bare id."""
    acc = config.find_account(cfg, ref)
    if acc:
        label = re.sub(r"[^A-Za-z0-9._-]+", "-", str(acc.get("label") or acc["customer_id"])).strip("-")
        return label or config.digits(acc["customer_id"]), config.digits(acc["customer_id"])
    cid = config.digits(ref)
    if not cid:
        raise config.ConfigError(f"Cannot work out an account from {ref!r}; give a label or a customer id.")
    return cid, cid


def _q(s) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def ensure(ref: str | None, cfg: dict | None = None, name: str = "", login: str = "") -> Path:
    cfg = config.load() if cfg is None else cfg
    folder, cid = folder_name(ref, cfg)
    base = root(cfg) / folder
    base.mkdir(parents=True, exist_ok=True)
    for d in SUBDIRS:
        (base / d).mkdir(exist_ok=True)
    acc = config.find_account(cfg, ref) or {}
    meta = base / "account.toml"
    if not meta.exists():
        meta.write_text(
            "# non-secret account info; edit login_customer_id if this account is reached through a manager\n"
            f"customer_id = {_q(cid)}\n"
            f"login_customer_id = {_q(config.digits(login) or config.digits(acc.get('login_customer_id')))}\n"
            f"name = {_q(name or acc.get('name', ''))}\n"
            f"created = {_q(dt.date.today().isoformat())}\n", encoding="utf-8")
    brief = base / "account-brief.md"
    if not brief.exists() and (TEMPLATES / "account-brief.md").exists():
        text = (TEMPLATES / "account-brief.md").read_text(encoding="utf-8")
        brief.write_text(text.replace("- Customer id / login (manager) id:", f"- Customer id / login (manager) id: {cid}"),
                         encoding="utf-8")
    log = base / "changelog.md"
    if not log.exists():
        log.write_text(f"# Changelog - {name or acc.get('name') or folder} ({cid})\n\n", encoding="utf-8")
    return base


def read_meta(cid: str, cfg: dict | None = None) -> dict:
    """account.toml of an unconfigured account (folder named by id), or {}."""
    cfg = config.load() if cfg is None else cfg
    meta = root(cfg) / config.digits(cid) / "account.toml"
    if not meta.exists() or config.tomllib is None:
        return {}
    with open(meta, "rb") as f:
        return config.tomllib.load(f)


def out_dir(ref: str | None, cfg: dict | None = None) -> Path:
    return ensure(ref, cfg) / "out"
