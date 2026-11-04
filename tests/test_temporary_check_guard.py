"""Real isolated guardian processes against a fake docker, including abrupt parent death."""
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from opencode_sandbox import core as c
from opencode_sandbox.environment_checks import StartGuard

pytestmark = pytest.mark.real_session
CID = 'a' * 64


@pytest.fixture
def daemon(tmp_path, monkeypatch):
    m = c.create('ocs-test-guard', 'scratch')
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'Running': False, 'StartedAt': 'initial', 'fail_stop': False}))
    binary = tmp_path / 'docker'
    binary.write_text(f'#!{sys.executable}\n' + '''import json,os,sys,time
from pathlib import Path
path=Path(''' + repr(str(state)) + ''')
def save(value):
 temporary=path.with_name('state-'+str(os.getpid())+'.tmp')
 try:
  temporary.write_text(json.dumps(value)); temporary.replace(path)
 finally: temporary.unlink(missing_ok=True)
value=json.loads(path.read_text())
args=sys.argv[3:]
if args[:2]==['container','inspect']:
 print(json.dumps([{'Id':''' + repr(CID) + ''', 'Config':{'Labels':{'org.opencode-sandbox.id':''' + repr(m['id']) + '''}}, 'State':value}]))
elif args[0]=='start':
 value.update(Running=True,StartedAt='check-start'); save(value)
elif args[0]=='stop':
 if value['fail_stop']: sys.exit(71)
 path.with_name('stop-entered').touch()
 while path.with_name('hold-stop').exists(): time.sleep(.02)
 value['Running']=False; save(value)
else: sys.exit(72)
''')
    binary.chmod(0o700)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    return m, state


def identity(m):
    return {'container': CID, 'endpoint': 'unix:///unused-ocs-test.sock', 'environment': m['id']}


def test_guard_starts_stops_and_failure_retains_actionable_marker(daemon):
    m, state = daemon
    for fail in (False, True):
        state.write_text(json.dumps({'Running': False, 'StartedAt': 'initial', 'fail_stop': fail}))
        with c.lock(m['id']) as lock:
            guard = StartGuard(m, identity(m), lock)
            guard.start()
            assert json.loads(state.read_text())['Running']
            if fail:
                with pytest.raises(c.SandboxError, match='cleanup was not fully successful'): guard.finish()
            else: guard.finish()
        marker = c.env_dir(m['id']) / 'version-check.json'
        assert marker.exists() == fail and json.loads(state.read_text())['Running'] == fail
        if fail:
            evidence = json.loads(marker.read_text())
            assert evidence['container'] == CID and 'Restoration unconfirmed' in evidence['error'] and 'F6' in evidence['hint']


def test_guard_does_not_stop_an_external_restart(daemon):
    m, state = daemon
    with c.lock(m['id']) as lock:
        guard = StartGuard(m, identity(m), lock)
        guard.start()
        value = json.loads(state.read_text())
        value['StartedAt'] = 'external-start'
        state.write_text(json.dumps(value))
        with pytest.raises(c.SandboxError, match='cleanup'): guard.finish()
    assert json.loads(state.read_text())['Running']


def test_existing_unknown_check_record_is_never_overwritten_or_deleted(daemon):
    from opencode_sandbox.environment_checks import clear_cleanup
    m, state = daemon
    marker = c.env_dir(m['id']) / 'version-check.json'
    original = json.dumps({'schema': 999, 'container': CID, 'error': 'future protocol'}).encode()
    marker.write_bytes(original); marker.chmod(0o600)
    with c.lock(m['id']) as lock:
        with pytest.raises(c.SandboxError, match='record preserved'): StartGuard(m, identity(m), lock).start()
        with pytest.raises(c.SandboxError, match='record preserved'): clear_cleanup(m)
    assert marker.read_bytes() == original and not json.loads(state.read_text())['Running']


def test_parent_sigkill_keeps_lifecycle_lock_until_guardian_restores(daemon, tmp_path):
    m, state = daemon
    # Control files avoid a host read/modify/write racing the fake daemon's state updates.
    # The old shared hold_stop JSON flag exposed truncated JSON or restored stale Running=True.
    hold_stop, stop_entered = state.with_name('hold-stop'), state.with_name('stop-entered')
    hold_stop.touch()
    source = str(Path(__file__).resolve().parents[1] / 'src')
    code = (f'import sys;sys.path.insert(0,{source!r})\n'
            'from opencode_sandbox import core as c\nfrom opencode_sandbox.environment_checks import StartGuard\n'
            f'c.BASE=__import__("pathlib").Path({str(c.BASE)!r}); c.CONFIG=__import__("pathlib").Path({str(c.CONFIG)!r})\n'
            f'm=c.resolve({m["id"]!r})\n'
            f'with c.lock(m["id"]) as lock:\n guard=StartGuard(m,{identity(m)!r},lock)\n guard.start()\n print("ready",flush=True)\n sys.stdin.read()\n')
    process = subprocess.Popen([sys.executable, '-I', '-B', '-c', code], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'ready'
        process.kill()
        process.wait(5)
        deadline = time.monotonic() + 5
        while not stop_entered.exists() and time.monotonic() < deadline: time.sleep(.02)
        assert stop_entered.exists(), 'guardian did not begin restoration after parent death'
        with (c.BASE / 'locks' / (m['id'] + '.lock')).open() as contender:
            with pytest.raises(BlockingIOError): fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            hold_stop.unlink()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try: fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except BlockingIOError: time.sleep(.02)
            else: pytest.fail('guardian did not release lifecycle lock after restoration')
            assert not json.loads(state.read_text())['Running']
            assert not (c.env_dir(m['id']) / 'version-check.json').exists()
    finally:
        hold_stop.unlink(missing_ok=True)
        if process.poll() is None: process.kill(); process.wait(5)
        process.communicate(timeout=5)
