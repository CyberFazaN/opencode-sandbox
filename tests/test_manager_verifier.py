"""Fresh fixed read-only verifier access is not a normal-manager lease exemption."""
import fcntl
import json
import os
import select
import signal
import socket
import struct
import subprocess
import sys
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest
from test_manager_helper import artifact as staged_artifact
from test_manager_helper import origin as set_origin
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_tools import tools as external_tools

from opencode_sandbox import __version__
from opencode_sandbox import core as c
from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_handoff as handoff
from opencode_sandbox import manager_verifier as verifier

tools = external_tools
artifact = staged_artifact


def test_verifier_capability_requires_an_existing_exclusive_guard():
    with pytest.raises(locks.Error, match='exclusive'), locks._verification():
        pytest.fail('uncoordinated verifier capability')


def test_shared_usage_never_grants_a_verifier_capability():
    locks.acquire_usage()
    with pytest.raises(locks.Error, match='exclusive'), locks._verification(): pass
    assert not locks._WITNESSES


def test_unlocked_witness_is_read_only_cloexec_and_closing_it_cannot_unlock_exclusive_owner():
    with locks.exclusive():
        with locks._verification() as (fd, owner_fd):
            assert not os.get_inheritable(fd)
            assert fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
            with pytest.raises(BlockingIOError): fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            locks._verify_descriptor(fd, os.getpid(), owner_fd)
            assert locks._WITNESSES == {fd}
        assert not locks._WITNESSES
        with pytest.raises(locks.Error, match='busy'): locks.acquire_usage()
    assert not locks._OPEN


@pytest.mark.parametrize('kind', ['shared', 'unheld', 'posix', 'wrong-owner', 'wrong-prefix', 'replaced-inode'])
def test_kernel_descriptor_witness_rejects_nonexclusive_foreign_and_replaced_capabilities(tmp_path, kind):
    if kind == 'shared':
        locks.acquire_usage()
        fd = os.open(os.readlink(f'/proc/self/fd/{locks._LEASE.fd}'), os.O_RDONLY | os.O_CLOEXEC)
        try:
            with pytest.raises(locks.Error, match='capability'): locks._verify_descriptor(fd, os.getpid(), locks._LEASE.fd)
        finally: os.close(fd)
        return
    if kind in ('unheld', 'posix'):
        with locks.exclusive(): pass
        namespace = locks._TMP / f'opencode-sandbox-locks-{os.getuid()}'
        path, = namespace.glob('installation-*.lock')
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        witness = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        try:
            if kind == 'posix': fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(locks.Error, match='capability'): locks._verify_descriptor(witness, os.getpid(), fd)
        finally: os.close(witness); os.close(fd)
        return
    prefix = tmp_path / 'other' if kind == 'wrong-prefix' else None
    changed = pytest.raises(locks.Error, match='path changed') if kind == 'replaced-inode' else nullcontext()
    with changed, locks.exclusive(prefix), locks._verification(prefix) as (fd, owner_fd):
        if kind == 'replaced-inode':
            path = Path(os.readlink(f'/proc/self/fd/{fd}'))
            path.rename(path.with_suffix('.saved')); path.touch(mode=0o600)
        with pytest.raises((locks.Error, OSError)):
            locks._verify_descriptor(fd, os.getpid() + 1 if kind == 'wrong-owner' else os.getpid(), owner_fd)


def test_fork_drops_unlocked_witnesses_without_unlocking_or_retaining_parent_exclusion():
    read, write = os.pipe()
    done, release = os.pipe()
    with locks.exclusive(), locks._verification():
        pid = os.fork()
        if pid == 0:
            os.close(read); os.close(release)
            try:
                assert not locks._WITNESSES and not locks._OPEN
                os.write(write, b'ready')
                os.read(done, 1)
                os._exit(0)
            finally: os._exit(1)
        os.close(write); os.close(done)
        assert select.select([read], [], [], 5)[0] and os.read(read, 5) == b'ready'
        with pytest.raises(locks.Error, match='busy'): locks.acquire_usage()
    try:
        with locks.exclusive(): pass  # fork child is still alive but cannot retain exclusion
    finally:
        os.close(release); os.close(read)
        status = os.waitpid(pid, 0)[1]
    assert os.waitstatus_to_exitcode(status) == 0


def test_ordinary_exec_children_do_not_inherit_the_transient_witness_descriptor():
    code = """
import os
from pathlib import Path
for path in Path('/proc/self/fd').iterdir():
 try: name=os.readlink(path)
 except OSError: continue
 assert 'opencode-sandbox-locks-' not in name
"""
    with locks.exclusive(), locks._verification():
        value = subprocess.run([sys.executable, '-B', '-c', code], close_fds=False, capture_output=True, timeout=5, check=False)
    assert value.returncode == 0, value.stderr


@pytest.mark.parametrize('kind', ['data', 'environment', 'base'])
def test_capability_issuance_refuses_reverse_lock_order(kind):
    later = c.base_lock('debian', 'build') if kind == 'base' else c.lock('registry' if kind == 'data' else '0' * 16)
    with locks.exclusive(), later, pytest.raises(locks.Error, match='order violation'), locks._verification(): pass
    assert not locks._WITNESSES


@pytest.mark.parametrize('entry', ['launcher', 'cli'])
@pytest.mark.parametrize('args', [['--version'], ['--help'], ['list'], ['create', 'ocs-test-refused']])
def test_even_explicitly_inherited_capability_and_environment_cannot_bypass_normal_startup(tmp_path, entry, args):
    code = (f"from pathlib import Path\nfrom opencode_sandbox import installation_locks as l\nl._TMP=Path({str(locks._TMP)!r})\n"
            f"import sys\nsys.argv=['opencode-sandbox',*{args!r}]\nfrom opencode_sandbox.{entry} import main\nmain()")
    with locks.exclusive(), locks._verification() as (_, fd):
        value = subprocess.run([sys.executable, '-B', '-c', code], pass_fds=(fd,), capture_output=True, text=True, timeout=5,
                               env=dict(os.environ, OCS_VERIFY_FD=str(fd), OPENCODE_SANDBOX_VERIFY='1',
                                        OPENCODE_SANDBOX_HOME=str(tmp_path / 'refused-data'), OPENCODE_SANDBOX_CONFIG=str(tmp_path / 'refused-config')),
                               check=False)
        assert value.returncode == 2 and 'installation busy' in value.stderr.lower()
    assert not (tmp_path / 'refused-data').exists() and not (tmp_path / 'refused-config').exists()


@pytest.fixture
def installation(tools):
    evidence, *_ = tools
    prefix = Path(evidence['evidence']['venv'])
    # Minimal REAL CPython venv runtime, no pip/network/package installation or distribution
    # provenance claim. The separately opt-in campaign uses actual installed pipx packages.
    (prefix / 'bin').mkdir()
    (prefix / 'bin/python').symlink_to(sys._base_executable)
    (prefix / 'pyvenv.cfg').write_text(f'home = {Path(sys._base_executable).parent}\ninclude-system-site-packages = false\n')
    site = prefix / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'
    package = site / 'opencode_sandbox'; package.mkdir(parents=True)
    for name in ('__init__.py', 'installation_locks.py', 'manager_verifier.py', 'launcher.py'):
        (package / name).write_bytes(Path(handoff.__file__).with_name(name).read_bytes())
    return evidence, prefix, package, site


@contextmanager
def running(installation, tmp_path, *, budget=15):
    evidence, prefix, *_ = installation
    staging = tmp_path / 'helper staging'; staging.mkdir()
    code = f"""
import json,sys
from pathlib import Path
from opencode_sandbox import installation_locks as l, manager_handoff as h
l._TMP=Path('/tmp')
sys.prefix={str(prefix)!r}
l.acquire_usage()
value=h.prepare({evidence!r},Path({str(staging)!r}))
assert value['supported'],value
artifact=value['artifact']
fixture=h.start_fixture(artifact,verify=True,budget={budget!r})
fixture.arm()
print(json.dumps({{'directory':str(artifact.directory),'helper':fixture.process.pid}}),flush=True)
sys.stdin.read()
"""
    with subreaper():
        origin = subprocess.Popen([sys.executable, '-B', '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        value = None
        try:
            assert select.select([origin.stdout], [], [], 8)[0]
            line = origin.stdout.readline()
            assert line, origin.stderr.read()
            value = json.loads(line)
            yield origin, value
        finally:
            if origin.poll() is None: origin.kill()
            origin.communicate(timeout=5)
            if value and value['helper'] is not None:
                try: os.kill(value['helper'], signal.SIGKILL); os.waitpid(value['helper'], 0)
                except (ProcessLookupError, ChildProcessError): pass


def complete(origin, value):
    origin.communicate(timeout=5)
    assert origin.returncode == 0
    status = wait_helper(value['helper'], timeout=10)
    value['helper'] = None  # never signal a reaped PID
    assert status == 0
    return result_at(value['directory'])


def wait_file(path):
    end = time.monotonic() + 8
    while time.monotonic() < end:
        if path.exists(): return json.loads(path.read_text())
        time.sleep(.01)
    pytest.fail('Owned verifier did not reach fixture rendezvous')


def hook(installation, marker, release, *, at_runtime, descendant=False):
    _, _, _, site = installation
    partial = marker.with_suffix('.partial')
    spawn = ''
    if descendant:
        spawn = ("import subprocess\n"
                 f"child=subprocess.Popen([{sys._base_executable!r},'-I','-B','-S','-c','import time; time.sleep(30)'],close_fds=False)\n")
    block = (spawn + f"Path({str(partial)!r}).write_text(json.dumps({{'pid':os.getpid(),'fds':links,'descendant':child.pid if {descendant!r} else None}}))\n"
             f"os.replace({str(partial)!r},{str(marker)!r})\n"
             f"while not Path({str(release)!r}).exists(): time.sleep(.01)\n")
    code = ('import os,sys,json,time\nfrom pathlib import Path\n'
            'def pause():\n links=[]\n for p in Path("/proc/self/fd").iterdir():\n'
            '  try: links.append(os.readlink(p))\n  except OSError: pass\n'
            + ''.join(' ' + line + '\n' for line in block.splitlines()))
    if at_runtime:
        code += ('def profile(frame,event,arg):\n if event=="call" and frame.f_code.co_name=="_runtime":\n'
                 '  sys.setprofile(None)\n  pause()\n'
                 'if sys.argv[0]=="-m" and len(sys.argv)==4: sys.setprofile(profile)\n')
    else: code += 'if sys.argv[0]=="-m" and len(sys.argv)==4: pause()\n'
    (site / 'ocs_test_verifier_hook.py').write_text(code)
    (site / 'ocs_test_verifier_hook.pth').write_text('import ocs_test_verifier_hook\n')


def test_frozen_helper_can_query_actual_target_runtime_without_normal_cli_dispatch(installation, tmp_path):
    _, prefix, package, _ = installation
    before = {path: path.read_bytes() for path in package.iterdir()}
    with running(installation, tmp_path) as (origin, value):
        result = complete(origin, value)
    assert result['outcome'] == 'quiescent' and result['verifier']['ok'] is True
    assert result['verifier']['observed'] == {'version': __version__, 'prefix': str(prefix), 'module': str(package / '__init__.py')}
    assert before == {path: path.read_bytes() for path in before} and not list(package.glob('__pycache__'))
    assert not c.BASE.exists() and not c.CONFIG.exists()


def test_capability_is_closed_before_fixed_query_while_helper_still_excludes_normal_startup(installation, tmp_path):
    _, prefix, _, _ = installation
    marker, release = tmp_path / 'ready', tmp_path / 'release'
    hook(installation, marker, release, at_runtime=True)
    with running(installation, tmp_path) as (origin, value):
        origin.communicate(timeout=5)
        seen = wait_file(marker)
        assert not any('opencode-sandbox-locks-' in name for name in seen['fds'])
        assert all('dummy-private' not in name for name in seen['fds'])
        code = 'from opencode_sandbox.launcher import main\nmain()\n'
        refused = subprocess.run([str(prefix / 'bin/python'), '-I', '-B', '-c', code, '--version'],
                                 env=dict(os.environ, OPENCODE_SANDBOX_HOME=str(tmp_path / 'other-data')),
                                 text=True, capture_output=True, timeout=5, check=False)
        assert refused.returncode == 2 and 'installation busy' in refused.stderr.lower()
        release.touch()
        status = wait_helper(value['helper']); value['helper'] = None
        assert status == 0 and result_at(value['directory'])['verifier']['ok'] is True
    assert not (tmp_path / 'other-data').exists()


@pytest.mark.parametrize('failure', ['missing-module', 'invalid-version', 'wrong-nonce', 'boolean-protocol'])
def test_failed_fresh_query_is_not_runtime_success_and_does_not_expose_raw_diagnostics(installation, tmp_path, failure):
    _, _, package, _ = installation
    module = package / 'manager_verifier.py'
    if failure == 'missing-module': module.unlink()
    if failure == 'invalid-version': (package / '__init__.py').write_text('__version__="dummy-private-token"\n')
    if failure == 'wrong-nonce': module.write_text(module.read_text().replace("'nonce': value['nonce']", "'nonce': '0' * 64"))
    if failure == 'boolean-protocol': module.write_text(module.read_text().replace("{'protocol': 1, 'nonce': value['nonce']", "{'protocol': True, 'nonce': value['nonce']"))
    with running(installation, tmp_path) as (origin, value): result = complete(origin, value)
    assert result['outcome'] == 'verification-failed' and result['verifier']['ok'] is False
    assert 'dummy-private' not in json.dumps(result) and 'Traceback' not in json.dumps(result)


def test_timed_out_target_site_hook_is_killed_reaped_and_cannot_keep_exclusion(installation, tmp_path):
    _, prefix, _, _ = installation
    marker, release = tmp_path / 'ready', tmp_path / 'never-release'
    hook(installation, marker, release, at_runtime=False)
    with running(installation, tmp_path, budget=3) as (origin, value):
        origin.communicate(timeout=5)
        child = wait_file(marker)['pid']
        status = wait_helper(value['helper']); value['helper'] = None
        assert status == 0 and result_at(value['directory'])['outcome'] == 'verification-failed'
        assert not Path(f'/proc/{child}').exists()
    # The fixture used the fixed namespace only for this owned prefix, not the user's install.
    code = f'from opencode_sandbox.installation_locks import exclusive\nwith exclusive({str(prefix)!r}): pass'
    assert subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5, check=False).returncode == 0


def test_killed_helper_cannot_leave_startup_verifier_or_exclusion_alive(installation, tmp_path):
    _, prefix, _, _ = installation
    marker, release = tmp_path / 'ready', tmp_path / 'never-release'
    hook(installation, marker, release, at_runtime=False)
    with running(installation, tmp_path) as (origin, value):
        origin.communicate(timeout=5)
        child = wait_file(marker)['pid']
        try:
            os.kill(value['helper'], signal.SIGKILL)
            status = wait_helper(value['helper']); value['helper'] = None
            assert status == -signal.SIGKILL
            status = wait_helper(child); child = None
            assert status == -signal.SIGKILL
        finally:
            if child is not None:
                try: os.kill(child, signal.SIGKILL); os.waitpid(child, 0)
                except (ProcessLookupError, ChildProcessError): pass
    code = f'from opencode_sandbox.installation_locks import exclusive\nwith exclusive({str(prefix)!r}): pass'
    assert subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5, check=False).returncode == 0


def test_early_startup_descendant_cannot_inherit_exclusive_access_after_helper_death(installation, tmp_path):
    _, prefix, _, _ = installation
    marker, release = tmp_path / 'ready', tmp_path / 'never-release'
    hook(installation, marker, release, at_runtime=False, descendant=True)
    with running(installation, tmp_path) as (origin, value):
        origin.communicate(timeout=5)
        seen = wait_file(marker)
        direct, descendant = seen['pid'], seen['descendant']
        try:
            os.kill(value['helper'], signal.SIGKILL)
            status = wait_helper(value['helper']); value['helper'] = None
            assert status == -signal.SIGKILL
            status = wait_helper(direct); direct = None
            assert status == -signal.SIGKILL
            assert Path(f'/proc/{descendant}').exists(), 'Descendant must still be alive for the lease-retention proof'
            code = f'from opencode_sandbox.installation_locks import exclusive\nwith exclusive({str(prefix)!r}): pass'
            checked = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5, check=False)
            assert checked.returncode == 0, 'Early site descendants must never inherit an exclusive descriptor'
        finally:
            for child in (direct, descendant):
                if child is not None:
                    try: os.kill(child, signal.SIGKILL); os.waitpid(child, 0)
                    except (ProcessLookupError, ChildProcessError): pass


@pytest.mark.parametrize('bad', ['boolean-protocol', 'wrong-prefix', 'command', 'nonce', 'oversized', 'unlocked-description',
                               'wrong-pidfd', 'stream', 'missing-isolation', 'aliased-descriptors'])
def test_dedicated_client_rejects_ungranted_requests_without_entering_normal_cli(installation, tmp_path, monkeypatch, bad):
    _, prefix, _, _ = installation
    monkeypatch.setattr(locks, '_TMP', Path('/tmp'))
    control, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM if bad == 'stream' else socket.SOCK_SEQPACKET)
    child.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    peer = process = None
    if bad == 'wrong-pidfd': peer = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
    pidfd = os.pidfd_open(peer.pid if peer else os.getpid())
    independent = None
    try:
        with locks.exclusive(prefix), locks._verification(prefix) as (fd, owner_fd):
            capability = fd
            if bad == 'unlocked-description':
                independent = os.open(os.readlink(f'/proc/self/fd/{fd}'), os.O_RDONLY | os.O_CLOEXEC)
                owner_fd = independent  # same busy inode, but NOT the owner's locked description
            request = {'protocol': True if bad == 'boolean-protocol' else 1,
                       'prefix': str(tmp_path / 'foreign') if bad == 'wrong-prefix' else str(prefix),
                       'nonce': 'dummy-private-token' if bad == 'nonce' else '1' * 64, 'owner_fd': owner_fd}
            if bad == 'command': request['command'] = ['create', 'ocs-test-refused']
            argv = [str(prefix / 'bin/python'), *([] if bad == 'missing-isolation' else ['-I']), '-B', '-m',
                    'opencode_sandbox.manager_verifier', str(child.fileno()), str(capability),
                    str(child.fileno() if bad == 'aliased-descriptors' else pidfd)]
            process = subprocess.Popen(argv, pass_fds=(child.fileno(), capability, pidfd),
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       env={key: value for key, value in os.environ.items() if key != 'PYTHONPATH'})
            child.close()
            raw = b'dummy-private-token-' * 1000 if bad == 'oversized' else json.dumps(request).encode()
            try: control.sendall(raw)
            except BrokenPipeError: pass
            out, error = process.communicate(timeout=5)
            assert process.returncode == 2 and not out and 'Fresh runtime verifier refused' in error
            assert 'dummy-private-token' not in error and 'Traceback' not in error
            with pytest.raises(locks.Error, match='busy'): locks._Guard(prefix, fcntl.LOCK_SH)
    finally:
        control.close(); child.close(); os.close(pidfd)
        if independent is not None: os.close(independent)
        for owned in (process, peer):
            if owned is not None:
                if owned.poll() is None: owned.kill()
                owned.communicate(timeout=5)
    assert not c.BASE.exists() and not c.CONFIG.exists()


@pytest.mark.parametrize('args', [[], ['--help'], ['--version'], ['create', 'ocs-test-refused']])
def test_dedicated_module_has_no_public_command_or_argument_dispatch(installation, args):
    _, prefix, _, _ = installation
    process = subprocess.run([str(prefix / 'bin/python'), '-I', '-B', '-m', 'opencode_sandbox.manager_verifier', *args],
                             text=True, capture_output=True, timeout=5, check=False)
    assert process.returncode == 2 and not process.stdout and 'Fresh runtime verifier refused' in process.stderr
    assert not c.BASE.exists() and not c.CONFIG.exists()


def test_message_credentials_bind_actual_sender_not_socketpair_creator():
    control, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    control.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    code = ("import socket,sys\ns=socket.socket(fileno=int(sys.argv[1]))\n"
            "s.sendall(b'{\"ok\":true}')\ns.sendall(b'{\"ok\":true}')\n")
    process = subprocess.Popen([sys.executable, '-B', '-c', code, str(child.fileno())], pass_fds=(child.fileno(),))
    child.close()
    try:
        with pytest.raises(verifier.Refused, match='message'): verifier._message(control, time.monotonic() + 5, os.getpid())
        assert verifier._message(control, time.monotonic() + 5, process.pid) == {'ok': True}
        assert process.wait(timeout=5) == 0
    finally:
        control.close()
        if process.poll() is None: process.kill()
        process.wait(timeout=5)


def test_unexpected_received_descriptors_are_rejected_and_closed(tmp_path):
    control, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    control.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    source = tmp_path / 'owned-witness'; source.touch(mode=0o600)
    fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
    before = len(list(Path('/proc/self/fd').iterdir()))
    try:
        child.sendmsg([b'{"ok":true}'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack('i', fd))])
        with pytest.raises(verifier.Refused, match='message'): verifier._message(control, time.monotonic() + 5, os.getpid())
        assert len(list(Path('/proc/self/fd').iterdir())) == before
        assert os.fstat(fd).st_ino == source.stat().st_ino  # receiving code did not close the sender's descriptor
    finally: os.close(fd); control.close(); child.close()


@pytest.mark.parametrize('choice', [None, 1, 'true', {}])
def test_fixture_verification_choice_is_strictly_boolean(artifact, monkeypatch, choice):
    set_origin(monkeypatch, artifact)
    with pytest.raises(c.SandboxError, match='boolean'): handoff.start_fixture(artifact, verify=choice)
    assert artifact.process is None and not artifact.used
    artifact.discard()


@pytest.mark.parametrize('change', ['extra', 'foreign-module', 'failed-reason'])
def test_changed_or_unfamiliar_verifier_records_are_preserved(artifact, monkeypatch, tmp_path, change):
    set_origin(monkeypatch, artifact)
    fixture = handoff.start_fixture(artifact, verify=True)
    fixture.close()
    path = artifact.directory / 'result.json'
    value = json.loads(path.read_text()); value['outcome'] = 'quiescent'
    value['verifier'] = {'ok': True, 'observed': {'prefix': artifact.prefix, 'module': artifact.prefix + '/package.py', 'version': __version__}}
    if change == 'extra': value['verifier']['keep'] = 'dummy-private-note'
    if change == 'foreign-module': value['verifier']['observed']['module'] = str(tmp_path / 'foreign.py')
    if change == 'failed-reason':
        value['outcome'] = 'verification-failed'; value['verifier'] = {'ok': False, 'reason': 'dummy-private-note'}
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    with pytest.raises(c.SandboxError, match='unfamiliar'): artifact.discard()
    assert path.read_bytes() == before
