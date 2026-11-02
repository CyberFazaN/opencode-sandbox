"""Explicit, locked version checks; optional temporary start never invokes normal launch flows."""
import json
import os
import select
import stat
import subprocess
import sys
from pathlib import Path

from . import core as c
from . import opencode_versions as v
from . import runtime_identity as rid


def cleanup_notice(m):
    path = c.env_dir(m['id']) / 'version-check.json'
    if not path.exists() and not path.is_symlink(): return None
    return 'A temporary check has unconfirmed cleanup. Inspect actual state and use Stop (F6) or opencode-sandbox stop ' + m['name'] + '.'


def clear_cleanup(m):
    """Explicit Stop may reconcile only this protocol's safe record and the same container."""
    marker = c.env_dir(m['id']) / 'version-check.json'
    try:
        fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return
    except OSError:
        raise c.SandboxError('Environment stopped, but temporary-check evidence is unsafe; record preserved for manual review') from None
    try:
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 4096:
                raise ValueError()
            record = json.loads(stream.read(4097))
        if not isinstance(record, dict) or type(record.get('schema')) is not int or record['schema'] != 1:
            raise ValueError()
        if record.get('container') != v._environment_identity(m)['container']:
            raise ValueError()
        state = c.inspect_container(m)
        if state is None or state.get('Running'): raise ValueError()
        current = marker.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino): raise ValueError()
    except (ValueError, TypeError, OSError, c.SandboxError):
        raise c.SandboxError('Environment stopped, but temporary-check record format/identity is unverified; record preserved for manual review') from None
    marker.unlink()


class StartGuard:
    """The child retains the same flock after abrupt parent death. Never arm without this guard."""
    def __init__(self, m, identity, lock):
        self.m, self.identity, self.lock = m, identity, lock
        self.process = None

    def start(self):
        marker = c.env_dir(self.m['id']) / 'version-check.json'
        try:
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            raise c.SandboxError('Unresolved temporary-check evidence already exists. Inspect actual state and use Stop (F6) before retrying; record preserved') from None
        with os.fdopen(fd, 'w') as stream:
            json.dump({'schema': 1, 'container': self.identity['container'], 'error': 'Temporary check in progress; cleanup not yet confirmed'}, stream)
            stream.flush(); os.fsync(stream.fileno())
        self.process = subprocess.Popen(
            [sys.executable, '-I', '-B', str(Path(__file__).with_name('temporary_check_guard.py')),
             self.identity['endpoint'], self.m['id'], self.identity['container'], str(marker), str(self.lock.fileno())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            pass_fds=(self.lock.fileno(),), env=rid.docker_env(), start_new_session=True)
        self.process.stdin.write('start\n'); self.process.stdin.flush()
        cancelled = (c._RUNTIME_FEEDBACK.get() or {}).get('cancelled')
        while not select.select([self.process.stdout], [], [], .05)[0]:
            if cancelled and cancelled(): raise rid.Cancelled()
            if self.process.poll() is not None: break
        if self.process.stdout.readline().strip() != 'started':
            raise c.SandboxError('Temporary start failed; inspect actual container state and Check Details')

    def finish(self):
        if self.process is None: return
        self.process.stdin.close()
        self.process.stdin = None
        # Child start/inspect/stop budgets are finite. Do not kill the restoration owner.
        out, _ = self.process.communicate()
        try:
            result = json.loads(out.strip().splitlines()[-1])
            if self.process.returncode or result.get('cleanup') not in ('stopped', 'not-started'): raise ValueError()
        except (ValueError, IndexError, AttributeError):
            raise c.SandboxError('Temporary-check cleanup was not fully successful. '
                                 + (cleanup_notice(self.m) or 'Inspect actual state and use Stop (F6) before retrying.')) from None
        if result.get('error'):
            raise c.SandboxError(result['error'] + ('; original stopped state restored' if result['cleanup'] == 'stopped' else '; no temporary start performed'))


def check(m, *, expected=None):
    """Restore original running state on all exits. Inventory and ordinary CLI reports stay passive."""
    c.ensure_runtime(False)
    with c.lock(m['id']) as lock:
        m = c.resolve(m['id'])
        if m.get('operation'): raise c.pending_operation(m)
        state = c.inspect_container(m)
        if state is None:
            if expected is not None and expected != (None, False, v._consent_metadata(m)):
                raise c.SandboxError('Environment changed since Check All review; check again')
            return {'state': 'not-created', 'version': None, 'observation': None, 'verification': 'unknown'}
        identity = v._environment_identity(m)
        if expected is not None and (identity, bool(state.get('Running')), v._consent_metadata(m)) != expected:
            raise c.SandboxError('Environment changed since Check All review; check again')
        if state.get('Paused') or state.get('Restarting') or state.get('Dead'):
            raise c.SandboxError('Paused, restarting or dead container; inspect its state before checking')
        if state.get('Running'):
            return v.environment_version(m, check=True)
        c.assert_volume_owned(m)
        c.recheck_mount(m)
        mounted = c.mounted_profile(m)
        if mounted and not os.path.exists(mounted):
            raise c.SandboxError('Mounted provider profile is missing; restore it before starting this container')
        guard = StartGuard(m, identity, lock)
        result = None
        try:
            guard.start()
            result = v.environment_version(m, check=True)
        finally:
            # A cancellation BaseException must not skip or cancel restoration.
            with c.runtime_feedback(progress=None, cancelled=None):
                guard.finish()
        current = c.resolve(m['id'])
        if v._environment_identity(current) != identity:
            raise c.SandboxError('Container changed during the check; no fresh result verified')
        state = c.inspect_container(current)
        if state is None or state.get('Running'):
            raise c.SandboxError('Restoration to stopped state could not be verified; inspect actual state and use Stop (F6)')
        return {**result, 'state': 'stopped'}


def review(keys):
    """A fixed batch snapshot, not authority inferred from cached table rows."""
    c.ensure_runtime(False)
    targets, stopped = {}, []
    for key in keys:
        m = c.resolve(key)
        with c.lock(key):
            m = c.resolve(key)
            state = c.inspect_container(m)
            if state is not None and not m.get('operation'):
                targets[key] = (v._environment_identity(m), bool(state.get('Running')), v._consent_metadata(m))
                if not state.get('Running'): stopped.append(m['name'])
            else:
                targets[key] = (None, False, v._consent_metadata(m))
    return targets, stopped
