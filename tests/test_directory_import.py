import json
import os
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from opencode_sandbox import agent_context as ac
from opencode_sandbox import core as c
from opencode_sandbox import directory_import as di
from opencode_sandbox import workspaces as ws
from opencode_sandbox.cli import app


def test_full_tree_is_literal_and_independent(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / '.git').mkdir()  # Not a Git repository, and no Git command may run.
    (source / '.git' / 'config').write_text('literal config')
    (source / '.gitignore').write_text('ignored\n')
    (source / 'ignored').write_text('included')
    (source / '.env').write_text('dummy=example')
    (source / 'untracked').write_bytes(b'\x00\x01')
    (source / 'node_modules').mkdir()
    (source / 'empty').mkdir()
    (source / 'empty').chmod(0o750)
    (source / 'script').write_text('echo ok\n')
    (source / 'script').chmod(0o4750)
    os.utime(source / 'script', ns=(123_000_000_000, 123_000_000_001))
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'private').write_text('not part of import')
    (source / 'external').symlink_to(outside)
    (source / 'relative').symlink_to('ignored')
    (source / 'dangling').symlink_to('missing')

    def no_command(*args, **kwargs):
        pytest.fail(f'Unexpected external command: {args}')

    monkeypatch.setattr(c, 'call', no_command)
    created = CliRunner().invoke(app, ['create', 'full-copy', '--source', str(source), '--copy-entire-directory'])
    assert created.exit_code == 0, created.output
    assert 'Review the folder for credentials' in created.output and 'Copy entire directory' in created.output
    m = c.resolve('full-copy')
    assert (m['kind'], m['workspace_import'], m['base_commit']) == ('project', 'entire', None)
    dest = ws.path(m)
    assert dest != source and not ws.is_direct(m)
    assert sorted(p.name for p in dest.iterdir()) == sorted(p.name for p in source.iterdir())
    assert (dest / '.git' / 'config').read_text() == 'literal config'
    assert (dest / '.env').read_text() == 'dummy=example' and (dest / 'untracked').read_bytes() == b'\x00\x01'
    assert (dest / 'ignored').read_text() == 'included'
    for name in ('relative', 'dangling', 'external'):
        assert (dest / name).is_symlink() and os.readlink(dest / name) == os.readlink(source / name)
    assert list((dest / 'empty').iterdir()) == [] and stat.S_IMODE((dest / 'empty').stat().st_mode) == 0o750
    assert stat.S_IMODE((dest / 'script').stat().st_mode) == 0o750
    assert (dest / 'script').stat().st_mtime_ns == (source / 'script').stat().st_mtime_ns
    (dest / 'ignored').write_text('sandbox edit')
    assert (source / 'ignored').read_text() == 'included'
    text = ac.render(m, **c.guidance_inputs(m, observe=False))
    assert 'Copy entire directory' in text and 'The original is not mounted' in text and str(source) not in text
    result = CliRunner().invoke(app, ['changes', 'show', 'full-copy'])
    assert result.exit_code == 0 and 'rather than a Git diff' in result.output
    monkeypatch.setattr(c, 'observed_runtime', lambda m: None)
    result = CliRunner().invoke(app, ['config', 'show', 'full-copy'])
    assert result.exit_code == 0
    settings = json.loads(result.output)
    assert settings['kind'] == 'project' and settings['workspace_origin'] == 'copy' and settings['workspace_import'] == 'entire'


def test_full_copy_from_git_subdirectory_and_promotion_preserve_workspace(tmp_path, monkeypatch):
    source = tmp_path / 'repo' / 'sub'
    source.mkdir(parents=True)
    (source.parent / '.git').mkdir()
    (source / '.ignored').write_text('included')
    monkeypatch.setattr(c, 'call', lambda *a, **kw: pytest.fail('Full import ran a subprocess'))
    m = c.create('disposable', 'quick', source, copy_entire_directory=True)
    assert (ws.path(m) / '.ignored').is_file()
    assert 'quick (disposable)' in '\n'.join(ac.workspace_lines(m))
    c.promote(m, 'scratch')
    kept = c.resolve(m['id'])
    assert kept['kind'] == 'scratch' and ws.path(kept) == ws.path(m)
    assert 'Copy entire directory' in ws.describe(kept) and 'disposable' not in '\n'.join(ac.workspace_lines(kept))


@pytest.mark.parametrize('method', ['fifo', 'mount', 'save'])
def test_full_copy_refuses_unsafe_entries_and_cleans_up(tmp_path, monkeypatch, method):
    source = tmp_path / 'source'
    source.mkdir()
    sub = source / 'readonly'
    sub.mkdir()
    (sub / 'plain').write_text('original')
    sub.chmod(0o500)
    if method == 'fifo':
        os.mkfifo(source / 'pipe')
        error = 'special files'
    elif method == 'mount':
        # Exercise refusal even when a simulated nested bind is on the same st_dev.
        monkeypatch.setattr(di, '_mount_id', lambda fd: 'nested' if Path(os.readlink(f'/proc/self/fd/{fd}')) == sub else 'source')
        error = 'nested mounts'
    else:
        def fail_save(m):
            raise c.SandboxError('save error')
        monkeypatch.setattr(c, 'save', fail_save)
        error = 'save error'

    with pytest.raises(c.SandboxError, match=error):
        c.create('refused', source=source, copy_entire_directory=True)
    assert (sub / 'plain').read_text() == 'original'
    assert not list((c.BASE / 'environments').iterdir())
    sub.chmod(0o700)


def test_full_copy_validates_source_and_mode(tmp_path):
    for source in (Path.home(), Path('/etc'), c.BASE.parent):
        with pytest.raises(c.SandboxError, match='Refusing'):
            c.create('refused', source=source, copy_entire_directory=True)
    for opts in ({}, {'workspace_mode': 'direct', 'workspace': tmp_path}, {'source': tmp_path, 'kind': 'scratch'},
                 {'source': tmp_path, 'include_working_changes': True}):
        with pytest.raises(c.SandboxError, match='Copy entire directory'):
            c.create('refused', copy_entire_directory=True, **opts)


def test_copy_reads_the_checked_file_not_a_replacement_symlink(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    entry = source / 'entry'
    entry.write_text('selected file')
    outside = tmp_path / 'private'
    outside.write_text('outside the selection')
    mount_id = di._mount_id

    def swap_after_open(fd):
        if Path(os.readlink(f'/proc/self/fd/{fd}')) == entry:
            entry.rename(source / 'original')
            entry.symlink_to(outside)
        return mount_id(fd)

    monkeypatch.setattr(di, '_mount_id', swap_after_open)
    m = c.create('pinned', source=source, copy_entire_directory=True)
    assert not (ws.path(m) / 'entry').is_symlink()
    assert (ws.path(m) / 'entry').read_text() == 'selected file'


@pytest.mark.parametrize('kind', ['scratch', 'project', 'quick'])
def test_managed_start_uses_the_generated_workspace_not_the_source(monkeypatch, tmp_path, kind):
    from docker_fixtures import start_transport

    source = tmp_path / 'source'
    source.mkdir()
    copies = kind != 'scratch'
    m = c.create('managed', kind, source if copies else None, copy_entire_directory=copies)
    calls = []
    monkeypatch.setattr(c, 'inspect_container', lambda m: None)
    monkeypatch.setattr(c, 'ensure_volume', lambda m: None)
    monkeypatch.setattr(c, 'ensure_runtime', lambda *a: None)
    monkeypatch.setattr(c, 'docker', start_transport(calls))
    c.start(m)
    run = next(cmd for cmd in calls if cmd[0] == 'run')
    assert f'type=bind,src={ws.managed_path(m)},dst=/workspace' in run
    assert not any(arg.startswith(f'type=bind,src={source},') for arg in run)
    assert ('Copy entire directory' if copies else 'started empty') in ac.path(m, c.env_dir).read_text()
