"""Internal helper materialization/process-exit fixture, not manager-update authorization.

An internal CLI/TUI restored-terminal fixture exists, with no public action/command/startup
trigger, normal-CLI bypass or installation execution. The fixture is separate from consent/
recovery; supported tools grant neither. Private artifacts/results are not disposable caches.
"""
import hashlib
import io
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import termios
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import core as c
from . import installation_locks as locks
from . import manager_tool_probe as paths
from . import manager_tools as tools

FILES = ('helper.pyz', 'artifact.json', 'result.json')
REVIEW = 'review.json'
BUNDLE = ('manager_helper.py', 'installation_locks.py', 'manager_tool_probe.py', 'manager_verifier.py',
          'manager_observations.py', 'installation_state.py', 'manager_source.py', 'manager_process.py',
          'manager_network.py', 'manager_pip_probe.py', 'manager_execution.py', 'http_probe.py')


@dataclass(frozen=True)
class TerminalRequest:
    artifact: object
    verify: bool = False


class Terminal:
    """Observe the original local foreground terminal; never repair or infer it from PID death.

    Ordinary dashboard startup is unaffected when observation is unavailable. Only the internal
    fixture requires all three original streams on the same foreground tty and exact restoration.
    Visual-mode teardown still belongs to Textual; real-pty tests assert its bytes precede handoff.
    """
    def __init__(self):
        self.owner, self.thread = os.getpid(), threading.get_ident()
        self.streams = (sys.__stdin__, sys.__stdout__, sys.__stderr__)
        self.before = self._observe()
        self.used = False

    def _observe(self):
        rows = []
        for stream in self.streams:
            fd = stream.fileno()
            info = os.fstat(fd)
            if not os.isatty(fd) or os.tcgetpgrp(fd) != os.getpgrp():
                raise c.SandboxError('Manager handoff requires the original foreground terminal')
            rows.append((fd, info.st_dev, info.st_ino, info.st_rdev, termios.tcgetattr(fd)))
        if len({row[3] for row in rows}) != 1:
            raise c.SandboxError('Manager handoff requires one local terminal for all streams')
        return rows

    def check(self):
        if self.used or self.owner != os.getpid() or self.thread != threading.get_ident() \
                or self.streams != (sys.__stdin__, sys.__stdout__, sys.__stderr__) or self.before != self._observe():
            raise c.SandboxError('Terminal restoration could not be verified; no handoff was armed')


def complete_terminal_fixture(request, terminal):
    """Called only after clean Dashboard.run()/driver shutdown, never while suspended/running.

    No callback/executor/installation payload. Snapshot verification and flushed plain output
    precede the helper launch/arming. Its pidfd still waits for actual origin death, including
    residual non-daemon/executor shutdown. The originating usage lease is never released here.
    """
    if type(request) is not TerminalRequest or type(terminal) is not Terminal \
            or type(request.artifact) is not Artifact or type(request.verify) is not bool:
        raise c.SandboxError('Restored-terminal handoff is unavailable; no fixture was armed')
    terminal.check()
    try:
        print('Non-mutating manager handoff fixture: terminal restored; no installation will be changed.', flush=True)
        fixture = start_fixture(request.artifact, verify=request.verify, execution=request.artifact.execution)
        try:
            terminal.check()
            fixture.arm()
            fixture.control.close()  # armed ownership transfer, NOT cancel or proof of origin death
        except BaseException:
            fixture.close()
            raise
    finally: terminal.used = True


def _private(path, *, directory=False):
    info = path.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600) \
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1):
        raise c.SandboxError('External helper artifact is not private and owned')
    return info.st_dev, info.st_ino


def _write(directory, name, raw):
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def _record(path):
    _private(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream: raw = stream.read(4097)
    if len(raw) > 4096: raise c.SandboxError('External helper record changed; preserved')
    return json.loads(raw)


def _bundle():
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', compression=zipfile.ZIP_STORED) as archive:
        for source in BUNDLE:
            name = '__main__.py' if source == 'manager_helper.py' else source
            fd = os.open(Path(__file__).with_name(source), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 65536: raise c.SandboxError('External helper source unavailable')
                raw = stream.read(65537)
                if len(raw) > 65536: raise c.SandboxError('External helper source exceeds its bound')
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, raw)
    return content.getvalue()


@dataclass
class Artifact:
    directory: Path
    prefix: str
    python: str
    sha256: str
    directory_identity: tuple
    file_identity: tuple
    python_identity: tuple
    owner: int = field(default_factory=os.getpid)
    process: object = field(default=None, repr=False)
    used: bool = False
    verify: bool = False
    review_sha256: str = ''
    review_identity: str = ''
    review_file_identity: tuple = ()
    execution: bool = False

    def check(self):
        if self.owner != os.getpid(): raise c.SandboxError('External helper artifact belongs to another process')
        paths.outside(str(self.directory), Path(self.prefix))
        if _private(self.directory, directory=True) != self.directory_identity \
                or _private(self.directory / FILES[0]) != self.file_identity:
            raise c.SandboxError('External helper artifact identity changed')
        fd = os.open(self.directory / FILES[0], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, 'rb') as stream: raw = stream.read(262145)
        if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != self.sha256:
            raise c.SandboxError('External helper artifact content changed')
        if self.review_sha256:
            from . import manager_observations as observations
            if _private(self.directory / REVIEW) != self.review_file_identity:
                raise c.SandboxError('Approved local observation file identity changed; preserved')
            fd = os.open(self.directory / REVIEW, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            with os.fdopen(fd, 'rb') as stream: raw = stream.read(observations.LIMIT + 1)
            if len(raw) > observations.LIMIT or hashlib.sha256(raw).hexdigest() != self.review_sha256:
                raise c.SandboxError('Approved local observation content changed; preserved')

    def discard(self):
        """Explicit exact-artifact cleanup only after our child is reaped; never on live transfer."""
        self.check()
        if self.process is not None and self.process.poll() is None:
            raise c.SandboxError('External helper is still alive; preserve its artifact')
        names = {path.name for path in self.directory.iterdir()}
        if not names <= set(FILES) | ({REVIEW} if self.review_sha256 else set()):
            raise c.SandboxError('External helper directory has unfamiliar files; preserved')
        for name in names: _private(self.directory / name)
        inventory = {'protocol': 1, 'fixture': True, 'sha256': self.sha256}
        if self.review_sha256: inventory.update(review_sha256=self.review_sha256, review_identity=self.review_identity)
        if _record(self.directory / FILES[1]) != inventory:
            raise c.SandboxError('External helper inventory changed; preserved')
        if FILES[2] in names:
            value = _record(self.directory / FILES[2])
            base = {'protocol', 'fixture', 'sha256', 'origin', 'helper', 'outcome'}
            if self.process is None or not isinstance(value, dict) or not base <= set(value) or set(value) - base - {'verifier', 'review', 'execution'} \
                    or value['protocol'] != 1 or value['fixture'] is not True or value['sha256'] != self.sha256 \
                    or value['origin'] != self.owner or value['helper'] != self.process.pid \
                    or value['outcome'] not in ('quiescent', 'busy', 'cancelled', 'abandoned', 'expired', 'verification-failed', 'review-failed', 'execution-failed'):
                raise c.SandboxError('External helper result is unfamiliar; preserved')
            if 'review' in value:
                review = value['review']
                if not self.review_sha256 or not isinstance(review, dict) or type(review.get('ok')) is not bool \
                        or review.get('identity') != self.review_identity \
                        or set(review) != ({'ok', 'identity'} if review['ok'] else {'ok', 'identity', 'reason'}) \
                        or (not review['ok'] and (value['outcome'] != 'review-failed' or 'verifier' in value
                            or review['reason'] != 'Approved local manager observations changed or unavailable; no installation was changed')) \
                         or (review['ok'] and value['outcome'] not in ('quiescent', 'verification-failed', 'execution-failed')):
                    raise c.SandboxError('External helper local observation result is unfamiliar; preserved')
            elif value['outcome'] == 'review-failed' or self.review_sha256 and value['outcome'] in ('quiescent', 'verification-failed', 'execution-failed'):
                raise c.SandboxError('External helper local observation result is missing; preserved')
            if 'execution' in value:
                check = value['execution']
                if not self.execution or not isinstance(check, dict) or type(check.get('ok')) is not bool \
                        or check != ({'ok': True} if check['ok'] else {'ok': False, 'reason': 'Independent manager execution validation failed; no installation was changed'}) \
                        or value['outcome'] not in (('quiescent', 'verification-failed') if check['ok'] else ('execution-failed',)) \
                        or value.get('review', {}).get('ok') is not True or not check['ok'] and 'verifier' in value:
                    raise c.SandboxError('External helper execution result is unfamiliar; preserved')
            elif value['outcome'] == 'execution-failed' or self.execution and value['outcome'] in ('quiescent', 'verification-failed'):
                raise c.SandboxError('External helper execution result is missing; preserved')
            if 'verifier' in value and (not self.verify or not isinstance(value['verifier'], dict)
                                        or type(value['verifier'].get('ok')) is not bool):
                raise c.SandboxError('External helper verifier result is unfamiliar; preserved')
            if 'verifier' in value:
                verifier = value['verifier']
                expected = {'ok', 'observed'} if verifier['ok'] else {'ok', 'reason'}
                if set(verifier) != expected or value['outcome'] != ('quiescent' if verifier['ok'] else 'verification-failed'):
                    raise c.SandboxError('External helper verifier result is unfamiliar; preserved')
                if verifier['ok']:
                    observed = verifier['observed']
                    if not isinstance(observed, dict) or set(observed) != {'prefix', 'module', 'version'} \
                            or observed['prefix'] != self.prefix or not isinstance(observed['module'], str) \
                            or not Path(observed['module']).resolve().is_relative_to(self.prefix) or not isinstance(observed['version'], str):
                        raise c.SandboxError('External helper runtime facts are unfamiliar; preserved')
                elif verifier['reason'] != 'Fresh runtime verification unavailable; no installation was changed':
                    raise c.SandboxError('External helper verifier result is unfamiliar; preserved')
        for name in names: (self.directory / name).unlink()
        self.directory.rmdir()


def prepare(installation, parent):
    """Fresh read-only prerequisites, then freeze an owned stdlib zipapp outside the target.

    Results never authorize a mutation. No helper is started just by preparing an artifact.
    """
    return _prepare(installation, parent, None)


def prepare_review_fixture(approval, parent):
    """Stage approved LOCAL observations only; no independent fresh tool/source/install grant.

    Ordinary startup/UI has no consumer. The explicit internal caller must separately finish
    the existing terminal/admission gate. Source/critical facts are fresh in the living origin;
    after death only the frozen bounded local observations are replayed. Never a recovery record.
    """
    from dataclasses import asdict

    from . import manager_installation, manager_observations, manager_review
    if type(approval) is not manager_review.Approval:
        raise c.SandboxError('An exact internal review receipt is required for the local observation fixture')
    review = manager_review.revalidate(approval.review)
    try:
        raw = manager_observations.capsule(origin=os.getpid(), prefix=review.prefix, version=review.version,
            identity=review.identity, binding=review.binding, target=asdict(review.target),
            context={name: os.environ.get(name) for name in manager_observations.CONTEXT})
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        raise c.SandboxError('Approved local observation input refused; no fixture was staged') from None
    return _prepare(manager_installation.classify(), parent, (raw, review.identity))


def _prepare(installation, parent, local_review):
    facts = tools.assess(installation)
    if not facts['supported']: return {'supported': False, 'reason': facts['reason']}
    directory = None
    try:
        prefix = tools._path(installation['evidence']['venv']).resolve()
        parent = Path(paths.outside(str(parent), prefix))
        if not parent.is_dir(): raise c.SandboxError('External helper staging parent must already exist')
        raw = _bundle()
        directory = Path(tempfile.mkdtemp(prefix='ocs-test-helper-', dir=parent))
        digest = hashlib.sha256(raw).hexdigest()
        _write(directory, FILES[0], raw)
        inventory = {'protocol': 1, 'fixture': True, 'sha256': digest}
        review_digest = review_identity = ''
        if local_review is not None:
            review_raw, review_identity = local_review
            _write(directory, REVIEW, review_raw)
            review_digest = hashlib.sha256(review_raw).hexdigest()
            inventory.update(review_sha256=review_digest, review_identity=review_identity)
        _write(directory, FILES[1], (json.dumps(inventory, sort_keys=True) + '\n').encode())
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try: os.fsync(fd)
        finally: os.close(fd)
        artifact = Artifact(directory, str(prefix), facts['evidence']['python'], digest,
                             _private(directory, directory=True), _private(directory / FILES[0]),
                             tuple(facts['evidence']['python_identity']), review_sha256=review_digest,
                             review_identity=review_identity,
                             review_file_identity=_private(directory / REVIEW) if review_digest else ())
        artifact.check()
        return {'supported': True, 'reason': 'Non-mutating helper fixture staged; no handoff or installation grant', 'artifact': artifact}
    except (OSError, ValueError, RuntimeError):
        # Preserve partial artifacts as named evidence; never repair/unlink unfamiliar paths.
        return {'supported': False, 'reason': 'External helper staging refused; no installation was changed',
                'preserved': str(directory) if directory is not None else None}


class Fixture:
    def __init__(self, artifact, control, process):
        self.artifact, self.control, self.process = artifact, control, process

    def arm(self):
        """Arm ONLY the non-mutating fixture. EOF/main return is never process-exit evidence."""
        self.control.sendall(b'arm')
        if self.control.recv(4096) != b'armed': raise c.SandboxError('External helper did not acknowledge fixture arming')

    def close(self):
        """Cancel and reap our exact fixture child; does not delete its evidence/artifact."""
        try:
            try: self.control.sendall(b'cancel')
            except OSError: pass
            try: self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=3)
        finally: self.control.close()


def start_fixture(artifact, *, budget=30.0, verify=False, execution=False):
    """One finite non-mutating fixture, with pidfd proof of this process's actual exit.

    Explicit close/cancel remains the origin's responsibility while alive. After an armed origin
    exits, the independent helper owns its remaining bounded lifetime and retains private result/
    artifact evidence. It never inherits usage leases or executes replacement. Optional fresh
    verification is one fixed read-only query, never normal CLI dispatch or a target/source grant.
    """
    artifact.check()
    # This is an originating-manager fixture, not an external shortcut around usage leasing.
    # Retain that lease unchanged until actual process exit, including all worker shutdown.
    if locks.identity() != artifact.prefix: raise c.SandboxError('External helper origin does not own the target installation')
    locks._ordered()
    locks.acquire_usage()
    if artifact.used: raise c.SandboxError('External helper artifact is single-use')
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 0 < budget <= 30:
        raise c.SandboxError('External helper fixture budget must be finite and at most 30 seconds')
    if type(verify) is not bool: raise c.SandboxError('External helper verification choice must be boolean')
    if type(execution) is not bool or execution and not artifact.review_sha256:
        raise c.SandboxError('Independent execution validation requires an approved local review fixture')
    if tuple(tools._controlled(artifact.python, Path(artifact.prefix))[1]) != artifact.python_identity:
        raise c.SandboxError('External helper interpreter changed since preparation')
    control, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    pidfd = directory = None
    fixture = None
    try:
        pidfd = os.pidfd_open(os.getpid())  # no PID polling/reuse window or fallback to socket EOF
        directory = os.open(artifact.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        artifact.check()
        with c._session_launch_signals():
            process = subprocess.Popen([artifact.python, '-I', '-B', '-S', str(artifact.directory / FILES[0]),
                                        'quiescence-fixture', str(child.fileno()), str(pidfd), str(directory)],
                                       pass_fds=(child.fileno(), pidfd, directory), close_fds=True, start_new_session=True,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       cwd=artifact.directory, env={'HOME': str(Path.home()), 'PATH': os.defpath, 'LANG': 'C.UTF-8'})
            artifact.process, artifact.used, artifact.verify, artifact.execution = process, True, verify, execution
            fixture = Fixture(artifact, control, process)
        child.close()
        control.settimeout(8)
        request = {'protocol': 1, 'prefix': artifact.prefix, 'sha256': artifact.sha256, 'budget': budget}
        if verify: request['verify'] = True
        if execution: request['execution_validate'] = True
        if artifact.review_sha256:
            request['local_review'] = {'sha256': artifact.review_sha256, 'identity': artifact.review_identity,
                                       'file_identity': list(artifact.review_file_identity)}
        control.sendall(json.dumps(request).encode())
        if control.recv(4096) != b'ready': raise c.SandboxError('External helper fixture readiness refused')
        return fixture
    except BaseException:
        if fixture is not None: fixture.close()
        else: control.close()
        raise
    finally:
        child.close()
        for fd in (pidfd, directory):
            if fd is not None: os.close(fd)
