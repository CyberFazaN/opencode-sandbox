"""Isolated temporary-start owner. Holds the inherited lifecycle lock until cleanup completes.

Run as a private child, not a CLI. EOF (including parent SIGKILL) restores the stopped state.
No application imports, normal launch/configuration flows, name-based stop or unbounded calls.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    endpoint, eid, cid, marker_name, lock_fd = sys.argv[1:]
    marker = Path(marker_name)
    os.fstat(int(lock_fd))  # retained until process exit, including parent death

    def docker(*args, timeout=5):
        p = subprocess.run(['docker', '-H', endpoint, *args], stdin=subprocess.DEVNULL, check=False,
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode: raise RuntimeError('Docker command failed; inspect daemon and container state')
        return p.stdout

    def inspect():
        (info,) = json.loads(docker('container', 'inspect', cid))
        if info['Id'] != cid or (info['Config'].get('Labels') or {}).get('org.opencode-sandbox.id') != eid:
            raise RuntimeError('Container identity/ownership changed; left untouched')
        return info['State']

    error = None
    armed = False
    started_at = None
    cleanup = 'not-started'
    try:
        if sys.stdin.readline() != 'start\n': return
        if inspect().get('Running'):
            raise RuntimeError('Container became running before temporary start; left untouched')
        armed = True  # start errors/timeouts can still leave a running container
        docker('start', cid, timeout=15)
        state = inspect()
        if not state.get('Running'): raise RuntimeError('Temporary start did not leave the container running')
        started_at = state.get('StartedAt')
        print('started', flush=True)
        sys.stdin.read()  # parent closes after probe; EOF on death takes the same cleanup path
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        error = str(exc)
    finally:
        if armed:
            try:
                state = inspect()  # never stop a replacement/name collision or external restart
                if started_at and state.get('Running') and state.get('StartedAt') != started_at:
                    raise RuntimeError('Container was restarted outside this check; left untouched')
                docker('stop', '--time', '2', cid, timeout=10)
                if inspect().get('Running'): raise RuntimeError('Container is still running')
                cleanup = 'stopped'
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
                cleanup = 'unconfirmed'
                error = (error + '; ' if error else '') + 'Restoration unconfirmed: ' + str(exc)
        if cleanup == 'unconfirmed':
            # No secrets or Docker output. Keep exact identity and next step after parent death.
            value = json.loads(marker.read_text())
            value.update(error=error, hint='Inspect actual state; stop this environment (F6 or opencode-sandbox stop NAME) before retrying.')
            fd = os.open(marker, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
            with os.fdopen(fd, 'w') as stream:
                json.dump(value, stream); stream.flush(); os.fsync(stream.fileno())
        else:
            marker.unlink(missing_ok=True)
        print(json.dumps({'error': error, 'cleanup': cleanup}), flush=True)


if __name__ == '__main__': main()
