"""Installation coordination uses real host files/processes, never product data or Docker."""
import os
import select
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import installation_locks as locks


def script(code):
    return f"from pathlib import Path\nfrom opencode_sandbox import installation_locks as locks\nlocks._TMP=Path({str(locks._TMP)!r})\n" + code


def child(code, *, env=None):
    return subprocess.run([sys.executable, '-B', '-c', script(code)], env=env, text=True,
                          capture_output=True, timeout=5, check=False)


def ready(process, stream=None):
    stream = stream or process.stdout
    assert select.select([stream], [], [], 5)[0], 'Child did not report readiness'
    return stream.readline().strip()


def namespace():
    return locks._TMP / f'opencode-sandbox-locks-{os.getuid()}'


def assert_excluded(prefix=None):
    result = child(f"with locks.exclusive({prefix!r}): print('acquired')")
    assert result.returncode != 0 and 'installation busy' in result.stderr.lower(), result


@pytest.mark.parametrize('entry', ['launcher', 'cli'])
@pytest.mark.parametrize('args', [[], ['--version'], ['--help'], ['list'], ['create', 'ocs-test-refused']])
def test_exclusive_blocks_normal_startup_before_data_or_dependency_import(tmp_path, entry, args):
    env = dict(os.environ, OPENCODE_SANDBOX_HOME=str(tmp_path / 'other-data'),
               OPENCODE_SANDBOX_CONFIG=str(tmp_path / 'other-config'), HOME=str(tmp_path / 'other-home'))
    code = script(f"""
import sys
sys.argv = ['opencode-sandbox', *{args!r}]
from opencode_sandbox.{entry} import main
main()
""")
    with locks.exclusive():
        result = subprocess.run([sys.executable, '-B', '-c', code, '--version'], env=env,
                                text=True, capture_output=True, timeout=5, check=False)
    assert result.returncode == 2 and 'installation busy' in result.stderr.lower()
    assert not (tmp_path / 'other-data').exists() and not (tmp_path / 'other-config').exists()


def test_bootstrap_refuses_even_if_cli_dependencies_cannot_be_imported():
    code = """
import sys
class MissingDependencies:
    def find_spec(self, fullname, *args):
        if fullname in ('typer', 'opencode_sandbox.core', 'opencode_sandbox.cli'):
            raise AssertionError('bootstrap imported application before exclusion')
sys.meta_path.insert(0, MissingDependencies())
from opencode_sandbox.launcher import main
main()
"""
    with locks.exclusive():
        result = child(code)
    assert result.returncode == 2 and 'installation busy' in result.stderr.lower()
    assert 'AssertionError' not in result.stderr


def test_lease_is_held_before_first_cli_import_and_failure_retains_it_until_exit():
    result = child("""
import sys
class MissingDependencies:
    def find_spec(self, fullname, *args):
        if fullname == 'opencode_sandbox.cli':
            try:
                with locks.exclusive(): raise AssertionError('not excluded')
            except locks.Error: print('excluded before CLI import', flush=True)
            raise ImportError('deliberately unavailable dependency')
sys.meta_path.insert(0, MissingDependencies())
from opencode_sandbox.launcher import main
try: main()
except ImportError:
    assert locks._LEASE is not None
    print('retained until exit')
""")
    assert result.returncode == 0 and result.stdout.splitlines() == ['excluded before CLI import', 'retained until exit'], result.stderr
    with locks.exclusive(): pass


def test_shared_processes_coexist_across_all_data_config_runtime_and_home_overrides(tmp_path):
    env = dict(os.environ, OPENCODE_SANDBOX_HOME=str(tmp_path / 'data'),
               OPENCODE_SANDBOX_CONFIG=str(tmp_path / 'config'), HOME=str(tmp_path / 'home'),
               TMPDIR=str(tmp_path / 'tmp'), XDG_RUNTIME_DIR=str(tmp_path / 'runtime'),
               XDG_DATA_HOME=str(tmp_path / 'xdg'), PIPX_HOME=str(tmp_path / 'pipx'))
    locks.acquire_usage()
    result = child("locks.acquire_usage()\nprint('shared')", env=env)
    assert result.returncode == 0 and result.stdout.strip() == 'shared', result.stderr
    assert_excluded()
    assert not c.BASE.exists() and not c.CONFIG.exists()
    assert list(tmp_path.iterdir()) == [namespace()]


def test_prefix_aliases_converge_but_unrelated_installations_do_not(tmp_path):
    prefix = tmp_path / 'real-prefix'; prefix.mkdir()
    alias = tmp_path / 'alias'; alias.symlink_to(prefix, target_is_directory=True)
    with locks.exclusive(prefix):
        assert_excluded(str(alias))
        result = child(f"with locks.exclusive({str(tmp_path / 'other-prefix')!r}): print('independent')")
        assert result.returncode == 0 and result.stdout.strip() == 'independent', result.stderr


def test_same_python_binary_does_not_merge_separate_venv_prefixes(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'prefix', str(tmp_path / 'venv-one'))
    locks.acquire_usage()
    with locks.exclusive(tmp_path / 'venv-two'): pass
    with pytest.raises(locks.Error, match='busy'), locks.exclusive(): pytest.fail('own lease upgraded')


def test_threaded_startup_is_idempotent_without_an_upgrade_or_descriptor_leak():
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lambda _: locks.acquire_usage(), range(24))) == [None] * 24
    assert len(locks._OPEN) == 1
    assert_excluded()
    with pytest.raises(locks.Error, match='busy'), locks.exclusive(): pytest.fail('shared lease upgraded')
    assert len(locks._OPEN) == 1


def test_main_return_does_not_release_lease_while_non_daemon_workers_drain():
    code = script("""
import sys, threading
thread = threading.Thread(target=lambda: sys.stdin.read())
thread.start()
sys.argv = ['opencode-sandbox', '--version']
from opencode_sandbox.launcher import main
try: main()
except SystemExit as exc: assert exc.code == 0
print('main returned; worker draining', file=sys.stderr, flush=True)
""")
    process = subprocess.Popen([sys.executable, '-B', '-c', code], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert ready(process, process.stderr) == 'main returned; worker draining'
        assert_excluded()
        out, error = process.communicate(timeout=5)
        assert process.returncode == 0 and not error and out.startswith('opencode-sandbox ')
        with locks.exclusive(): pass
    finally:
        if process.poll() is None: process.kill()
        process.communicate(timeout=5)


@pytest.mark.parametrize('mode', ['usage', 'exclusive'])
def test_exec_children_do_not_inherit_any_guard_even_with_close_fds_false(mode):
    check = """
import os
found = []
for name in os.listdir('/proc/self/fd'):
    try: value = os.readlink('/proc/self/fd/' + name)
    except OSError: continue
    if 'opencode-sandbox-locks-' in value: found.append(value)
print(found)
"""
    if mode == 'usage':
        locks.acquire_usage()
        process = subprocess.run([sys.executable, '-c', check], close_fds=False, text=True, capture_output=True, check=False, timeout=5)
    else:
        with locks.exclusive():
            process = subprocess.run([sys.executable, '-c', check], close_fds=False, text=True, capture_output=True, check=False, timeout=5)
    assert process.returncode == 0 and process.stdout.strip() == '[]', process.stderr


def test_fork_only_child_drops_copies_without_unlocking_parent_or_retaining_lease():
    locks.acquire_usage()
    read, write = os.pipe()
    release_read, release_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read); os.close(release_write)
        status = 1
        try:
            assert locks._LEASE is None and not locks._OPEN
            with pytest.raises(locks.Error, match='busy'), locks.exclusive(): pass
            os.write(write, b'ready')
            os.read(release_read, 1)
            status = 0
        finally: os._exit(status)
    os.close(write); os.close(release_read)
    try:
        assert select.select([read], [], [], 5)[0] and os.read(read, 5) == b'ready'
        assert_excluded()
        with locks._MUTEX:
            locks._LEASE.close(); locks._LEASE = None
        # Fork child is still alive, but it cannot keep its parent's lease alive.
        with locks.exclusive(): pass
    finally:
        os.close(release_write); os.close(read)
        _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0


@pytest.mark.parametrize('kind', ['data', 'environment', 'base'])
def test_new_installation_access_refuses_reverse_lock_order(kind):
    guard = c.base_lock('debian', 'build') if kind == 'base' else c.lock('registry' if kind == 'data' else '0' * 16)
    with guard:
        with pytest.raises(locks.Error, match='order violation'): locks.acquire_usage()
        with pytest.raises(locks.Error, match='order violation'), locks.exclusive(): pass
    assert not list(namespace().glob('installation-*.lock')) if namespace().exists() else True


def test_existing_usage_can_be_reentered_inside_later_guards():
    locks.acquire_usage()
    with c.lock('registry'), c.lock('0' * 16), c.base_lock('debian', 'build'):
        locks.acquire_usage()
    assert_excluded()
    assert not c.locks_held()


@pytest.mark.parametrize('bad', ['symlink', 'permissions', 'file'])
def test_unsafe_namespace_refuses_without_repair(tmp_path, bad):
    target = namespace()
    if bad == 'symlink':
        other = tmp_path / 'other'; other.mkdir()
        target.symlink_to(other, target_is_directory=True)
    elif bad == 'permissions': target.mkdir(mode=0o755)
    else: target.write_text('keep')
    before = target.lstat()
    with pytest.raises(locks.Error, match='[Uu]nsafe|safely'): locks.acquire_usage()
    assert target.lstat() == before and not locks._OPEN


@pytest.mark.parametrize('bad', ['symlink', 'hardlink', 'permissions', 'fifo', 'directory'])
def test_unsafe_lock_file_refuses_without_repair(tmp_path, bad):
    with locks.exclusive(): pass
    path, = namespace().glob('installation-*.lock')
    path.unlink()  # isolated fault injection on this test's unheld inode only
    other = tmp_path / 'keep'
    if bad == 'symlink': other.write_text('keep'); path.symlink_to(other)
    elif bad == 'hardlink': other.touch(mode=0o600); os.link(other, path)
    elif bad == 'permissions': path.touch(mode=0o644)
    elif bad == 'fifo': os.mkfifo(path, mode=0o600)
    else: path.mkdir(mode=0o700)
    before = path.lstat()
    with pytest.raises(locks.Error, match='[Uu]nsafe|safely'): locks.acquire_usage()
    assert path.lstat() == before and not locks._OPEN


@pytest.mark.parametrize('directory', [False, True])
def test_replaced_namespace_or_lock_path_refuses_split_inode(monkeypatch, directory):
    real = locks.fcntl.flock
    def changed(fd, operation):
        real(fd, operation)
        path = namespace() if directory else next(namespace().glob('installation-*.lock'))
        path.rename(path.with_name(path.name + '.saved'))
        if directory: path.mkdir(mode=0o700)
        else: path.touch(mode=0o600)
    monkeypatch.setattr(locks.fcntl, 'flock', changed)
    with pytest.raises(locks.Error, match='path changed'): locks.acquire_usage()
    assert not locks._OPEN


def test_reentry_detects_replaced_persistent_inode():
    locks.acquire_usage()
    path, = namespace().glob('installation-*.lock')
    path.rename(path.with_suffix('.saved')); path.touch(mode=0o600)
    with pytest.raises(locks.Error, match='path changed'): locks.acquire_usage()


def test_foreign_owner_is_refused_even_with_safe_permissions(monkeypatch):
    namespace().mkdir(mode=0o700)
    inode = namespace().stat().st_ino
    real = locks.os.fstat
    def fstat(fd):
        result = real(fd)
        if result.st_ino == inode:
            values = list(result); values[4] = os.getuid() + 1
            return os.stat_result(values)
        return result
    monkeypatch.setattr(locks.os, 'fstat', fstat)
    with pytest.raises(locks.Error, match='own UID'): locks.acquire_usage()


def test_unsafe_writable_parent_is_refused_before_creating_namespace(tmp_path):
    tmp_path.chmod(0o777)
    try:
        with pytest.raises(locks.Error, match='parent directory'): locks.acquire_usage()
        assert not namespace().exists()
    finally: tmp_path.chmod(0o700)


def test_relative_prefix_cannot_create_an_alternate_namespace():
    with pytest.raises(locks.Error, match='absolute'), locks.exclusive('relative/venv'): pass
    assert not namespace().exists()


def test_modes_stable_inode_and_exclusive_body_error_are_preserved():
    with pytest.raises(OSError, match='operation body'), locks.exclusive():
        raise OSError('operation body')
    path, = namespace().glob('installation-*.lock')
    inode = path.stat().st_ino
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and stat.S_IMODE(namespace().stat().st_mode) == 0o700
    with locks.exclusive(): assert path.stat().st_ino == inode
    assert not locks._OPEN


@pytest.mark.parametrize('mode', ['usage', 'exclusive'])
def test_process_death_releases_guard_without_inode_replacement(mode):
    body = "locks.acquire_usage()\nprint('ready',flush=True)\ninput()" if mode == 'usage' else "with locks.exclusive():\n print('ready',flush=True)\n input()"
    process = subprocess.Popen([sys.executable, '-B', '-c', script(body)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert ready(process) == 'ready'
        path, = namespace().glob('installation-*.lock')
        inode = path.stat().st_ino
        assert_excluded()
        process.kill(); process.communicate(timeout=5)
        with locks.exclusive(): assert path.stat().st_ino == inode
    finally:
        if process.poll() is None: process.kill()
        process.communicate(timeout=5)
