"""Real CLI shell/execution leases, across data overrides; no updater or verifier bypass."""
import select
import sys
from pathlib import Path

import pytest
from campaign import DISTROS, INSTALLED, MANAGER
from pty_term import Term
from test_66_manager_inventory import exclusion

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]


@pytest.mark.parametrize('distro', DISTROS)
def test_real_attached_session_and_exec_exclude_replacement(campaign, checks, distro):
    camp, ck = campaign, checks
    # Installed-manager campaigns intentionally use a different venv from the pytest runner.
    # Check the actual configured console installation, not the runner's unrelated prefix.
    prefix = Path(MANAGER[0]).resolve().parent.parent if INSTALLED else Path(sys.prefix)
    if INSTALLED:
        assert (prefix / 'bin/opencode-sandbox').samefile(MANAGER[0])
    name = f'ocs-test-installation-lease-{distro}'
    eid = camp.create(name, '--distro', distro, '--no-integrations')
    camp.ocs('start', name)
    term = Term([*MANAGER, 'shell', name], env=camp.env, log=camp.log)
    try:
        term.send("printf 'ocs-test-shell-%s\\n' lease-ready\r", .6)
        assert ck(term.wait_for('ocs-test-shell-lease-ready', 30), 'Installation lease: actual attached shell is active')
        ck(exclusion(camp, prefix, busy=True), 'Installation lease: attached CLI session prevents exclusive access')
        if prefix != Path(sys.prefix):
            ck(exclusion(camp, sys.prefix, busy=False), 'Installation lease: independent runner installation is not locked by the attached session')
        ck(camp.ocs('list').returncode == 0, 'Installation lease: other supported CLI instance still works during session')
        term.send('exit\r', .4)
        ck(term.exit_code(15) == 0, 'Installation lease: attached shell exits normally')
    finally: term.close()
    ck(exclusion(camp, prefix, busy=False), 'Installation lease: exited session releases guard')
    process = camp.popen('exec', name, '--', 'sh', '-c',
                         "echo ocs-test-exec-lease-ready; while [ ! -e /tmp/ocs-test-lease-release ]; do sleep 0.1; done")
    try:
        assert select.select([process.stdout], [], [], 30)[0], 'Exec did not report readiness'
        assert ck(process.stdout.readline().strip() == 'ocs-test-exec-lease-ready', 'Installation lease: real Docker exec is active')
        ck(exclusion(camp, prefix, busy=True), 'Installation lease: long CLI execution prevents exclusive access')
        camp.sh(eid, 'touch /tmp/ocs-test-lease-release')
        process.communicate(timeout=20)
        ck(process.returncode == 0, 'Installation lease: actual command completes without deadline or cancellation')
    finally:
        if process.poll() is None:
            try:
                camp.sh(eid, 'touch /tmp/ocs-test-lease-release', check=False)
                process.communicate(timeout=20)
            finally:
                if process.poll() is None: process.kill(); process.communicate(timeout=10)
    ck(exclusion(camp, prefix, busy=False), 'Installation lease: completed CLI execution releases guard')
    camp.delete(name)
