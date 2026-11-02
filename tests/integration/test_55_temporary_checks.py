"""Real Debian/Arch temporary-check restoration, process death and compact batch consent.

Only campaign-owned environments; no image replacement, provider calls, host service changes or
configuration provisioning during checks. npm is stubbed in the terminal harness, not Docker.
"""
import base64
import json
import os
import shutil
import subprocess
import sys

import pytest
from campaign import DISTROS

pytest.importorskip('pyte')
from pty_term import ENTER, ESC, TAB, Term

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]


@pytest.mark.parametrize('distro', DISTROS)
def test_temporary_check_state_failure_and_parent_death(campaign, checks, distro):
    camp, ck = campaign, checks
    name = f'ocs-test-temporary-check-{distro}'
    eid = camp.create(name, '--distro', distro, '--no-integrations')
    camp.ocs('start', name)
    version = camp.sh(eid, 'opencode --version').stdout.strip().split()[-1].removeprefix('v')
    camp.sh(eid, 'umask 022; echo keep-check-workspace > /workspace/ocs-test-check; echo keep-check-home > /root/ocs-test-check')
    camp.ocs('stop', name)
    path = camp.data / 'environments' / eid / 'metadata.json'
    marker = path.with_name('version-check.json')
    before = path.read_bytes()
    code = ('from opencode_sandbox import core as c, environment_checks as checks\n'
            f'm=c.resolve({eid!r})\nimport json; print(json.dumps(checks.check(m)))\n')
    for running in (False, True):
        if running: camp.ocs('start', name)
        before = path.read_bytes()
        old = camp.inspect(eid)
        result = json.loads(camp.python(code).stdout)
        after = camp.inspect(eid)
        ck(result['version'] == version and result['verification'] == 'verified', 'Temporary check: actual binary verified')
        ck(after['Id'] == old['Id'] and after['State']['Running'] == running,
           'Temporary check: original identity and running/stopped state preserved')
        ck(path.read_bytes() == before and not marker.exists(), 'Temporary check: no metadata/config provisioning or pending cleanup')
        if running:
            ck(after['State']['StartedAt'] == old['State']['StartedAt'], 'Running check: no restart or stop')
            camp.ocs('stop', name)
    # Real failed stop on this exact run-owned immutable container; no fake restoration result.
    work = camp.tmp('temporary-check-' + distro)
    bindir = work / 'bin'; bindir.mkdir()
    binary = bindir / 'docker'
    cid = camp.inspect(eid)['Id']
    binary.write_text(f'#!{sys.executable}\nimport os,sys\n'
                      f'if sys.argv[3:6]==["stop","--time","2"] and sys.argv[-1]=={cid!r}: sys.exit(71)\n'
                      f'os.execv({shutil.which("docker")!r}, ["docker",*sys.argv[1:]])\n')
    binary.chmod(0o700)
    env = dict(camp.env, PATH=str(bindir) + os.pathsep + camp.env['PATH'])
    failed = camp._run([sys.executable, '-c', code], check=False, env=env)
    ck(failed.returncode != 0 and marker.exists() and camp.inspect(eid)['State']['Running'],
       'Temporary check: failed restoration is retained and not claimed as success')
    ck('cleanup was not fully successful' in failed.stderr, 'Temporary check: actionable cleanup failure reported')
    camp.ocs('stop', name)
    ck(not marker.exists(), 'Temporary check: explicit Stop reconciles failed cleanup')
    # Kill only this run's parent after actual temporary start, during the probe.
    ready = work / 'probe-ready'
    interrupted = ('from pathlib import Path\nimport time\n'
                   'from opencode_sandbox import core as c, environment_checks as checks, opencode_versions as v\n'
                   f'def probe(*a,**kw):\n Path({str(ready)!r}).write_text("ready")\n time.sleep(60)\n'
                   f'v._exec_version=probe\nchecks.check(c.resolve({eid!r}))\n')
    camp.note(f'owned parent process: temporary-check crash fixture for environment {eid}')
    proc = subprocess.Popen([sys.executable, '-c', interrupted], env=camp.env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    try:
        assert ck(camp.wait_for(ready.exists, timeout=30), 'Temporary check: probe reached after real temporary start')
        before = path.read_bytes()
        camp.kill(proc)
        ck(camp.wait_for(lambda: not camp.inspect(eid)['State']['Running'] and not marker.exists(), timeout=30),
           'Temporary check: independent guardian restores stopped state after parent SIGKILL')
        ck(path.read_bytes() == before, 'Temporary check: process-death cleanup leaves authoritative metadata untouched')
    finally:
        if proc.poll() is None: camp.kill(proc)
    camp.ocs('start', name)
    target = '2.2.0' if version == '2.1.4' else '2.1.4'
    update = camp.python('from opencode_sandbox import core as c, opencode_versions as v\n'
                         f'm=c.resolve({eid!r})\nplan=v.prepare_environment_update(m,{target!r},stop_running=True)\n'
                         f'assert plan.running\nprint(v.update_environment(m,{target!r},plan=plan))\n')
    ck(update.returncode == 0 and not camp.inspect(eid)['State']['Running'],
       'Running update: explicit running-state plan stops and finishes stopped, without restart')
    camp.ocs('start', name)
    ck(target in camp.sh(eid, 'opencode --version').stdout, 'Running update: exact installed binary verified after explicit Start')
    kept = camp.sh(eid, 'cat /workspace/ocs-test-check /root/ocs-test-check').stdout
    ck('keep-check-workspace' in kept and 'keep-check-home' in kept, 'Temporary checks retain workspace and home')
    camp.delete(name)


@pytest.mark.parametrize('distro', DISTROS)
@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_check_all_terminal_consent_and_fkeys(campaign, checks, distro, size):
    camp, ck = campaign, checks
    name = f'ocs-test-check-all-{distro}-{size[0]}'
    eid = camp.create(name, '--distro', distro, '--no-integrations')
    camp.ocs('start', name); camp.ocs('stop', name)
    old = camp.inspect(eid)
    script = camp.tmp('check-all-terminal') / f'{distro}-{size[0]}.py'
    script.write_text('from opencode_sandbox import opencode_versions as v\n'
                      'from opencode_sandbox.tui import Dashboard\nv.latest=lambda: "2.2.0"\nDashboard().run()\n')
    term = Term([sys.executable, str(script)], *size, env=camp.env, log=camp.log)
    try:
        assert ck(term.wait_for(name, 30), 'Check All terminal: dashboard ready')
        term.send('v', .3); term.send('3', .3); term.send('C', .4)
        assert ck(term.wait_for('Check All installed OpenCode versions', 20), 'Check All terminal: stopped targets require consent')
        ck('Cancel' in term.text() and 'Confirm' in term.text(), 'Check All terminal: buttons fit')
        term.send(ESC, .3)
        ck(camp.inspect(eid)['State']['StartedAt'] == old['State']['StartedAt'], 'Check All Cancel does not start stopped targets')
        term.send('C', .3)
        assert ck(term.wait_for('Check All installed OpenCode versions', 20), 'Check All terminal: retry consent')
        term.send(TAB + ENTER, .4)
        ck(term.wait_for('Check complete', 30), 'Check All terminal: actual batch completed')
        after = camp.inspect(eid)
        ck(not after['State']['Running'] and after['State']['StartedAt'] != old['State']['StartedAt'],
           'Check All terminal: actual temporary start followed by stop')
        term.send('\x1b[15~', .3)
        assert ck(term.wait_for('Review environment operation', 20), 'Check All terminal: F5 targets selected environment')
        term.send(TAB + ENTER, .4)
        ck(term.wait_for('Started; remains running', 30) and camp.inspect(eid)['State']['Running'], 'F5 leaves environment running')
        term.send('\x1b[17~', .3)
        assert ck(term.wait_for('Stop this environment', 20), 'F6 honors stop confirmation')
        term.send(TAB + ENTER, .4)
        ck(term.wait_for('Stopped; workspace', 30) and not camp.inspect(eid)['State']['Running'], 'F6 explicitly stops')
        term.send(ESC, .2); term.send('q', .3)
        ck(term.exit_code(15) == 0 and term.restored(), 'Check All terminal: terminal restored')
    finally: term.close()
    camp.delete(name)


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_manual_command_osc52_terminal_feedback(campaign, checks, size):
    camp, ck = campaign, checks
    command = 'echo ocs-test-clipboard'
    script = camp.tmp('clipboard-terminal') / f'clipboard-{size[0]}.py'
    script.write_text('from opencode_sandbox.tui import Dashboard\n'
                      'from opencode_sandbox.updates_tui import UpdatesScreen\n'
                      'from opencode_sandbox.manager_review_tui import ManualUpdateScreen\n'
                      'class TestApp(Dashboard):\n'
                      ' async def on_mount(self):\n'
                      '  super().on_mount()\n'
                      '  await self.push_screen(UpdatesScreen())\n'
                      f'  await self.push_screen(ManualUpdateScreen("Copy this command only", {command!r}))\n'
                      'TestApp().run()\n')
    # Force terminal transport; no writes to the VM user's actual desktop clipboard.
    term = Term([sys.executable, str(script)], *size, env=dict(camp.env, SSH_CONNECTION='ocs-test'), log=camp.log)
    try:
        assert ck(term.wait_for('Manual update required', 20), 'Clipboard terminal: modal visible')
        term.send(TAB + ENTER, .4)
        ck(term.wait_for('acceptance unverified', 10), 'Clipboard terminal: accurate inline OSC 52 feedback after modal closes')
        sequence = b'\x1b]52;c;' + base64.b64encode(command.encode()) + b'\a'
        ck(term.raw.count(sequence) == 1, 'Clipboard terminal: exactly one correct OSC 52 payload, no command execution')
        term.send(ESC, .2); term.send('q', .3)
        ck(term.exit_code(15) == 0 and term.restored(), 'Clipboard terminal: normal terminal restoration')
    finally: term.close()
