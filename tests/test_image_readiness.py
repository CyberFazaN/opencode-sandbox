"""Managed base-definition diagnostics, shared by doctor and dashboard (mocked Docker)."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_tui import run, settle
from typer.testing import CliRunner

from opencode_sandbox import cli, distros
from opencode_sandbox import core as c
from opencode_sandbox import readiness as r

LABEL = distros.LABEL


def response(stdout="", stderr="", rc=0):
    return SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


@pytest.fixture
def images(monkeypatch):
    distro = replace(distros.get(distros.DEFAULT), revision=2)
    monkeypatch.setitem(distros.REGISTRY, distro.id, distro)
    replies = {d.image: response(json.dumps({LABEL + "managed": "true", **d.image_labels()}))
               for d in distros.REGISTRY.values()}
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            result = replies[args[-1]]
            if isinstance(result, Exception):
                raise result
            return result
        assert args[:2] == ("system", "df"), args
        return response()

    monkeypatch.setattr(c, "docker", docker)
    monkeypatch.setattr(c, "docker_root", lambda: None)
    monkeypatch.setattr(r, "host_checks", list)
    return distro, replies, calls


def result(images):
    return next(check for check in r.image_checks() if check.id == f"image-{images[0].id}")


@pytest.mark.parametrize(("revision", "status", "detail"), [
    ("1", r.WARNING, "older than"), ("2", r.PASSED, "image revision 2"),
    ("3", r.WARNING, "newer than"),
])
def test_base_revision_comparison(images, revision, status, detail):
    distro, replies, calls = images
    labels = {LABEL + "managed": "true", **distro.image_labels(), LABEL + "image-revision": revision}
    replies[distro.image] = response(json.dumps(labels))
    check = result(images)
    assert check.status == status and detail in check.detail
    if revision == "1":
        assert check.hint == f"opencode-sandbox build --distro {distro.id}"
    elif revision == "3":
        assert "do not rebuild" in check.hint.lower() and "opencode-sandbox --version" in check.hint
    assert all(args[:2] == ("image", "inspect") for args in calls)
    assert calls[0][2:4] == ("--format", "{{json .Config.Labels}}")


@pytest.mark.parametrize("revision", [None, "", "0", "-1", "+2", "02", "2.0", " 2", "two", "٢", 2, True, "9" * 5000])
def test_missing_or_invalid_revision_is_not_current(images, revision):
    distro, replies, _ = images
    labels = {LABEL + "managed": "true", **distro.image_labels()}
    if revision is None:
        labels.pop(LABEL + "image-revision")
    else:
        labels[LABEL + "image-revision"] = revision
    replies[distro.image] = response(json.dumps(labels))
    check = result(images)
    assert check.status == r.WARNING and "revision" in check.detail and "cannot be verified" in check.detail
    assert f"opencode-sandbox build --distro {distro.id}" in check.hint


@pytest.mark.parametrize("labels", [None, {}, {LABEL + "image-revision": "2"},
                                     {LABEL + "managed": "false", LABEL + "distro": distros.DEFAULT},
                                     {LABEL + "managed": "true", LABEL + "distro": "other"}])
def test_unrecognized_labels_are_not_trusted(images, labels):
    distro, replies, _ = images
    replies[distro.image] = response(json.dumps(labels))
    check = result(images)
    assert check.status == r.WARNING and "cannot be verified" in check.detail
    assert "review" in check.hint.lower()


@pytest.mark.parametrize("version", [None, "", 12, "unexpected"])
def test_inconsistent_distribution_version_is_not_current(images, version):
    distro, replies, _ = images
    replies[distro.image] = response(json.dumps({LABEL + "managed": "true", **distro.image_labels(),
                                                LABEL + "distro-version": version}))
    check = result(images)
    assert check.status == r.WARNING and "distribution version" in check.detail


@pytest.mark.parametrize("error", ["Error: No such image: opencode-sandbox:debian",
                                    "Error response from daemon: No such image: opencode-sandbox:debian"])
def test_confirmed_missing_image_names_build_command(images, error):
    distro, replies, _ = images
    replies[distro.image] = response(stderr=error, rc=1)
    check = result(images)
    assert check.status == r.WARNING and check.detail.startswith("missing")
    assert check.hint == f"opencode-sandbox build --distro {distro.id}"


@pytest.mark.parametrize("error", ["Cannot connect to the Docker daemon", "permission denied", "", "template parsing error"])
def test_inspect_failure_is_not_a_missing_image(images, error):
    distro, replies, _ = images
    replies[distro.image] = response(stderr=error, rc=1)
    check = result(images)
    assert check.status == r.NOT_CHECKED and "inspect failed" in check.detail
    assert "missing" not in check.detail and "build" not in check.hint
    assert len(r.image_checks()) == len(distros.REGISTRY)


@pytest.mark.parametrize("stdout", ["", "not json", "[]", "42", '"labels"'])
def test_invalid_inspect_response_is_not_a_success(images, stdout):
    distro, replies, _ = images
    replies[distro.image] = response(stdout)
    check = result(images)
    assert check.status == r.NOT_CHECKED and "invalid" in check.detail.lower()
    assert "build" not in check.hint


def test_one_inspect_exception_does_not_hide_other_images(images):
    distro, replies, _ = images
    replies[distro.image] = c.SandboxError("Docker CLI disappeared")
    checks = r.image_checks()
    assert checks[0].status == r.NOT_CHECKED and "Docker CLI disappeared" in checks[0].detail
    assert checks[1].status == r.PASSED


@pytest.mark.parametrize("case", ["old", "missing", "inspect-error"])
def test_doctor_and_dashboard_share_nonblocking_image_report(images, case):
    distro, replies, calls = images
    if case == "old":
        replies[distro.image] = response(json.dumps({LABEL + "managed": "true", **distro.image_labels(),
                                                    LABEL + "image-revision": "1"}))
    else:
        replies[distro.image] = response(stderr="No such image: " + distro.image if case == "missing" else "permission denied", rc=1)
    expected = result(images)
    text = "\n".join(r.format_report({"checks": [vars(expected)]}))
    m = c.create("ocs-test-image-warning", "scratch")
    metadata = c.env_dir(m["id"]) / "metadata.json"
    before = metadata.read_bytes()
    out = CliRunner().invoke(cli.app, ["doctor"])
    assert out.exit_code == 0 and text in out.output, out.output

    async def test(app, pilot):
        await settle(pilot)
        notes = [n for n in app._notifications if n.title == "Base images need attention"]
        assert notes and text in notes[0].message
        assert not notes[0].markup and "opencode-sandbox doctor" in str(app.query_one("#status").render())
        assert app.query_one("#envs").row_count == 1 and metadata.read_bytes() == before
    run(test, size=(80, 24))
    assert all(args[:2] in (("image", "inspect"), ("system", "df")) for args in calls)


def test_dashboard_does_not_report_an_image_problem_when_current(images):
    async def test(app, pilot):
        await settle(pilot)
        assert not [n for n in app._notifications if n.title == "Base images need attention"]
    run(test)


def test_advisory_does_not_replace_an_operation_status_or_change_its_guard(images):
    check = result(images)

    async def test(app, pilot):
        await settle(pilot)
        app._operation_pending = True
        app._set_busy("Starting an existing environment")
        app._show_image_checks([check])
        assert app._operation_pending and str(app.query_one("#status").render()) == "Starting an existing environment"
    run(test)
