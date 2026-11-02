"""Real configuration-presence refusals, including test-owned frozen system paths."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from manager_policy_fixture import SYSTEM_CONFIGS, system_paths, system_source

from opencode_sandbox import manager_network as policy


def inputs(root):
    evidence = {'venv': str(root / 'venvs/opencode-sandbox'), 'locations': {'shared_libs': str(root / 'shared')}}
    facts = {'pipx_runtime': {'runtime': {'prefix': str(root / 'external')}}}
    context = {'HOME': str(root / 'home'), 'XDG_CONFIG_HOME': str(root / 'home/.config'),
               'XDG_CONFIG_DIRS': str(root / 'xdg')}
    return evidence, facts, context


def test_production_system_paths_and_default_refusal_are_not_changed_by_fixture_isolation(tmp_path):
    assert policy.SYSTEM_CONFIGS == SYSTEM_CONFIGS
    assert policy.configurations.__kwdefaults__['system'] == SYSTEM_CONFIGS
    source = Path(policy.__file__).read_bytes()
    isolated = system_source(source, system_paths(tmp_path / 'system'))
    assert isolated != source and Path(policy.__file__).read_bytes() == source
    args = inputs(tmp_path)
    if any(os.path.lexists(value) for value in SYSTEM_CONFIGS):
        with pytest.raises(policy.Refused, match='manual preservation'):
            policy.configurations(*args)
    else:
        assert set(map(Path, SYSTEM_CONFIGS)) <= set(policy.configurations(*args))


@pytest.mark.parametrize('index', range(3))
@pytest.mark.parametrize('kind', ['absent', 'unreadable', 'broken-link'])
def test_parent_and_frozen_checks_refuse_owned_system_files_without_reading_or_changing_them(tmp_path, index, kind):
    paths = system_paths(tmp_path / 'system')
    path = Path(paths[index])
    if kind != 'absent':
        path.parent.mkdir(parents=True)
        if kind == 'broken-link':
            path.symlink_to(tmp_path / 'missing-config-target')
        else:
            path.write_bytes(b'dummy-secret-config-contents')
            path.chmod(0)
    before = path.lstat() if kind != 'absent' else None
    args = inputs(tmp_path)
    if kind == 'absent':
        assert set(map(Path, paths)) <= set(policy.configurations(*args, system=paths))
    else:
        with pytest.raises(policy.Refused, match='manual preservation'):
            policy.configurations(*args, system=paths)
    raw = system_source(Path(policy.__file__).read_bytes(), paths)
    code = (raw.decode() + '\ntry:\n' + f' configurations(*{args!r})\n'
            'except Refused:\n print("refused");raise SystemExit(2)\nprint("allowed")\n')
    completed = subprocess.run([sys.executable, '-I', '-B', '-S', '-c', code], capture_output=True,
                               text=True, timeout=5, check=False)
    assert completed.returncode == (0 if kind == 'absent' else 2), completed.stderr
    assert completed.stdout.strip() == ('allowed' if kind == 'absent' else 'refused')
    assert 'dummy-secret' not in completed.stdout + completed.stderr
    if before is not None:
        after = path.lstat()
        assert (after.st_mode, after.st_ino, after.st_size, after.st_mtime_ns) == (before.st_mode, before.st_ino, before.st_size, before.st_mtime_ns)
        if kind == 'broken-link':
            assert path.readlink() == tmp_path / 'missing-config-target'
        else:
            path.chmod(0o600)  # test operator cleanup, only after unchanged-mode checks
            assert path.read_bytes() == b'dummy-secret-config-contents'
