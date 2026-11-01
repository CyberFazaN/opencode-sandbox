"""Affected real installed-pipx terminal handoff acceptance; not installation execution."""
import json
import os
import signal
import termios
from pathlib import Path

from campaign import ROOT
from pty_term import Term
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_terminal import read_state


def _reap(pid):
    if pid is None: return
    try:
        if os.waitpid(pid, os.WNOHANG)[0] == 0:
            os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
    except ChildProcessError: pass


def exercise(camp, ck, prefix, env, evidence, staging, base, layout):
    from test_66_manager_inventory import exclusion
    # Like the installed-pipx lifecycle row, isolated HOME retains read-only access to the
    # existing Docker context store. No context/default/identity response or credential is copied.
    env = dict(env, DOCKER_CONFIG=camp.env.get('DOCKER_CONFIG', str(Path.home() / '.docker')))
    distro = 'debian' if layout == 'default' else 'arch'
    name = 'ocs-test-handoff-' + distro
    camp.create(name, '--distro', distro, '--no-integrations')
    for mode, size in [('drain', (80, 24)), ('explicit', (120, 40)), ('worker', (80, 24)),
                       ('cancelled-worker', (120, 40)), ('session', (80, 24)), ('modes', (80, 24)), ('busy', (80, 24))]:
        state = base / ('terminal-' + mode + '.json')
        options = {'verify': True, 'drain': mode == 'drain', 'explicit': mode == 'explicit',
                   'worker': mode in ('worker', 'cancelled-worker'), 'cancel': mode == 'cancelled-worker'}
        if options['worker']: options['environment'] = name
        if mode == 'session': options['session'] = name
        if mode == 'modes': options['fault'] = 'modes'
        camp.note(f'owned installed terminal fixture mode={mode}, state/release/partial/pty-bytes={state}, artifacts={staging}; '
                  'test-only F9 injection, actual App.run/driver/terminal/lease/helper/verifier, no installation executor; exact children reaped')
        helper = other = None
        if mode == 'session': camp.ocs('start', name)
        with subreaper():
            term = Term([str(prefix / 'bin/python'), '-B', str(ROOT / 'tests/manager_terminal_fixture.py'),
                         json.dumps(evidence), str(staging), str(state), json.dumps(options)], *size, env=env, log=camp.log)
            try:
                if mode == 'busy':
                    other = Term([str(prefix / 'bin/opencode-sandbox')], env=env, log=camp.log)
                    assert ck(other.wait_for('OpenCode Sandbox', 20), 'Manager handoff: another actual installed dashboard remains live')
                if mode == 'session':
                    value = read_state(state, lambda value: value.get('session_refused'), timeout=20, pump=term.pump)
                    ck('session' in value['session_refused'] and value['client'] > 0,
                       'Manager handoff: actual attached Docker client start refuses request while session owns terminal')
                    term.send("printf 'ocs-test-handoff-%s\\n' session-ready\r", .6)
                    assert ck(term.wait_for('ocs-test-handoff-session-ready', 30), 'Manager handoff: actual attached container shell is operational')
                    ck(exclusion(camp, prefix, busy=True), 'Manager handoff: live installed attached session retains installation usage')
                    term.send('exit\r', .8)
                assert ck(term.wait_for('OpenCode Sandbox', 30), 'Manager handoff: real installed dashboard visible at requested terminal size')
                if options['worker']: read_state(state, lambda value: value.get('worker_started'))
                else: read_state(state, lambda value: value.get('idle'), timeout=30, pump=term.pump)
                term.send('\x1b[20~', .3)
                if options['worker']:
                    value = read_state(state, lambda value: value.get('refused'))
                    ck(('operation' in value['refused'] or 'work is still running' in value['refused'])
                       and not value.get('requested') and not value.get('helper'),
                       'Manager handoff: approved actual lifecycle worker refuses transfer, including canceled-but-live body')
                    ck(not (Path(value['directory']) / 'result.json').exists(), 'Manager handoff: refusal neither launches nor arms a helper')
                    state.with_suffix('.release').touch()
                    read_state(state, lambda value: value.get('worker_done'), timeout=30, pump=term.pump)
                    inspected = camp.ocs('status', name).stdout
                    ck('Running: True' in inspected,
                       'Manager handoff: refused handoff did not cancel approved real environment start')
                    term.send('q', .3)
                    ck(term.exit_code(15) == 0 and term.restored(), 'Manager handoff: ordinary quit after refused request restores terminal without handoff')
                    ck(not json.loads(state.read_text()).get('helper'), 'Manager handoff: rejected request is not retained as future consent')
                    camp.ocs('stop', name)
                    continue
                if mode == 'modes':
                    value = read_state(state, lambda value: value.get('failed'))
                    ck(value['helper'] is None and not (Path(value['directory']) / 'result.json').exists(),
                       'Manager handoff: changed real tty modes after driver shutdown refuse before helper launch')
                    ck(term.exit_code(15) == 2, 'Manager handoff: failed terminal restoration reports nonzero, never fixture success')
                    continue
                value = read_state(state, lambda value: value.get('returned') or value.get('failed'))
                assert ck(value.get('returned'), 'Manager handoff: actual CLI clean return occurs only after terminal checks and arming'), value
                helper = value['helper']; assert helper is not None
                term.pump(.2)
                marker = term.raw.index(b'Non-mutating manager handoff fixture:')
                ck(all(term.raw.rfind(sequence, 0, marker) >= 0 for sequence in
                       (b'\x1b[?1049l', b'\x1b[?25h', b'\x1b[?1000l'))
                   and b'\x1b[?1049h' not in term.raw[marker:],
                   'Manager handoff: real alternate-screen/cursor/mouse teardown precedes flushed handoff output; no auto-restart')
                ck(termios.tcgetattr(term.fd)[3] & termios.ICANON and termios.tcgetattr(term.fd)[3] & termios.ECHO,
                   'Manager handoff: real terminal canonical and echo modes restored before ownership transfer')
                if mode == 'drain':
                    ck(not (Path(value['directory']) / 'result.json').exists() and exclusion(camp, prefix, busy=True),
                       'Manager handoff: armed helper cannot act on restored terminal/main return while actual non-daemon shutdown is live')
                    state.with_suffix('.release').touch()
                ck(term.exit_code(15) == 0, 'Manager handoff: actual originating installed manager process exits cleanly')
                status = wait_helper(helper, timeout=15); helper = None
                ck(status == 0, 'Manager handoff: external helper/verifier finishes, exact adopted helper reaped')
                result = result_at(value['directory'])
                ck(result['outcome'] == ('busy' if mode == 'busy' else 'quiescent'),
                   'Manager handoff: one non-waiting exclusive attempt refuses other supported instance or succeeds after actual origin death')
                if mode != 'busy': ck(result['verifier']['ok'] is True, 'Manager handoff: dedicated fresh runtime query still succeeds under helper-owned exclusion')
            finally:
                state.with_suffix('.release').touch()
                term.pump(.1)
                state.with_suffix('.pty').write_bytes(term.raw)
                _reap(term.pid); os.close(term.fd)
                if state.exists(): helper = helper or json.loads(state.read_text()).get('helper')
                _reap(helper)
                if other is not None:
                    other.send('q', .2)
                    ck(other.exit_code(15) == 0 and other.restored(), 'Manager handoff: other supported dashboard preserved and exits normally')
                    _reap(other.pid); os.close(other.fd)
    ck(exclusion(camp, prefix, busy=False), 'Manager handoff: all actual fixture processes finished and installation exclusion is free')
    camp.delete(name)
