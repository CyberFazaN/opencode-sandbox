"""Actual isolated exact-tag pipx force replacement/recovery on owned Git source fixtures.

Official URL spelling is transported to an owned local repository by an explicit test-only Git
wrapper, and the frozen GitHub API reader uses owned loopback transport. This does NOT prove
public release authenticity or sandbox arbitrary host build code. Production gates are real.
"""
import json
import os
import select
import shutil
import signal
import sys
import time
from pathlib import Path

import pytest
from campaign import ROOT
from manager_source_fixture import graph, serve
from pty_term import STAB, TAB, Term
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_installer import wait_marker
from test_manager_terminal import read_state

from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_installer


def finish_helper(pid, terminal, timeout=180):
    descriptor = os.pidfd_open(pid)
    try:
        deadline = time.monotonic() + timeout
        while not select.select([descriptor], [], [], 0)[0]:
            assert time.monotonic() < deadline, 'Owned updater did not finish before the test deadline'
            terminal.pump(.1)  # real responsive progress must not block on an undrained pty
    finally: os.close(descriptor)
    terminal.pump(.1)
    return wait_helper(pid, timeout=3)


def public_start(camp, ck, prefix, launcher, environment, endpoint, case, tag, *, dashboard, size):
    site = next(prefix.glob('lib/python*/site-packages'))
    hook, module = site / 'ocs_test_public_update.pth', site / 'ocs_test_public_update.py'
    assert not hook.exists() and not module.exists()
    state = case / 'public-state.json'
    options = {'endpoint': endpoint, 'state': str(state)}
    module.write_text('import runpy\n' + f'runpy.run_path({str(ROOT / "tests/manager_public_fixture.py")!r})["install"]({options!r})\n')
    hook.write_text('import ocs_test_public_update\n')
    camp.note(f'owned public CLI/TUI transport/observer hooks={hook},{module}; state/partial/release/pty={state}; '
              'no subclass/new action/consent/driver/admission/exclusion bypass, exact hooks removed after case')
    arguments = ['tui'] if dashboard else ['manager', 'update', '--tag', tag]
    term = Term([str(launcher), *arguments], *size, env=environment, log=camp.log)
    try:
        if dashboard:
            assert ck(term.wait_for('OpenCode Sandbox', 30), 'Manager public update: actual dashboard visible')
            term.send('v', .3)
            assert ck(term.wait_for('verified official-tag pipx', 15), 'Manager public update: actual local classification visible without discovery')
            term.send('c', .3)
            assert ck(term.wait_for('Update available', 15), 'Manager public update: explicit published release check supplies availability only')
            term.send('u', .3)
            assert ck(term.wait_for('Update & close', 30), 'Manager public update: exact fresh public review visible with compact explicit controls')
            term.send(STAB + ' ', .2); term.send(TAB + TAB, .2); term.send('\r', .2)
        else:
            assert ck(term.wait_for('exit now', 30), 'Manager public CLI: full exact impact/network/source review and Cancel-default confirmation visible')
            term.send('y\r', .2)
        value = read_state(state, lambda item: item.get('armed'), timeout=30, pump=term.pump)
        ck((not dashboard or term.restored()) and 'terminal restored' in term.raw.decode(errors='replace'),
           'Manager public update: actual terminal restoration/driver shutdown precede helper arming')
        return term, value, (hook, module, state)
    except BaseException:
        if state.exists():
            observed = json.loads(state.read_text())
            descriptor = None
            try:
                descriptor = os.pidfd_open(observed['helper'])
                fields = Path(f'/proc/{observed["helper"]}/stat').read_text().rsplit(')', 1)[1].split()
                if fields[19] == observed['start'] and int(fields[1]) in (term.pid, os.getpid()):
                    signal.pidfd_send_signal(descriptor, signal.SIGTERM)
            except (ProcessLookupError, FileNotFoundError): pass
            finally:
                if descriptor is not None: os.close(descriptor)
        state.with_suffix('.release').touch()
        term.close()
        camp.note(f'owned failed-public-flow adopted cleanup: {manager_installer._children()}')
        assert manager_installer.drain()[0], 'Owned failed-public-flow descendants did not stop'
        for path in (hook, module):
            if path.exists(): path.unlink()
        raise


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
    control = transport / 'mode.json'; control.write_text('{}')
    native_git = shutil.which('git')
    wrapper.write_text(f'#!{sys.executable}\nimport json,os,sys,time,subprocess\nfrom pathlib import Path\n'
        'args=sys.argv[1:]\n'
        'if "clone" in args:\n'
        f' mode=json.loads(Path({str(control)!r}).read_text())\n'
        ' if mode.get("pause"):\n'
        f'  child=subprocess.Popen([{sys.executable!r},"-I","-B","-S","-c","import time;time.sleep(90)"],start_new_session=True)\n'
        '  Path(mode["marker"]).write_text(json.dumps({"wrapper":os.getpid(),"descendant":child.pid}))\n'
        '  while True: time.sleep(.02)\n'
        f' args=["-c",{("url.file://" + str(repo) + ".insteadOf=https://github.com/CyberFazaN/opencode-sandbox.git")!r},"-c","protocol.file.allow=always",*args]\n'
        f'os.execve({native_git!r},[{native_git!r},*args],dict(os.environ))\n')
    wrapper.chmod(0o700)
    public = {'HOME': str(home), 'PATH': str(bindir) + ':' + str(transport) + ':' + str(Path(sys.executable).parent) + ':/usr/bin:/bin',
              **settings, 'OPENCODE_SANDBOX_HOME': str(base / 'data'), 'OPENCODE_SANDBOX_CONFIG': str(base / 'config')}
    public['DOCKER_CONFIG'] = camp.env.get('DOCKER_CONFIG', str(Path.home() / '.docker'))
    px = [sys.executable, '-m', 'pipx']
    camp.note(f'owned actual updater source={repo}, commits previous={previous}, target={target}, broken={broken}; '
              f'isolated HOME/pipx/bin/config and explicit clone-only local Git transport {wrapper}; frozen loopback API only. '
              'All operation inputs/results/state remain below this owned pipx home. No public source authentication claim.')
    sentinel = base / 'ocs-test-user-data'; sentinel.write_text('preserve workspace/configuration/provider data')
    try:
        cases = [('success', 'v6.2.0', target, annotation), ('broken-cli', 'v6.2.1', broken, broken_annotation)]
        if layout == 'default': cases += [(mode, 'v6.2.0', target, annotation) for mode in ('handled-interrupt', 'terminal-loss', 'hard-interrupt')]
        for mode, tag, oid, tag_oid in cases:
            control.write_text('{}')
            camp._run([*px, 'install', '--force', '--python', sys.executable,
                       'git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.1.0'], env=setup, timeout=180, check=True)
            before = json.loads((prefix / 'pipx_metadata.json').read_text())
            case = base / mode; case.mkdir()
            marker = case / 'clone-ready.json'
            if mode.endswith('interrupt'): control.write_text(json.dumps({'pause': True, 'marker': str(marker)}))
            terminal = helper = None
            hooks = None
            with serve(graph(commit=oid, tags=(tag_oid,), tag=tag)) as (endpoint, _server), subreaper():
                try:
                    terminal, value, hooks = public_start(camp, ck, prefix, launcher, public, endpoint, case, tag,
                                                          dashboard=mode == 'success', size=(80, 24) if layout == 'default' else (120, 40))
                    helper = value['helper']; directory = Path(value['directory'])
                    camp.note(f'owned actual public update origin={terminal.pid}, helper={helper}, recursive private operation evidence={directory}; '
                              f'case {mode}, actual pipx force, exact source/version/runtime/launcher/health checks independent')
                    ck(not (directory / 'operation.json').exists() and not (directory / 'result.json').exists(),
                       'Manager real update: no replacement/prepared state while actual origin drain retains shared usage')
                    hooks[2].with_suffix('.release').touch()
                    assert ck(terminal.exit_code(15) == 0, 'Manager real update: actual public console origin exits before exclusive execution')
                    if mode.endswith('interrupt'):
                        started = wait_marker(marker)
                        state = locks.operation_state(prefix)
                        camp.note(f'owned native pipx interruption mode={mode}, installer={state["installer"]}, '
                                  f'wrapper={started["wrapper"]}, escaped descendant={started["descendant"]}; supervisor adopts/reaps only this family')
                        descriptor = os.pidfd_open(helper)
                        try: signal.pidfd_send_signal(descriptor, signal.SIGKILL if mode == 'hard-interrupt' else signal.SIGTERM)
                        finally: os.close(descriptor)
                    if mode == 'terminal-loss':
                        terminal.close()  # origin already reaped; close only the pty, never a reused PID
                        status = wait_helper(helper, timeout=180)
                    else: status = finish_helper(helper, terminal)
                    helper = None
                    if mode == 'hard-interrupt':
                        ck(status == -signal.SIGKILL and not (directory / 'result.json').exists(),
                           'Manager real interruption: hard-killed helper cannot publish success; pending state survives outside venv')
                        leader = locks.operation_state(prefix)['installer']['pid']
                        # Reserved adopted leader before any reap/group signal, then owned pidfd
                        # cleanup catches the escaped native transport descendant too.
                        try: os.killpg(leader, signal.SIGKILL)
                        except ProcessLookupError: pass
                        camp.note(f'owned adopted native installer family cleanup: {manager_installer._children()}')
                        ck(manager_installer.drain()[0], 'Manager real interruption: supervisor reaps only actual adopted test installer descendants')
                        before_recover = locks.operation_state(prefix)
                        failed = camp._run([sys.executable, '-I', '-B', '-S', str(directory / 'helper.pyz'), 'recover', str(directory / 'operation.json')],
                                           env={'HOME': str(home), 'PATH': os.defpath}, timeout=15, check=False)
                        ck(failed.returncode == 2 and 'quiescence is unknown' in failed.stdout and locks.operation_state(prefix) == before_recover,
                           'Manager real interruption: even an empty old group cannot authorize same-boot recovery after unconfirmed hard death')
                        refused = camp._run([str(launcher), '--version'], env=public, check=False)
                        ck(refused.returncode == 2 and 'update incomplete' in refused.stderr,
                           'Manager real interruption: operational previous launcher still blocked until independent recovery, not a cache/exit-code guess')
                        continue
                    result = result_at(directory)
                    expected = 'previous-verified' if mode == 'handled-interrupt' else 'target-unverified' if mode == 'broken-cli' else 'target-verified'
                    assert ck(result['outcome'] == expected and status == (0 if mode in ('success', 'terminal-loss') else 2),
                              'Manager real update: actual pipx replacement and independent outcome agree, not inferred from return code'), terminal.text()
                    state = locks.operation_state(prefix)
                    ck(state['phase'] == ('manual-recovery' if mode == 'broken-cli' else 'complete') and state['installer'] is None,
                       'Manager real update: only verified/quiescent result reopens startup; actual failed CLI result retains pending barrier')
                    after = json.loads((prefix / 'pipx_metadata.json').read_text())
                    ck(after['source_interpreter'] == before['source_interpreter'] and after['venv_args'] == before['venv_args']
                       and after['injected_packages'] == before['injected_packages'], 'Manager real update: source Python/default pipx options preserved through actual force reuse')
                    ck(sentinel.read_text() == 'preserve workspace/configuration/provider data', 'Manager real update: unrelated workspace/configuration/provider sentinel unchanged')
                    if mode in ('success', 'terminal-loss', 'handled-interrupt'):
                        healthy = camp._run([str(launcher), '--version'], env=public, check=True)
                        ck(healthy.stdout.strip() == 'opencode-sandbox ' + ('6.1.0' if mode == 'handled-interrupt' else '6.2.0'),
                           'Manager real update: ordinary exposed launcher starts independently after verified completion, including terminal loss/handled interruption; no automatic restart')
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
                    if hooks:
                        hooks[2].with_suffix('.release').touch()
                    if helper is not None:
                        try:
                            if os.waitpid(helper, os.WNOHANG)[0] == 0:
                                os.kill(helper, signal.SIGTERM); wait_helper(helper, timeout=15)
                        except ChildProcessError: pass
                    if terminal is not None:
                        terminal.pump(.1); (case / 'public.pty').write_bytes(terminal.raw)
                        terminal.close()
                    if hooks:
                        for path in hooks[:2]:
                            if path.exists(): path.unlink()
    finally:
        if prefix.exists(): camp._run([*px, 'uninstall', 'opencode-sandbox'], env=setup, timeout=30, check=True)
        ck(not prefix.exists() and not launcher.exists(), 'Manager real update: only manifested test installation uninstalled, durable operation evidence retained')
