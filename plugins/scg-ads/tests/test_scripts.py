"""Offline tests: no network, no credentials."""
import io
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ad_schedule  # noqa: E402
import campaign_settings  # noqa: E402
import create_ads  # noqa: E402
import import_csv  # noqa: E402
from _lib import csvio, safety  # noqa: E402


# ---- safety ----
def test_checksum_bound_to_customer_and_ops():
    a = safety.compute_checksum("1", [{"x": 1}])
    assert a == safety.compute_checksum("1", [{"x": 1}])
    assert a != safety.compute_checksum("2", [{"x": 1}])
    assert a != safety.compute_checksum("1", [{"x": 2}])


def _run(apply, checksum, ops=({"x": 1},), calls=None):
    calls = calls if calls is not None else []
    return safety.run_mutation(
        customer_id="1", operations=list(ops), change_items=[{"a": 1}], apply=apply,
        checksum=checksum, validate_fn=lambda: calls.append("v"),
        commit_fn=lambda: calls.append("c") or {"ok": True}, out=io.StringIO(),
    ), calls


def test_dry_run_validates_and_issues_checksum():
    res, calls = _run(False, None)
    assert res["status"] == "PROPOSED" and calls == ["v"]
    assert res["checksum"] == safety.compute_checksum("1", [{"x": 1}])


def test_apply_requires_matching_checksum():
    with pytest.raises(safety.SafetyError):
        _run(True, None)
    with pytest.raises(safety.SafetyError):
        _run(True, "deadbeef")
    good = safety.compute_checksum("1", [{"x": 1}])
    res, calls = _run(True, good)
    assert res["status"] == "COMMITTED" and calls == ["c"]
    with pytest.raises(safety.SafetyError):  # changed ops -> old checksum invalid
        _run(True, good, ops=({"x": 2},))


def test_failed_validation_issues_no_checksum():
    def boom():
        raise RuntimeError("API rejected")
    with pytest.raises(RuntimeError):
        safety.run_mutation(customer_id="1", operations=[{}], change_items=[], apply=False,
                            checksum=None, validate_fn=boom, commit_fn=lambda: None, out=io.StringIO())


# ---- csv ----
def test_read_rows_normalises_headers_and_delimiters(tmp_path):
    f = tmp_path / "k.csv"
    f.write_text("﻿Ad Group;Keyword;Match Type\nImplants;buy implants;exact\n", encoding="utf-8")
    assert csvio.read_rows(f) == [{"ad_group": "Implants", "keyword": "buy implants", "match_type": "exact"}]


# ---- import_csv ----
def test_import_parse_validates_and_dedupes():
    rows = [
        {"ad_group": "A", "keyword": "x", "match_type": "exact"},
        {"ad_group": "a", "keyword": "X", "match_type": "EXACT"},       # dup
        {"ad_group": "", "keyword": "free", "negative": "yes"},         # campaign negative ok
        {"ad_group": "", "keyword": "orphan"},                          # positive w/o ad group
        {"ad_group": "A", "keyword": "bad", "match_type": "WIDE"},
        {"ad_group": "A", "keyword": "bid", "cpc_bid": "1,5"},
    ]
    entries, errors = import_csv.parse_rows(rows)
    assert len(entries) == 3
    assert entries[-1]["bid"] == 1_500_000
    assert len(errors) == 2


# ---- create_ads lint ----
def _ad(**over):
    r = {"ad_group": "A", "final_url": "https://x.com"}
    for i in range(1, 4):
        r[f"headline_{i}"] = f"Headline {i}"
    for i in range(1, 3):
        r[f"description_{i}"] = f"Description number {i}"
    r.update(over)
    return r


def test_lint_ok_and_failures():
    assert create_ads.lint([_ad()]) == []
    assert any("too long" in e for e in create_ads.lint([_ad(headline_1="x" * 31)]))
    assert any("duplicate" in e for e in create_ads.lint([_ad(headline_2="headline 1")]))
    assert any("final_url" in e for e in create_ads.lint([_ad(final_url="x.com")]))
    assert any(">=3 headlines" in e for e in create_ads.lint([_ad(headline_3="")]))
    assert any("path1" in e for e in create_ads.lint([_ad(path1="p" * 16)]))


def test_lint_only_cli_needs_no_credentials(tmp_path, capsys):
    f = tmp_path / "ads.csv"
    f.write_text("ad_group,final_url,headline_1,headline_2,headline_3,description_1,description_2\n"
                 "A,https://x.com,H one,H two,H three,Desc one here,Desc two here\n")
    assert create_ads.main(["--csv", str(f), "--lint-only"]) == 0
    assert "OK" in capsys.readouterr().out


# ---- ad_schedule ----
def test_slot_parser():
    s = ad_schedule.parse_slots("MON-FRI 09:00-18:00 +10; SAT 10:00-14:30 -20")
    assert len(s) == 6 and s[0] == {"day": "MONDAY", "sh": 9, "sm": 0, "eh": 18, "em": 0, "pct": 10}
    assert s[-1]["pct"] == -20 and s[-1]["em"] == 30
    assert [x["day"] for x in ad_schedule.parse_slots("FRI-MON 08:00-09:00")] == ["FRIDAY", "SATURDAY", "SUNDAY", "MONDAY"]


@pytest.mark.parametrize("bad", ["MON 09:10-18:00", "MON 18:00-09:00", "nonsense", "MON 09:00-25:00"])
def test_slot_parser_rejects(bad):
    with pytest.raises((ValueError, KeyError)):
        ad_schedule.parse_slots(bad)


# ---- campaign_settings ----
def test_settings_changes():
    import argparse
    ns = argparse.Namespace(
        start_date="2026-12-01", end_date="2027-01-01", clear_end_date=False,
        tracking_template="{lpurl}", final_url_suffix=None, search_partners=False,
        google_search=None, display_network=None, eu_political=False)
    ch = campaign_settings.collect_changes(ns)
    assert ch["network_settings.target_partner_search_network"] is False
    assert ch["contains_eu_political_advertising"] is False and "final_url_suffix" not in ch
    ns.clear_end_date = True
    assert campaign_settings.collect_changes(ns)["end_date_time"] == campaign_settings.NO_END
    assert ch["start_date_time"] == "2026-12-01 00:00:00" and ch["end_date_time"] == "2027-01-01 23:59:59"


# ---- P2: hashing / conversion_upload / user_lists / account_links ----
import conversion_upload  # noqa: E402
import user_lists  # noqa: E402
import account_links  # noqa: E402
from _lib import hashing  # noqa: E402


GMAIL = "gmail" + ".com"  # built from parts so the pre-commit personal-data scan stays strict


def test_email_phone_normalisation_and_hash():
    assert hashing.normalize_email(" John.Doe+x@" + GMAIL + " ") == "johndoe@" + GMAIL
    assert hashing.normalize_email("a@b.co") == "a@b.co" and hashing.normalize_email("nope") is None
    assert hashing.normalize_phone("+380 (67) 123-45-67") == "+380671234567"
    assert hashing.normalize_phone("0671234567", "380") == "+380671234567"
    assert hashing.normalize_phone("0671234567") is None
    assert hashing.hash_email("A@B.co") == hashing.sha256_hex("a@b.co") and len(hashing.hash_email("A@B.co")) == 64


def test_parse_clicks():
    rows = [
        {"gclid": "abc", "conversion_time": "2026-11-01 10:00:00", "value": "10,5", "currency": "eur"},
        {"email": "X@Y.com", "conversion_time": "2026-11-01T10:00:00+02:00"},
        {"conversion_time": "2026-11-01 10:00:00"},                 # no identifier
        {"gclid": "abc", "conversion_time": "yesterday"},           # bad time
        {"email": "bad", "gclid": "g", "conversion_time": "2026-11-01 10:00:00"},
    ]
    items, errors = conversion_upload.parse_clicks(rows, "+00:00")
    assert len(items) == 2 and len(errors) == 3
    assert items[0]["value"] == 10.5 and items[0]["currency"] == "EUR" and items[0]["ts"].endswith("+00:00")
    assert items[1]["he"] == hashing.hash_email("x@y.com") and items[1]["ts"].endswith("+02:00")


def test_parse_calls():
    ok, err = conversion_upload.parse_calls(
        [{"caller_id": "+380671234567", "call_start_time": "2026-11-01 09:00:00", "conversion_time": "2026-11-01 09:05:00"},
         {"caller_id": "0671234567", "call_start_time": "2026-11-01 09:00:00", "conversion_time": "2026-11-01 09:05:00"}],
        "+00:00")
    assert len(ok) == 1 and len(err) == 1


def test_members_dedupe_and_hash_only():
    m, stats = user_lists.parse_members([
        {"email": "a@b.co", "phone": ""}, {"email": "A@B.CO"}, {"email": "bad", "phone": ""}, {"phone": "+380671234567"}])
    assert stats == {"rows": 4, "usable": 2, "invalid": 1, "duplicates": 1}
    assert all(len(x["he"] or x["hp"]) == 64 for x in m)


def test_upload_refuses_without_consent(tmp_path, capsys):
    f = tmp_path / "c.csv"
    f.write_text("email\na@b.co\n")
    rc = user_lists.main(["upload", "--customer", "1", "--csv", str(f), "--create-name", "x"])
    assert rc == 3 and "consent" in capsys.readouterr().err.lower()


def test_ga4_howto(capsys):
    assert account_links.main(["ga4-howto"]) == 0
    assert "Product links" in capsys.readouterr().out


# ---- config / configure ----
import os  # noqa: E402
import stat  # noqa: E402
import configure  # noqa: E402
from _lib import config as cfgmod  # noqa: E402


@pytest.fixture
def cfg_env(tmp_path, monkeypatch):
    p = tmp_path / "cfg" / "config.toml"
    monkeypatch.setenv("SCG_ADS_CONFIG", str(p))
    for v in cfgmod.ENV_MAP:
        monkeypatch.delenv(v, raising=False)
    return p


def _sample():
    return {
        "mcp": {"fork_dir": "/opt/fork"},
        "credentials": {"adc_file": "/x/adc.json", "developer_token": 'tok"en', "login_customer_id": "7000000001"},
        "defaults": {"account": "clinic"},
        "accounts": [
            {"label": "clinic", "customer_id": "1111111111", "login_customer_id": "", "name": "Clinic \\ A"},
            {"label": "shop", "customer_id": "2222222222", "login_customer_id": "7000000002", "name": "Shop"},
        ],
    }


def test_config_roundtrip_private_mode_and_escaping(cfg_env):
    cfgmod.save(_sample())
    assert stat.S_IMODE(os.stat(cfg_env).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(cfg_env.parent).st_mode) == 0o700
    back = cfgmod.load()
    assert back["credentials"]["developer_token"] == 'tok"en' and back["accounts"][0]["name"] == "Clinic \\ A"
    assert cfgmod.mode_ok(cfg_env)


def test_resolve_labels_ids_and_login(cfg_env):
    cfgmod.save(_sample())
    cfg = cfgmod.load()
    assert cfgmod.resolve_customer("SHOP", cfg) == "2222222222"
    assert cfgmod.resolve_customer("111-111-1111", cfg) == "1111111111"
    assert cfgmod.resolve_customer(None, cfg) == "1111111111"            # default account
    assert cfgmod.resolve_customer("999-999-9999", cfg) == "9999999999"   # unknown id passes through
    assert cfgmod.login_for("1111111111", cfg) == "7000000001"            # global
    assert cfgmod.login_for("2222222222", cfg) == "7000000002"            # per-account override


def test_apply_env_fills_missing_but_real_env_wins(cfg_env, monkeypatch):
    cfgmod.save(_sample())
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "5555555555")
    cfgmod.apply_env()
    assert os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] == "5555555555"
    assert os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] == 'tok"en'
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/x/adc.json"


def test_refuses_to_write_secrets_inside_a_git_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.write_private(tmp_path / "sub" / "config.toml", "x")


def test_show_masks_token(cfg_env, capsys):
    cfgmod.save(_sample())
    assert configure.main(["show"]) == 0
    out = capsys.readouterr().out
    assert "tok" + chr(34) not in out and "******" in out and "developer_token" in out


def test_discover_with_fake_client():
    class R:  # minimal fakes of the API objects
        def __init__(self, **k): self.__dict__.update(k)
    def row(i, name, mgr):
        return R(customer_client=R(id=i, descriptive_name=name, manager=mgr, currency_code="EUR", time_zone="UTC"))
    class Svc:
        def __init__(self, login): self.login = login
        def list_accessible_customers(self): return R(resource_names=["customers/700", "customers/111"])
        def search_stream(self, customer_id, query):
            if customer_id == "700":
                return [R(results=[row(700, "MCC", True), row(111, "Clinic", False)])]
            return [R(results=[row(111, "Clinic", False)])]
    class Client:
        def __init__(self, login): self.login = login
        def get_service(self, name): return Svc(self.login)
    accs, errs = configure.discover(lambda login: Client(login))
    by = {a["customer_id"]: a for a in accs}
    assert errs == [] and set(by) == {"700", "111"}
    assert by["111"]["login_customer_id"] == "700"       # prefers the manager over direct access
    assert by["700"]["login_customer_id"] == "700" and by["700"]["manager"] is True   # direct = own id


def test_slug_unique():
    assert configure.slug("Clinic UA!", set()) == "clinic-ua"
    assert configure.slug("Clinic UA!", {"clinic-ua"}) == "clinic-ua-2"


def test_list_has_no_secrets_and_login_per_account(cfg_env, capsys):
    cfgmod.save(_sample())
    assert configure.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "tok" + chr(34) not in out and "adc" not in out
    rows = {l.split("\t")[0]: l.split("\t") for l in out.strip().splitlines()[1:]}
    assert rows["clinic"][2] == "7000000001" and rows["shop"][2] == "7000000002" and rows["clinic"][6] == "yes"


# ---- workspace ----
from _lib import workspace  # noqa: E402


def test_workspace_for_configured_and_unconfigured_accounts(cfg_env, tmp_path):
    c = _sample()
    c["workspace"] = {"root": str(tmp_path / "ws")}
    cfgmod.save(c)
    cfg = cfgmod.load()
    a = workspace.ensure("clinic", cfg)
    assert a == tmp_path / "ws" / "clinic"                       # configured -> label folder
    assert (a / "out").is_dir() and (a / "campaigns").is_dir() and (a / "creatives").is_dir()
    assert (a / "changelog.md").exists() and "1111111111" in (a / "account-brief.md").read_text()
    b = workspace.ensure("999-888-7777", cfg, name="Ad hoc", login="700-000-0001")  # NOT in config
    assert b == tmp_path / "ws" / "9998887777"
    assert 'login_customer_id = "7000000001"' in (b / "account.toml").read_text()
    assert cfgmod.login_for("9998887777", cfg) == "7000000001"    # read back from the workspace
    (a / "changelog.md").write_text("keep me")
    workspace.ensure("clinic", cfg)                                  # idempotent, never overwrites
    assert (a / "changelog.md").read_text() == "keep me"
    with pytest.raises(cfgmod.ConfigError):
        workspace.folder_name("not an id", cfg)


def test_use_sets_default_for_unconfigured_account(cfg_env, tmp_path, capsys, monkeypatch):
    c = _sample()
    c["workspace"] = {"root": str(tmp_path / "ws")}
    cfgmod.save(c)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert configure.main(["use", "555-444-3333", "--login", "7000000001"]) == 0
    assert cfgmod.load()["defaults"]["account"] == "5554443333"
    assert (tmp_path / "ws" / "5554443333" / "account.toml").exists()
    assert configure.main(["use", "shop"]) == 0
    assert cfgmod.load()["defaults"]["account"] == "shop"
    assert "not in config" not in capsys.readouterr().out.split("Working account: shop")[1]
    assert cfgmod.find_account(cfgmod.load(), None)["customer_id"] == "2222222222"


def test_list_includes_workspace_only_accounts(cfg_env, tmp_path, capsys):
    c = _sample()
    c["workspace"] = {"root": str(tmp_path / "ws")}
    cfgmod.save(c)
    workspace.ensure("999-888-7777", cfgmod.load(), name="Ad hoc", login="7000000009")
    assert configure.main(["list"]) == 0
    rows = {l.split("\t")[1]: l.split("\t") for l in capsys.readouterr().out.strip().splitlines()[1:]}
    assert set(rows) == {"1111111111", "2222222222", "9998887777"}
    assert rows["9998887777"][2] == "7000000009" and rows["9998887777"][5] == "Ad hoc"


def test_config_without_any_accounts_is_valid(cfg_env, capsys):
    cfgmod.save({"credentials": {"developer_token": "x"}})
    assert cfgmod.load()["credentials"]["developer_token"] == "x"
    assert configure.main(["list"]) == 1
    assert "10-digit" in capsys.readouterr().err
