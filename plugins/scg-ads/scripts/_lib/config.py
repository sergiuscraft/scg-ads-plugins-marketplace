"""User config for scg-ads: ONE TOML file outside any repository, mode 600.

Default path: ~/.config/scg-ads/config.toml   (override: SCG_ADS_CONFIG)

It holds paths and ids so nothing has to be typed into chat or exported by
hand. Real environment variables always win over the file. The OAuth refresh token lives in a
separate adc.json (mode 600) that `configure.py login` writes.

Schema (see config.example.toml):
  [mcp]          fork_dir
  [credentials]  adc_file, login_customer_id
  [defaults]     account            # the account you work with now: label or any customer id
  [workspace]    root               # per-account folders (default ~/ads-workspaces)
  [[accounts]]   label, customer_id, login_customer_id, name, currency, time_zone, notes
"""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    tomllib = None

ENV_MAP = {
    "GOOGLE_APPLICATION_CREDENTIALS": ("credentials", "adc_file"),
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID": ("credentials", "login_customer_id"),
    "GOOGLE_ADS_MCP_FORK_DIR": ("mcp", "fork_dir"),
}


class ConfigError(RuntimeError):
    pass


def config_path() -> Path:
    return Path(os.environ.get("SCG_ADS_CONFIG") or "~/.config/scg-ads/config.toml").expanduser()


def default_adc_path() -> Path:
    return config_path().parent / "adc.json"


def digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def load(path: Path | None = None) -> dict:
    p = Path(path) if path else config_path()
    if not p.exists():
        return {}
    if tomllib is None:
        raise ConfigError("Python 3.11+ is required to read the config (run scripts with `uv run`).")
    with open(p, "rb") as f:
        return tomllib.load(f)


def get(cfg: dict, section: str, key: str, default=None):
    value = (cfg.get(section) or {}).get(key)
    return default if value in (None, "") else value


def apply_env(cfg: dict | None = None) -> dict:
    """Fill os.environ from the config for variables that are not already set. Returns cfg."""
    cfg = load() if cfg is None else cfg
    for var, (section, key) in ENV_MAP.items():
        if os.environ.get(var):
            continue
        value = get(cfg, section, key)
        if value:
            os.environ[var] = str(Path(value).expanduser()) if var in (
                "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_ADS_MCP_FORK_DIR") else str(value)
    return cfg


def accounts(cfg: dict) -> list[dict]:
    return list(cfg.get("accounts") or [])


def find_account(cfg: dict, ref: str | None) -> dict | None:
    """ref = label (case-insensitive), customer id (any format) or None -> default account."""
    ref = ref or get(cfg, "defaults", "account")
    if not ref:
        return None
    for a in accounts(cfg):
        if str(a.get("label", "")).lower() == str(ref).lower() or (
            digits(ref) and digits(a.get("customer_id")) == digits(ref)
        ):
            return a
    return None


def resolve_customer(ref: str | None, cfg: dict | None = None) -> str | None:
    """Label / id / None -> 10-digit customer id (or the digits given if unknown)."""
    cfg = load() if cfg is None else cfg
    acc = find_account(cfg, ref)
    if acc:
        return digits(acc["customer_id"])
    return digits(ref) or None


def login_for(customer_id: str, cfg: dict | None = None) -> str | None:
    cfg = load() if cfg is None else cfg
    acc = find_account(cfg, customer_id)
    if acc and acc.get("login_customer_id"):
        return digits(acc["login_customer_id"])
    if not acc:  # unconfigured account: login may live in its workspace/account.toml
        from . import workspace
        meta = workspace.read_meta(customer_id, cfg)
        if digits(meta.get("login_customer_id")):
            return digits(meta["login_customer_id"])
    return digits(get(cfg, "credentials", "login_customer_id")) or None


# ---------- writing ----------
def _q(s) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(cfg: dict) -> str:
    lines = [
        "# scg-ads config - managed by `configure.py`, safe to edit by hand.",
        "# Keep this file private (mode 600). Never commit or paste it anywhere.",
        "",
        "[mcp]",
        f"fork_dir = {_q(get(cfg, 'mcp', 'fork_dir', ''))}   # your clone of the google-ads-mcp fork",
        "",
        "[credentials]",
        f"adc_file = {_q(get(cfg, 'credentials', 'adc_file', ''))}   # written by `configure.py login`",
        f"login_customer_id = {_q(get(cfg, 'credentials', 'login_customer_id', ''))}   # your manager (MCC) id, digits only",
        "",
        "[defaults]",
        f"account = {_q(get(cfg, 'defaults', 'account', ''))}   # the account you are working with now: label or any customer id (`configure.py use`)",
        "",
        "[workspace]",
        f"root = {_q(get(cfg, 'workspace', 'root', '~/ads-workspaces'))}   # one folder per account: briefs, CSVs, changelog",
    ]
    for a in accounts(cfg):
        lines += ["", "[[accounts]]"]
        for k in ("label", "customer_id", "login_customer_id", "name", "currency", "time_zone", "notes"):
            lines.append(f"{k} = {_q(a.get(k, ''))}")
    return "\n".join(lines) + "\n"


def _inside_git_repo(path: Path) -> bool:
    for parent in [path.parent, *path.parent.parents]:
        if (parent / ".git").exists():
            return True
    return False


def write_private(path: Path, text: str, allow_in_repo: bool = False) -> None:
    path = Path(path).expanduser()
    if _inside_git_repo(path.resolve()) and not allow_in_repo:
        raise ConfigError(f"{path} is inside a git repository. Keep secrets outside repos "
                          "(default ~/.config/scg-ads/) or pass --allow-in-repo.")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def save(cfg: dict, path: Path | None = None, allow_in_repo: bool = False) -> Path:
    p = Path(path) if path else config_path()
    write_private(p, render(cfg), allow_in_repo)
    return p


def mode_ok(path: Path) -> bool:
    try:
        return stat.S_IMODE(os.stat(path).st_mode) & 0o077 == 0
    except OSError:
        return False
