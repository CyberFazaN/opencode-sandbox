"""Non-mutating helper artifacts and real process-exit ownership; no updater authority."""
import ast
import ctypes
import hashlib
import json
import os
import select
import signal
import socket
import stat
import subprocess
import sys
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from test_manager_tools import tools as external_tools

from opencode_sandbox import core as c
from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_handoff

tools = external_tools  # reuse the real-process synthetic-tool fixture, not subprocess mocks


@contextmanager
def subreaper():
    """Test-only supervisor reaps its exact adopted helper; never rely on the host's PID 1."""
    libc = ctypes.CDLL(None, use_errno=True)
    old = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(old), 0, 0, 0) == 0  # PR_GET_CHILD_SUBREAPER
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    try: yield
    finally: assert libc.prctl(36, old.value, 0, 0, 0) == 0


def wait_helper(pid, timeout=8):
    fd = os.pidfd_open(pid)
    try: assert select.select([fd], [], [], timeout)[0], 'Owned helper did not terminate'
    finally: os.close(fd)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def result_at(directory):
    path = Path(directory) / 'result.json'
    end = time.monotonic() + 8
    while time.monotonic() < end:
        if path.exists(): return json.loads(path.read_text())
        time.sleep(.01)
    pytest.fail('Owned helper did not leave its bounded fixture result')


@pytest.fixture
def artifact(tools, tmp_path):
    evidence, *_ = tools
    parent = tmp_path / 'staging'; parent.mkdir()
    result = manager_handoff.prepare(evidence, parent)
    assert result['supported'], result
    return result['artifact']


def origin(monkeypatch, artifact):
    monkeypatch.setattr(sys, 'prefix', artifact.prefix)
    # Staged helpers deliberately use the unchanged production namespace, on fresh test prefixes
    # only. Their persistent protocol inodes must not be deleted as scratch.
    monkeypatch.setattr(locks, '_TMP', Path('/tmp'))


def excluded(prefix):
    code = f'from opencode_sandbox.installation_locks import exclusive\nwith exclusive({prefix!r}): pass\n'
    value = subprocess.run([sys.executable, '-B', '-c', code], text=True, capture_output=True, timeout=5, check=False)
    return value.returncode != 0 and 'installation busy' in value.stderr.lower()


def test_unclassified_installation_cannot_stage_or_launch_helper(tmp_path):
    result = manager_handoff.prepare({'verified': False}, tmp_path)
    assert not result['supported'] and not list(tmp_path.iterdir())


def test_staged_artifact_is_private_deterministic_and_contains_exact_standalone_sources(artifact):
    directory = artifact.directory
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert {path.name for path in directory.iterdir()} == {'helper.pyz', 'artifact.json'}
    raw = (directory / 'helper.pyz').read_bytes()
    assert raw == manager_handoff._bundle() and hashlib.sha256(raw).hexdigest() == artifact.sha256
    with zipfile.ZipFile(directory / 'helper.pyz') as archive:
        expected = ('manager_helper.py', 'installation_locks.py', 'manager_tool_probe.py', 'manager_verifier.py',
                    'manager_observations.py', 'installation_state.py', 'manager_source.py', 'manager_process.py',
                    'manager_network.py', 'manager_pip_probe.py', 'manager_execution.py', 'http_probe.py')
        assert manager_handoff.BUNDLE == expected
        assert archive.namelist() == ['__main__.py', *expected[1:]]
        for source in expected:
            name = '__main__.py' if source == 'manager_helper.py' else source
            assert archive.read(name) == Path(manager_handoff.__file__).with_name(source).read_bytes()
            tree = ast.parse(archive.read(name))
            # The bundled path module's unused diagnostic main has local pipx imports, but
            # importing its route primitive (the helper's only use) requires stdlib alone.
            nodes = tree.body if name in ('manager_tool_probe.py', 'manager_pip_probe.py') else ast.walk(tree)
            for node in nodes:
                if isinstance(node, ast.Import): names = [item.name.split('.')[0] for item in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if name == 'manager_verifier.py' and node.level:
                        assert node.module is None and node.names[0].name in ('installation_locks', '__version__')
                        continue  # only the installed dedicated client imports its package
                    if name == 'installation_locks.py' and node.level:
                        assert node.module is None and node.names[0].name == 'installation_state'
                        continue  # fixed stdlib bootstrap import, also frozen as a top-level module
                    if name == 'manager_execution.py' and node.level:
                        assert node.module is None and all(item.name + '.py' in expected for item in node.names)
                        continue  # same stdlib modules shared by origin-side preflight
                    assert not node.level
                    names = [node.module.split('.')[0]]
                else: continue
                assert all(item in sys.stdlib_module_names or item + '.py' in expected for item in names), names
    assert not list(Path(artifact.prefix).iterdir()) and artifact.process is None
    artifact.discard()
    assert not directory.exists()


@pytest.mark.parametrize('bad', ['target', 'alias-via-target', 'unsafe-parent', 'relative', 'missing'])
def test_staging_parent_refusals_never_repair_or_modify_the_target(tools, tmp_path, bad):
    evidence, *_ = tools
    target = Path(evidence['evidence']['venv'])
    parent = target
    if bad == 'alias-via-target':
        external = tmp_path / 'outside'; external.mkdir()
        inside = target / 'route'; inside.symlink_to(external)
        parent = tmp_path / 'alias'; parent.symlink_to(inside)
    if bad == 'unsafe-parent': parent = tmp_path / 'unsafe'; parent.mkdir(mode=0o777); parent.chmod(0o777)
    if bad == 'relative': parent = Path('relative')
    if bad == 'missing': parent = tmp_path / 'missing'
    before = sorted(path.name for path in target.iterdir())
    try:
        result = manager_handoff.prepare(evidence, parent)
        assert not result['supported'] and result['preserved'] is None, result
        assert before == sorted(path.name for path in target.iterdir())
    finally:
        if bad == 'unsafe-parent': parent.chmod(0o700)


@pytest.mark.parametrize('change', ['bytes', 'mode', 'hardlink', 'symlink', 'directory', 'extra', 'inventory', 'result'])
def test_changed_artifacts_refuse_start_or_discard_without_deleting_unfamiliar_data(artifact, monkeypatch, change):
    origin(monkeypatch, artifact)
    path = artifact.directory / 'helper.pyz'
    if change == 'bytes': path.write_bytes(b'unfamiliar dummy token')
    if change == 'mode': path.chmod(0o644)
    if change == 'hardlink': os.link(path, artifact.directory / 'other')
    if change == 'symlink': path.rename(path.with_suffix('.saved')); path.symlink_to(path.with_suffix('.saved'))
    if change == 'directory':
        artifact.directory.rename(artifact.directory.with_suffix('.saved')); artifact.directory.mkdir(mode=0o700)
        path.write_bytes(manager_handoff._bundle()); path.chmod(0o600)
    if change == 'extra': (artifact.directory / 'keep').write_text('unfamiliar dummy token')
    if change == 'inventory': (artifact.directory / 'artifact.json').write_text('{}')
    if change == 'result':
        (artifact.directory / 'result.json').write_text('{}'); (artifact.directory / 'result.json').chmod(0o600)
    before = {item.name for item in artifact.directory.iterdir()}
    if change not in ('extra', 'inventory', 'result'):
        with pytest.raises((c.SandboxError, OSError)): manager_handoff.start_fixture(artifact)
    with pytest.raises((c.SandboxError, OSError)): artifact.discard()
    assert before == {item.name for item in artifact.directory.iterdir()} and artifact.process is None


@pytest.mark.parametrize('armed', [False, True])
def test_fixture_cancel_reaps_and_never_releases_origin_usage(artifact, monkeypatch, armed):
    origin(monkeypatch, artifact)
    fixture = manager_handoff.start_fixture(artifact)
    try:
        if armed: fixture.arm()
        assert excluded(artifact.prefix)
        assert not (artifact.directory / 'result.json').exists()
        with pytest.raises(c.SandboxError, match='still alive'): artifact.discard()
    finally: fixture.close()
    assert fixture.process.returncode == 0
    result = result_at(artifact.directory)
    assert result['outcome'] == 'cancelled' and result['fixture'] is True and result['sha256'] == artifact.sha256
    assert excluded(artifact.prefix)
    artifact.discard()


@pytest.mark.parametrize('armed', [False, True])
def test_fixture_budget_expires_while_origin_is_still_alive(artifact, monkeypatch, armed):
    origin(monkeypatch, artifact)
    fixture = manager_handoff.start_fixture(artifact, budget=.3)
    try:
        if armed: fixture.arm()
        fixture.process.wait(timeout=5)
        assert result_at(artifact.directory)['outcome'] == 'expired'
        assert excluded(artifact.prefix) and fixture.process.returncode == 0
    finally: fixture.close()
    artifact.discard()


def test_socket_eof_is_not_process_exit_or_quiescence(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    fixture = manager_handoff.start_fixture(artifact, budget=.3)
    fixture.arm(); fixture.control.close()
    fixture.process.wait(timeout=5)
    assert result_at(artifact.directory)['outcome'] == 'expired' and excluded(artifact.prefix)
    artifact.discard()


@pytest.mark.parametrize('budget', [True, 0, -1, 31, float('nan'), float('inf'), '1',
                                  pytest.param(10 ** 1000, id='huge-integer')])
def test_invalid_fixture_budget_cannot_start_a_child(artifact, monkeypatch, budget):
    origin(monkeypatch, artifact)
    with pytest.raises(c.SandboxError, match='budget'): manager_handoff.start_fixture(artifact, budget=budget)
    assert artifact.process is None and not artifact.used
    artifact.discard()


def test_wrong_origin_is_not_an_external_shortcut_into_an_installation(artifact):
    with pytest.raises(c.SandboxError, match='origin'): manager_handoff.start_fixture(artifact)
    assert artifact.process is None
    artifact.discard()


@pytest.mark.parametrize('kind', ['data', 'environment', 'base'])
def test_fixture_refuses_reverse_lock_order(artifact, monkeypatch, kind):
    origin(monkeypatch, artifact)
    guard = c.base_lock('debian', 'build') if kind == 'base' else c.lock('registry' if kind == 'data' else '0' * 16)
    with guard, pytest.raises(locks.Error, match='order violation'): manager_handoff.start_fixture(artifact)
    assert artifact.process is None
    artifact.discard()


def test_fixture_requires_real_pidfd_without_pid_or_eof_fallback(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    before = len(list(Path('/proc/self/fd').iterdir()))
    def unavailable(*args): raise OSError('dummy unavailable pidfd')
    monkeypatch.setattr(os, 'pidfd_open', unavailable)
    with pytest.raises(OSError, match='unavailable'): manager_handoff.start_fixture(artifact)
    assert artifact.process is None and len(list(Path('/proc/self/fd').iterdir())) == before + 3  # process-lifetime lease
    artifact.discard()


def test_helper_gets_only_three_explicit_descriptors_and_a_minimal_environment(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    monkeypatch.setenv('DUMMY_PROVIDER_TOKEN', 'dummy-secret-not-forwarded')
    monkeypatch.setenv('PYTHONPATH', 'dummy-python-path-not-forwarded')
    actual = subprocess.Popen
    seen = []
    def popen(argv, **kwargs):
        assert argv[:4] == [artifact.python, '-I', '-B', '-S']
        assert kwargs['close_fds'] and kwargs['start_new_session'] and len(kwargs['pass_fds']) == 3
        assert set(kwargs['env']) == {'HOME', 'PATH', 'LANG'}
        process = actual(argv, **kwargs); seen.append(process)
        return process
    monkeypatch.setattr(subprocess, 'Popen', popen)
    fixture = manager_handoff.start_fixture(artifact)
    try:
        environment = Path(f'/proc/{fixture.process.pid}/environ').read_bytes()
        assert b'dummy-secret' not in environment and b'dummy-python' not in environment
        links = []
        for path in Path(f'/proc/{fixture.process.pid}/fd').iterdir():
            try: links.append(os.readlink(path))
            except FileNotFoundError: pass
        assert not any('opencode-sandbox-locks-' in link for link in links)
        assert not any(str(Path(artifact.prefix)) in link for link in links)
    finally: fixture.close()
    assert seen == [fixture.process] and fixture.process.returncode == 0
    artifact.discard()


def test_fixture_is_single_use_and_fork_cannot_claim_origin_artifact(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    fixture = manager_handoff.start_fixture(artifact)
    fixture.close()
    with pytest.raises(c.SandboxError, match='single-use'): manager_handoff.start_fixture(artifact)
    pid = os.fork()
    if pid == 0:
        try:
            try: artifact.check()
            except c.SandboxError: os._exit(0)
            os._exit(1)
        finally: os._exit(2)
    assert os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) == 0
    artifact.discard()


@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_signal_during_spawn_is_deferred_until_fixture_child_is_owned_and_reaped(artifact, monkeypatch, signum):
    origin(monkeypatch, artifact)
    actual = subprocess.Popen
    created = []
    def interrupted(argv, **kwargs):
        process = actual(argv, **kwargs); created.append(process)
        os.kill(os.getpid(), signum)
        return process
    monkeypatch.setattr(subprocess, 'Popen', interrupted)
    previous = signal.getsignal(signum)
    def interrupted_handler(*args): raise SystemExit(128 + signum)
    signal.signal(signum, interrupted_handler)
    try:
        with pytest.raises(SystemExit) as exc: manager_handoff.start_fixture(artifact)
        assert exc.value.code == 128 + signum
    finally: signal.signal(signum, previous)
    assert len(created) == 1 and created[0].poll() is not None
    monkeypatch.setattr(subprocess, 'Popen', actual)
    assert excluded(artifact.prefix)
    artifact.discard()


def test_readiness_failure_is_static_and_the_owned_child_is_reaped(artifact, monkeypatch):
    origin(monkeypatch, artifact)
    actual, children = subprocess.Popen, []
    digest = artifact.sha256
    def changed_request(argv, **kwargs):
        child = actual(argv, **kwargs); children.append(child)
        artifact.sha256 = '0' * 64  # corruption between parent preflight and child validation
        return child
    monkeypatch.setattr(subprocess, 'Popen', changed_request)
    with pytest.raises(c.SandboxError, match='readiness refused'): manager_handoff.start_fixture(artifact)
    assert len(children) == 1 and children[0].returncode == 2
    artifact.sha256 = digest
    artifact.discard()


@pytest.mark.parametrize('args', [[], ['--help'], ['--version'], ['install'], ['quiescence-fixture', '3', '4', '5']])
def test_staged_helper_has_no_generic_dispatch_or_normal_manager_bypass(artifact, args):
    result = subprocess.run([artifact.python, '-I', '-B', '-S', str(artifact.directory / 'helper.pyz'), *args],
                            text=True, capture_output=True, timeout=5, check=False)
    assert result.returncode == 2 and not result.stdout and 'no installation was changed' in result.stderr
    assert 'Traceback' not in result.stderr and not (artifact.directory / 'result.json').exists()
    artifact.discard()


@pytest.mark.parametrize('bad', ['protocol', 'boolean-protocol', 'huge-budget', 'oversized', 'wrong-pidfd', 'site-enabled', 'stream-socket', 'duplicate-arm'])
def test_frozen_helper_refuses_invalid_channels_requests_and_transitions_without_secret_output(artifact, bad):
    kind = socket.SOCK_STREAM if bad == 'stream-socket' else socket.SOCK_SEQPACKET
    control, child = socket.socketpair(socket.AF_UNIX, kind)
    peer = None
    if bad == 'wrong-pidfd':
        peer = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    pidfd = os.pidfd_open(peer.pid if peer else os.getpid())
    directory = os.open(artifact.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    process = None
    try:
        process = subprocess.Popen([artifact.python, '-I', '-B', *([] if bad == 'site-enabled' else ['-S']),
                                   str(artifact.directory / 'helper.pyz'), 'quiescence-fixture',
                                   str(child.fileno()), str(pidfd), str(directory)],
                                  pass_fds=(child.fileno(), pidfd, directory), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        child.close()
        request = {'protocol': 99 if bad == 'protocol' else True if bad == 'boolean-protocol' else 1, 'prefix': artifact.prefix,
                   'sha256': artifact.sha256, 'budget': 10 ** 1000 if bad == 'huge-budget' else 3}
        raw = b'dummy-private-token-' * 1000 if bad == 'oversized' else json.dumps(request).encode()
        control.settimeout(5)
        control.sendall(raw)
        if bad == 'duplicate-arm':
            assert control.recv(4096) == b'ready'
            control.sendall(b'arm'); assert control.recv(4096) == b'armed'
            control.sendall(b'arm')
        out, error = process.communicate(timeout=5)
        assert process.returncode == 2 and not out and 'no installation was changed' in error
        assert 'dummy-private-token' not in error and 'Traceback' not in error
        assert not (artifact.directory / 'result.json').exists()
    finally:
        control.close(); child.close(); os.close(pidfd); os.close(directory)
        if process is not None:
            if process.poll() is None: process.kill()
            process.communicate(timeout=5)
        if peer is not None:
            if peer.poll() is None: peer.kill()
            peer.communicate(timeout=5)
    artifact.discard()


@pytest.mark.parametrize('ending', ['exit', 'worker', 'threadpool', 'killed', 'unarmed', 'killed-unarmed', 'other-instance'])
def test_staged_helper_survives_actual_origin_exit_and_waits_for_all_workers(tools, tmp_path, ending):
    evidence, *_ = tools
    parent = tmp_path / 'staging'; parent.mkdir()
    prefix = evidence['evidence']['venv']
    code = f"""
import concurrent.futures,json,sys,threading
from pathlib import Path
from opencode_sandbox import installation_locks as locks, manager_handoff as h
locks._TMP=Path('/tmp')
sys.prefix={prefix!r}
locks.acquire_usage()
value=h.prepare({evidence!r}, Path({str(parent)!r}))
assert value['supported'], value
artifact=value['artifact']
fixture=h.start_fixture(artifact, budget=8)
if {ending!r} not in ('unarmed','killed-unarmed'): fixture.arm()
print(json.dumps({{'directory':str(artifact.directory),'helper':fixture.process.pid}}),flush=True)
if {ending!r} in ('worker','threadpool'):
 if {ending!r} == 'worker': threading.Thread(target=lambda:sys.stdin.read()).start()
 else:
  pool=concurrent.futures.ThreadPoolExecutor()
  pool.submit(lambda:sys.stdin.read())
 print('main returned; worker draining',flush=True)
else: sys.stdin.read()
"""
    peer = None
    with subreaper():
        process = subprocess.Popen([sys.executable, '-B', '-c', code], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        helper = None
        try:
            assert select.select([process.stdout], [], [], 8)[0]
            line = process.stdout.readline()
            assert line, process.stderr.read()
            value = json.loads(line); helper = value['helper']; directory = Path(value['directory'])
            assert excluded(prefix)
            assert not (directory / 'result.json').exists()
            if ending in ('worker', 'threadpool'):
                assert process.stdout.readline().strip() == 'main returned; worker draining'
                assert process.poll() is None and excluded(prefix)
                time.sleep(.2)  # negative observation after main return, not readiness polling
                assert not (directory / 'result.json').exists()
            if ending == 'other-instance':
                peer = subprocess.Popen([sys.executable, '-B', '-c', f"import sys\nfrom opencode_sandbox import installation_locks as l\nsys.prefix={prefix!r}\nl.acquire_usage()\nprint('shared',flush=True)\ninput()"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                assert select.select([peer.stdout], [], [], 5)[0] and peer.stdout.readline().strip() == 'shared'
            if ending in ('killed', 'killed-unarmed'): process.kill()
            process.communicate(timeout=8)
            assert process.returncode == (-signal.SIGKILL if ending in ('killed', 'killed-unarmed') else 0)
            child_pid = helper
            status = wait_helper(helper)
            helper = None  # never signal a PID after reaping it
            assert status == 0
            outcome = result_at(directory)
            assert outcome['outcome'] == ('busy' if peer else 'abandoned' if ending in ('unarmed', 'killed-unarmed') else 'quiescent')
            assert outcome['origin'] == process.pid and outcome['helper'] == child_pid and outcome['fixture'] is True
            assert not list(Path(prefix).iterdir())
            if peer: assert excluded(prefix)
            else: assert not excluded(prefix)
        finally:
            if process.poll() is None: process.kill()
            process.communicate(timeout=5)
            if helper is not None:
                try: os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except (ProcessLookupError, ChildProcessError): pass
            if peer is not None:
                if peer.poll() is None: peer.kill()
                peer.communicate(timeout=5)
