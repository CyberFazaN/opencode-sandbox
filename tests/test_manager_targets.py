"""Exact published source identity is fresh read-only evidence, never installation consent."""
import copy
import dataclasses
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from manager_source_fixture import graph, serve
from test_discovery_schedule import wait_for

from opencode_sandbox import core as c
from opencode_sandbox import manager_releases as r
from opencode_sandbox import manager_targets as t
from opencode_sandbox import runtime_identity as rid
from opencode_sandbox import update_cache as cache


@pytest.fixture
def github(monkeypatch):
    with serve() as (endpoint, state):
        monkeypatch.setattr(t, 'ENDPOINT', endpoint)
        monkeypatch.setattr(r, 'API', endpoint + '/releases?per_page=100')
        yield state


@pytest.mark.parametrize('tags', [(), ('a' * 40,), ('a' * 40, 'b' * 40), tuple(str(n) * 40 for n in range(4))])
def test_exact_lightweight_and_bounded_nested_annotated_tags(github, tags):
    github['routes'] = graph(tags=tags)
    target = t.resolve('v6.2.0', '6.1.0')
    assert target.commit == 'c' * 40 and target.objects == (*tags, 'c' * 40)
    assert target.tag == 'v6.2.0' and target.version == '6.2.0' and target.release_id == 42
    assert target.source == r.REPOSITORY + '.git' and target.url == r.REPOSITORY + '/releases/tag/v6.2.0'
    assert target.notes == 'Release [notes]' and not target.notes_truncated
    assert not any('not-a-commit' in path for path, _ in github['requests'])
    assert len(github['requests']) == len(tags) + 5
    with pytest.raises(dataclasses.FrozenInstanceError): target.tag = 'v6.3.0'
    assert r.discovery()['success'] is None and r.discovery()['release'] is None
    saved = cache.read(r.target_key())
    assert saved['attempt']['ok'] and set(saved) == {'key', 'format', 'attempt'}


@pytest.mark.parametrize('tag,installed', [('v6.1.0', '6.1.0'), ('v6.0.9', '6.1.0'), ('main', '6.1.0'),
                                         ('v6.2.0;execute', '6.1.0'), ('v6.2.0', 'development'), ('v06.2.0', '6.1.0'),
                                         ('v6.2.0', None), ('v6.2.0', 123)])
def test_invalid_same_or_older_targets_refuse_before_network_or_claim(github, tag, installed):
    with pytest.raises(c.SandboxError): t.resolve(tag, installed)
    assert not github['requests'] and not c.BASE.exists()


@pytest.mark.parametrize('budget', [0, -1, 9, True, None, float('nan'), float('inf')])
def test_invalid_diagnostic_budgets_refuse_before_network(github, budget):
    with pytest.raises(c.SandboxError): t.resolve('v6.2.0', '6.1.0', timeout=budget)
    assert not github['requests']


@pytest.mark.parametrize('field,value', [('draft', True), ('prerelease', True), ('published_at', None),
    ('published_at', '2999-01-01T00:00:00Z'), ('tag_name', 'v6.3.0'), ('id', True), ('id', 0),
    ('id', 2**63), ('url', 'https://foreign.invalid/releases/42'), ('html_url', 'https://foreign.invalid'), ('body', {})])
def test_exact_release_requires_published_full_matching_official_identity(github, field, value):
    github['routes']['/releases/tags/v6.2.0'][field] = value
    with pytest.raises(c.SandboxError, match='Invalid published'): t.resolve('v6.2.0', '6.1.0')
    assert not cache.read(r.target_key())['attempt']['ok'] and r.discovery()['success'] is None


@pytest.mark.parametrize('part,field,value', [
    ('ref', 'ref', 'refs/heads/v6.2.0'), ('ref', 'url', 'https://foreign.invalid'),
    ('refobject', 'sha', 'deadbeef'), ('refobject', 'sha', 'A' * 40), ('refobject', 'sha', 'a' * 64),
    ('refobject', 'type', 'tree'), ('refobject', 'url', 'https://foreign.invalid/git/tags/' + 'a' * 40),
    ('tag', 'sha', 'b' * 40), ('tag', 'tag', 'v6.3.0'), ('tag', 'url', 'https://foreign.invalid'),
    ('tagobject', 'type', 'blob'), ('tagobject', 'sha', None), ('tagobject', 'url', 'https://foreign.invalid'),
    ('commit', 'sha', 'd' * 40), ('commit', 'url', 'https://foreign.invalid')])
def test_ref_annotated_tag_and_commit_must_agree_and_never_redirect_graph_urls(github, part, field, value):
    nodes = {'ref': github['routes']['/git/ref/tags/v6.2.0'], 'tag': github['routes']['/git/tags/' + 'a' * 40],
             'commit': github['routes']['/git/commits/' + 'c' * 40]}
    node = nodes['ref' if part == 'refobject' else 'tag' if part == 'tagobject' else part]
    if part.endswith('object'): node = node['object']
    node[field] = value
    with pytest.raises(c.SandboxError, match='Invalid published'): t.resolve('v6.2.0', '6.1.0')
    assert all(not path.startswith('http') for path, _ in github['requests'])


@pytest.mark.parametrize('cycle', [False, True])
def test_cycles_and_excessive_nested_tags_fail_with_bounded_requests(github, cycle):
    github['routes'] = graph(tags=tuple(str(n) * 40 for n in range(5)))
    if cycle:
        item = github['routes']['/git/tags/' + '0' * 40]
        item['object'] = copy.deepcopy(github['routes']['/git/ref/tags/v6.2.0']['object'])
    with pytest.raises(c.SandboxError, match='Invalid published'): t.resolve('v6.2.0', '6.1.0')
    assert len(github['requests']) == (3 if cycle else 6)


def test_one_oid_cannot_claim_both_tag_and_commit_types(github):
    github['routes'] = graph(tags=('c' * 40,))
    with pytest.raises(c.SandboxError, match='Invalid published'): t.resolve('v6.2.0', '6.1.0')
    assert len(github['requests']) == 3


@pytest.mark.parametrize('changed', ['ref', 'release', 'notes-tail'])
def test_graph_bracketing_rejects_source_change_during_resolution(github, changed):
    if changed == 'notes-tail': github['routes']['/releases/tags/v6.2.0']['body'] = 'x' * 9000
    def before(path, state):
        if len(state['requests']) == 5:
            if changed == 'ref':
                state['routes']['/git/ref/tags/v6.2.0']['object'] = graph(tags=())['/git/ref/tags/v6.2.0']['object']
            else: state['routes']['/releases/tags/v6.2.0']['body'] += 'changed'
    github['before'] = before
    with pytest.raises(c.SandboxError, match='changed during resolution'): t.resolve('v6.2.0', '6.1.0')


def test_revalidation_is_fresh_and_same_target_not_latest_even_after_cache_corruption(github):
    target = t.resolve('v6.2.0', '6.1.0')
    count = len(github['requests'])
    cache.write(r.cache_key(), {'release': {'tag': 'v99.0.0'}, 'success': {'value': '99.0.0'}})
    cache.write(r.target_key(), {'target': {'tag': 'v99.0.0'}, 'attempt': {'ok': True}})
    newer = graph(tag='v6.3.0', tags=('e' * 40,))
    github['routes'].update(newer)
    fresh = t.revalidate(target, '6.1.0')
    assert fresh == target and fresh.at >= target.at and len(github['requests']) == count * 2
    assert all('v6.3.0' not in path for path, _ in github['requests'])


@pytest.mark.parametrize('changed', ['commit', 'tag-object', 'release-id', 'notes', 'publication', 'unpublished'])
def test_fresh_revalidation_refuses_changed_target_instead_of_substituting(github, changed):
    target = t.resolve('v6.2.0', '6.1.0')
    if changed in ('commit', 'tag-object'):
        github['routes'] = graph(commit='d' * 40 if changed == 'commit' else 'c' * 40,
                                 tags=('b' * 40,) if changed == 'tag-object' else ('a' * 40,))
    else:
        release = github['routes']['/releases/tags/v6.2.0']
        if changed == 'release-id': release.update(id=43, url=t.SOURCE_API + '/releases/43')
        if changed == 'notes': release['body'] += 'changed'
        if changed == 'publication': release['published_at'] = '2026-10-29T12:00:00Z'
        if changed == 'unpublished': release['draft'] = True
    with pytest.raises(c.SandboxError): t.revalidate(target, '6.1.0')
    assert target.commit == 'c' * 40 and target.release_id == 42


@pytest.mark.parametrize('candidate', [None, {}, 'v6.2.0'])
def test_revalidation_never_accepts_a_plain_cache_record_as_a_target(github, candidate):
    with pytest.raises(c.SandboxError, match='exact manager source target'): t.revalidate(candidate, '6.1.0')
    assert not github['requests']


def test_network_is_bounded_no_redirect_or_auth_and_notes_remain_plain_data(github, monkeypatch):
    for name in ('GITHUB_TOKEN', 'GH_TOKEN', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'PYTHONPATH', 'SSL_CERT_FILE'):
        monkeypatch.setenv(name, 'dummy-secret-never-forwarded')
    github['routes']['/releases/tags/v6.2.0']['body'] = '\x1b[31m[literal] $(execute) ' + 'x' * 9000
    target = t.resolve('v6.2.0', '6.1.0')
    assert '\x1b' not in target.notes and '$(execute)' in target.notes and target.notes_truncated
    for _, headers in github['requests']:
        assert headers['Accept'] == 'application/vnd.github+json'
        assert not any(key.lower() in ('authorization', 'proxy-authorization', 'cookie') for key in headers)
    github.update(status=302, headers={'Location': t.ENDPOINT + '/redirected'})
    before = len(github['requests'])
    with pytest.raises(c.SandboxError, match='HTTP 302'): t.resolve('v6.2.0', '6.1.0')
    assert len(github['requests']) == before + 1


@pytest.mark.parametrize('body', [b'not json dummy-secret', b'[]', b'"dummy-secret"', b'{"body":"dummy-secret"}',
                                  b'{"id":42,"id":43}', b'{"id":NaN}', b' ' * (t.LIMIT + 1)])
def test_invalid_or_oversized_http_evidence_is_not_cached_or_echoed(github, body):
    github['routes']['/releases/tags/v6.2.0'] = body
    with pytest.raises(c.SandboxError) as caught: t.resolve('v6.2.0', '6.1.0')
    assert 'dummy-secret' not in str(caught.value) and 'dummy-secret' not in json.dumps(cache.read(r.target_key()))


def test_total_graph_budget_not_per_request_and_all_children_are_reaped(github):
    github['delay'] = .09
    start = time.monotonic()
    with pytest.raises(c.SandboxError): t.resolve('v6.2.0', '6.1.0', timeout=.4)
    assert time.monotonic() - start < 1.5 and len(github['requests']) < 6
    assert cache.read(r.target_key())['attempt']['ok'] is False


def test_actual_inflight_http_cancellation_keeps_attempt_and_no_target_grant(github):
    github['delay'] = .3
    cancel = threading.Event()
    def resolve():
        with c.runtime_feedback(cancelled=cancel.is_set): return t.resolve('v6.2.0', '6.1.0')
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(resolve)
        wait_for(lambda: github['requests'])
        cancel.set()
        with pytest.raises(rid.Cancelled): pending.result(timeout=2)
    assert cache.read(r.target_key())['attempt']['error'] == 'check did not complete'
    assert len(github['requests']) == 1 and r.discovery()['success'] is None


def test_network_failure_after_success_never_falls_back_to_the_old_target(github):
    target = t.resolve('v6.2.0', '6.1.0')
    github['status'] = 404
    with pytest.raises(c.SandboxError, match='HTTP 404'): t.revalidate(target, '6.1.0')
    assert cache.read(r.target_key())['attempt']['ok'] is False
    assert 'target' not in cache.read(r.target_key())


def test_source_observation_executes_only_fixed_http_children_and_no_install_or_docker_work(github, monkeypatch):
    from opencode_sandbox import manager_handoff, manager_tools
    def forbidden(*args, **kwargs): pytest.fail('Source inspection crossed into install/Docker/handoff')
    monkeypatch.setattr(c, 'docker', forbidden)
    monkeypatch.setattr(manager_handoff, 'prepare', forbidden)
    monkeypatch.setattr(manager_tools, 'assess', forbidden)
    actual, calls = c.call, []
    def observed(argv, **kwargs):
        calls.append(argv)
        assert argv[:4] == [sys.executable, '-I', '-B', '-S']
        assert Path(argv[4]).name == 'http_probe.py' and argv[-1] == 'github'
        assert kwargs['env'] == {'PATH': os.defpath, 'LANG': 'C.UTF-8'}
        return actual(argv, **kwargs)
    monkeypatch.setattr(c, 'call', observed)
    assert t.resolve('v6.2.0', '6.1.0').version == '6.2.0'
    assert len(calls) == 6 and not c.CONFIG.exists()


def test_source_and_discovery_requests_share_exclusion_but_not_success_claims(github):
    github['delay'] = .02
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(t.resolve, 'v6.2.0', '6.1.0')
        wait_for(lambda: github['requests'])
        discovery = pool.submit(r.latest)
        assert owner.result().version == discovery.result()['version'] == '6.2.0'
    assert len(github['requests']) == 7 and github['requests'][-1][0] == '/releases?per_page=100'
    assert r.discovery()['success'] is not None


@pytest.mark.parametrize('source', ['discovery', 'target'])
@pytest.mark.parametrize('status', [403, 429, 503])
@pytest.mark.parametrize('header', ['Retry-After', 'X-RateLimit-Reset'])
def test_source_rate_limit_blocks_both_paths_without_overwriting_discovery_success(github, source, status, header):
    r.latest()
    previous = r.discovery()['success']
    github.update(status=status, headers={header: '120' if header == 'Retry-After' else str(int(time.time()) + 120)})
    with pytest.raises(c.SandboxError, match=f'HTTP {status}'):
        if source == 'discovery': r.latest()
        else: t.resolve('v6.2.0', '6.1.0')
    before = len(github['requests'])
    for action in (lambda: r.latest(), lambda: r.latest(automatic=True), lambda: t.resolve('v6.2.0', '6.1.0')):
        with pytest.raises(c.SandboxError, match='rate limited'): action()
    assert len(github['requests']) == before and r.discovery()['success'] == previous


def test_failed_target_never_becomes_latest_success_or_erases_previous_discovery(github):
    r.latest()
    previous = cache.read(r.cache_key())
    github['status'] = 500
    with pytest.raises(c.SandboxError): t.resolve('v6.2.0', '6.1.0')
    assert cache.read(r.cache_key()) == previous
    github['status'] = 200
    t.resolve('v6.2.0', '6.1.0')
    assert cache.read(r.cache_key()) == previous


@pytest.mark.parametrize('fault', ['directory', 'write'])
def test_unsafe_or_unavailable_claim_storage_refuses_without_network_or_repairs(github, monkeypatch, fault):
    cache.write(r.cache_key(), {})
    directory = c.BASE / cache.DIRECTORY
    if fault == 'directory': directory.chmod(0o755)
    else: monkeypatch.setattr(cache, 'write', lambda *args, **kwargs: False)
    with pytest.raises(c.SandboxError, match='source resolution unavailable'): t.resolve('v6.2.0', '6.1.0')
    assert not github['requests']
    if fault == 'directory': assert directory.stat().st_mode & 0o777 == 0o755


def test_known_target_rate_limit_still_blocks_manual_discovery_when_source_lock_is_unsafe(github):
    github.update(status=429, headers={'Retry-After': '120'})
    with pytest.raises(c.SandboxError): t.resolve('v6.2.0', '6.1.0')
    lock = c.BASE / cache.DIRECTORY / (cache._name(r.cache_key()) + '.lock')
    lock.chmod(0o644)
    with pytest.raises(c.SandboxError, match='rate limited'): r.latest()
    assert len(github['requests']) == 1 and lock.stat().st_mode & 0o777 == 0o644


def test_source_lock_wait_consumes_the_budget_without_a_request_or_claim(github):
    with ThreadPoolExecutor(max_workers=1) as pool, cache.source_lock(r.cache_key()):
        pending = pool.submit(t.resolve, 'v6.2.0', '6.1.0', timeout=.12)
        with pytest.raises(c.SandboxError, match='source busy'): pending.result(timeout=2)
    assert not github['requests'] and not cache.read(r.target_key())


def test_cancellation_retains_attempt_before_first_request_without_target_or_consent(github, monkeypatch):
    def canceled(*args, **kwargs):
        assert cache.read(r.target_key())['attempt']['error'] == 'check did not complete'
        raise rid.Cancelled()
    monkeypatch.setattr(c, 'call', canceled)
    with pytest.raises(rid.Cancelled): t.resolve('v6.2.0', '6.1.0')
    assert not github['requests'] and cache.read(r.target_key())['attempt']['ok'] is False


def test_unexpected_launch_diagnostics_never_echo_paths_or_secrets(github, monkeypatch):
    def broken(*args, **kwargs): raise c.SandboxError('Cannot execute dummy-secret-private-path')
    monkeypatch.setattr(c, 'call', broken)
    with pytest.raises(c.SandboxError) as caught: t.resolve('v6.2.0', '6.1.0')
    assert 'dummy-secret' not in str(caught.value) and 'dummy-secret' not in json.dumps(cache.read(r.target_key()))


def test_overlapping_exact_requests_are_serialized_but_never_reuse_another_callers_target(github):
    github['delay'] = .02
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(t.resolve, 'v6.2.0', '6.1.0')
        wait_for(lambda: github['requests'])
        waiter = pool.submit(t.resolve, 'v6.2.0', '6.1.0')
        assert owner.result() == waiter.result()
    assert len(github['requests']) == 12
    assert [path for path, _ in github['requests']][:6] == [path for path, _ in github['requests']][6:]


def test_cancelled_waiter_does_not_cancel_the_target_owner(github):
    github['delay'] = .03
    cancel = threading.Event()
    def waiter():
        with c.runtime_feedback(cancelled=cancel.is_set): return t.resolve('v6.2.0', '6.1.0')
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(t.resolve, 'v6.2.0', '6.1.0')
        wait_for(lambda: github['requests'])
        pending = pool.submit(waiter)
        cancel.set()
        with pytest.raises(rid.Cancelled): pending.result()
        assert owner.result().commit == 'c' * 40
    assert len(github['requests']) == 6


def test_process_restart_honors_target_rate_limit_without_a_cached_target_grant(github):
    github.update(status=429, headers={'Retry-After': '120'})
    with pytest.raises(c.SandboxError): t.resolve('v6.2.0', '6.1.0')
    code = ('from pathlib import Path\nfrom opencode_sandbox import core as c,manager_releases as r,manager_targets as t\n'
            f'c.BASE=Path({str(c.BASE)!r})\nr.API={r.API!r}\nt.ENDPOINT={t.ENDPOINT!r}\n'
            "try: t.resolve('v6.2.0','6.1.0')\nexcept c.SandboxError as exc: print(str(exc))\nelse: raise AssertionError('rate limit bypass')\n")
    result = subprocess.run([sys.executable, '-B', '-c', code], env=dict(os.environ, PYTHONPATH=str(Path(t.__file__).parents[1])),
                            text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0 and 'rate limited' in result.stdout and len(github['requests']) == 1
