"""Actual isolated exact-tag pipx force replacement/recovery on owned Git source fixtures.

Official URL spelling is transported to an owned local repository by an explicit test-only Git
wrapper, and the frozen GitHub API reader uses owned loopback transport. This does NOT prove
public release authenticity or sandbox arbitrary host build code. Production gates are real.
"""
import json
import os
import shutil
import signal
import sys
from pathlib import Path

import pytest
from campaign import ROOT
from manager_source_fixture import graph, serve
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_update import start

from opencode_sandbox import installation_locks as locks


@pytest.mark.parametrize('layout', ['default', 'custom-spaces'])
def test_real_pipx_exact_replacement_and_independent_recovery(campaign, checks, layout):
    camp, ck = campaign, checks
    base = camp.tmp('ocs-test-manager-update-' + layout)
    home, repo = base / 'home', base / 'tagged-source'
    home.mkdir(); repo.mkdir()
    for name in ('pyproject.toml', 'README.md', 'LICENSE'): shutil.copy2(ROOT / name, repo / name)
    shutil.copytree(ROOT / 'src/opencode_sandbox', repo / 'src/opencode_sandbox', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    git = ['git', '-C', str(repo), '-c', 'user.name=ocs-test', '-c', 'user.email=test@example.invalid']
    camp._run([*git, 'init', '--quiet'], check=True)
    def commit(tag):
        camp._run([*git, 'add', '.'], check=True)
        camp._run([*git, 'commit', '--quiet', '-m', 'owned updater fixture ' + tag], check=True)
        camp._run([*git, 'tag', '-a', tag, '-m', 'owned updater fixture only'], check=True)
        return (camp._run([*git, 'rev-parse', tag + '^{commit}'], check=True).stdout.strip(),
                camp._run([*git, 'rev-parse', tag], check=True).stdout.strip())
    previous, _ = commit('v6.1.0')
    version_file = repo / 'src/opencode_sandbox/__init__.py'
    version_file.write_text('__version__ = "6.2.0"\n')
    target, annotation = commit('v6.2.0')
    cli = repo / 'src/opencode_sandbox/cli.py'; original_cli = cli.read_bytes()
    version_file.write_text('__version__ = "6.2.1"\n')
    cli.write_text('raise RuntimeError("owned target CLI-health fault")\n')
    broken, broken_annotation = commit('v6.2.1')
    cli.write_bytes(original_cli)
    # The setup-only rewrite is explicit and not forwarded into the reviewed public environment.
    config = base / 'setup-gitconfig'
    config.write_text(f'[url "file://{repo}"]\n\tinsteadOf = https://github.com/CyberFazaN/opencode-sandbox.git\n')
    pipx_home = home / '.local/share/pipx' if layout == 'default' else base / 'custom pipx'
    bindir = home / '.local/bin' if layout == 'default' else base / 'custom bin'
    prefix, launcher = pipx_home / 'venvs/opencode-sandbox', bindir / 'opencode-sandbox'
    settings = {'PIPX_HOME': str(pipx_home), 'PIPX_BIN_DIR': str(bindir), 'PIPX_MAN_DIR': str(base / 'man'),
                'PIPX_SHARED_LIBS': str(pipx_home / 'shared'), 'PIPX_COMPLETION_DIR': str(base / 'completion'), 'PIPX_DEFAULT_PYTHON': sys.executable}
    setup = {'HOME': str(home), 'PATH': str(bindir) + ':' + str(Path(sys.executable).parent) + ':/usr/bin:/bin', **settings,
             'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_NOSYSTEM': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    transport = base / 'git-transport'; transport.mkdir()
    wrapper = transport / 'git'
    native_git = shutil.which('git')
    wrapper.write_text(f'#!{sys.executable}\nimport os,sys\n'
        'args=sys.argv[1:]\n'
        'if "clone" in args:\n'
        f' args=["-c",{("url.file://" + str(repo) + ".insteadOf=https://github.com/CyberFazaN/opencode-sandbox.git")!r},"-c","protocol.file.allow=always",*args]\n'
        f'os.execve({native_git!r},[{native_git!r},*args],dict(os.environ))\n')
    wrapper.chmod(0o700)
    public = {'HOME': str(home), 'PATH': str(bindir) + ':' + str(transport) + ':' + str(Path(sys.executable).parent) + ':/usr/bin:/bin',
              **settings, 'OPENCODE_SANDBOX_HOME': str(base / 'data'), 'OPENCODE_SANDBOX_CONFIG': str(base / 'config')}
    px = [sys.executable, '-m', 'pipx']
    camp.note(f'owned actual updater source={repo}, commits previous={previous}, target={target}, broken={broken}; '
              f'isolated HOME/pipx/bin/config and explicit clone-only local Git transport {wrapper}; frozen loopback API only. '
              'All operation inputs/results/state remain below this owned pipx home. No public source authentication claim.')
    sentinel = base / 'ocs-test-user-data'; sentinel.write_text('preserve workspace/configuration/provider data')
    try:
        for mode, tag, oid, tag_oid in [('success', 'v6.2.0', target, annotation), ('broken-cli', 'v6.2.1', broken, broken_annotation)]:
            camp._run([*px, 'install', '--force', '--python', sys.executable,
                       'git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.1.0'], env=setup, timeout=180, check=True)
            before = json.loads((prefix / 'pipx_metadata.json').read_text())
            case = base / mode; case.mkdir()
            installed = (prefix, launcher, None, None, public, None)
            origin = helper = None
            with serve(graph(commit=oid, tags=(tag_oid,), tag=tag)) as (endpoint, _server), subreaper():
                try:
                    origin, value, log = start(installed, endpoint, case, tag=tag)
                    helper = value['helper']; directory = Path(value['directory'])
                    camp.note(f'owned update origin={origin.pid}, helper={helper}, recursive private operation evidence={directory}, '
                              f'helper log={log}; case {mode}, actual pipx force, all exact source/version/runtime/launcher/health checks independent')
                    ck(origin.poll() is None and not (directory / 'operation.json').exists(), 'Manager real update: no replacement/prepared state while actual origin drain retains shared usage')
                    origin.communicate(timeout=15)
                    assert ck(origin.returncode == 0, 'Manager real update: actual installed origin exits before exclusive execution')
                    status = wait_helper(helper, timeout=180); helper = None
                    result = result_at(directory)
                    expected = 'target-verified' if mode == 'success' else 'target-unverified'
                    assert ck(result['outcome'] == expected and status == (0 if mode == 'success' else 2),
                              'Manager real update: actual pipx replacement and independent outcome agree, not inferred from return code'), log.read_text()
                    state = locks.operation_state(prefix)
                    ck(state['phase'] == ('complete' if mode == 'success' else 'manual-recovery') and state['installer'] is None,
                       'Manager real update: only verified/quiescent result reopens startup; actual failed CLI result retains pending barrier')
                    after = json.loads((prefix / 'pipx_metadata.json').read_text())
                    ck(after['source_interpreter'] == before['source_interpreter'] and after['venv_args'] == before['venv_args']
                       and after['injected_packages'] == before['injected_packages'], 'Manager real update: source Python/default pipx options preserved through actual force reuse')
                    ck(sentinel.read_text() == 'preserve workspace/configuration/provider data', 'Manager real update: unrelated workspace/configuration/provider sentinel unchanged')
                    if mode == 'success':
                        healthy = camp._run([str(launcher), '--version'], env=public, check=True)
                        ck(healthy.stdout.strip() == 'opencode-sandbox 6.2.0', 'Manager real update: ordinary exposed launcher starts independently after completion; no automatic restart')
                    else:
                        refused = camp._run([str(launcher), '--version'], env=public, check=False)
                        ck(refused.returncode == 2 and 'update incomplete' in refused.stderr, 'Manager real update: broken-target normal startup blocked before dispatch')
                        # Explicit operator-guided previous-tag reinstall, not automatic rollback or a backup promise.
                        camp._run([*px, 'install', '--force', '--python', sys.executable,
                                   'git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.1.0'], env=setup, timeout=180, check=True)
                        recovery = camp._run([sys.executable, '-I', '-B', '-S', str(directory / 'helper.pyz'), 'recover', str(directory / 'operation.json')],
                                             env={'HOME': str(home), 'PATH': os.defpath}, timeout=30, check=True)
                        ck('previous installation is independently verified' in recovery.stdout
                           and locks.operation_state(prefix)['result'] == 'previous-verified',
                           'Manager real recovery: frozen helper independently verifies actual manual previous-tag reinstall and explicitly reopens startup')
                        healthy = camp._run([str(launcher), '--version'], env=public, check=True)
                        ck(healthy.stdout.strip() == 'opencode-sandbox 6.1.0', 'Manager real recovery: actual restored exposed launcher operational; no identical-dependency/offline restoration claim')
                finally:
                    if origin is not None:
                        if origin.poll() is None: origin.kill()
                        origin.communicate(timeout=5)
                    if helper is not None:
                        try:
                            if os.waitpid(helper, os.WNOHANG)[0] == 0: os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                        except ChildProcessError: pass
    finally:
        if prefix.exists(): camp._run([*px, 'uninstall', 'opencode-sandbox'], env=setup, timeout=30, check=True)
        ck(not prefix.exists() and not launcher.exists(), 'Manager real update: only manifested test installation uninstalled, durable operation evidence retained')
