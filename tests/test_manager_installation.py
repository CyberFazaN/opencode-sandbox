"""Real local evidence with a synthetic runtime identity; no pipx execution or user paths."""
import json
import os
import sys

import pytest

from opencode_sandbox import __version__
from opencode_sandbox import manager_installation as i


@pytest.fixture
def installation(tmp_path, monkeypatch):
    home = tmp_path / 'pipx-home'
    prefix = home / 'venvs/opencode-sandbox'
    bindir = tmp_path / 'custom-bin'
    bindir.mkdir()
    site = prefix / 'lib/python3/site-packages'
    dist = site / f'opencode_sandbox-{__version__}.dist-info'
    dist.mkdir(parents=True)
    module = site / 'opencode_sandbox/__init__.py'
    module.parent.mkdir()
    module.write_text(f'__version__ = {__version__!r}\n')
    python = prefix / 'bin/python'
    python.parent.mkdir()
    python.symlink_to(sys.executable)
    app = python.with_name('opencode-sandbox')
    app.write_text(f'#!{python}\nfrom opencode_sandbox.cli import main\nif __name__ == "__main__":\n    sys.exit(main())\n')
    app.chmod(0o700)
    launcher = bindir / app.name
    launcher.symlink_to(app)
    record = {'pipx_metadata_version': '0.12', 'environment': i.NAME, 'main_package': {
        'package': i.NAME, 'package_or_url': 'git+' + i.URL + '@v' + __version__, 'package_version': __version__,
        'apps': [i.NAME], 'app_paths': [{'__type__': 'Path', '__Path__': str(app)}],
        'include_apps': True, 'include_dependencies': False, 'pip_args': [], 'suffix': '',
        'apps_of_dependencies': ['typer'], 'app_paths_of_dependencies': {'typer': [str(prefix / 'bin/typer')]}},
        'source_interpreter': {'__type__': 'Path', '__Path__': sys._base_executable},
        'python_version': 'Python ' + '.'.join(str(n) for n in sys.version_info[:3]), 'venv_args': [], 'injected_packages': {}}
    direct = {'url': i.URL, 'vcs_info': {'vcs': 'git', 'requested_revision': 'v' + __version__, 'commit_id': 'a' * 40}}
    def save():
        (dist / 'direct_url.json').write_text(json.dumps(direct))
        (prefix / 'pipx_metadata.json').write_text(json.dumps(record))
    save()
    monkeypatch.setattr(i, '_running_distribution', lambda: (module, dist))
    monkeypatch.setattr(sys, 'prefix', str(prefix))
    monkeypatch.setattr(sys, 'executable', str(python))
    monkeypatch.setattr(sys, 'argv', [str(launcher)])
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('PIPX_HOME', str(home))
    monkeypatch.setenv('PIPX_BIN_DIR', str(bindir))
    return record, direct, save, prefix, launcher


def test_custom_paths_source_python_and_tag_are_reconciled_read_only(installation):
    _record, _direct, _save, prefix, launcher = installation
    before = {p: p.read_bytes() for p in (prefix / 'pipx_metadata.json', launcher.resolve())}
    result = i.classify()
    assert result['verified'], result
    assert result['evidence']['tag'] == 'v' + __version__
    assert result['evidence']['commit'] == 'a' * 40
    assert result['evidence']['pipx_home'] == str(prefix.parent.parent)
    assert 'Unavailable' in result['execution'] and 'not yet assessed' in result['guidance']
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('change,reason', [
    ('editable', 'Editable'), ('foreign', 'Foreign'), ('branch', 'full release tag'), ('tag', 'disagree'),
    ('commit', 'commit identity'), ('source', 'recorded source'), ('version', 'recorded source'),
    ('pip_args', 'manual preservation'), ('injected', 'manual preservation'), ('venv_args', 'manual preservation'),
    ('pin', 'manual preservation'), ('suffix', 'manual preservation'), ('backend', 'manual preservation'),
    ('unknown', 'Unrecognized'), ('schema', 'Unrecognized'), ('python_version', 'Python version'),
    ('python', 'interpreter'), ('app_path', 'recorded executable'), ('script', 'template'),
    ('launcher', 'foreign'), ('shadow', 'shadowed'), ('invocation', 'invocation'), ('home', 'another installation'),
    ('unsafe', 'unsafe'), ('symlink', 'unavailable'), ('fifo', 'unsafe'),
    ('environment', 'environment settings'), ('default_python', 'default Python'),
])
def test_inconsistent_or_unpreservable_installation_is_manual_and_never_leaks_options(installation, monkeypatch, tmp_path, change, reason):
    record, direct, save, prefix, launcher = installation
    secret = 'dummy-private-token-123'
    if change == 'editable': direct.update(dir_info={'editable': True})
    if change == 'foreign': direct['url'] = 'https://user:' + secret + '@foreign.invalid/repo.git'
    if change == 'branch': direct['vcs_info']['requested_revision'] = 'main'
    if change == 'tag': direct['vcs_info']['requested_revision'] = 'v1.0.0'
    if change == 'commit': direct['vcs_info']['commit_id'] = 'main'
    if change == 'source': record['main_package']['package_or_url'] = 'git+file:///foreign@v' + __version__
    if change == 'version': record['main_package']['package_version'] = '1.0.0'
    if change == 'pip_args': record['main_package']['pip_args'] = ['--index-url=https://user:' + secret + '@index.invalid']
    if change == 'injected': record['injected_packages'] = {'x': {'package_or_url': secret}}
    if change == 'venv_args': record['venv_args'] = ['--system-site-packages']
    if change == 'pin': record['main_package']['pinned'] = True
    if change == 'suffix': record['main_package']['suffix'] = '-other'
    if change == 'backend': record['backend'] = 'uv'
    if change == 'unknown': record[secret] = secret
    if change == 'schema': record['pipx_metadata_version'] = '999'
    if change == 'python_version': record['python_version'] = 'Python 3.9.0'
    if change == 'python': record['source_interpreter'] = str(launcher.resolve())
    if change == 'app_path': record['main_package']['app_paths'] = [str(tmp_path / 'other')]
    if change == 'script': launcher.resolve().write_text('#!/bin/sh\necho ' + secret)
    if change == 'launcher': launcher.unlink(); launcher.write_text('foreign ' + secret)
    if change == 'shadow':
        shadow = tmp_path / 'shadow'; shadow.mkdir()
        (shadow / i.NAME).write_text('#!/bin/sh\necho foreign'); (shadow / i.NAME).chmod(0o700)
        monkeypatch.setenv('PATH', str(shadow) + os.pathsep + os.environ['PATH'])
    if change == 'invocation': monkeypatch.setattr(sys, 'argv', [str(prefix / 'bin' / i.NAME)])
    if change == 'home': monkeypatch.setenv('PIPX_HOME', str(tmp_path / 'other-home'))
    if change == 'environment': monkeypatch.setenv('PIPX_CUSTOM_UNKNOWN', secret)
    if change == 'default_python': monkeypatch.setenv('PIPX_DEFAULT_PYTHON', str(prefix / 'bin/opencode-sandbox'))
    save()
    evidence = prefix / 'pipx_metadata.json'
    if change == 'unsafe': evidence.chmod(0o666)
    if change == 'symlink': evidence.rename(prefix / 'preserve'); evidence.symlink_to(prefix / 'preserve')
    if change == 'fifo': evidence.unlink(); os.mkfifo(evidence)
    result = i.classify()
    assert not result['verified'] and reason.lower() in result['reason'].lower(), result
    assert secret not in json.dumps(result) and 'No installation was changed' in result['guidance']
    assert 'evidence' not in result


@pytest.mark.parametrize('schema', ['0.5', '0.6', '0.12'])
def test_explicitly_recognized_wire_versions_with_default_settings(installation, schema):
    record, _, save, *_ = installation
    record['pipx_metadata_version'] = schema
    save()
    assert i.classify()['verified']


def test_recognized_custom_resource_paths_and_same_default_python_are_retained(installation, monkeypatch, tmp_path):
    record, _, _, _, _ = installation
    for name in ('MAN_DIR', 'COMPLETION_DIR', 'SHARED_LIBS'):
        monkeypatch.setenv('PIPX_' + name, str(tmp_path / name.lower()))
    monkeypatch.setenv('PIPX_DEFAULT_PYTHON', record['source_interpreter']['__Path__'])
    result = i.classify()
    assert result['verified'], result
    assert result['evidence']['locations'] == {name.lower(): str(tmp_path / name.lower()) for name in ('MAN_DIR', 'COMPLETION_DIR', 'SHARED_LIBS')}
