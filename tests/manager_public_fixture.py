"""Test-only published-source transport/observation for ACTUAL public CLI/TUI flows.

No Dashboard subclass, new action, consent/admission/terminal bypass or installer replacement.
The optional owned non-daemon drain begins only after real terminal verification/start/arming.
"""
import io
import json
import threading
import time
import zipfile
from pathlib import Path


def install(options):
    from opencode_sandbox import manager_handoff as handoff
    from opencode_sandbox import manager_releases, manager_targets
    manager_targets.ENDPOINT = options['endpoint']
    manager_releases.API = options['endpoint'] + '/releases?per_page=100'
    original_bundle = handoff._bundle
    def bundle():
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original_bundle())) as old, zipfile.ZipFile(output, 'w') as new:
            for name in old.namelist():
                raw = old.read(name)
                if name == 'manager_execution.py':
                    raw = raw.replace(b'SOURCE_API = source.API', ('SOURCE_API = ' + repr(options['endpoint'])).encode())
                new.writestr(name, raw)
        return output.getvalue()
    handoff._bundle = bundle
    start = handoff.start_update
    state = Path(options['state'])
    def report(value):
        partial = state.with_suffix('.partial'); partial.write_text(json.dumps(value)); partial.replace(state)
    def started(artifact):
        pending = start(artifact)
        fields = Path(f'/proc/{pending.process.pid}/stat').read_text().rsplit(')', 1)[1].split()
        report({'ready': True, 'helper': pending.process.pid, 'start': fields[19], 'directory': str(artifact.directory)})
        return pending
    handoff.start_update = started
    complete = handoff.complete_terminal_update
    def completed(request, terminal):
        complete(request, terminal)
        current = json.loads(state.read_text()); report({**current, 'armed': True})
        def drain():
            deadline = time.monotonic() + 30
            while not state.with_suffix('.release').exists():
                if time.monotonic() >= deadline: raise RuntimeError('Owned public handoff drain expired')
                time.sleep(.01)
        threading.Thread(target=drain, name='owned-public-manager-drain').start()
    handoff.complete_terminal_update = completed
