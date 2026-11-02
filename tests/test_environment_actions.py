"""Environment action consent is immutable and never derives authority from version caches."""
import hashlib
from contextlib import contextmanager

import pytest
from test_opencode_lifecycle import Crash, FakeDocker, env

from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v


@pytest.fixture
def runtime(monkeypatch):
    fake = FakeDocker(monkeypatch)
    fake.image_ids = {}
    def docker(*args, **kwargs):
        if args[:4] == ("image", "inspect", "--format", "{{.Id}}") and args[-1] in fake.images:
            fake.calls.append(args)
            return fake.ok(fake.image_ids.get(args[-1], "sha256:" + hashlib.sha256(args[-1].encode()).hexdigest()))
        return fake(*args, **kwargs)
    monkeypatch.setattr(c, "docker", docker)
    return fake


def test_rollback_has_an_exact_checkpoint_plan_before_consent(runtime):
    m = env()
    v.update_environment(m, '2.2.0')
    runtime.calls.clear()
    plan = v.prepare_checkpoint_action(c.resolve(m['id']), 'rollback')
    assert plan.action == 'rollback' and plan.checkpoint
    assert plan.checkpoint_id.startswith('sha256:') and plan.target == '2.1.4'
    assert not runtime.running
    assert not any(a[0] in ('commit', 'start', 'stop', 'exec', 'rm') for a in runtime.calls)


@pytest.mark.parametrize('action', ['rollback', 'recover'])
@pytest.mark.parametrize('change', ['checkpoint', 'container', 'image', 'running', 'metadata', 'pin', 'journal', 'endpoint', 'data', 'volume'])
def test_checkpoint_consent_is_revalidated_under_lock_before_any_mutation(runtime, monkeypatch, action, change):
    m = env()
    v.update_environment(m, '2.2.0')
    m = c.resolve(m['id'])
    if action == 'recover': c.mark(m, 'updating', operation=v.UPDATE_OP)
    plan = v.prepare_checkpoint_action(m, action)
    if change == 'checkpoint': runtime.image_ids[plan.checkpoint] = 'sha256:' + 'f' * 64
    if change == 'container': runtime.cid = 'c' * 64
    if change == 'image': runtime.iid = 'sha256:' + 'd' * 64
    if change == 'running': runtime.running = True
    if change == 'metadata': m['profile'] = 'other'; c.save(m)
    if change == 'pin': m['opencode_policy'] = 'pinned'; m['opencode_pin'] = '2.2.0'; c.save(m)
    if change == 'journal': c.mark(m, 'error', operation='runtime-recreate')
    if change == 'endpoint': monkeypatch.setattr(c, 'docker_endpoint', lambda: 'unix:///other.sock')
    if change == 'data': monkeypatch.setattr(c, 'data_id', lambda: 'other')
    if change == 'volume':
        def foreign(m): raise c.SandboxError('Volume ownership mismatch')
        monkeypatch.setattr(c, 'assert_volume_owned', foreign)
    runtime.calls.clear()
    with pytest.raises(c.SandboxError):
        (v.rollback_environment if action == 'rollback' else v.update_recover)(m, plan=plan)
    assert not any(a[0] in ('commit', 'start', 'stop', 'exec', 'rm', 'tag') for a in runtime.calls)


@pytest.mark.parametrize('action', ['rollback', 'recover'])
def test_checkpoint_execution_uses_confirmed_immutable_image_and_existing_journal(runtime, monkeypatch, action):
    m = env()
    v.update_environment(m, '2.2.0')
    m = c.resolve(m['id'])
    if action == 'recover': c.mark(m, 'updating', operation=v.UPDATE_OP)
    plan = v.prepare_checkpoint_action(m, action)
    runtime.images.add(plan.checkpoint_id)
    locked = []
    real_lock, recheck = c.lock, v._recheck_checkpoint_plan
    @contextmanager
    def lock(key, **kwargs):
        with real_lock(key, **kwargs):
            locked.append(key)
            try: yield
            finally: locked.pop()
    def checked(current, action, consent):
        assert locked == [m['id']]
        recheck(current, action, consent)
    monkeypatch.setattr(c, 'lock', lock)
    monkeypatch.setattr(v, '_recheck_checkpoint_plan', checked)
    result = (v.rollback_environment if action == 'rollback' else v.update_recover)(m, plan=plan)
    assert result['image'] == plan.checkpoint_id and not runtime.exists
    current = c.resolve(m['id'])
    assert current['operation'] is None and current['opencode_update']['checkpoint'] == plan.checkpoint


@pytest.mark.parametrize('action', ['rollback', 'recover'])
def test_missing_checkpoint_plan_is_read_only_and_explains_data_salvage(runtime, action):
    m = env()
    v.update_environment(m, '2.2.0')
    m = c.resolve(m['id'])
    if action == 'recover': c.mark(m, 'updating', operation=v.UPDATE_OP)
    runtime.images.discard(m['opencode_update']['checkpoint'])
    before = (c.env_dir(m['id']) / 'metadata.json').read_bytes()
    with pytest.raises(c.SandboxError, match='workspace.*not affected.*changes export'):
        v.prepare_checkpoint_action(m, action)
    assert (c.env_dir(m['id']) / 'metadata.json').read_bytes() == before


def test_failed_restore_keeps_persistent_runtime_journal_and_reason(runtime, monkeypatch):
    m = env()
    runtime.install = 'crash'
    with pytest.raises(Crash): v.update_environment(m, '2.2.0')
    docker = c.docker
    def fail_remove(*args, **kwargs):
        if args[0] == 'rm': raise c.SandboxError('test remove failed [literal]')
        return docker(*args, **kwargs)
    monkeypatch.setattr(c, 'docker', fail_remove)
    with pytest.raises(c.SandboxError, match='test remove failed'): v.update_recover(m)
    current = c.resolve(m['id'])
    assert current['operation'] == 'runtime-recreate'
    assert 'test remove failed [literal]' in current['last_error']
    assert 'config recover' in str(c.pending_operation(current))
    for op in (c.start, lambda m: v.set_policy(m, 'manual'), lambda m: v.update_environment(m, '2.2.0')):
        with pytest.raises(c.SandboxError, match='config recover'): op(current)


def test_failed_update_and_failed_rollback_name_actual_successor_recovery(runtime, monkeypatch):
    m = env()
    runtime.install = 'fail'
    docker = c.docker
    def fail_remove(*a, **k):
        if a[0] == 'rm': raise c.SandboxError('test remove failed')
        return docker(*a, **k)
    monkeypatch.setattr(c, 'docker', fail_remove)
    with pytest.raises(c.SandboxError, match='rollback failed.*config recover'):
        v.update_environment(m, '2.2.0')
    assert c.resolve(m['id'])['operation'] == 'runtime-recreate'


@pytest.mark.parametrize('operation', ['runtime-recreate', 'config-update'])
def test_configuration_recovery_precondition_runs_inside_handler_before_mutation(runtime, operation):
    from opencode_sandbox import config_plan
    m = env()
    m.update(operation=operation, image='ocs-runtime:' + m['id'] + '-test', last_snapshot='ocs-runtime:' + m['id'] + '-test',
             pending_config={'runtime': c.runtime_settings(m), 'restart': False, 'start': False})
    c.save(m)
    def refuse(current):
        assert current['id'] == m['id'] and current['operation'] == operation
        raise c.SandboxError('test stale consent refused')
    with pytest.raises(c.SandboxError, match='test stale consent refused'):
        config_plan.recover(m, precondition=refuse)
    assert not any(a[0] in ('rm', 'update', 'start', 'stop', 'exec') for a in runtime.calls)
    assert c.resolve(m['id'])['operation'] == operation


def test_missing_immutable_checkpoint_at_start_retains_salvage_guidance(runtime):
    image = 'sha256:' + 'f' * 64
    m = env(image=image, last_snapshot=image)
    runtime.exists = False
    with pytest.raises(c.SandboxError, match='workspace.*not affected.*changes export'):
        c.start(m)
    assert not runtime.running


@pytest.mark.parametrize('change', ['policy', 'metadata', 'data', 'journal'])
def test_policy_plan_requires_fresh_explicit_consent(runtime, monkeypatch, change):
    m = env()
    plan = v.prepare_environment_policy(m, 'pinned', '2.2.0')
    if change == 'policy': v.set_policy(m, 'manual')
    if change == 'metadata': m['profile'] = 'other'; c.save(m)
    if change == 'data': monkeypatch.setattr(c, 'data_id', lambda: 'other')
    if change == 'journal': c.mark(m, 'updating', operation=v.UPDATE_OP)
    with pytest.raises(c.SandboxError): v.set_policy(m, plan.mode, plan.version, plan=plan)
    assert c.resolve(m['id']).get('opencode_pin') is None
    assert not runtime.calls


@pytest.mark.parametrize('change', ['metadata', 'container', 'running', 'journal'])
def test_start_plan_refuses_changed_target_before_starting(runtime, change):
    m = env()
    plan = v.prepare_environment_start(m)
    if change == 'metadata': m['profile'] = 'other'; c.save(m)
    if change == 'container': runtime.cid = 'c' * 64
    if change == 'running': runtime.running = True
    if change == 'journal': c.mark(m, 'updating', operation=v.UPDATE_OP)
    runtime.calls.clear()
    with pytest.raises(c.SandboxError): c.start(m, precondition=lambda current: v.recheck_environment_start(current, plan))
    assert not any(a[0] in ('run', 'start', 'exec') for a in runtime.calls)
