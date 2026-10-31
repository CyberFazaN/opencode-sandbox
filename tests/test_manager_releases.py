"""Manager releases are published GitHub releases, never OpenCode/npm or checkout tags."""
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import test_opencode_versions
from test_discovery_schedule import wait_for

from opencode_sandbox import core as c
from opencode_sandbox import manager_releases as r
from opencode_sandbox import runtime_identity as rid
from opencode_sandbox import update_cache as cache

registry = test_opencode_versions.registry


@pytest.fixture
def github(registry, monkeypatch):
    from opencode_sandbox import opencode_versions as v
    monkeypatch.setattr(r, 'API', v.REGISTRY + '/manager')
    registry['body'] = json.dumps([release()]).encode()
    return registry


def test_only_full_official_published_release_tags_are_candidates():
    assert r.select([release('v6.2.0'), release('v99.0.0', prerelease=True),
                     release('v98.0.0', draft=True), release('v97.0.0', published_at=None)])['version'] == '6.2.0'


def release(tag='v6.2.0', **values):
    return {'tag_name': tag, 'draft': False, 'prerelease': False, 'published_at': '2026-10-30T12:00:00Z',
            'html_url': r.REPOSITORY + '/releases/tag/' + str(tag), 'body': 'Release [notes]', **values}


@pytest.mark.parametrize('tag', ['6.2.0', 'v06.2.0', 'v6.2', 'v6.2.0-beta', 'v6.2.0+build', 'main', 'v6.2.0;echo x', 'v6.2.0\n', 123, None])
def test_strict_tag_validation(tag):
    with pytest.raises(c.SandboxError): r.version(tag)
    assert r.select([release(), release(tag)])['version'] == '6.2.0'


def test_numeric_latest_notes_as_data_and_no_downgrade():
    selected = r.select([release('v6.9.0'), release('v6.10.0', body='\x1b[31m[literal]\n$(execute)')])
    assert selected['version'] == '6.10.0' and '\x1b' not in selected['notes'] and '$(execute)' in selected['notes']
    assert r.comparison('6.11.0', selected).endswith('no downgrade offered')
    assert r.comparison('6.10.0', selected).startswith('Up to date')
    assert r.comparison('6.9.0', selected).startswith('Update available')


@pytest.mark.parametrize('items', [None, {}, [], [release(published_at=None)], [release(html_url='https://foreign.invalid')],
                                    [release(published_at='2999-01-01T00:00:00Z')], [release(), release()], [release()] * 100])
def test_invalid_unpublished_foreign_duplicate_or_truncated_inventory_refuses(items):
    with pytest.raises(c.SandboxError): r.select(items)


def test_actual_http_headers_no_auth_and_independent_manager_cache(github, monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'dummy-never-send')
    assert r.latest()['tag'] == 'v6.2.0'
    assert github['requests'][0][1] == 'application/vnd.github+json'
    assert not any(key.lower() == 'authorization' for key in github['request_headers'][0])
    state = r.discovery()
    assert state['success']['source'] == r.SOURCE and state['release']['notes'] == 'Release [notes]'
    from opencode_sandbox import opencode_versions as v
    assert v.discovery()['success'] is None


@pytest.mark.parametrize('failed', [False, True])
def test_daily_attempt_throttles_success_and_failure_but_manual_can_refresh(github, failed):
    github['status'] = 500 if failed else 200
    for _ in range(3):
        if failed:
            with pytest.raises(c.SandboxError, match='HTTP 500'): r.latest(automatic=True)
        else: assert r.latest(automatic=True)['version'] == '6.2.0'
    assert len(github['requests']) == 1
    github['status'] = 200
    assert r.latest()['version'] == '6.2.0' and len(github['requests']) == 2


@pytest.mark.parametrize('status', [403, 429, 503])
@pytest.mark.parametrize('header', ['Retry-After', 'X-RateLimit-Reset'])
def test_rate_limit_blocks_both_callers_and_keeps_installed_cached_evidence(github, status, header):
    r.latest()
    old = r.discovery()['success']
    github.update(status=status, headers={header: '120' if header == 'Retry-After' else str(int(time.time()) + 120)})
    with pytest.raises(c.SandboxError, match=f'HTTP {status}'): r.latest()
    for automatic in (False, True):
        with pytest.raises(c.SandboxError, match='rate limited'): r.latest(automatic=automatic)
    assert len(github['requests']) == 2 and r.discovery()['success'] == old and r.discovery()['stale']


@pytest.mark.parametrize('failed', [False, True])
def test_threads_share_actual_overlapping_attempt(github, failed):
    github.update(status=500 if failed else 200, delay=.3)
    with ThreadPoolExecutor(max_workers=3) as pool:
        owner = pool.submit(r.latest)
        wait_for(lambda: github['requests'])
        waiters = [pool.submit(r.latest, automatic=flag) for flag in (False, True)]
        for pending in [owner, *waiters]:
            if failed:
                with pytest.raises(c.SandboxError, match='HTTP 500'): pending.result()
            else: assert pending.result()['version'] == '6.2.0'
    assert len(github['requests']) == 1


def test_process_restart_keeps_failed_claim_and_explicit_cache_only_contention_still_checks(github):
    r.latest()
    code = ("from pathlib import Path\nfrom opencode_sandbox import core as c, manager_releases as r\n"
            f"c.BASE=Path({str(c.BASE)!r})\nr.API={r.API!r}\nprint(r.latest(automatic=True)['version'])\n")
    p = subprocess.run([sys.executable, '-B', '-c', code], check=False, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src')), timeout=5)
    assert p.returncode == 0 and p.stdout.strip() == '6.2.0' and len(github['requests']) == 1
    with ThreadPoolExecutor(max_workers=1) as pool:
        with cache.source_lock(r.cache_key()):
            future = pool.submit(r.latest)
            time.sleep(.1)
        assert future.result()['version'] == '6.2.0'
    assert len(github['requests']) == 2


def test_cancellation_leaves_durable_attempt_before_request_and_never_retries_automatically(github, monkeypatch):
    def canceled(*a, **kw):
        assert r.discovery()['attempt']['error'] == 'check did not complete'
        raise rid.Cancelled()
    monkeypatch.setattr(c, 'call', canceled)
    with pytest.raises(rid.Cancelled): r.latest()
    with pytest.raises(c.SandboxError, match='check did not complete'): r.latest(automatic=True)
    assert not github['requests']


@pytest.mark.parametrize('kind', ['directory', 'write'])
def test_unsafe_storage_fails_closed_only_for_automatic(github, monkeypatch, kind):
    cache.write(r.cache_key(), {})
    if kind == 'directory': (c.BASE / cache.DIRECTORY).chmod(0o755)
    else: monkeypatch.setattr(cache, 'write', lambda *a, **k: False)
    with pytest.raises(c.SandboxError, match='Automatic manager discovery unavailable'): r.latest(automatic=True)
    assert not github['requests']
    assert r.latest()['version'] == '6.2.0'


def test_actual_http_child_is_bounded_cancelable_and_previous_success_survives(github):
    r.latest()
    old = r.discovery()['success']
    github['delay'] = 1
    with pytest.raises(c.SandboxError, match='timed out'): r.latest(timeout=.2)
    assert r.discovery()['success'] == old and not r.discovery()['attempt']['ok']
    assert r.discovery()['stale']


def test_cancelled_waiter_does_not_cancel_owner(github):
    github['delay'] = .3
    canceled = threading.Event()
    def waiter():
        with c.runtime_feedback(cancelled=canceled.is_set): return r.latest()
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(r.latest)
        wait_for(lambda: github['requests'])
        pending = pool.submit(waiter)
        canceled.set()
        with pytest.raises(rid.Cancelled): pending.result()
        assert owner.result()['version'] == '6.2.0'
    assert len(github['requests']) == 1


def test_redirect_is_refused_without_following_to_another_source(github):
    github.update(status=302, headers={'Location': r.API + '/redirected'})
    with pytest.raises(c.SandboxError, match='HTTP 302'): r.latest()
    assert len(github['requests']) == 1 and r.discovery()['success'] is None


def test_response_size_is_bounded_and_oversized_body_never_becomes_evidence(github, monkeypatch):
    monkeypatch.setattr(r, 'LIMIT', 128)
    github['body'] = b'[' + b' ' * 300 + b']'
    with pytest.raises(c.SandboxError, match='GitHub request failed'): r.latest()
    assert r.discovery()['release'] is None


def test_retry_after_is_still_enforced_when_source_lock_becomes_unavailable(github):
    github.update(status=429, headers={'Retry-After': '120'})
    with pytest.raises(c.SandboxError, match='HTTP 429'): r.latest()
    lock = c.BASE / cache.DIRECTORY / (cache._name(r.cache_key()) + '.lock')
    lock.chmod(0o644)
    with pytest.raises(c.SandboxError, match='rate limited'): r.latest()
    assert len(github['requests']) == 1


@pytest.mark.parametrize('elapsed,requests', [(86399, 1), (86401, 2), (-86400, 1)])
def test_clock_changes_preserve_attempt_based_daily_contract(github, elapsed, requests):
    r.latest()
    data = cache.read(r.cache_key())
    data['attempt']['at'] = time.time() - elapsed
    cache.write(r.cache_key(), data)
    r.latest(automatic=True)
    assert len(github['requests']) == requests
