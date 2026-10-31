"""Isolated real pipx provenance/settings/launcher evidence, without an updater or user install.

An explicit Git URL rewrite maps the official spelling to run-owned tagged test sources. This
exercises real pipx/PEP 610 records and launchers, NOT authenticity of a public GitHub release.
No source/provenance check is patched; the local transport fixture is declared, not shipped.
"""
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from campaign import ROOT
from pty_term import ESC, Term
from test_manager_helper import result_at, subreaper, wait_helper


def exclusion(camp, prefix, *, busy):
    code = ("from opencode_sandbox.installation_locks import exclusive\n"
            f"with exclusive({str(prefix)!r}): print('exclusive acquired')\n")
    result = camp._run([sys.executable, '-B', '-c', code], check=False)
    return result.returncode != 0 and 'installation busy' in result.stderr.lower() if busy else result.returncode == 0


@pytest.mark.parametrize('layout', ['default', 'custom-spaces'])
def test_real_pipx_readonly_classification(campaign, checks, layout):
    camp, ck = campaign, checks
    base = camp.tmp('manager-inventory-' + layout)
    repo, home = base / 'tagged-source', base / 'home'
    repo.mkdir(); home.mkdir()
    for name in ('pyproject.toml', 'README.md', 'LICENSE'):
        shutil.copy2(ROOT / name, repo / name)
    shutil.copytree(ROOT / 'src/opencode_sandbox', repo / 'src/opencode_sandbox', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    git = ['git', '-C', str(repo), '-c', 'user.name=ocs-test', '-c', 'user.email=test@example.invalid']
    camp._run([*git, 'init', '--quiet'], check=True)
    camp._run([*git, 'add', '.'], check=True)
    camp._run([*git, 'commit', '--quiet', '-m', 'run-owned manager classification fixture'], check=True)
    version = (repo / 'src/opencode_sandbox/__init__.py').read_text().split('"')[1]
    camp._run([*git, 'tag', 'v' + version], check=True)
    commit = camp._run([*git, 'rev-parse', 'HEAD'], check=True).stdout.strip()
    config = base / 'gitconfig'
    config.write_text(f'[url "file://{repo}"]\n\tinsteadOf = https://github.com/CyberFazaN/opencode-sandbox.git\n')
    pipx_home, bindir = ((home / '.local/share/pipx', home / '.local/bin') if layout == 'default'
                         else (base / 'custom pipx', base / 'custom bin'))
    env = {key: value for key, value in camp.env.items() if key not in ('PYTHONPATH', 'VIRTUAL_ENV')}
    env.update(HOME=str(home), PIPX_HOME=str(pipx_home), PIPX_BIN_DIR=str(bindir),
               PIPX_MAN_DIR=str(base / 'man'), GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM='1',
               PATH=str(bindir) + ':/usr/bin:/bin', PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONDONTWRITEBYTECODE='1')
    if layout == 'default':
        env.pop('PIPX_HOME'); env.pop('PIPX_BIN_DIR')
        env.pop('XDG_DATA_HOME', None)
    camp.note(f'run-owned local tagged Git transport fixture commit={commit}; private pipx/HOME/config/bin, official URL spelling mapped only inside this fixture')
    px = [sys.executable, '-m', 'pipx']
    launcher = bindir / 'opencode-sandbox'
    prefix = pipx_home / 'venvs/opencode-sandbox'
    def run(*args, check=True, environment=None):
        return camp._run([str(launcher), 'manager', 'status', *args], env=env if environment is None else environment, check=check)
    try:
        camp._run([*px, 'install', '--python', sys.executable,
                   'git+https://github.com/CyberFazaN/opencode-sandbox.git@v' + version], env=env, timeout=180, check=True)
        paths = [prefix / 'pipx_metadata.json', launcher.resolve(), *prefix.glob('lib/python*/site-packages/opencode_sandbox-*.dist-info/direct_url.json')]
        before = {str(path): path.read_bytes() for path in paths}
        (base / 'original-test-metadata.json').write_bytes((prefix / 'pipx_metadata.json').read_bytes())
        (base / 'original-test-launcher').write_bytes(launcher.resolve().read_bytes())
        value = json.loads(run().stdout)['installation']
        assert ck(value['verified'], 'Manager real pipx: recognized tagged VCS/runtime/Python/custom paths/actual launcher agree'), value
        ck(value['evidence']['commit'] == commit and value['evidence']['tag'] == 'v' + version, 'Manager real pipx: exact recorded commit and version tag retained')
        ck(before == {str(path): path.read_bytes() for path in paths}, 'Manager real pipx: inspection did not rewrite records or launcher')
        # Internal dated prerequisite API, not manager consent/execution or a verifier bypass.
        # The actual installed launcher supplied `value`; all probe children use external pipx.
        probe = ('import json,sys\nfrom opencode_sandbox.manager_tools import assess\n'
                 'print(json.dumps(assess(json.loads(sys.argv[1]))))\n')
        probe_env = dict(camp.env, HOME=str(home), PATH=str(Path(sys.executable).parent) + ':/usr/bin:/bin')
        def inspect_tools(environment=probe_env):
            result = camp._run([sys.executable, '-B', '-c', probe, json.dumps(value)], env=environment, check=True)
            return json.loads(result.stdout)
        tool_facts = inspect_tools()
        assert ck(tool_facts['supported'], 'Manager real tools: actual external Python/pipx/dependency closure is independent'), tool_facts
        ck(tool_facts['evidence']['settings']['PIPX_HOME'] == str(pipx_home)
           and tool_facts['evidence']['settings']['PIPX_BIN_DIR'] == str(bindir)
           and tool_facts['evidence']['settings']['PIPX_MAN_DIR'] == str(base / 'man'),
           'Manager real tools: default/custom-space pipx home/bin/man locations explicitly retained')
        ck(tool_facts['evidence']['settings']['PIPX_DEFAULT_PYTHON'] == value['evidence']['source_python']
           and 'Unavailable' in tool_facts['execution'], 'Manager real tools: source Python preserved; no helper or execution grant')
        hidden = prefix.with_name('ocs-test-tool-independence-hidden')
        assert not hidden.exists()
        camp.note(f'owned application venv temporarily renamed {prefix} -> {hidden} only for non-mutating external-tool independence proof; always restored')
        prefix.rename(hidden)
        try:
            independent = inspect_tools()
            ck(independent['supported'] and not prefix.exists(), 'Manager real tools: external stdlib/pipx probes work with application venv absent')
        finally: hidden.rename(prefix)
        inside = prefix / 'ocs-test-external-tool-refusal'; inside.mkdir()
        pipx_script = Path(sys.executable).parent / 'pipx'
        (inside / 'pipx').write_bytes(pipx_script.read_bytes()); (inside / 'pipx').chmod(0o700)
        camp.note(f'owned test-only pipx console copy {inside / "pipx"}; exact file/directory removed after refusal proof')
        try:
            refused_tools = inspect_tools(dict(probe_env, PATH=str(inside) + ':' + probe_env['PATH']))
            ck(not refused_tools['supported'] and 'replaceable installation' in refused_tools['reason'],
               'Manager real tools: pipx inside the application refused before execution despite external shebang')
        finally: (inside / 'pipx').unlink(); inside.rmdir()
        ck(before == {str(path): path.read_bytes() for path in paths}, 'Manager real tools: version-only assessment left installed records/launcher unchanged')
        # Freeze the helper from the ACTUAL installed package, not the source checkout. The
        # stdlib-only child then outlives that installation's origin and works with it absent.
        # This is a non-mutating process-exit fixture, NOT restored-terminal handoff evidence.
        staging = base / 'helper staging'; staging.mkdir()
        camp.note(f'owned non-mutating helper staging/evidence parent {staging}; all nested artifacts/results retained, no install/verifier dispatch')
        origin_code = ("import json,sys,threading\nfrom pathlib import Path\n"
            "from opencode_sandbox import installation_locks as locks\nlocks.acquire_usage()\n"
            "from opencode_sandbox import manager_handoff as h\n"
            "assert Path(h.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())\n"
            "value=h.prepare(json.loads(sys.argv[1]),Path(sys.argv[2]))\nassert value['supported'],value\n"
            "artifact=value['artifact']\nfixture=h.start_fixture(artifact,budget=20)\nfixture.arm()\n"
            "threading.Thread(target=lambda:sys.stdin.read()).start()\n"
            "print(json.dumps({'directory':str(artifact.directory),'helper':fixture.process.pid}),flush=True)\n")
        helper_env = dict(env, PATH=str(Path(sys.executable).parent) + ':/usr/bin:/bin')
        helper = None
        with subreaper():
            origin = subprocess.Popen([str(prefix / 'bin/python'), '-B', '-c', origin_code, json.dumps(value), str(staging)],
                                      env=helper_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            camp.note(f'owned installed helper origin pid={origin.pid}; process-lifetime shared lease and non-daemon stdin worker; always reaped')
            try:
                assert select.select([origin.stdout], [], [], 15)[0], 'Installed helper origin did not report readiness'
                line = origin.stdout.readline()
                assert line, origin.stderr.read()
                fixture = json.loads(line); helper = fixture['helper']; directory = Path(fixture['directory'])
                camp.note(f'owned frozen helper pid={helper}, artifact/result evidence {directory}; supervisor adopts/reaps this exact helper after origin exit')
                ck(directory.parent == staging and (directory / 'helper.pyz').is_file(), 'Manager real helper: actual installed package materializes private independent zipapp')
                time.sleep(.2)  # main has returned; non-daemon worker and its lease must still live
                ck(origin.poll() is None and not (directory / 'result.json').exists(), 'Manager real helper: main return with worker draining is not quiescence')
                ck(exclusion(camp, prefix, busy=True), 'Manager real helper: origin retains process-lifetime usage while fixture waits')
                assert not hidden.exists()
                camp.note(f'owned installed venv temporarily hidden {prefix} -> {hidden} for staged-helper process-exit proof; restored in finally before pipx uninstall')
                prefix.rename(hidden)
                try:
                    origin.communicate(timeout=10)
                    ck(origin.returncode == 0, 'Manager real helper: originating installed process exits normally with its venv absent')
                    child_pid = helper
                    status = wait_helper(helper)
                    helper = None  # reaped PID is never a signal target
                    ck(status == 0, 'Manager real helper: independent child finishes and is explicitly adopted/reaped')
                    result = result_at(directory)
                    ck(result['outcome'] == 'quiescent' and result['fixture'] is True
                       and result['origin'] == origin.pid and result['helper'] == child_pid and not prefix.exists(),
                       'Manager real helper: frozen stdlib artifact observes actual process death and acquires exclusion with application absent')
                    ck(exclusion(camp, prefix, busy=False), 'Manager real helper: fixture exit releases exclusion without changing the persistent lock inode')
                finally: hidden.rename(prefix)
            finally:
                if origin.poll() is None: origin.kill()
                origin.communicate(timeout=5)
                if helper is not None:
                    try:
                        # This PID is still an unreaped adopted child, never a reaped/reused PID.
                        os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                    except (ProcessLookupError, ChildProcessError): pass
        ck(before == {str(path): path.read_bytes() for path in paths}, 'Manager real helper: fixture left installed records/executable unchanged')
        ck(run().returncode == 0, 'Manager real helper: restored original installation remains operational; no automatic restart')
        # This external guard runs from the test venv, not from the guarded application. It
        # exercises the real fixed namespace/prefix key without patching the installed package.
        hold = subprocess.Popen([sys.executable, '-B', '-c',
            ("from opencode_sandbox.installation_locks import exclusive\n"
             f"with exclusive({str(prefix)!r}):\n print('ready', flush=True)\n input()\n")],
            env=camp.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        camp.note(f'non-mutating exclusive guard pid={hold.pid} for isolated installed prefix; stdin lifetime, always reaped')
        try:
            assert select.select([hold.stdout], [], [], 15)[0], 'Exclusive guard did not report readiness'
            assert hold.stdout.readline().strip() == 'ready'
            other_env = dict(env, OPENCODE_SANDBOX_HOME=str(base / 'excluded-data'),
                             OPENCODE_SANDBOX_CONFIG=str(base / 'excluded-config'))
            for args in (['--version'], ['--help'], ['create', 'ocs-test-refused']):
                refused = camp._run([str(launcher), *args], env=other_env, check=False)
                ck(refused.returncode == 2 and 'installation busy' in refused.stderr.lower(),
                   'Manager real pipx: exclusive access refuses ' + ' '.join(args) + ' across data/config overrides')
            ck(not (base / 'excluded-data').exists() and not (base / 'excluded-config').exists(),
               'Manager real pipx: excluded entry point created no data/config paths')
        finally:
            try: hold.communicate(timeout=10)
            finally:
                if hold.poll() is None: hold.kill(); hold.communicate(timeout=10)
        ck(exclusion(camp, prefix, busy=False), 'Manager real pipx: exclusive exit releases guard, persistent inode retained')
        record_path = prefix / 'pipx_metadata.json'
        original = record_path.read_bytes()
        for field, changed in [('pip_args', ['--no-deps']), ('pinned', True), ('suffix', '-custom')]:
            record = json.loads(original); record['main_package'][field] = changed
            record_path.write_text(json.dumps(record))
            refused = json.loads(run().stdout)['installation']
            ck(not refused['verified'] and 'manual preservation' in refused['reason'], 'Manager real pipx: custom ' + field + ' not silently discarded')
        record_path.write_bytes(original)
        foreign = base / 'foreign-launcher'
        foreign.write_text('#!/bin/sh\necho foreign-test-launcher\n'); foreign.chmod(0o700)
        launcher.unlink(); launcher.symlink_to(foreign)
        # Invoke the real venv entry point while exposed PATH launcher is foreign. No takeover.
        refused = camp._run([str(prefix / 'bin/opencode-sandbox'), 'manager', 'status'], env=env, check=True)
        ck(not json.loads(refused.stdout)['installation']['verified'] and launcher.resolve() == foreign,
           'Manager real pipx: foreign exposed launcher refused and untouched')
        launcher.unlink(); launcher.symlink_to(prefix / 'bin/opencode-sandbox')
        shadow = base / 'shadow'; shadow.mkdir()
        (shadow / 'opencode-sandbox').symlink_to(foreign)
        refused = json.loads(run(environment=dict(env, PATH=str(shadow) + ':' + env['PATH'])).stdout)['installation']
        ck(not refused['verified'] and 'shadowed' in refused['reason'], 'Manager real pipx: PATH shadowing refused even with direct official launcher invocation')
        ck(json.loads(run().stdout)['installation']['verified'], 'Manager real pipx: intact original evidence remains recognizable after test restoration')
        # Only a test-installed .pth source URL hook; the real console launcher, package,
        # interpreter, records and Docker calls remain unchanged. No production override.
        state = {'requests': 0, 'status': 200}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                state['requests'] += 1
                self.send_response(state['status']); self.end_headers()
                self.wfile.write(json.dumps([{'tag_name': 'v6.2.0', 'draft': False, 'prerelease': False,
                    'published_at': '2026-10-30T12:00:00Z', 'body': 'Read-only real terminal [notes]',
                    'html_url': 'https://github.com/CyberFazaN/opencode-sandbox/releases/tag/v6.2.0'}]).encode())
            def log_message(self, *a): pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        site = next(prefix.glob('lib/python*/site-packages'))
        (site / 'ocs_test_manager_source.pth').write_text(
            f"import opencode_sandbox.manager_releases as mr; mr.API='http://127.0.0.1:{server.server_port}/manager'\n")
        camp.note('test-only installed .pth redirects manager metadata to loopback, no mutation/installation identity hook')
        try:
            for size in ((80, 24), (120, 40)):
                requests = state['requests']
                term = Term([str(launcher), 'tui'], *size, env=env, log=camp.log)
                try:
                    assert ck(term.wait_for('OpenCode Sandbox', 30), 'Manager terminal: actual installed launcher starts dashboard')
                    ck(exclusion(camp, prefix, busy=True), 'Manager terminal: supported live dashboard prevents exclusive installation access')
                    ck(json.loads(run().stdout)['installation']['verified'], 'Manager terminal: another supported read-only instance can coexist')
                    term.send('v', .4)
                    assert ck(term.wait_for('verified official-tag pipx', 15), 'Manager terminal: real installation classification visible')
                    ck(state['requests'] == requests and 'Close' in term.text(), 'Manager terminal: opening remains network-free with visible compact controls')
                    term.send('c', .4)
                    ck(term.wait_for('Update available', 20) and state['requests'] == requests + 1,
                       'Manager terminal: explicit published-release check independent of installed identity')
                    term.send('d', .4)
                    ck(term.wait_for('Manager discovery evidence', 10), 'Manager terminal: scrollable Details retains full discovery evidence')
                    term.send(ESC, .2)
                    state['status'] = 503
                    term.send('c', .4)
                    ck(term.wait_for('HTTP 503', 20) and 'cached' in term.text(), 'Manager terminal: failed GitHub check keeps dated release and local installation')
                    state['status'] = 200
                    term.send('u', .2)
                    ck('verified manager handoff is not implemented' in term.text(), 'Manager terminal: Update remains unavailable; no replacement begun')
                    term.send(ESC, .2); term.send('q', .3)
                    ck(term.exit_code(15) == 0 and term.restored(), 'Manager terminal: normal exit restores terminal')
                    ck(exclusion(camp, prefix, busy=False), 'Manager terminal: exited dashboard no longer holds installation lease')
                finally: term.close()
        finally:
            server.shutdown(); thread.join(); server.server_close()
        ck(before == {str(path): path.read_bytes() for path in paths}, 'Manager terminal: checks/failures/Update key left installation records/executable unchanged')
        if layout == 'default':
            camp._run([*px, 'uninstall', 'opencode-sandbox'], env=env, check=True)
            camp._run([*px, 'install', '--python', sys.executable, 'git+file://' + str(repo) + '@v' + version],
                      env=env, check=True, timeout=180)
            foreign_source = json.loads(run().stdout)['installation']
            ck(not foreign_source['verified'] and 'Foreign' in foreign_source['reason'],
               'Manager real pipx: actual foreign/local VCS source refused, not converted')
            camp._run([*px, 'uninstall', 'opencode-sandbox'], env=env, check=True)
            camp._run([*px, 'install', '--python', sys.executable, '--editable', str(repo)], env=env, check=True, timeout=180)
            editable = json.loads(run().stdout)['installation']
            ck(not editable['verified'] and ('Editable' in editable['reason'] or 'ambiguous' in editable['reason']),
               'Manager real pipx: actual editable development source receives manual guidance')
    finally:
        camp._run([*px, 'uninstall', 'opencode-sandbox'], env=env, check=False)
    ck(not launcher.exists() and not prefix.exists(), 'Manager real pipx: isolated product installation uninstalled; no user launcher touched')
