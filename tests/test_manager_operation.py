"""Recovery inputs are strict private immutable operation evidence, not caches or consent grants."""
import json
import os
from pathlib import Path

import pytest
from test_manager_installer import prepared as parked_installation
from test_manager_installer import tools as external_tools

from opencode_sandbox import manager_operation as operation

prepared = parked_installation
tools = external_tools


def test_private_identity_bound_operation_round_trips_without_target_import_or_state_creation(prepared):
    record, path, *_ = prepared
    assert operation.read(path) == record
    assert not list((Path(record['prefix']).parent.parent / '.opencode-sandbox-updates').glob('*.json'))
    assert path.stat().st_mode & 0o777 == 0o600
    rendered = operation.instructions(record, path)
    assert record['previous']['tag'] in rendered and str(path) in rendered
    assert 'never installs' in rendered and 'not a backup' in rendered and 'identical dependencies' in rendered


@pytest.mark.parametrize('fault', ['format', 'settings', 'source', 'nonce', 'unknown', 'mode', 'symlink', 'hardlink', 'fifo', 'duplicate', 'huge'])
def test_unknown_unsafe_or_changed_recovery_record_is_preserved_not_repaired(prepared, fault):
    record, path, *_ = prepared
    altered = json.loads(path.read_text())
    if fault == 'format': altered['format'] = 999
    if fault == 'settings': altered['settings']['PIPX_HOME'] = '/foreign'
    if fault == 'source': altered['target']['source'] = 'https://user:dummy-secret@foreign.invalid'
    if fault == 'nonce': altered['nonce'] = 'changed'
    if fault == 'unknown': altered['success-cache'] = {'ok': True, 'installer_exit': 0}
    path.write_text(json.dumps(altered))
    if fault == 'mode': path.chmod(0o644)
    if fault == 'symlink': path.rename(path.with_suffix('.saved')); path.symlink_to(path.with_suffix('.saved'))
    if fault == 'hardlink': os.link(path, path.with_suffix('.link'))
    if fault == 'fifo': path.unlink(); os.mkfifo(path, mode=0o600)
    if fault == 'duplicate': path.write_text('{"format":1,"format":2}')
    if fault == 'huge': path.write_text(' ' * (operation.LIMIT + 1))
    before = path.lstat()
    with pytest.raises((RuntimeError, ValueError, OSError, TypeError, KeyError)) as caught: operation.read(path)
    assert 'dummy-secret' not in str(caught.value)
    assert path.lstat().st_ino == before.st_ino
    assert not list((Path(record['prefix']).parent.parent / '.opencode-sandbox-updates').glob('*.json'))


def test_changed_or_foreign_quiescence_evidence_cannot_be_treated_as_process_completion(prepared):
    record, path, *_ = prepared
    from opencode_sandbox import installation_state as state
    assert not operation.quiescence(record, path, state.owner())
    operation.record_quiescence(record, path)
    assert operation.quiescence(record, path, state.owner())
    proof = operation._quiescence_path(path, state.owner())
    changed = json.loads(proof.read_bytes()); changed['operation'] = 'f' * 64
    proof.write_text(json.dumps(changed))
    with pytest.raises(operation.Refused, match='quiescence'): operation.quiescence(record, path, state.owner())


def test_operation_inputs_and_results_never_overwrite_existing_private_evidence(prepared):
    record, path, *_ = prepared
    before = path.read_bytes()
    with pytest.raises(FileExistsError): operation.write(path, record)
    operation.result(path, {'operation': record['operation'], 'result': 'unavailable'})
    operation.result(path, {'operation': record['operation'], 'result': 'target-verified'})
    assert len(list(path.parent.glob('result-*.json'))) == 2 and path.read_bytes() == before
