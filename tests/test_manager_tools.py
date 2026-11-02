"""External-tool evidence never authorizes an update; actual isolated child processes below.

Synthetic pipx packages/metadata exercise runtime boundaries without installing a tool. The
opt-in campaign separately executes real pipx; these are not claims about fake installs.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import manager_tools
from opencode_sandbox import runtime_identity as rid


@pytest.fixture
def tools(tmp_path, monkeypatch):
    target = tmp_path / 'application-home/venvs/opencode-sandbox'
    target.mkdir(parents=True)
    bindir = tmp_path / 'external tools'; bindir.mkdir()
    package = bindir / 'pipx'; package.mkdir()
    (package / '__init__.py').write_text('')
    cli = package / '__main__.py'
    cli.write_text("def cli():\n    print('1.18.7')\n    return 0\n")
    (package / 'paths.py').write_text('import os\nfrom pathlib import Path\nclass Paths:\n'
        + ''.join(f"    {attribute} = Path(os.environ[{key!r}])\n" for attribute, key in {
            'home': 'PIPX_HOME', 'bin_dir': 'PIPX_BIN_DIR', 'man_dir': 'PIPX_MAN_DIR',
            'completion_dir': 'PIPX_COMPLETION_DIR', 'shared_libs': 'PIPX_SHARED_LIBS'}.items()) + 'ctx = Paths()\n')
    (package / 'interpreter.py').write_text("import os\ndef get_default_python():\n    return os.environ['PIPX_DEFAULT_PYTHON']\n")
    metadata = bindir / 'pipx-1.18.7.dist-info'; metadata.mkdir()
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: pipx\nVersion: 1.18.7\nRequires-Dist: packaging>=0\n')
    (metadata / 'entry_points.txt').write_text('[console_scripts]\npipx = pipx.__main__:cli\n')
    (metadata / 'RECORD').write_text('pipx/__init__.py,,\npipx/__main__.py,,\npipx/paths.py,,\npipx/interpreter.py,,\npipx-1.18.7.dist-info/METADATA,,\n')
    launcher = bindir / 'pipx-tool'
    # Name the console pipx, but keep its package directory alongside it in another search
    # directory using a symlink. Normal Python script-directory resolution follows that link.
    launcher.write_text(f'#!{sys.executable}\nimport sys\nfrom pipx.__main__ import cli\n'
                       "if __name__ == '__main__':\n    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n    sys.exit(cli())\n")
    launcher.chmod(0o700)
    command_dir = tmp_path / 'commands'; command_dir.mkdir()
    (command_dir / 'pipx').symlink_to(launcher)
    monkeypatch.setenv('PATH', str(command_dir))
    evidence = {'verified': True, 'evidence': {'venv': str(target), 'pipx_home': str(target.parent.parent),
        'pipx_bin_dir': str(tmp_path / 'app bin'), 'source_python': sys._base_executable,
        'locations': {'man_dir': str(tmp_path / 'app man'), 'completion_dir': str(tmp_path / 'app completion'),
                      'shared_libs': str(tmp_path / 'app shared')}}}
    return evidence, launcher, package, metadata


def test_unclassified_installation_cannot_trigger_external_execution(monkeypatch):
    monkeypatch.setattr(manager_tools.c, 'call', lambda *a, **k: (_ for _ in ()).throw(AssertionError('executed tool')))
    result = manager_tools.assess({'verified': False})
    assert not result['supported'] and 'classification' in result['reason']


def test_observed_external_runtime_and_locations_are_independent_without_installing(tools):
    evidence, launcher, package, metadata = tools
    before = {path: path.read_bytes() for path in [launcher, *package.glob('*.py'), *metadata.iterdir()]}
    result = manager_tools.assess(evidence)
    assert result['supported'], result
    facts = result['evidence']
    assert facts['pipx_runtime']['pipx_version'] == '1.18.7'
    assert facts['settings']['PIPX_HOME'] == evidence['evidence']['pipx_home']
    assert facts['settings']['PIPX_MAN_DIR'] == evidence['evidence']['locations']['man_dir']
    assert facts['settings']['PIPX_DEFAULT_PYTHON'] == evidence['evidence']['source_python']
    assert facts['pipx_runtime']['locations'] == {name: str(Path(value).resolve()) for name, value in facts['settings'].items()}
    assert set(facts['pipx_runtime']['dependencies']) == {'pipx', 'packaging'}
    assert 'Unavailable' in result['execution'] and 'no execution grant' in result['reason']
    assert before == {path: path.read_bytes() for path in before}
    assert not list(Path(evidence['evidence']['venv']).iterdir())
    assert not (package / '__pycache__').exists()


@pytest.mark.parametrize('change', ['missing', 'wrapper', 'env-shebang', 'script-in-target', 'python-in-target',
    'unsafe-file', 'unsafe-parent', 'fifo', 'empty', 'oversized', 'unknown-environment', 'relative-path',
    'home-mismatch', 'unsupported-version', 'missing-dependency', 'bad-constraint', 'no-inventory',
    'unrecognized-entry', 'settings-mismatch', 'runtime-search', 'runtime-origin', 'record-file-target', 'metadata-target',
    'script-via-target', 'python-via-target', 'writable-module', 'writable-package', 'writable-alias-parent',
    'shared-in-target', 'man-in-target', 'oversized-inventory', 'malformed-inventory', 'empty-inventory'])
def test_unsupported_or_replaceable_runtime_refuses_without_secret_output(tools, monkeypatch, tmp_path, change):
    evidence, launcher, package, metadata = tools
    target = Path(evidence['evidence']['venv'])
    secret = 'dummy-never-report-token-123'
    if change == 'missing': monkeypatch.setenv('PATH', str(tmp_path / 'missing'))
    if change == 'wrapper': launcher.write_text('#!/bin/sh\necho ' + secret)
    if change == 'env-shebang': launcher.write_text(launcher.read_text().replace('#!' + sys.executable, '#!/usr/bin/env python'))
    if change == 'script-in-target':
        inside = target / 'script'; inside.write_bytes(launcher.read_bytes()); inside.chmod(0o700)
        launcher.unlink(); launcher.symlink_to(inside)
    if change == 'python-in-target':
        python = target / 'python'; python.symlink_to(sys.executable)
        launcher.write_text(launcher.read_text().replace(sys.executable, str(python)))
    if change == 'script-via-target':
        link = target / 'pipx-external-alias'; link.symlink_to(launcher)
        command = Path(os.environ['PATH']) / 'pipx'; command.unlink(); command.symlink_to(link)
    if change == 'python-via-target':
        link = target / 'python-external-alias'; link.symlink_to(sys.executable)
        alias = launcher.parent / 'python-alias'; alias.symlink_to(link)
        launcher.write_text(launcher.read_text().replace(sys.executable, str(alias)))
    if change == 'unsafe-file': launcher.chmod(0o777)
    if change == 'unsafe-parent': launcher.parent.chmod(0o777)
    if change == 'fifo': launcher.unlink(); os.mkfifo(launcher, mode=0o700)
    if change == 'empty': launcher.write_text('')
    if change == 'oversized': launcher.write_text('#!' + sys.executable + '\n' + secret * 1000)
    if change == 'unknown-environment': monkeypatch.setenv('PIPX_CUSTOM_UNKNOWN', secret)
    if change == 'relative-path': evidence['evidence']['locations']['man_dir'] = secret
    if change == 'home-mismatch': evidence['evidence']['pipx_home'] = str(tmp_path / secret)
    if change == 'unsupported-version': (metadata / 'METADATA').write_text('Name: pipx\nVersion: 99.0\n')
    if change == 'missing-dependency':
        with (metadata / 'METADATA').open('a') as stream: stream.write('Requires-Dist: ocs-test-missing-runtime>=1\n')
    if change == 'bad-constraint':
        with (metadata / 'METADATA').open('a') as stream: stream.write('Requires-Dist: packaging<0\n')
    if change == 'no-inventory': (metadata / 'RECORD').unlink()
    if change == 'unrecognized-entry': (metadata / 'entry_points.txt').write_text('[console_scripts]\npipx = foreign:run\n')
    if change == 'settings-mismatch':
        (package / 'interpreter.py').write_text(f'def get_default_python():\n    return {str(tmp_path / secret)!r}\n')
    if change == 'runtime-search':
        (package / '__main__.py').write_text(f"import sys\ndef cli():\n    sys.path.append({str(target)!r})\n    print('1.18.7')\n    return 0\n")
    if change == 'runtime-origin':
        hidden = target / 'hidden.py'; hidden.write_text('value = 1\n')
        (package / '__main__.py').write_text(f"import sys, importlib.util\ndef cli():\n    spec = importlib.util.spec_from_file_location('hidden', {str(hidden)!r})\n    module = importlib.util.module_from_spec(spec)\n    sys.modules['hidden'] = module\n    spec.loader.exec_module(module)\n    print('1.18.7')\n    return 0\n")
    if change == 'record-file-target':
        with (metadata / 'RECORD').open('a') as stream: stream.write(str(target / 'declared-but-lazy.py') + ',,\n')
    if change == 'metadata-target':
        moved = target / 'METADATA'; moved.write_bytes((metadata / 'METADATA').read_bytes())
        (metadata / 'METADATA').unlink(); (metadata / 'METADATA').symlink_to(moved)
    if change == 'writable-module': (package / '__main__.py').chmod(0o777)
    if change == 'writable-package': package.chmod(0o777)
    if change == 'writable-alias-parent': Path(os.environ['PATH']).chmod(0o777)
    if change == 'shared-in-target': evidence['evidence']['locations']['shared_libs'] = str(target / 'shared')
    if change == 'man-in-target': evidence['evidence']['locations']['man_dir'] = str(target / 'man')
    if change == 'oversized-inventory': (metadata / 'RECORD').write_text('x' * 524289)
    if change == 'malformed-inventory': (metadata / 'RECORD').write_text('only-a-filename\n')
    if change == 'empty-inventory': (metadata / 'RECORD').write_text('')
    try:
        result = manager_tools.assess(evidence)
        assert not result['supported'] and 'evidence' not in result, result
        assert secret not in json.dumps(result) and 'Unavailable' in result['execution']
    finally:
        if change == 'unsafe-parent': launcher.parent.chmod(0o700)
        if change == 'writable-alias-parent': Path(os.environ['PATH']).chmod(0o700)


def test_known_paths_and_source_python_are_explicit_but_credentials_and_python_injection_are_not_forwarded(tools, monkeypatch):
    evidence, _, package, _ = tools
    for name in ('PYTHONPATH', 'PYTHONHOME', 'PIP_INDEX_URL', 'DUMMY_PROVIDER_TOKEN', 'LD_PRELOAD'):
        monkeypatch.setenv(name, 'dummy-do-not-forward')
    original = (package / '__main__.py').read_text()
    (package / '__main__.py').write_text("import os\nassert not any(name in os.environ for name in "
        "('PYTHONPATH','PYTHONHOME','PIP_INDEX_URL','DUMMY_PROVIDER_TOKEN','LD_PRELOAD'))\n" + original)
    result = manager_tools.assess(evidence)
    assert result['supported'], result
    assert 'dummy-do-not-forward' not in json.dumps(result)


def test_tools_stay_independent_if_the_named_replaceable_prefix_is_temporarily_absent(tools):
    evidence, *_ = tools
    target = Path(evidence['evidence']['venv'])
    saved = target.with_name(target.name + '-owned-hidden-fixture')
    target.rename(saved)
    try:
        result = manager_tools.assess(evidence)
        assert result['supported'] and 'no execution grant' in result['reason'], result
        assert not target.exists()
    finally: saved.rename(target)


@pytest.mark.parametrize('route', ['venv', 'external-alias'])
def test_recorded_source_python_spelling_is_preserved_not_replaced_with_its_binary_target(tools, tmp_path, route):
    evidence, *_ = tools
    source = sys.executable
    if route == 'external-alias':
        alias = tmp_path / 'source-python-alias'; alias.symlink_to(sys.executable)
        source = str(alias)
    evidence['evidence']['source_python'] = source
    result = manager_tools.assess(evidence)
    assert result['supported'], result
    assert result['evidence']['settings']['PIPX_DEFAULT_PYTHON'] == source
    assert result['evidence']['pipx_runtime']['locations']['PIPX_DEFAULT_PYTHON'] == str(Path(source).resolve())


def test_source_python_alias_through_target_is_not_canonicalized_away(tools):
    evidence, launcher, *_ = tools
    target = Path(evidence['evidence']['venv'])
    inside = target / 'source-python'; inside.symlink_to(sys.executable)
    alias = launcher.parent / 'source-python'; alias.symlink_to(inside)
    evidence['evidence']['source_python'] = str(alias)
    result = manager_tools.assess(evidence)
    assert not result['supported'] and 'replaceable installation' in result['reason'], result


def test_only_two_fixed_diagnostic_argv_are_used_and_changed_script_is_refused(tools, monkeypatch):
    evidence, launcher, *_ = tools
    actual, calls = c.call, []
    def call(argv, **kwargs):
        assert kwargs['timeout'] == manager_tools.TIMEOUT and kwargs['max_output'] == manager_tools.LIMIT
        assert '-I' in argv and '-B' in argv and not any(word in argv for word in ('install', 'list', 'reinstall', 'upgrade'))
        calls.append(argv)
        result = actual(argv, **kwargs)
        if len(calls) == 2: os.utime(launcher, ns=(launcher.stat().st_atime_ns, launcher.stat().st_mtime_ns + 1))
        return result
    monkeypatch.setattr(c, 'call', call)
    result = manager_tools.assess(evidence)
    assert not result['supported'] and 'changed during inspection' in result['reason'], result
    assert len(calls) == 2 and '-S' in calls[0] and calls[0][-2] == 'stdlib' and calls[1][-3] == 'pipx'


@pytest.mark.parametrize('mode', ['timeout', 'output', 'cancel'])
def test_owned_diagnostic_child_is_reaped_on_deadline_output_limit_or_cancellation(tools, monkeypatch, tmp_path, mode):
    evidence, _, package, _ = tools
    ready = tmp_path / 'child-ready'
    if mode == 'output':
        (package / '__main__.py').write_text("def cli():\n    print('dummy-private-token-' * 100000)\n    return 0\n")
    else:
        (package / '__main__.py').write_text(f"import time\nfrom pathlib import Path\ndef cli():\n    Path({str(ready)!r}).write_text('ready')\n    time.sleep(30)\n    return 0\n")
    children, actual = [], c.subprocess.Popen
    def popen(argv, **kwargs):
        child = actual(argv, **kwargs); children.append(child)
        return child
    monkeypatch.setattr(c.subprocess, 'Popen', popen)
    if mode == 'timeout': monkeypatch.setattr(manager_tools, 'TIMEOUT', .5)
    started = time.monotonic()
    if mode == 'cancel':
        with c.runtime_feedback(cancelled=ready.exists), pytest.raises(rid.Cancelled): manager_tools.assess(evidence)
    else:
        result = manager_tools.assess(evidence)
        assert not result['supported'] and 'dummy-private-token' not in json.dumps(result)
    assert time.monotonic() - started < 4
    assert children and all(child.poll() is not None for child in children)


def test_standard_shell_trampoline_is_inspected_as_data_not_evaluated(tools):
    evidence, launcher, *_ = tools
    lines = launcher.read_text().splitlines()
    interpreter = lines[0][2:]
    quoted = '"' + interpreter + '"' if ' ' in interpreter else interpreter
    launcher.write_text('#!/bin/sh\n' + "'''exec' " + quoted + ' "$0" "$@"\n' + "' '''\n" + '\n'.join(lines[1:]) + '\n')
    assert manager_tools.assess(evidence)['supported']


def test_probe_source_has_only_stdlib_top_level_imports():
    import ast
    source = Path(manager_tools.__file__).with_name('manager_tool_probe.py')
    tree = ast.parse(source.read_text())
    imports = {node.names[0].name.split('.')[0] if isinstance(node, ast.Import) else node.module.split('.')[0]
               for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))}
    assert imports <= sys.stdlib_module_names


@pytest.mark.parametrize('metacharacter', [';', '&', '*', "'", '('])
def test_unquoted_shell_metacharacters_in_external_console_interpreter_refuse_before_any_execution(tools, tmp_path, monkeypatch, metacharacter):
    evidence, launcher, *_ = tools
    alias = tmp_path / ('python' + metacharacter + 'not-a-command')
    alias.symlink_to(sys.executable)
    body = launcher.read_text().splitlines()[1:]
    launcher.write_text('#!/bin/sh\n' + "'''exec' " + str(alias) + ' "$0" "$@"\n' + "' '''\n" + '\n'.join(body) + '\n')
    monkeypatch.setattr(c, 'call', lambda *args, **kwargs: pytest.fail('unsafe shell route reached a diagnostic child'))
    result = manager_tools.assess(evidence)
    assert not result['supported'] and 'trampoline' in result['reason']


def test_shell_quoting_cannot_hide_a_python_triple_quote_in_external_console_route(tools, tmp_path, monkeypatch):
    evidence, launcher, *_ = tools
    alias = tmp_path / "python'''not-a-console"; alias.symlink_to(sys.executable)
    body = launcher.read_text().splitlines()[1:]
    launcher.write_text('#!/bin/sh\n' + "'''exec' \"" + str(alias) + '\" "$0" "$@"\n' + "' '''\n" + '\n'.join(body) + '\n')
    monkeypatch.setattr(c, 'call', lambda *args, **kwargs: pytest.fail('ambiguous Python trampoline reached a diagnostic child'))
    observed = manager_tools.assess(evidence)
    assert not observed['supported'] and 'trampoline' in observed['reason']
