"""Real environment update/rollback and independent recovery terminal acceptance.

Both retained distributions, actual OpenCode installation/checkpoint/layers and keyboard consent.
No model provider or base replacement. Faults affect only this run's named resources.
"""
import re
import shutil
import sys

import pytest
import test_30_faults
from campaign import DISTROS

pytest.importorskip('pyte')
from pty_term import DOWN, ENTER, ESC, TAB, UP, Term

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]
fault = test_30_faults.fault


def fixture_environment(camp, name, distro):
    eid = camp.create(name, '--distro', distro, '--no-integrations')
    camp.ocs('start', name)
    camp.sh(eid, "umask 022; mkdir -p /root/.config/opencode; echo '{}' > /root/.config/opencode/opencode.json; "
                 "echo system-before > /etc/ocs-test-update; echo home-kept > /root/ocs-test-update; "
                 "echo workspace-kept > /workspace/ocs-test-update")
    config = camp.sh(eid, 'sha256sum /root/.config/opencode/opencode.json').stdout
    camp.ocs('opencode', 'versions')
    camp.ocs('stop', name)
    return eid, config


def confirm(t, ck, subject):
    assert ck(t.wait_for('Review environment operation', 30), subject + ': exact consent appears')
    ck('Cancel' in t.text() and 'Confirm' in t.text(), subject + ': consent buttons fit')
    t.snap(subject + ' consent')
    t.send(TAB + ENTER, .4)  # initial focus is Cancel


def enter_target(t):
    # Send editing keys independently: Textual may batch a burst of controls+printable text.
    t.send('\x01', .1)
    t.send('\x0b', .1)
    t.send('2.1.4', .2)
    t.send(ENTER, .4)


@pytest.mark.parametrize('distro', DISTROS)
@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
def test_environment_actions_terminal(campaign, checks, distro, size):
    camp, ck = campaign, checks
    name = f'ocs-test-envupdates-{distro}-{size[0]}'
    eid, config = fixture_environment(camp, name, distro)
    before = camp.inspect(eid)
    t = Term([sys.executable, '-m', 'opencode_sandbox.cli', 'tui'], *size, env=camp.env, log=camp.log)
    try:
        ck(t.wait_for(name, 30), 'Environment actions: dashboard ready')
        t.send('v', .3); t.send('3', .5)
        ck(all(label in t.text() for label in ('Start', 'Update', 'Policy', 'Rollback', 'Recover', 'Close')), 'Environment actions: all compact controls visible')
        t.send('p', .3)
        ck(t.wait_for('OpenCode policy', 10), 'Environment policy: compact form visible')
        t.send(ENTER, .2); t.send(DOWN * 2, .2); t.send(ENTER, .2)
        t.send(TAB, .1); t.send('2.2.0', .2); t.send(TAB * 2 + ENTER, .3)
        confirm(t, ck, 'Environment pin')
        ck(t.wait_for('OpenCode policy saved', 20) and camp.metadata(name).get('opencode_pin') == '2.2.0', 'Environment pin: exact policy saved only after consent')
        t.send('u', .3); enter_target(t)
        ck(t.wait_for('pinned to OpenCode 2.2.0', 20) and camp.metadata(name).get('opencode_update') is None, 'Environment pin: incompatible real update refused without installation')
        t.send('p', .3); t.send(ENTER, .2); t.send(UP, .2); t.send(ENTER, .2)
        t.send(TAB * 3 + ENTER, .3)
        confirm(t, ck, 'Environment Manual policy')
        ck(t.wait_for('OpenCode policy saved', 20) and camp.metadata(name).get('opencode_policy') == 'manual'
           and camp.metadata(name).get('opencode_pin') is None, 'Environment Manual policy: explicit unpin does not install anything')
        # Explicit F5 Start remains running, unlike temporary version checks.
        t.send('\x1b[15~', .3)
        confirm(t, ck, 'Explicit Start')
        ck(t.wait_for('Started; remains running', 30) and camp.inspect(eid)['State']['Running'], 'Explicit Start: actual running state preserved')
        t.send(ESC, .2)
        camp.ocs('stop', name)
        t.send('v', .3); t.send('3', .4)
        t.send('u', .3)
        ck(t.wait_for('Exact 2.x version', 10), 'Environment update: target form visible')
        t.snap('Target before keyboard edit')
        enter_target(t)
        if not t.wait_for('Install exact OpenCode 2.1.4', 30): t.snap('Missing exact consent')
        assert ck('Install exact OpenCode 2.1.4' in t.text(), 'Environment update: explicit target resolved before consent')
        t.send(ESC, .3)
        ck(camp.metadata(name).get('opencode_update') is None and not camp.inspect(eid)['State']['Running'], 'Environment update: cancel did not install/start')
        t.send('u', .3); enter_target(t)
        confirm(t, ck, 'Environment update')
        ck(t.wait_for('OpenCode update complete; stopped', 300), 'Environment update: real install finishes stopped')
        current = camp.metadata(name)
        ck(current.get('operation') is None and current['opencode_update']['to'] == '2.1.4' and not camp.inspect(eid)['State']['Running'], 'Environment update: exact target and final state authoritative')
        ck(camp.inspect(eid)['Id'] == before['Id'], 'Environment update: retained original container, not a base migration')
        camp.ocs('start', name)
        camp.sh(eid, 'echo later-system-change > /etc/ocs-test-after-update')
        camp.ocs('stop', name)
        t.send('r', .3)
        ck(t.wait_for('ENTIRE checkpointed system layer', 30), 'Environment rollback: full layer semantics disclosed')
        confirm(t, ck, 'Environment rollback')
        ck(t.wait_for('OpenCode rollback complete', 60), 'Environment rollback: existing handler completes')
        current = camp.metadata(name)
        ck(current.get('operation') is None and current['opencode_update']['state'] == 'rolled-back', 'Environment rollback: authoritative journal closed')
        snapshot = re.search(r'ocs-snapshot:[^ ]+', current['opencode_update']['result']).group(0)
        helper = f'ocs-test-{camp.run}-{distro}-{size[0]}-snapshot'
        camp.note(f'container {helper} test={camp.run}; one-shot proof of preserved current snapshot, no mounts/network')
        kept = camp.docker('run', '--rm', '--name', helper, '--network', 'none', '--label', f'org.opencode-sandbox.test={camp.run}',
                           '--entrypoint', 'sh', snapshot, '-c', 'cat /etc/ocs-test-after-update; opencode --version').stdout
        ck('later-system-change' in kept and '2.1.4' in kept, 'Environment rollback: actual present snapshot keeps later system changes and updated binary')
        t.send('\x1b[15~', .3)
        confirm(t, ck, 'Post-rollback Start')
        ck(t.wait_for('Started; remains running', 30), 'Post-rollback Start: explicit recreation completes')
        ck('2.2.0' in camp.sh(eid, 'opencode --version').stdout, 'Environment rollback: actual original OpenCode restored')
        ck(camp.sh(eid, 'test ! -e /etc/ocs-test-after-update', check=False).returncode == 0, 'Environment rollback: whole earlier system layer restored, not just the binary')
        ck(camp.sh(eid, 'sha256sum /root/.config/opencode/opencode.json').stdout == config, 'Environment rollback: user OpenCode config unchanged')
        markers = camp.sh(eid, 'cat /etc/ocs-test-update /root/ocs-test-update /workspace/ocs-test-update').stdout
        ck(all(marker in markers for marker in ('system-before', 'home-kept', 'workspace-kept')), 'Environment rollback: system/home/workspace markers preserved')
        ck(camp.inspect(eid)['Id'] != before['Id'], 'Environment rollback: fresh container, not stale installed evidence')
        t.send(ESC, .2); t.send('q', .4)
        ck(t.exit_code(15) == 0 and t.restored(), 'Environment actions: terminal restored on normal quit')
    finally: t.close()
    camp.delete(name)


@pytest.mark.parametrize('distro', DISTROS)
def test_environment_recovery_terminal(campaign, checks, fault, distro):
    camp, ck = campaign, checks
    name = f'ocs-test-envrecovery-{distro}'
    eid, config = fixture_environment(camp, name, distro)
    rc = fault(['opencode', 'update', name, '--version', '2.1.4', '--yes'], '*-H * exec *ocs-install-opencode*', 'before')
    ck(rc == -9 and camp.metadata(name).get('operation') == 'opencode-update', 'Recovery: actual SIGKILL preserves update journal')
    checkpoint = camp.metadata(name)['opencode_update']['checkpoint']
    checkpoint_id = camp.docker('image', 'inspect', '--format', '{{.Id}}', checkpoint).stdout.strip()
    retained = 'ocs-checkpoint:' + eid + '-test-retained'
    camp.note(f'image {retained} temporary alias of run-owned checkpoint {checkpoint}; removed after missing-image test')
    camp.docker('tag', checkpoint, retained)
    camp.docker('image', 'rm', checkpoint)

    bindir = camp.tmp('recovery-refusal-' + distro)
    shim, trigger = bindir / 'docker', bindir / 'fail-remove'
    # Actual docker operations except one explicitly requested failure of this run's removal.
    shim.write_text('#!/bin/sh\n'
                    f'case "$*" in *" rm ocs-{eid}")\n'
                    f' if [ -e {str(trigger)!r} ]; then echo "test owned removal refused" >&2; exit 71; fi;;\n'
                    'esac\n'
                    f'exec {shutil.which("docker")!r} "$@"\n')
    shim.chmod(0o755)
    camp.note(f'host shim {shim}; fails only rm of run-owned ocs-{eid} while {trigger} exists')
    terminal_env = dict(camp.env, PATH=f'{bindir}:{camp.env["PATH"]}')
    t = Term([sys.executable, '-m', 'opencode_sandbox.cli', 'tui'], 80, 24, env=terminal_env, log=camp.log)
    try:
        ck(t.wait_for(name, 30), 'Recovery: dashboard resumes interrupted metadata')
        t.send('v', .3); t.send('3', .4)
        ck(t.wait_for('pending operation', 20), 'Recovery: persistent reason, not an availability guess')
        t.send('e', .5)
        t.send('d', .3)
        ck(t.wait_for(r'removed outside the[\s\S]*manager', 20), 'Recovery: missing checkpoint refused without guessing success')
        t.snap('Missing checkpoint refusal in Details')
        t.send(ESC, .3)
        ck(camp.metadata(name).get('operation') == 'opencode-update' and camp.inspect(eid)['State']['Running'], 'Recovery: missing-image refusal leaves journal and container untouched')
        camp.docker('tag', retained, checkpoint)
        camp.docker('image', 'rm', retained)
        trigger.write_text('fail only this run-owned removal')
        t.send('e', .5)
        confirm(t, ck, 'Interrupted update recovery')
        ck(t.wait_for('test owned removal refused', 30), 'Recovery: real failed removal shown')
        current = camp.metadata(name)
        ck(current.get('operation') == 'runtime-recreate' and 'test owned removal refused' in current.get('last_error', ''), 'Recovery: failure persists current journal and error reason')
        ck(current['image'] == checkpoint_id and not camp.inspect(eid)['State']['Running'], 'Recovery: exact checkpoint selected, safe stopped old container retained')
        t.send('d', .3)
        t.snap('Recovery failure Details and successor route')
        ck(t.wait_for('config recover', 15), 'Recovery: Details routes successor journal correctly')
        t.send(ESC, .3)
        t.send('e', .4)
        ck(t.wait_for('Recovery Center', 15), 'Recovery: successor journal opens existing Recovery Center')
        trigger.unlink()
        t.send(TAB * 2 + ENTER, .4)  # table -> Repair -> Recover selected
        ck(t.wait_for('Recover interrupted container recreation', 20), 'Recovery Center: existing configuration recovery confirmation')
        t.send(TAB + ENTER, .5)
        ck(t.wait_for('Recovered:', 30), 'Recovery Center: existing recovery finishes after fault removed')
        ck(camp.metadata(name).get('operation') is None, 'Recovery: journal closed only after successful existing handler')
        t.send(ESC, .3); t.send(ESC, .3); t.send('q', .4)
        ck(t.exit_code(15) == 0 and t.restored(), 'Recovery: terminal restored after failed and successful attempts')
        camp.ocs('start', name)
        ck('2.2.0' in camp.sh(eid, 'opencode --version').stdout, 'Recovery: actual original binary restored')
        ck(camp.sh(eid, 'sha256sum /root/.config/opencode/opencode.json').stdout == config, 'Recovery: user OpenCode config unchanged')
        markers = camp.sh(eid, 'cat /etc/ocs-test-update /root/ocs-test-update /workspace/ocs-test-update').stdout
        ck(all(marker in markers for marker in ('system-before', 'home-kept', 'workspace-kept')), 'Recovery: full checkpoint/home/workspace data preserved')
        camp.ocs('stop', name)
        rc = fault(['opencode', 'update', name, '--version', '2.1.4', '--yes'], '*-H * exec *ocs-install-opencode*', 'before')
        ck(rc == -9 and camp.metadata(name).get('operation') == 'opencode-update', 'Recovery Center direct: second actual interruption retains intent')
        t.close()
        t = Term([sys.executable, '-m', 'opencode_sandbox.cli', 'tui'], 120, 40, env=camp.env, log=camp.log)
        ck(t.wait_for(name, 30), 'Recovery Center direct: new process sees interrupted environment')
        t.send('\x1b[19~', .5)  # F8: dashboard Recovery Center
        ck(t.wait_for('Recovery Center', 20), 'Recovery Center direct: independent entry point')
        t.send(TAB * 2 + ENTER, .4)
        confirm(t, ck, 'Recovery Center direct')
        ck(t.wait_for('OpenCode recovery complete', 30), 'Recovery Center direct: existing update-recover succeeds')
        ck(camp.metadata(name).get('operation') is None, 'Recovery Center direct: journal closed on verified recovery completion')
        t.send(ESC, .3); t.send('q', .4)
        ck(t.exit_code(15) == 0 and t.restored(), 'Recovery Center direct: larger terminal restored')
        camp.ocs('start', name)
        ck('2.2.0' in camp.sh(eid, 'opencode --version').stdout, 'Recovery Center direct: actual recovered binary verified')
    finally:
        t.close()
        if trigger.exists(): trigger.unlink()
        # Never leave this run's temporary alias, even if a prior assertion/operation failed.
        camp.docker('image', 'rm', retained, check=False)
    camp.delete(name)
