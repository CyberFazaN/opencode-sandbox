"""Explicit internal UP-16 external-tool assessment; never scheduled or an execution grant.

The caller supplies dated local classification, not authoritative consent. No tool installation,
configuration repair, Python switch, helper handoff, verifier bypass or replacement occurs. All
facts must be revalidated by the future execution gate, independently of caches/this result.
"""
import json
import os
import shutil
import time
from pathlib import Path

from . import core as c
from . import manager_tool_probe as probe

LIMIT = 131072
TIMEOUT = 8.0
KNOWN = {'PIPX_HOME', 'PIPX_BIN_DIR', 'PIPX_MAN_DIR', 'PIPX_COMPLETION_DIR', 'PIPX_SHARED_LIBS', 'PIPX_DEFAULT_PYTHON'}


def _path(value):
    try: return probe.path(value)
    except probe.Refused as exc: raise c.SandboxError(str(exc)) from None


def _controlled(path, target):
    try: return probe.controlled(path, target)
    except probe.Refused as exc: raise c.SandboxError(str(exc)) from None


def _launcher(path, target):
    try: return probe.launcher(path, target)
    except probe.Refused as exc: raise c.SandboxError(str(exc)) from None


def _probe(python, target, mode, environment, *, candidate=None):
    source = Path(__file__).with_name('manager_tool_probe.py').read_text()
    args = [str(python), '-I', '-B', *(['-S'] if mode == 'stdlib' else []), '-c', source, mode, str(target)]
    if candidate is not None: args.append(str(candidate))
    process = c.call(args, env=environment, capture=True, check=False, timeout=TIMEOUT, max_output=LIMIT)
    lines = process.stdout.splitlines()
    if process.returncode or not lines or (mode == 'pipx' and lines[:-1] != ['1.18.7']) or (mode == 'stdlib' and len(lines) != 1):
        # A refusal may be the only line; do not echo arbitrary stdout/stderr or exception text.
        if not process.returncode and len(lines) == 1:
            value = json.loads(lines[0])
            if isinstance(value, dict) and value.get('ok') is False:
                raise c.SandboxError('External runtime could not be proved independent; use manual guidance')
        raise c.SandboxError('External runtime probe did not return a valid bounded result')
    value = json.loads(lines[-1])
    if not isinstance(value, dict) or value.get('ok') is not True:
        raise c.SandboxError('External runtime could not be proved independent; use manual guidance')
    return value


def assess(installation):
    """Dated prerequisite facts only. Not called by status, discovery, startup or the dashboard."""
    result = {'at': time.time(), 'supported': False, 'reason': '',
              'execution': 'Unavailable: manager replacement and failure-recovery gates remain pending'}
    try:
        if not isinstance(installation, dict) or installation.get('verified') is not True:
            raise c.SandboxError('A recognized local installation classification is required before external-tool inspection')
        evidence = installation['evidence']
        target = _path(evidence['venv']).resolve()
        if target == Path('/') or target.name != 'opencode-sandbox' or target.parent.name != 'venvs':
            raise c.SandboxError('External-tool inspection requires the recognized application prefix')
        if any(name.startswith('PIPX_') and value and name not in KNOWN for name, value in os.environ.items()):
            raise c.SandboxError('Unrecognized pipx environment settings require manual preservation (values not displayed)')
        locations = evidence['locations']
        settings = {name: str(_path(value).resolve()) for name, value in {
            'PIPX_HOME': evidence['pipx_home'], 'PIPX_BIN_DIR': evidence['pipx_bin_dir'],
            'PIPX_MAN_DIR': locations['man_dir'], 'PIPX_COMPLETION_DIR': locations['completion_dir'],
            'PIPX_SHARED_LIBS': locations['shared_libs']}.items()}
        # Preserve the recorded source-interpreter selection, not just a shared binary endpoint.
        # Resolving it here could also erase a symlink route through the replaceable venv.
        settings['PIPX_DEFAULT_PYTHON'] = str(_path(evidence['source_python']).absolute())
        if _path(settings['PIPX_HOME']) / 'venvs/opencode-sandbox' != target:
            raise c.SandboxError('Recorded pipx home does not select the classified application prefix')
        if any(Path(value).is_relative_to(target) for name, value in settings.items() if name != 'PIPX_DEFAULT_PYTHON'):
            raise c.SandboxError('External pipx locations depend on the replaceable installation; manual preservation required')
        # No ambient Python, pip, loader, proxy, credential or provider environment is handed to
        # these version-only children. Future installation network/environment consent is separate.
        environment = {**settings, 'HOME': str(Path.home()), 'PATH': os.environ.get('PATH', os.defpath),
                       'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        candidate = shutil.which('pipx')
        if not candidate: raise c.SandboxError('External pipx executable not found; no installation or conversion was attempted')
        candidate = Path(candidate).absolute()
        python, launcher_identity = _launcher(candidate, target)
        _, python_identity = _controlled(python, target)
        _controlled(settings['PIPX_DEFAULT_PYTHON'], target)
        helper = _probe(python, target, 'stdlib', environment)
        pipx = _probe(python, target, 'pipx', environment, candidate=candidate)
        if _launcher(candidate, target) != (python, launcher_identity) or _controlled(python, target)[1] != python_identity:
            raise c.SandboxError('External pipx or interpreter changed during inspection; no execution is authorized')
        if pipx.get('locations') != {name: str(Path(value).resolve()) for name, value in settings.items()}:
            raise c.SandboxError('External pipx did not preserve recognized locations and source Python')
        result.update(supported=True, reason='Observed external interpreter, pipx runtime/dependencies and recognized settings agree; no execution grant',
                      evidence={'pipx': str(candidate), 'python': str(python), 'launcher_identity': launcher_identity,
                                'python_identity': python_identity, 'helper_runtime': helper['runtime'], 'pipx_runtime': pipx,
                                'settings': settings})
    except (c.SandboxError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        result['reason'] = str(exc) if isinstance(exc, c.SandboxError) and str(exc).startswith(('External ', 'A recognized ', 'Recorded ', 'Unrecognized ')) \
            else 'External-tool inspection unavailable (' + type(exc).__name__ + '); no installation changed'
    return result
