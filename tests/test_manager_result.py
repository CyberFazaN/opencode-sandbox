"""Expected installed files are checked independently of pipx status, caches and exit codes."""
import json
import os
import sys
from pathlib import Path

import pytest
from test_manager_installation import installation as local_installation

from opencode_sandbox import manager_installation as installation_module
from opencode_sandbox import manager_result as result

installation = local_installation


@pytest.fixture
def installed(installation):
    record, _direct, _save, prefix, launcher = installation
    dist = next(prefix.glob('lib/python*/site-packages/*.dist-info'))
    (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: opencode-sandbox\nVersion: 6.1.0\n')
    (dist / 'entry_points.txt').write_text('[console_scripts]\nopencode-sandbox = opencode_sandbox.launcher:main\n')
    app = launcher.resolve()
    app.write_text(f'#!{prefix / "bin/python"}\nimport sys\nfrom opencode_sandbox.launcher import main\n'
                   "if __name__ == '__main__':\n    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n    sys.exit(main())\n")
    files = [app, dist / 'METADATA', dist / 'RECORD', dist / 'entry_points.txt', dist / 'direct_url.json',
             dist.parent / 'opencode_sandbox/__init__.py']
    (dist / 'RECORD').write_text(''.join(os.path.relpath(path, dist.parent) + ',,\n' for path in files))
    (prefix / 'pyvenv.cfg').write_text('include-system-site-packages = false\nversion = '
                                    + '.'.join(map(str, sys.version_info[:3])) + '\nexecutable = ' + sys._base_executable + '\n')
    settings = {'PIPX_HOME': str(prefix.parent.parent), 'PIPX_BIN_DIR': str(launcher.parent),
                'PIPX_DEFAULT_PYTHON': str(installation_module._path(record['source_interpreter']))}
    expected = {'version': '6.1.0', 'tag': 'v6.1.0', 'commit': 'a' * 40, 'source': installation_module.URL}
    return prefix, settings, expected, record['python_version'], dist, installation


def inspect(installed):
    prefix, settings, expected, version, *_ = installed
    return result.inspect(prefix, settings, expected, python_version=version)


def test_expected_files_source_commit_launcher_and_preserved_settings_agree_without_execution(installed):
    value = inspect(installed)
    assert value['version'] == '6.1.0' and value['commit'] == 'a' * 40
    assert value['launcher'] == str(Path(installed[1]['PIPX_BIN_DIR']) / 'opencode-sandbox')


@pytest.mark.parametrize('fault', ['source', 'commit', 'tag', 'version', 'metadata-version', 'duplicate-version',
    'foreign-launcher', 'script-body', 'entrypoint', 'injected', 'python-version', 'python-selection', 'system-site',
    'config-version', 'record-outside', 'record-symlink', 'record-empty', 'record-incomplete', 'module-symlink', 'ambiguous'])
def test_incomplete_foreign_or_unexpected_result_never_verifies_or_repairs_unfamiliar_data(installed, tmp_path, fault):
    prefix, _settings, _expected, _version, dist, original = installed
    record, direct, save, _, launcher = original
    if fault == 'source': direct['url'] = 'https://user:dummy-secret@foreign.invalid'
    if fault == 'commit': direct['vcs_info']['commit_id'] = 'b' * 40
    if fault == 'tag': direct['vcs_info']['requested_revision'] = 'v9.0.0'
    if fault == 'version': record['main_package']['package_version'] = '9.0.0'
    if fault == 'metadata-version': (dist / 'METADATA').write_text('Name: opencode-sandbox\nVersion: 9.0.0\n')
    if fault == 'duplicate-version':
        with (dist / 'METADATA').open('a') as stream: stream.write('Version: 9.0.0\n')
    if fault == 'foreign-launcher': launcher.unlink(); launcher.write_text('dummy-secret-foreign')
    if fault == 'script-body':
        with launcher.resolve().open('a') as stream: stream.write('print("dummy-secret")\n')
    if fault == 'entrypoint': (dist / 'entry_points.txt').write_text('[console_scripts]\nopencode-sandbox=foreign:main\n')
    if fault == 'injected': record['injected_packages'] = {'foreign': {}}
    if fault == 'python-version': record['python_version'] = 'Python 3.9.0'
    if fault == 'python-selection': record['source_interpreter'] = str(tmp_path / 'foreign-python')
    if fault in ('system-site', 'config-version'):
        config = prefix / 'pyvenv.cfg'
        config.write_text(config.read_text().replace('false', 'true') if fault == 'system-site' else 'version = 9.9.9\n')
    if fault == 'record-outside':
        with (dist / 'RECORD').open('a') as stream: stream.write(str(tmp_path / 'foreign-file') + ',,\n')
    if fault == 'record-symlink':
        link = prefix / 'outside'; link.symlink_to(tmp_path)
        with (dist / 'RECORD').open('a') as stream: stream.write(str(link / 'foreign-file') + ',,\n')
    if fault == 'record-empty': (dist / 'RECORD').write_text('')
    if fault == 'record-incomplete': (dist / 'RECORD').write_text('opencode_sandbox/__init__.py,,\n')
    if fault == 'module-symlink':
        module = dist.parent / 'opencode_sandbox/__init__.py'; module.unlink(); module.symlink_to(tmp_path / 'foreign-module.py')
    if fault == 'ambiguous': dist.with_name('opencode_sandbox-9.0.0.dist-info').mkdir()
    save()
    before = {str(path): path.lstat().st_ino for path in (dist / 'METADATA', dist / 'RECORD', launcher)}
    with pytest.raises((RuntimeError, OSError, ValueError)) as caught: inspect(installed)
    assert 'dummy-secret' not in str(caught.value)
    assert before == {str(path): path.lstat().st_ino for path in (dist / 'METADATA', dist / 'RECORD', launcher)}


def test_record_inspection_never_imports_or_executes_the_target_package(installed, tmp_path):
    marker = tmp_path / 'must-not-run'
    module = installed[4].parent / 'opencode_sandbox/__init__.py'
    module.write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
    assert inspect(installed)['version'] == '6.1.0' and not marker.exists()
    # Deliberately only filesystem evidence: a separate fresh runtime query must catch wrong code.
    assert not marker.exists()


def test_unknown_record_fields_cannot_be_hidden_by_healthy_cached_or_installer_results(installed):
    prefix = installed[0]
    value = json.loads((prefix / 'pipx_metadata.json').read_text())
    value['unknown-success-cache'] = {'ok': True, 'installer_exit': 0}
    (prefix / 'pipx_metadata.json').write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='Unrecognized'): inspect(installed)


def test_long_path_shell_launcher_cannot_claim_health_with_unquoted_shell_metacharacters(installed, tmp_path):
    python = tmp_path / ('x' * 130 + ';not-a-command') / 'python'
    app = installed[0] / 'bin/opencode-sandbox'
    body = app.read_text().split('\n', 1)[1]
    app.write_text('#!/bin/sh\n' + "'''exec' " + str(python) + ' "$0" "$@"\n' + "' '''\n" + body)
    with pytest.raises(result.Refused, match='template'):
        result._launcher(app, python, 'opencode_sandbox.launcher:main')
