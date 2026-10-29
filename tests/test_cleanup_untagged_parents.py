"""Since a restore commits the loaded image under the new
environment's labels, the loaded image stays as an untagged parent. Removing the child removes it
too (containerd image store), or Docker refuses the parent while the child exists (classic
store). Neither is a failed cleanup."""
import pytest
from test_cleanup import GONE, Daemon, fail, lab, runner

from opencode_sandbox import cleanup as cl
from opencode_sandbox.cli import app


class ChainDaemon(Daemon):
    """Images with children: removing a child also removes an untagged parent that nothing
    else uses (`cascade`), or the parent's removal is refused while a child exists."""

    def __init__(self, monkeypatch, *, cascade):
        super().__init__(monkeypatch)
        self.cascade = cascade

    def __call__(self, *a, capture=False, check=True):
        if a[:2] == ("image", "rm"):
            iid = self.tag_of(a[2])
            if iid is not None:
                children = [i for i, x in self.images.items() if x["parent"] == iid]
                if children and not self.cascade:
                    self.calls.append(a)
                    return fail("Error response from daemon: conflict: unable to delete " + iid[7:19]
                                + " (cannot be forced) - image has dependent child images")
                parent = self.images[iid]["parent"]
                result = super().__call__(*a, capture=capture, check=check)
                if self.cascade and parent in self.images and not self.images[parent]["tags"]:
                    del self.images[parent]  # removed together with its last child
                return result
        return super().__call__(*a, capture=capture, check=check)


def _chain(d):
    """A deleted environment's restored image and the untagged image it was committed from,
    listed child first (as `docker image ls` did in the run that showed the defect)."""
    child = d.image([f"ocs-backup:{GONE}-0123456789"], lab(GONE))
    parent = d.image([], lab(GONE))
    d.images[child]["parent"] = parent
    return parent, child


@pytest.mark.parametrize("cascade", [True, False])
def test_cleanup_of_a_restore_chain_is_not_a_failure(monkeypatch, cascade):
    d = ChainDaemon(monkeypatch, cascade=cascade)
    parent, child = _chain(d)
    items = cl.inventory().eligible()
    assert {i.image_id for i in items if i.category == "image"} == {parent, child}
    results = cl.apply([i.key for i in items])
    errors = [e for _, e in results if e is not None and not e.startswith("skipped:")]
    assert errors == []
    assert child not in d.images


def test_cli_cleanup_of_a_restore_chain_exits_zero(monkeypatch):
    d = ChainDaemon(monkeypatch, cascade=True)
    _chain(d)
    result = runner.invoke(app, ["disk", "cleanup", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Not removed" not in result.output
    assert d.images == {}


def test_cli_reports_a_refused_parent_as_skipped(monkeypatch):
    d = ChainDaemon(monkeypatch, cascade=False)
    parent = d.image([], lab(GONE))
    d.image([f"ocs-snapshot:{'7' * 16}-20260101000000"], lab("7" * 16, data="2" * 16), parent=parent)  # another directory's
    result = runner.invoke(app, ["disk", "cleanup", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Skipped: untagged image" in result.output and "still the base of another image" in result.output
    assert parent in d.images


def test_a_real_refusal_still_fails(monkeypatch):
    """Guard: an image Docker refuses for another reason (a container uses it) still fails."""
    d = Daemon(monkeypatch)
    image = d.image([f"ocs-runtime:{GONE}-abcdef012345"], lab(GONE))
    d.container("my-container", {}, image=image)
    result = runner.invoke(app, ["disk", "cleanup", "--yes"])
    assert result.exit_code == 1 and f"Not removed: runtime image ocs-runtime:{GONE}-abcdef012345" in result.output
