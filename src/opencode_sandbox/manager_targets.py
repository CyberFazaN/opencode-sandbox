"""Internal exact published-source evidence for UP-17, NOT installation consent or an updater.

No startup/discovery/UI consumer, cached target grant, pipx/Git execution or helper payload. The
official GitHub HTTPS API is the authority for publication and Git object identity, not signed
tag authentication. Revalidation observes the same target afresh; it does not lock a remote tag
or an installation. A future exclusive executor must independently bind/revalidate installation,
tools, consent and source and verify what was actually installed.
"""
import json
import math
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import core as c
from . import manager_releases as releases
from . import manager_source
from . import update_cache as cache

SOURCE_API = manager_source.API
ENDPOINT = SOURCE_API  # test transport may substitute loopback, never a product setting/argument
LIMIT = 131072
TIMEOUT = 8.0  # whole read-only graph, NOT a future installation/build deadline
MAX_TAGS = manager_source.MAX_TAGS


@dataclass(frozen=True)
class Target:
    tag: str
    version: str
    release_id: int
    published_at: str
    notes: str
    notes_truncated: bool
    notes_sha256: str
    objects: tuple[str, ...]  # zero to four annotated-tag OIDs followed by the exact commit OID
    at: float = field(compare=False)

    @property
    def commit(self): return self.objects[-1]

    @property
    def source(self): return releases.REPOSITORY + '.git'

    @property
    def url(self): return releases.REPOSITORY + '/releases/tag/' + self.tag


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError('Ambiguous duplicate JSON field')
        value[key] = item
    return value


def _get(path, deadline, attempt):
    left = deadline - time.monotonic()
    if left <= 0: raise c.SandboxError('Manager source resolution timed out')
    # Separate isolated stdlib children bound DNS/TLS/body reads with the parent's total budget.
    # No token, proxy credential, Python/site/loader/index setting or user command is forwarded.
    try:
        process = c.call([sys.executable, '-I', '-B', '-S', str(Path(__file__).with_name('http_probe.py')),
                          ENDPOINT + path, str(left), str(LIMIT), 'github'],
                         env={'PATH': os.defpath, 'LANG': 'C.UTF-8'}, capture=True, check=False,
                         timeout=left, max_output=LIMIT + 1024)
    except c.SandboxError:
        raise c.SandboxError('GitHub source request failed or timed out; no source identity verified') from None
    if process.returncode:
        try: error = json.loads(process.stderr)
        except ValueError: error = None
        if isinstance(error, dict) and type(error.get('status')) is int:
            attempt['retry_until'] = releases._rate_until(error)
            raise c.SandboxError(f"GitHub source request failed (HTTP {error['status']})")
        raise c.SandboxError('GitHub source request failed; check network/TLS configuration')
    if time.monotonic() >= deadline: raise c.SandboxError('Manager source resolution timed out')
    value = json.loads(process.stdout, object_pairs_hook=_unique, parse_constant=cache._invalid_constant)
    if not isinstance(value, dict): raise TypeError('Expected GitHub object')
    return value


def _resolve(tag, deadline, attempt):
    try: value = manager_source.resolve(tag, lambda path: _get(path, deadline, attempt))
    except ValueError as exc:
        if str(exc).startswith('Published manager source changed'): raise c.SandboxError(str(exc)) from None
        raise
    value['objects'] = tuple(value['objects'])
    return Target(**value, at=time.time())


def resolve(tag, installed, *, timeout=TIMEOUT):
    """Fresh explicit exact release/ref/peeled-commit observation. No cached selection or grant.

    Both versions are strict full stable versions, and only a strictly newer target is eligible.
    `installed` is a caller's version comparison input, NOT proof of an installation's identity.
    The separate disposable attempt claim holds no target/consent and shares GitHub rate limits.
    """
    version = releases.version(tag)
    current = releases.version('v' + installed if isinstance(installed, str) else installed)
    if releases._key(version) <= releases._key(current):
        raise c.SandboxError('Manager target must be newer than the installed version; no implicit downgrade or reinstall')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= TIMEOUT:
        raise c.SandboxError('Manager source resolution requires a finite budget of at most eight seconds')
    deadline = time.monotonic() + timeout
    try:
        with cache.source_lock(releases.cache_key(), timeout=timeout):
            releases._rate_gate()
            attempt = {'at': time.time(), 'ok': False, 'id': secrets.token_hex(16), 'error': 'check did not complete'}
            if not cache.write(releases.target_key(), {'attempt': attempt}, durable=True):
                raise c.SandboxError('Manager source resolution unavailable: cannot persist safe attempt claim')
            try:
                target = _resolve(tag, deadline, attempt)
            except (c.SandboxError, OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
                # No raw metadata/URL/OS/child diagnostic is surfaced; known errors are static.
                attempt['error'] = str(exc) if isinstance(exc, c.SandboxError) else 'Invalid published manager release/tag/commit evidence'
                cache.write(releases.target_key(), {'attempt': attempt}, durable=True)
                raise c.SandboxError(attempt['error']) from None
            cache.write(releases.target_key(), {'attempt': {**attempt, 'ok': True, 'error': ''}}, durable=True)
            return target
    except cache.Unavailable:
        raise c.SandboxError('Manager source resolution unavailable: safe source coordination is required') from None


def revalidate(target, installed, *, timeout=TIMEOUT):
    """Observe the *same* published source again; never substitute latest or trust a cached grant.

    This is not yet wired into handoff/exclusive execution. Callers must not infer installation
    consent, a persistent recovery record or replacement authority from a successful return.
    """
    if type(target) is not Target: raise c.SandboxError('An exact manager source target is required')
    fresh = resolve(target.tag, installed, timeout=timeout)
    if fresh != target: raise c.SandboxError('Published manager target changed; review and confirm the target again')
    return fresh
