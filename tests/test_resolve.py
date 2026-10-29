"""Environment lookup must never select an environment the user
did not name. Exact id, then exact name, then a unique id prefix of at least 6 hex characters."""
import json

import pytest
from typer.testing import CliRunner

from opencode_sandbox import core as c
from opencode_sandbox.cli import app


def _env(name, eid=None):
    m = c.create(name, "scratch")
    if eid is None:
        return m
    old = c.env_dir(m["id"])
    m["id"] = eid
    old.rename(c.env_dir(eid))
    c.save(m)
    return m


def test_empty_key_is_refused(tmp_path):
    _env("only-one")
    with pytest.raises(c.SandboxError, match="empty"):
        c.resolve("")


@pytest.mark.parametrize("key", ["a", "ab", "abc", "abcd", "abcde"])
def test_short_id_prefixes_are_refused(key):
    _env("target", "abcdef0123456789")
    with pytest.raises(c.SandboxError, match="not found"):
        c.resolve(key)


def test_unique_prefix_of_six_hex_characters_is_accepted():
    m = _env("target", "abcdef0123456789")
    assert c.resolve("abcdef")["id"] == m["id"]
    assert c.resolve("abcdef0123456789")["id"] == m["id"]


def test_ambiguous_prefix_is_refused():
    _env("one", "abcdef0000000001")
    _env("two", "abcdef0000000002")
    with pytest.raises(c.SandboxError, match="ambiguous"):
        c.resolve("abcdef")


def test_stale_hex_like_name_does_not_select_another_environment():
    """`delete cafe --yes` after cafe is gone must not hit an environment whose id starts so."""
    _env("other", "cafe000000000001")
    for stale in ("cafe", "42", "c"):
        with pytest.raises(c.SandboxError, match="not found"):
            c.resolve(stale)


def test_exact_name_wins_over_an_id_prefix():
    _env("other", "deadbe0000000001")
    named = _env("deadbe", "1111110000000001")
    assert c.resolve("deadbe")["id"] == named["id"]


def test_name_equal_to_another_id_does_not_block_that_environment():
    victim = _env("victim", "0123456789abcdef")
    m = c.create("placeholder", "scratch")
    m["name"] = victim["id"]  # written by hand: creation refuses such names
    c.save(m)
    assert c.resolve(victim["id"])["name"] == "victim"


def test_new_names_shaped_like_an_id_are_refused():
    with pytest.raises(c.SandboxError, match="looks like an environment id"):
        c.create("0123456789abcdef", "scratch")
    m = c.create("fine", "scratch")
    with pytest.raises(c.SandboxError, match="looks like an environment id"):
        c.promote(m, "scratch", "fedcba9876543210")


def test_key_is_not_a_pattern_or_path():
    _env("target", "abcdef0123456789")
    for key in ("ABCDEF", "abcdef*", "../abcdef0123456789", " abcdef"):
        with pytest.raises(c.SandboxError):
            c.resolve(key)


def test_cli_delete_with_an_empty_name_refuses_and_keeps_the_environment():
    m = _env("only-one")
    result = CliRunner().invoke(app, ["delete", "", "--yes"])
    assert result.exit_code != 0
    assert "empty" in str(result.exception)
    meta = json.loads((c.env_dir(m["id"]) / "metadata.json").read_text())
    assert meta["name"] == "only-one" and meta["status"] != "deleting"


def test_cli_delete_with_a_stale_short_name_refuses():
    m = _env("other", "cafe000000000001")
    result = CliRunner().invoke(app, ["delete", "cafe", "--yes"])
    assert result.exit_code != 0 and "not found" in str(result.exception)
    assert (c.env_dir(m["id"]) / "metadata.json").exists()
