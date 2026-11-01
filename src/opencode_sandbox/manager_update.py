"""Independent frozen exact pipx replacement and explicit verify-only recovery.

No automatic restart/reinstall/rollback, cache authority, normal-CLI exemption or venv import in
the executor. Fresh separate read-only result clients run only under actual own exclusion.
"""
import os
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

if __package__:
    from . import installation_state as state
    from . import manager_execution as execution
    from . import manager_installer as installer
    from . import manager_observations as observations
    from . import manager_operation as operation
    from . import manager_result as installed
else:
    import installation_state as state
    import manager_execution as execution
    import manager_installer as installer
    import manager_observations as observations
    import manager_operation as operation
    import manager_result as installed


class Refused(RuntimeError):
    pass


def notice(text):
    try: print(text, flush=True)
    except OSError: pass  # terminal loss never authorizes another mutation or erases durable state


def _own(locks, prefix):
    with locks._verification(prefix) as (witness, owner_fd): locks._verify_descriptor(witness, os.getpid(), owner_fd, prefix)


def _verify(locks, record, name, deadline):
    try:
        installed.verify(locks, Path(record['prefix']), record['settings'], record[name],
                         python_version=record['python_version'], deadline=deadline)
        return True
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, AttributeError, RecursionError):
        return False


def reconcile(locks, record, path, *, installer_exit=None):
    """Only a quiescent owner may close pending state; verify target and previous independently."""
    prefix = record['prefix']
    _own(locks, prefix)
    current = locks.operation_state(prefix)
    if current is None or current['operation'] != record['operation'] or current['owner'] != state.owner() \
            or current['phase'] != 'verifying' or current['installer'] is not None:
        raise Refused('Expected-result reconciliation requires authoritative quiescent verification state')
    deadline = time.monotonic() + 40  # two separate fixed read-only clients per expected installation
    result = None
    quiet = True
    for name in ('target', 'previous'):
        verified = _verify(locks, record, name, deadline)
        stopped, live = installer.drain()
        quiet = quiet and stopped
        if not stopped: break
        if verified and not live:
            result = name + '-verified'
            break
    if not quiet: result = 'interrupted'
    elif result is None:
        try:
            installed.inspect(Path(prefix), record['settings'], record['target'], python_version=record['python_version'])
            result = 'target-unverified'
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, AttributeError, RecursionError):
            result = 'unavailable'
    value = {'operation': record['operation'], 'result': result, 'installer_exit': installer_exit}
    operation.result(path, value)  # durable evidence BEFORE the completion marker can reopen startup
    if quiet: operation.record_quiescence(record, path)
    verified = result in ('target-verified', 'previous-verified')
    current.update(phase='complete' if verified else 'manual-recovery', result=result, at=time.time())
    locks.record_operation(current, prefix)
    messages = {'target-verified': 'Sandbox Manager target installation independently verified.',
                'previous-verified': 'Requested update did not complete; the previous installation is independently verified and operational.',
                'target-unverified': 'Target records are installed, but fresh verification failed. Normal startup remains blocked.',
                'unavailable': 'Manager installation or launcher is unavailable/unverified. Normal startup remains blocked.',
                'interrupted': 'Fresh verifier descendants could not be confirmed stopped. Normal startup remains blocked.'}
    notice(messages[result])
    if installer_exit not in (None, 0): notice('pipx reported a nonzero exit; the installed state above was checked independently.')
    notice(operation.instructions(record, path))
    return value


def execute(locks, directory, expected, *, prefix, origin, helper_sha256):
    """Called only by the authenticated live-origin handoff AFTER pidfd-proven death/exclusion."""
    _own(locks, prefix)
    current = locks.operation_state(prefix)
    if current is not None and current['phase'] != 'complete': raise Refused('An incomplete manager update must be recovered first')
    installer.begin()
    # Preflight is finite and fresh; installation itself has no inherited fixture/diagnostic budget.
    deadline = time.monotonic() + 60
    observations.validate(locks, directory, expected, prefix=str(prefix), origin=origin, deadline=deadline)
    value = observations.load(locks, directory, expected, prefix=str(prefix), origin=origin)
    binding = observations.parse(value['binding'])
    notice('Validating exact manager source, external tools and effective installer policy...')
    validated = execution.validate(locks, value, cwd=Path(__file__).parent.parent, deadline=deadline)
    path = Path(__file__).parent.parent / operation.RECORD
    python_version = observations.parse(observations.read_record(Path(prefix) / 'pipx_metadata.json'))['python_version']
    # Previous-record and CLI health must be real before pipx is allowed to consume its RECORD.
    previous = {'version': value['version'], 'tag': binding['installation']['evidence']['tag'],
                'commit': binding['installation']['evidence']['commit'], 'source': state.SOURCE}
    installed.verify(locks, Path(prefix), binding['tools']['settings'], previous, python_version=python_version, deadline=deadline)
    observations.validate(locks, directory, expected, prefix=str(prefix), origin=origin, deadline=deadline)
    # Recheck effective standard clients after the fresh target-runtime probes, before persisting
    # the operation. The environment is constructed by policy, never copied from capsule context.
    effective = execution.installer_policy(Path(prefix), binding['installation']['evidence'], binding['tools'],
                                          value['context'], path.parent, deadline)
    if effective != validated['policy']: raise Refused('Effective installer inputs changed during final validation')
    stopped, live = installer.drain()
    if not stopped or live: raise Refused('Preflight descendants did not finish cleanly; no installer was admitted')
    record = operation.prepare(value, path=path, helper_sha256=helper_sha256, python_version=python_version, environment=effective['environment'])
    operation.check_archive(record, path)
    notice(operation.instructions(record, path))
    locks.record_operation(operation.status(record, path), prefix)
    notice('Installing exact reviewed tag with existing pipx and source Python; do not start another manager or external installer...')
    code = None
    try:
        code = installer.replace(locks, record, path, effective)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, AttributeError, RecursionError,
            subprocess.SubprocessError, KeyboardInterrupt, SystemExit):
        notice('Installer did not return normally; checking only independently proven stopped state.')
        # replace() reserves/reaps its leader and records whether descendants are quiescent.
        current = locks.operation_state(prefix)
        if current['phase'] != 'verifying' or current['installer'] is not None:
            notice('Installer interruption has unconfirmed quiescence. Startup stays blocked; use the private recovery record.')
            operation.result(path, {'operation': record['operation'], 'result': 'interrupted', 'installer_exit': None})
            return {'operation': record['operation'], 'result': 'interrupted', 'installer_exit': None}
    current = locks.operation_state(prefix)
    if current['phase'] != 'verifying' or current['installer'] is not None:
        notice('Installer descendants could not be confirmed stopped; normal startup remains blocked.')
        return {'operation': record['operation'], 'result': 'interrupted', 'installer_exit': code}
    notice('Installer stopped; independently verifying exact installed result...')
    return reconcile(locks, record, path, installer_exit=code)


def recover(path):
    """Explicit frozen verify-only recovery, also usable when the app/Python venv is broken.

    A hard-killed installer owner cannot attest escaped descendant quiescence. Never guess or
    signal old PIDs: same-boot active-installer state remains manual. A different boot proves all
    prior installer descendants dead. Handled failures persist installer=None only after own
    subreaper/group cleanup; those can be verified/recovered in the same boot without a reboot.
    """
    import installation_locks as locks
    import manager_tool_probe as tools
    path = observations._path(str(path))
    record = operation.read(path)
    operation.check_archive(record, path)
    prefix = record['prefix']
    if sys.version_info < (3, 11) or not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode:
        raise Refused('Independent recovery requires isolated stdlib-only external Python')
    for value in (sys.executable, sys.prefix, sys.base_prefix, sysconfig.get_path('stdlib'), *sys.path): tools.outside(value, Path(prefix))
    with locks.exclusive(prefix):
        current = locks.operation_state(prefix)
        if current is None or current['operation'] != record['operation'] or current['record'] != str(path) \
                or current['target'] != record['target'] or current['previous'] != record['previous']:
            raise Refused('Authoritative manager operation does not match these recovery inputs')
        if current['phase'] == 'complete':
            notice('This operation was already completed; its record is historical, not a fresh health observation. No state changed.')
            return {'operation': record['operation'], 'result': current['result'], 'historical': True}
        if state.alive(current['owner']): raise Refused('The original operation owner is still alive; recovery cannot take over')
        same_boot = current['owner']['boot'] == state.owner()['boot']
        prepared = current['phase'] == 'prepared' and current['installer'] is None
        proven = current['installer'] is None and operation.quiescence(record, path, current['owner'])
        if same_boot and not prepared and not proven:
            notice(operation.instructions(record, path))
            raise Refused('Interrupted installer descendant quiescence is unknown in this boot; no state changed')
        installer.begin()
        current.update(owner=state.owner(), phase='manual-recovery', installer=None, result='interrupted', at=time.time())
        locks.record_operation(current, prefix)
        current.update(phase='verifying', result=None, at=time.time())
        locks.record_operation(current, prefix)
        return reconcile(locks, record, path)
