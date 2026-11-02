"""Separate fixed fresh CLI-help query under exclusion; no normal CLI exemption/dispatch."""
import json
import os
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest
from test_manager_helper import subreaper, wait_helper

from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_handoff as handoff

EXTERNAL = sys.executable
SITE = sysconfig.get_path('purelib')


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(locks, '_TMP', Path('/tmp'))
    prefix = tmp_path / 'pipx/venvs/opencode-sandbox'
    subprocess.run([EXTERNAL, '-I', '-B', '-m', 'venv', '--without-pip', str(prefix)], check=True, capture_output=True, timeout=10)
    site = next(prefix.glob('lib/python*/site-packages'))
    (site / 'ocs_test_dependencies.pth').write_text(SITE + '\n')
    shutil.copytree(Path(handoff.__file__).parent, site / 'opencode_sandbox', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # The owned result records below describe a synthetic 6.1.0 installation at any release.
    (site / 'opencode_sandbox/__init__.py').write_text('__version__ = "6.1.0"\n')
    archive = tmp_path / 'helper.pyz'; archive.write_bytes(handoff._bundle()); archive.chmod(0o600)
    environment = {'HOME': str(tmp_path), 'PATH': os.defpath}
    return prefix, site, archive, environment


def query(installed, *, exclusive=True, wait=False, expected=None):
    prefix, _site, archive, environment = installed
    statement = 'health.run(locks,prefix)'
    if expected is not None:
        settings = {'PIPX_HOME': str(prefix.parent.parent), 'PIPX_BIN_DIR': str(prefix.parent.parent.parent / 'bin'), 'PIPX_DEFAULT_PYTHON': EXTERNAL}
        statement = f'verifier.verify(locks,Path(prefix),{settings!r},{expected!r},python_version={"Python " + ".".join(map(str,sys.version_info[:3]))!r},deadline=time.monotonic()+8)'
    code = ('import json,sys,time\nfrom pathlib import Path\n'
            f'sys.path.insert(0,{str(archive)!r})\nimport installation_locks as locks,manager_health as health\n'
            'import manager_result as verifier\n'
            f'prefix={str(prefix)!r}\n'
            'try:\n'
            + (' with locks.exclusive(prefix):\n  result=' + statement + '\n' if exclusive else ' result=' + statement + '\n') +
            'except (RuntimeError,OSError,ValueError,ImportError):\n print("fixed CLI-health refused");raise SystemExit(2)\n'
            'print(json.dumps(result),flush=True)\n')
    if wait:
        return subprocess.Popen([EXTERNAL, '-I', '-B', '-S', '-c', code], env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return subprocess.run([EXTERNAL, '-I', '-B', '-S', '-c', code], env=environment, capture_output=True, text=True, check=False, timeout=12)


def test_fixed_cli_help_is_constructed_in_fresh_target_process_without_any_command_callbacks(installed):
    prefix, site, _archive, _env = installed
    cli = site / 'opencode_sandbox/cli.py'
    # Guard actual dispatch and Docker, not just the query's returned bool. The module is still
    # the real CLI and command graph; only forbidden callbacks get tripwires in this fixture.
    with cli.open('a') as stream:
        stream.write('\ndef forbidden(*args,**kwargs): raise AssertionError("ordinary dispatch/daemon must not run")\n'
                     'main=forbidden\nc.docker=forbidden\n_root=forbidden\n_print_version=forbidden\n'
                     'original_help=_HelpOrder.get_help\n'
                     'def checked_help(self,context):\n'
                     ' assert isinstance(context,self.context_class),"command must own its help context implementation"\n'
                     ' return original_help(self,context)\n'
                     '_HelpOrder.get_help=checked_help\n')
    completed = query(installed)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'version': '6.1.0', 'prefix': str(prefix), 'cli_help': True}
    assert not (Path(installed[3]['HOME']) / '.local/share/opencode-sandbox').exists()


def test_no_existing_exclusion_cannot_initialize_target_site_or_query_even_with_valid_paths(installed):
    _prefix, site, _archive, environment = installed
    marker = Path(environment['HOME']) / 'site-must-not-run'
    (site / 'ocs_test_no_access.pth').write_text(f'import pathlib; pathlib.Path({str(marker)!r}).touch()\n')
    completed = query(installed, exclusive=False)
    assert completed.returncode == 2 and 'refused' in completed.stdout and not marker.exists()


@pytest.mark.parametrize('fault', ['syntax', 'missing-dependency', 'bad-graph', 'site-exit'])
def test_basic_cli_health_failure_never_verifies_or_echoes_target_diagnostics(installed, fault):
    _prefix, site, _archive, _environment = installed
    if fault == 'syntax': (site / 'opencode_sandbox/cli.py').write_text('dummy-secret invalid syntax !\n')
    if fault == 'missing-dependency': (site / 'opencode_sandbox/cli.py').write_text('import ocs_test_missing_dependency\n')
    if fault == 'bad-graph': (site / 'opencode_sandbox/cli.py').write_text('import typer\napp=typer.Typer()\n')
    if fault == 'site-exit': (site / 'ocs_test_exit.pth').write_text('import os; os._exit(73)\n')
    completed = query(installed)
    assert completed.returncode == 2 and 'refused' in completed.stdout and 'dummy-secret' not in completed.stdout + completed.stderr


def test_helper_death_kills_health_before_target_cli_and_descendants_never_retain_exclusion(installed):
    prefix, site, _archive, environment = installed
    marker = Path(environment['HOME']) / 'health-startup.json'
    module = ('import json,os,subprocess,sys,time\nfrom pathlib import Path\n'
              f'child=subprocess.Popen([{EXTERNAL!r},"-I","-B","-S","-c","import time;time.sleep(30)"])\n'
              f'Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid(),"child":child.pid}}))\n'
              'while True: time.sleep(.01)\n')
    (site / 'ocs_test_health_pause.py').write_text(module)
    (site / 'ocs_test_health_pause.pth').write_text('import ocs_test_health_pause\n')
    helper = health = descendant = None
    with subreaper():
        try:
            helper = query(installed, wait=True)
            end = time.monotonic() + 8
            while not marker.exists() and time.monotonic() < end: time.sleep(.01)
            assert marker.exists(), 'Fixed CLI-health site hook did not reach rendezvous'
            value = json.loads(marker.read_text()); health, descendant = value['pid'], value['child']
            with pytest.raises(locks.Error, match='busy'), locks.exclusive(prefix): pass
            # The health process is already paused inside the loaded module. Remove only this
            # owned .pth before testing an unrelated normal entry, which must not run the hook.
            (site / 'ocs_test_health_pause.pth').unlink()
            refused = subprocess.run([str(prefix / 'bin/python'), '-I', '-B', '-m', 'opencode_sandbox.launcher', '--help'],
                                     env=environment, text=True, capture_output=True, timeout=3, check=False)
            assert refused.returncode == 2 and 'installation busy' in refused.stderr.lower()
            helper.kill(); helper.communicate(timeout=5)
            assert wait_helper(health) == -signal.SIGKILL; health = None
            with locks.exclusive(prefix): pass  # still-live site descendant cannot retain a witness/lease
            assert Path(f'/proc/{descendant}').exists()
            os.kill(descendant, signal.SIGKILL)
            assert wait_helper(descendant) == -signal.SIGKILL; descendant = None
        finally:
            if helper is not None:
                if helper.poll() is None: helper.kill()
                helper.communicate(timeout=5)
            for pid in (health, descendant):
                if pid is not None:
                    try:
                        if os.waitpid(pid, os.WNOHANG)[0] == 0: os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
                    except ChildProcessError: pass


@pytest.mark.parametrize('fault', ['none', 'runtime-version', 'cli-failure', 'metadata-commit'])
def test_separate_files_runtime_and_cli_health_checks_all_must_match_expected_result(installed, fault):
    prefix, site, _archive, _environment = installed
    expected = {'version': '6.1.0', 'tag': 'v6.1.0', 'commit': 'a' * 40, 'source': 'https://github.com/CyberFazaN/opencode-sandbox.git'}
    dist = site / 'opencode_sandbox-6.1.0.dist-info'; dist.mkdir()
    (dist / 'METADATA').write_text('Name: opencode-sandbox\nVersion: 6.1.0\n')
    (dist / 'entry_points.txt').write_text('[console_scripts]\nopencode-sandbox=opencode_sandbox.launcher:main\n')
    direct = {'url': expected['source'], 'vcs_info': {'vcs': 'git', 'requested_revision': expected['tag'], 'commit_id': expected['commit']}}
    if fault == 'metadata-commit': direct['vcs_info']['commit_id'] = 'b' * 40
    (dist / 'direct_url.json').write_text(json.dumps(direct))
    app, python = prefix / 'bin/opencode-sandbox', prefix / 'bin/python'
    app.write_text('#!/bin/sh\n' + "'''exec' " + str(python) + ' "$0" "$@"\n' + "' '''\n"
                   'import sys\nfrom opencode_sandbox.launcher import main\n'
                   "if __name__ == '__main__':\n    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n    sys.exit(main())\n")
    app.chmod(0o700)
    bindir = prefix.parent.parent.parent / 'bin'; bindir.mkdir()
    (bindir / 'opencode-sandbox').symlink_to(app)
    package = {'package': 'opencode-sandbox', 'package_version': '6.1.0', 'package_or_url': 'git+' + expected['source'] + '@v6.1.0',
               'apps': ['opencode-sandbox'], 'app_paths': [str(app)], 'pip_args': [], 'include_dependencies': False, 'include_apps': True}
    record = {'main_package': package, 'source_interpreter': EXTERNAL, 'python_version': 'Python ' + '.'.join(map(str, sys.version_info[:3])),
              'venv_args': [], 'injected_packages': {}, 'pipx_metadata_version': '0.12'}
    (prefix / 'pipx_metadata.json').write_text(json.dumps(record))
    inventory = [app, site / 'opencode_sandbox/__init__.py', *(dist / name for name in ('METADATA', 'entry_points.txt', 'direct_url.json', 'RECORD'))]
    (dist / 'RECORD').write_text(''.join(os.path.relpath(path, site) + ',,\n' for path in inventory))
    if fault == 'runtime-version': (site / 'opencode_sandbox/__init__.py').write_text('__version__="6.2.0"\n')
    if fault == 'cli-failure': (site / 'opencode_sandbox/cli.py').write_text('raise RuntimeError("dummy-secret")\n')
    completed = query(installed, expected=expected)
    assert completed.returncode == (0 if fault == 'none' else 2), completed.stderr
    if fault == 'none': assert json.loads(completed.stdout)['commit'] == expected['commit']
    assert 'dummy-secret' not in completed.stdout + completed.stderr
    assert not (prefix.parent.parent / '.opencode-sandbox-updates').exists()
