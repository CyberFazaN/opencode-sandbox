"""Internal exact published-source evidence for UP-17, NOT installation consent or an updater.

No startup/discovery/UI consumer, cached target grant, pipx/Git execution or helper payload. The
official GitHub HTTPS API is the authority for publication and Git object identity, not signed
tag authentication. Revalidation observes the same target afresh; it does not lock a remote tag
or an installation. A future exclusive executor must independently bind/revalidate installation,
tools, consent and source and verify what was actually installed.
"""
import hashlib
import json
import math
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import core as c
from . import manager_releases as releases
from . import update_cache as cache

SOURCE_API = 'https://api.github.com/repos/CyberFazaN/opencode-sandbox'
ENDPOINT = SOURCE_API  # test transport may substitute loopback, never a product setting/argument
LIMIT = 131072
TIMEOUT = 8.0  # whole read-only graph, NOT a future installation/build deadline
MAX_TAGS = 4


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


def _oid(value):
    # GitHub's inspected Git database API uses SHA-1. Unknown formats fail closed, not truncated.
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('Invalid Git object identity')
    return value


def _object(value):
    if not isinstance(value, dict) or value.get('type') not in ('tag', 'commit'):
        raise ValueError('Unsupported Git reference type')
    oid, kind = _oid(value.get('sha')), value['type']
    if value.get('url') != SOURCE_API + '/git/' + kind + 's/' + oid:
        raise ValueError('Foreign Git object URL')
    return kind, oid


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


def _release(tag, deadline, attempt):
    item = _get('/releases/tags/' + tag, deadline, attempt)
    release = releases._release(item)
    rid = item.get('id')
    if release['tag'] != tag or type(rid) is not int or not 0 < rid < 2**63 \
            or item.get('url') != SOURCE_API + '/releases/' + str(rid):
        raise ValueError('Invalid exact published release identity')
    return release, rid, hashlib.sha256((item.get('body') or '').encode()).hexdigest()


def _ref(tag, deadline, attempt):
    item = _get('/git/ref/tags/' + tag, deadline, attempt)
    if item.get('ref') != 'refs/tags/' + tag or item.get('url') != SOURCE_API + '/git/refs/tags/' + tag:
        raise ValueError('Invalid exact Git tag reference')
    return _object(item.get('object'))


def _resolve(tag, deadline, attempt):
    publication = _release(tag, deadline, attempt)
    root = kind, oid = _ref(tag, deadline, attempt)
    objects = []
    while kind == 'tag':
        if oid in objects or len(objects) >= MAX_TAGS: raise ValueError('Cyclic or excessive annotated tags')
        item = _get('/git/tags/' + oid, deadline, attempt)
        if _oid(item.get('sha')) != oid or item.get('url') != SOURCE_API + '/git/tags/' + oid \
                or (not objects and item.get('tag') != tag):
            raise ValueError('Annotated tag identity disagrees')
        objects.append(oid)
        kind, oid = _object(item.get('object'))
    if oid in objects: raise ValueError('One Git object cannot be both annotated tag and commit')
    item = _get('/git/commits/' + oid, deadline, attempt)
    if _oid(item.get('sha')) != oid or item.get('url') != SOURCE_API + '/git/commits/' + oid:
        raise ValueError('Commit identity disagrees')
    objects.append(oid)
    # Bracket the graph with fresh publication/ref reads; never accept a mixed observed target.
    if _ref(tag, deadline, attempt) != root or _release(tag, deadline, attempt) != publication:
        raise c.SandboxError('Published manager source changed during resolution; review the target again')
    release, rid, notes_hash = publication
    return Target(tag, release['version'], rid, release['published_at'], release['notes'],
                  release['notes_truncated'], notes_hash, tuple(objects), time.time())


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
