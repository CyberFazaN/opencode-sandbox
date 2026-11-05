"""Real campaign: the manager against the real rootless Docker daemon, real OpenCode and
real terminals. Opt-in: `OCS_TEST_DOCKER=1 pytest tests/integration` (otherwise every test is
reported as skipped). Everything runs as subprocesses in an isolated data and configuration
directory under `.work/<run-id>/`; names start with `ocs-test-`; every created object is written
to `.work/logs/<run-id>-manifest.txt`; the session ends with `delete` of this run's environments
and the product's `disk cleanup --yes` behind a guard, then a leak check.

Environment: OCS_TEST_RUN (run id, default run-<UTC time>), OCS_TEST_DISTROS (default
"debian arch")."""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from campaign import ENABLED, Campaign


def pytest_collection_modifyitems(config, items):
    here = Path(__file__).parent
    for item in items:
        if here in Path(item.fspath).parents:
            item.add_marker(pytest.mark.docker)
            if not ENABLED:
                item.add_marker(pytest.mark.skip(reason="real campaign: set OCS_TEST_DOCKER=1"))


def pytest_configure(config):
    config.addinivalue_line("markers", "docker: real rootless Docker campaign (tests/integration, OCS_TEST_DOCKER=1)")
    # Without the real campaign the terminal modules skip themselves when pyte is missing (hosted CI);
    # with it, a missing pyte would silently skip the terminal rows: refuse to start instead.
    if ENABLED:
        try:
            import pyte  # noqa: F401
        except ImportError:
            raise pytest.UsageError("the real campaign needs pyte: pip install pyte") from None


class Checks:
    """Soft checks: every result is logged (PASS/FAIL) and the test fails at its end, so one
    failed expectation does not hide the remaining ones."""
    def __init__(self, camp, test):
        self.camp, self.test, self.failed = camp, test, []

    def __call__(self, ok, what):
        self.camp.log(("PASS " if ok else "FAIL ") + f"[{self.test}] {what}")
        if not ok:
            self.failed.append(what)
        return ok


@pytest.fixture
def checks(campaign, request):
    ck = Checks(campaign, request.node.name)
    campaign.log(f"===== {request.node.name}")
    yield ck
    assert ck.failed == [], ck.failed


@pytest.fixture(scope="session")
def campaign():
    run = os.environ.get("OCS_TEST_RUN") or "run-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    camp = Campaign(run)
    camp.ocs("doctor")
    images = lambda: sorted(camp.docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}").stdout.splitlines())
    before = images()
    camp.note("images before: " + "; ".join(before))
    yield camp
    guard, left = camp.finish()
    after = images()
    camp.note("images after: " + "; ".join(after))
    assert after == before, f"tagged images changed: {sorted(set(before) ^ set(after))}"
    assert guard == 0, "cleanup guard refused: see the log"
    assert left == {"container": [], "volume": [], "image": []}, left


@pytest.fixture(scope="session")
def custom_image(campaign):
    """Run-owned Ubuntu with the documented managed-start tools; never retag the user's base."""
    camp = campaign
    tag = f"ocs-test-{camp.run}-custom:ubuntu"
    probe = camp.docker("image", "inspect", tag, check=False)
    assert probe.returncode and "no such image" in probe.stderr.lower(), "Refusing a pre-existing/unknown custom fixture"
    context = camp.tmp("custom-image")
    (context / "Dockerfile").write_text(
        "FROM ubuntu:24.04\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends python3 coreutils "
        "&& rm -rf /var/lib/apt/lists/*\n")
    camp.note(f"planned custom fixture image {tag}; pre-existing ubuntu:24.04 remains unchanged")
    camp.docker("build", "--pull=false", "--label", f"org.opencode-sandbox.test={camp.run}",
                "-t", tag, str(context), timeout=1200)
    (created,) = json.loads(camp.docker("image", "inspect", tag).stdout)
    camp.note(f"custom fixture image {tag} id={created['Id']}")
    try:
        yield tag
    finally:
        # A failed body may leave a manifested environment. Delete only this run's users of
        # the fixture before untagging it; campaign cleanup handles the remaining own objects.
        for name in list(camp.ids):
            if camp.metadata(name).get("custom_image") == tag:
                camp.delete(name)
        (current,) = json.loads(camp.docker("image", "inspect", tag).stdout)
        assert current["Id"] == created["Id"] and current["Config"]["Labels"]["org.opencode-sandbox.test"] == camp.run
        camp.docker("image", "rm", tag)
        camp.note(f"removed custom fixture image {tag} id={created['Id']}")
