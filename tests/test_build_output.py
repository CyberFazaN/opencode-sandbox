"""Actual host clients: long build output is drained/bounded, not a short diagnostic."""
import os
import sys
import time

import pytest

from opencode_sandbox import build_output as b
from opencode_sandbox import core as c


def test_real_output_tail_is_bounded_drained_and_never_written_into_terminal(capsys):
    events = []
    code = "import sys; print('begin'); print('x'*200000); print('tail [literal]'); print('stderr-tail',file=sys.stderr)"
    with b.listen(lambda *event: events.append(event)):
        b.phase('Building cached candidate')
        result = c.call([sys.executable, '-c', code], build_stream=True, capture=True)
        b.phase('Verifying candidate')
    assert result.returncode == 0 and 'tail [literal]' in result.stdout and 'stderr-tail' in result.stdout
    assert len(result.stdout) <= b.LIMIT
    assert 'Earlier build output omitted' in events[-1][1]
    assert events[-1][0] == 'Verifying candidate' and len(events[-1][1]) < b.LIMIT + 100
    assert not capsys.readouterr().out and b.current() is None


def test_output_callback_receives_phases_and_process_is_reaped_even_on_nonzero_exit():
    events = []
    with b.listen(lambda *event: events.append(event)), pytest.raises(c.SandboxError, match=r'Command failed \(7\).*'):
        c.call([sys.executable, '-c', "print('failed-package'); raise SystemExit(7)"], build_stream=True, capture=True)
    assert 'failed-package' in events[-1][1]
    with pytest.raises(ChildProcessError): os.waitpid(-1, os.WNOHANG)


def test_build_stream_has_no_short_diagnostic_cancellation_or_output_termination(monkeypatch):
    events = []
    started = time.monotonic()
    monkeypatch.setattr(c.diagnostics, 'run', lambda *a, **kw: pytest.fail('not a bounded diagnostic'))
    with c.runtime_feedback(cancelled=lambda: True), b.listen(lambda *event: events.append(event)):
        result = c.call([sys.executable, '-c', "import time; print('start',flush=True); time.sleep(.2); print('end')"],
                        build_stream=True, capture=True)
    assert result.returncode == 0 and 'end' in result.stdout and time.monotonic() - started >= .2
    assert events and 'start' in events[0][1]
