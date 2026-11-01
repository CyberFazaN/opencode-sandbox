"""Read-only official manager release discovery. Not an installation or target-consent API."""
import json
import math
import re
import secrets
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import core as c
from . import update_cache as cache

REPOSITORY = 'https://github.com/CyberFazaN/opencode-sandbox'
API = 'https://api.github.com/repos/CyberFazaN/opencode-sandbox/releases?per_page=100'
LIMIT = 4 * 1024 * 1024
TAG = re.compile(r'v((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))')
SOURCE = 'github-published-releases'


def version(tag):
    match = TAG.fullmatch(tag) if isinstance(tag, str) and len(tag) < 80 else None
    if not match: raise c.SandboxError('Expected a full release tag vX.Y.Z (no prerelease, prefix or command)')
    return match[1]


def _key(value):
    return tuple(int(x) for x in version('v' + value).split('.'))


def comparison(installed, release):
    if not release: return 'Release availability unknown'
    try: order = (_key(installed) > _key(release['version'])) - (_key(installed) < _key(release['version']))
    except c.SandboxError: return 'Installed version is not a full stable version; manual comparison required'
    if order < 0: return f"Update available: {installed} -> {release['version']}"
    if order > 0: return f"Installed {installed} is newer than published {release['version']}; no downgrade offered"
    return 'Up to date with the discovered published release'


def _release(item):
    if not isinstance(item, dict) or item.get('draft') is not False or item.get('prerelease') is not False:
        raise ValueError('not a full release')
    tag = item.get('tag_name')
    value = version(tag)
    published = item.get('published_at')
    if not isinstance(published, str) or not published.endswith('Z') or len(published) > 40:
        raise ValueError('not published')
    if not 0 < datetime.fromisoformat(published).timestamp() <= time.time():
        raise ValueError('invalid publication date')
    url = REPOSITORY + '/releases/tag/' + tag
    if item.get('html_url') != url: raise ValueError('foreign release URL')
    body = item.get('body')
    if body is None: body = ''
    if not isinstance(body, str): raise TypeError('invalid release notes')
    return {'version': value, 'tag': tag, 'url': url, 'published_at': published,
            'notes': c.printable(body[:8192]), 'notes_truncated': len(body) > 8192}


def select(items):
    if not isinstance(items, list): raise c.SandboxError('Invalid GitHub releases response: expected a list')
    # Never call a truncated recent page the complete latest-version inventory. No unbounded
    # pagination/retry loop; a growing repository can add bounded pagination deliberately later.
    if len(items) >= 100: raise c.SandboxError('GitHub release listing reached its page limit; review releases manually')
    releases = {}
    for item in items:
        try: release = _release(item)
        except (c.SandboxError, ValueError, TypeError, OverflowError): continue
        if release['version'] in releases: raise c.SandboxError('Ambiguous duplicate GitHub release tag')
        releases[release['version']] = release
    if not releases: raise c.SandboxError('No valid published full manager release found')
    return releases[max(releases, key=_key)]


def cache_key():
    return 'manager:' + API


def target_key():
    return 'manager-target:' + API


def discovery():
    data = cache.read(cache_key())
    success = cache.observation(data, SOURCE, {'url': API})
    if success:
        try:
            release = data['release']
            verified = _release({'tag_name': release['tag'], 'html_url': release['url'],
                                 'published_at': release['published_at'], 'body': release['notes'],
                                 'draft': False, 'prerelease': False})
            if verified['version'] != success['value'] or release['version'] != success['value']: success = None
            release = {**verified, 'notes_truncated': release.get('notes_truncated') is True}
        except (KeyError, TypeError, ValueError, c.SandboxError, OverflowError): success = None
    attempt = cache.attempt(data)
    return {'success': success, 'release': release if success else None, 'attempt': attempt,
            'stale': success is None or time.time() - success['at'] >= 86400 or bool(attempt and not attempt['ok'])}


def _attempt(key=None):
    # Future claims after clock rollback still throttle; they are not fresh success evidence.
    item = cache.read(cache_key() if key is None else key).get('attempt')
    if not isinstance(item, dict) or type(item.get('at')) not in (int, float) or not math.isfinite(item['at']) \
            or not 0 < item['at'] <= 253402300799 or type(item.get('ok')) is not bool \
            or (not item['ok'] and not isinstance(item.get('error'), str)): return None
    return item


def _rate_gate():
    # Exact-target requests share GitHub's rate limit, not latest-release success/cache claims.
    for item in (_attempt(), _attempt(target_key())):
        retry = (item or {}).get('retry_until')
        if type(retry) in (int, float) and time.time() < retry <= 253402300799:
            raise c.SandboxError('Cannot check manager releases: rate limited; retry after ' + cache.when(retry))


def _rate_until(error):
    if error.get('status') not in (403, 429, 503): return None
    until = _retry_until(error.get('retry_after', ''))
    reset = error.get('rate_reset', '')
    if not until and isinstance(reset, str) and reset.isdigit() and len(reset) < 14:
        value = int(reset)
        if time.time() < value <= 253402300799: until = value
    return until


def _result(attempt):
    state = discovery()
    if attempt and attempt['ok'] and state['release']: return state['release']
    raise c.SandboxError('Cannot check manager releases: ' + (attempt or {}).get('error', 'check did not complete'))


def latest(timeout=8, *, automatic=False):
    previous = _attempt()
    try:
        with cache.source_lock(cache_key()) as waited:
            attempt = _attempt()
            if (waited and attempt and attempt.get('error') == 'check did not complete') or (attempt and attempt != previous):
                return _result(attempt)
            _rate_gate()
            if automatic and attempt and time.time() < attempt['at'] + 86400: return _result(attempt)
            return _request(timeout, automatic=automatic)
    except cache.Unavailable:
        if automatic: raise c.SandboxError('Automatic manager discovery unavailable: cannot persist safe attempt claims') from None
        return _request(timeout)


def _retry_until(value):
    try:
        if not isinstance(value, str): return None
        delay = int(value) if value.isdigit() else parsedate_to_datetime(value).timestamp() - time.time()
        until = time.time() + max(delay, 0)
        return until if until <= 253402300799 else None
    except (ValueError, TypeError, OverflowError): return None


def _request(timeout, *, automatic=False):
    old = discovery()
    _rate_gate()
    attempt = {'at': time.time(), 'ok': False, 'id': secrets.token_hex(16), 'error': 'check did not complete'}
    saved = {'success': old['success'], 'release': old['release'], 'attempt': attempt}
    if not cache.write(cache_key(), saved, durable=True) and automatic:
        raise c.SandboxError('Automatic manager discovery unavailable: cannot persist attempt claim')
    try:
        p = c.call([sys.executable, '-I', '-B', str(Path(__file__).with_name('http_probe.py')), API,
                    str(timeout), str(LIMIT), 'github'], capture=True, check=False, timeout=timeout, max_output=LIMIT + 1024)
        if p.returncode:
            try: error = json.loads(p.stderr)
            except ValueError: error = {}
            if isinstance(error, dict) and type(error.get('status')) is int:
                attempt['retry_until'] = _rate_until(error)
                raise c.SandboxError(f"HTTP {error['status']}")
            # Do not echo arbitrary proxy/URL diagnostics (which can contain credentials).
            raise c.SandboxError('GitHub request failed; check network/TLS/proxy configuration')
        release = select(json.loads(p.stdout))
    except (c.SandboxError, OSError, ValueError, TypeError, RecursionError) as exc:
        attempt['error'] = c.error_text(exc)[:1000]
        cache.write(cache_key(), saved, durable=True)
        raise c.SandboxError('Cannot check manager releases: ' + attempt['error']) from exc
    cache.write(cache_key(), {'success': cache.evidence(release['version'], SOURCE, {'url': API}),
                             'release': release, 'attempt': {**attempt, 'ok': True, 'error': ''}}, durable=True)
    return release
