"""An incomplete manager operation outlives its helper/venv; caches and lock expiry cannot clear it."""
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from opencode_sandbox import installation_locks as locks
from opencode_sandbox import installation_state as state


@pytest.fixture
def target(tmp_path):
    prefix = tmp_path / 'pipx/venvs/opencode-sandbox'
    prefix.mkdir(parents=True)
    return prefix


def record(target):
    source = {'version': '6.1.0', 'tag': 'v6.1.0', 'commit': 'a' * 40, 'source': state.SOURCE}
    return {'format': 1, 'prefix': str(target), 'operation': 'b' * 64, 'phase': 'prepared',
            'record': str(target.parent.parent / 'owned-operation/operation.json'), 'owner': state.owner(), 'installer': None,
            'previous': source, 'target': {**source, 'version': '6.2.0', 'tag': 'v6.2.0', 'commit': 'c' * 40},
            'result': None, 'at': time.time()}


def child_start(target, *, environment=None):
    code = ('from pathlib import Path\nfrom opencode_sandbox import installation_locks as locks\n'
            f'locks._TMP=Path({str(locks._TMP)!r})\n'
            f'import sys\nsys.prefix={str(target)!r}\n'
            'try: locks.acquire_usage()\n'
            'except locks.Error as exc: print(str(exc));raise SystemExit(2)\n'
            'print("ordinary startup allowed")\n')
    env = dict(os.environ, PYTHONPATH=str(Path(locks.__file__).parents[1]))
    if environment: env.update(environment)
    return subprocess.run([sys.executable, '-B', '-c', code], env=env, text=True, capture_output=True, check=False, timeout=5)


def test_pending_state_blocks_normal_startup_after_exclusive_owner_has_finished(target):
    value = record(target)
    with locks.exclusive(target): locks.record_operation(value, target)
    assert locks.operation_state(target) == value
    result = child_start(target)
    assert result.returncode == 2 and 'update incomplete' in result.stdout and 'ordinary startup allowed' not in result.stdout
    assert state.location(target).is_relative_to(target.parent.parent) and not state.location(target).is_relative_to(target)
    assert child_start(target, environment={'HOME': str(target.parent / 'other-home'),
        'OPENCODE_SANDBOX_HOME': str(target.parent / 'other-data'), 'OPENCODE_SANDBOX_CONFIG': str(target.parent / 'other-config')}).returncode == 2


def test_missing_operation_state_is_read_only_and_normal_startup_is_unchanged(target):
    assert child_start(target).returncode == 0
    assert not state.location(target).parent.exists()


def test_only_verified_completion_unblocks_and_old_operation_is_immutable(target):
    value = record(target)
    with locks.exclusive(target):
        locks.record_operation(value, target)
        locks.record_operation({**value, 'phase': 'installing'}, target)
        locks.record_operation({**value, 'phase': 'verifying'}, target)
        complete = {**value, 'phase': 'complete', 'result': 'target-verified'}
        locks.record_operation(complete, target)
        with pytest.raises(locks.Error, match='immutable'): locks.record_operation(complete, target)
    assert child_start(target).returncode == 0 and locks.operation_state(target) == complete
    assert state.location(target).is_file()


def test_operation_write_requires_actual_kernel_exclusion_and_never_converts_usage(target, monkeypatch):
    with pytest.raises(locks.Error, match='exclusive'): locks.record_operation(record(target), target)
    monkeypatch.setattr(sys, 'prefix', str(target))
    locks.acquire_usage()
    with pytest.raises(locks.Error, match='exclusive'): locks.record_operation(record(target), target)
    assert locks._LEASE is not None and not state.location(target).parent.exists()


@pytest.mark.parametrize('change', ['format', 'prefix', 'phase', 'operation', 'source', 'complete', 'installer', 'owner', 'at'])
def test_invalid_or_unverified_record_cannot_authorize_startup_or_overwrite_state(target, change):
    value = record(target)
    altered = copy.deepcopy(value)
    if change == 'format': altered['format'] = 2
    if change == 'prefix': altered['prefix'] = '/foreign'
    if change == 'phase': altered['phase'] = 'guess-success'
    if change == 'operation': altered['operation'] = 'short'
    if change == 'source': altered['target']['source'] = 'https://user:dummy-secret@foreign.invalid'
    if change == 'complete': altered.update(phase='complete', result='target-unverified')
    if change == 'installer': altered['installer'] = {'pid': 1, 'pgid': True, 'start': '1'}
    if change == 'owner': altered['owner']['uid'] = -1
    if change == 'at': altered['at'] = float('nan')
    with locks.exclusive(target):
        locks.record_operation(value, target)
        before = state.location(target).read_bytes()
        with pytest.raises(locks.Error): locks.record_operation(altered, target)
    assert state.location(target).read_bytes() == before and child_start(target).returncode == 2


@pytest.mark.parametrize('kind', ['schema', 'malformed', 'duplicate', 'mode', 'symlink', 'hardlink', 'fifo', 'oversized'])
def test_unsafe_unknown_or_corrupt_existing_state_is_preserved_and_never_silently_reset(target, kind):
    path = state.location(target); path.parent.mkdir(mode=0o700)
    if kind == 'fifo': os.mkfifo(path, mode=0o600)
    else:
        value = record(target)
        if kind == 'schema': value['format'] = 999
        path.write_text(json.dumps(value)); path.chmod(0o600)
        if kind == 'malformed': path.write_text('dummy-secret malformed state')
        if kind == 'duplicate': path.write_text('{"format":1,"format":2}')
        if kind == 'mode': path.chmod(0o644)
        if kind == 'symlink': path.rename(path.with_suffix('.saved')); path.symlink_to(path.with_suffix('.saved'))
        if kind == 'hardlink': os.link(path, path.with_suffix('.link'))
        if kind == 'oversized': path.write_bytes(b' ' * (state.LIMIT + 1))
    before = path.lstat()
    result = child_start(target)
    assert result.returncode == 2 and 'dummy-secret' not in result.stdout + result.stderr
    with locks.exclusive(target), pytest.raises(locks.Error): locks.record_operation(record(target), target)
    assert path.lstat().st_ino == before.st_ino


def test_pending_operation_cannot_be_replaced_by_new_consent_or_cache_success(target):
    value = record(target)
    with locks.exclusive(target):
        locks.record_operation(value, target)
        with pytest.raises(locks.Error, match='recovered first'):
            locks.record_operation({**value, 'operation': 'd' * 64}, target)
    assert state.read(target)['operation'] == value['operation']


def test_previous_verified_recovery_can_close_known_operation_without_erasing_history(target):
    value = record(target)
    with locks.exclusive(target):
        locks.record_operation(value, target)
        locks.record_operation({**value, 'phase': 'manual-recovery', 'result': 'interrupted'}, target)
        locks.record_operation({**value, 'phase': 'verifying'}, target)
        complete = {**value, 'phase': 'complete', 'result': 'previous-verified'}
        locks.record_operation(complete, target)
    assert child_start(target).returncode == 0 and state.read(target) == complete
