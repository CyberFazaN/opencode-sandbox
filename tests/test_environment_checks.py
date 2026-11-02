"""Temporary checks: lifecycle guards, restoration, cancellation and batch identity consent."""
import threading

import pytest
from test_opencode_lifecycle import FakeDocker, env

from opencode_sandbox import core as c
from opencode_sandbox import environment_checks as checks
from opencode_sandbox import opencode_versions as v
from opencode_sandbox import runtime_identity as rid


@pytest.fixture
def runtime(monkeypatch):
    runtime = FakeDocker(monkeypatch)
    class Guard:
        def __init__(self, m, identity, lock):
            self.cid = identity['container']
            assert not lock.closed and c.locks_held()
        def start(self): c.docker('start', self.cid, capture=True)
        def finish(self):
            assert c._RUNTIME_FEEDBACK.get()['cancelled'] is None and c.locks_held()
            c.docker('stop', self.cid, capture=True)
    monkeypatch.setattr(checks, 'StartGuard', Guard)
    monkeypatch.setattr(c, 'recheck_mount', lambda m: None)
    return runtime


@pytest.mark.parametrize('running', [False, True])
@pytest.mark.parametrize('failure', [None, 'probe', 'cancel'])
def test_original_state_restored_and_no_launch_or_configuration_changes(runtime, monkeypatch, running, failure):
    m = env()
    runtime.running = running
    before = (c.env_dir(m['id']) / 'metadata.json').read_bytes()
    monkeypatch.setattr(c, 'start', lambda *a, **k: pytest.fail('must not use normal launch'))
    if failure:
        def broken(*a, **k):
            if failure == 'cancel': raise rid.Cancelled()
            raise c.SandboxError('probe unavailable')
        monkeypatch.setattr(v, '_exec_version', broken)
    if failure == 'cancel':
        with pytest.raises(rid.Cancelled): checks.check(m)
    else:
        result = checks.check(m)
        assert result['state'] == ('running' if running else 'stopped')
        assert ('probe unavailable' in result['error']) if failure else result['version'] == '2.1.4'
    assert runtime.running == running
    mutations = [a for a in runtime.calls if a[0] in ('start', 'stop')]
    assert mutations == ([] if running else [('start', runtime.cid), ('stop', runtime.cid)])
    assert before == (c.env_dir(m['id']) / 'metadata.json').read_bytes()


def test_missing_container_is_not_created_and_pending_operation_is_not_bypassed(runtime):
    m = env()
    runtime.exists = False
    assert checks.check(m)['state'] == 'not-created'
    c.mark(m, 'updating', operation=v.UPDATE_OP)
    with pytest.raises(c.SandboxError, match='pending operation'): checks.check(m)
    assert not any(a[0] in ('run', 'start', 'stop', 'exec') for a in runtime.calls)


def test_cleanup_failure_is_not_reported_as_restored(runtime, monkeypatch):
    m = env()
    real = c.docker
    def docker(*a, **kw):
        if a[0] == 'stop': raise c.SandboxError('stop failed; still running')
        return real(*a, **kw)
    monkeypatch.setattr(c, 'docker', docker)
    with pytest.raises(c.SandboxError, match='stop failed'): checks.check(m)
    assert runtime.running


def test_batch_revalidates_live_state_identity_and_metadata(runtime):
    m = env()
    targets, stopped = checks.review([m['id']])
    assert stopped == [m['name']]
    runtime.running = True
    runtime.calls.clear()
    with pytest.raises(c.SandboxError, match='changed since Check All'): checks.check(m, expected=targets[m['id']])
    assert runtime.running and not any(a[0] in ('start', 'stop') for a in runtime.calls)


def test_lifecycle_lock_spans_start_probe_and_restoration(runtime, monkeypatch):
    m = env()
    entered, release, acquired = threading.Event(), threading.Event(), threading.Event()
    original = v._exec_version
    def probe(*a, **kw):
        entered.set()
        assert release.wait(3)
        return original(*a, **kw)
    monkeypatch.setattr(v, '_exec_version', probe)
    errors = []
    def check():
        try: checks.check(m)
        except (c.SandboxError, rid.Cancelled, AssertionError) as exc: errors.append(exc)
    def contender():
        with c.lock(m['id']):
            assert not runtime.running
            acquired.set()
    first, second = threading.Thread(target=check), threading.Thread(target=contender)
    first.start()
    assert entered.wait(2)
    second.start()
    try:
        assert not acquired.wait(.1)
    finally:
        release.set(); first.join(4); second.join(4)
    assert acquired.is_set() and not errors
