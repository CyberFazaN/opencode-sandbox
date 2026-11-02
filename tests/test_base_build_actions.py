"""Base build consent and refresh are independent from inventory/discovery and environment state."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_opencode_versions import NEW, OLD, fake_docker
from typer.testing import CliRunner

from opencode_sandbox import cli, distros
from opencode_sandbox import core as c
from opencode_sandbox import opencode_versions as v


def test_base_build_plan_binds_current_image_and_explicit_refresh(monkeypatch):
    calls = []
    monkeypatch.setattr(c, 'ensure_runtime', lambda *a: None)
    monkeypatch.setattr(c, 'docker', fake_docker(calls))
    plan = v.prepare_base_build('2.1.4', 'debian', refresh=True)
    assert plan.target == '2.1.4' and plan.refresh and plan.current_id
    assert not any(a[0] in ('build', 'run', 'tag') for a in calls)


@pytest.fixture
def runtime(monkeypatch):
    calls = []
    monkeypatch.setattr(c, 'ensure_runtime', lambda *a: None)
    monkeypatch.setattr(c, 'require_docker_space', lambda _: None)
    monkeypatch.setattr(c, 'docker', fake_docker(calls))
    return calls


@pytest.mark.parametrize('distro', list(distros.REGISTRY))
@pytest.mark.parametrize('refresh', [False, True])
def test_both_modes_build_verify_and_preserve_copy_without_cache_pruning(runtime, monkeypatch, distro, refresh):
    monkeypatch.setattr(c, 'docker', fake_docker(runtime, os_release='ID=arch\nBUILD_ID=rolling' if distro == 'arch' else 'ID=debian\nVERSION_ID=13'))
    plan = v.prepare_base_build('2.1.4', distro, refresh=refresh)
    result = v.update_base(plan.target, distro, refresh=refresh, plan=plan)
    build = next(a for a in runtime if a[0] == 'build')
    assert ('--pull' in build) == refresh and ('--no-cache' in build) == refresh
    assert 'OPENCODE_VERSION=2.1.4' in build
    assert ('tag', OLD, result['previous_image']) in runtime
    assert not any('prune' in a for a in runtime)
    probe = next(a for a in runtime if a[0] == 'run')
    assert NEW in probe and not any('candidate' in value for value in probe)


@pytest.mark.parametrize('distro', list(distros.REGISTRY))
def test_explicit_package_upgrade_forces_fresh_package_layer_without_upstream_pull(runtime, monkeypatch, distro):
    monkeypatch.setattr(c, 'docker', fake_docker(runtime, os_release='ID=arch\nBUILD_ID=rolling' if distro == 'arch' else 'ID=debian\nVERSION_ID=13'))
    plan = v.prepare_base_build('2.1.4', distro, update_system=True)
    assert plan.update_system and not plan.refresh
    with pytest.raises(c.SandboxError, match='changed since confirmation'):
        v.update_base(plan.target, distro, plan=plan)  # the package choice is part of immutable consent
    assert not any(a[0] == 'build' for a in runtime)
    for _ in range(2): v.update_base(plan.target, distro, update_system=True)
    builds = [a for a in runtime if a[0] == 'build']
    assert len(builds) == 2
    assert all('UPGRADE_SYSTEM=1' in a and '--pull' not in a and '--no-cache' not in a for a in builds)
    nonces = [next(arg for arg in a if arg.startswith('SYSTEM_PACKAGE_REFRESH=')) for a in builds]
    assert nonces[0] != nonces[1] and all(not value.endswith('cached') for value in nonces)


@pytest.mark.parametrize('distro', list(distros.REGISTRY))
def test_refresh_includes_package_upgrades_in_plan_and_build(runtime, distro):
    plan = v.prepare_base_build('2.1.4', distro, refresh=True)
    assert plan.update_system and 'upgrade installed packages' in v.describe_base_build(plan)


@pytest.mark.parametrize('when,change', [(when, change) for when in ('before', 'during')
    for change in ('current', 'missing', 'owner', 'endpoint', 'mode', 'target', 'keep', 'definition', 'assets', 'namespace')
    if when == 'before' or change not in ('mode', 'target', 'keep')])
def test_changed_build_consent_refuses_before_build_or_publication(runtime, monkeypatch, when, change):
    plan = v.prepare_base_build('2.1.4', 'debian')
    real_docker = c.docker
    mutated = False
    def mutate():
        nonlocal mutated
        mutated = True
        if change == 'endpoint': monkeypatch.setattr(c, '_ENDPOINT', 'unix:///other.sock')
        if change == 'mode': return replace(plan, refresh=True)
        if change == 'target': return replace(plan, target='2.2.0')
        if change == 'keep': return replace(plan, keep_previous=False)
        if change == 'definition': monkeypatch.setitem(distros.REGISTRY, 'debian', replace(distros.get('debian'), revision=99))
        if change == 'assets': monkeypatch.setattr(v, '_build_assets', lambda: 'changed')
        if change == 'namespace': monkeypatch.setattr(distros, 'REPOSITORY', 'ocs-test-other')
        return plan
    def docker(*a, **kw):
        if a == ('image', 'inspect', 'opencode-sandbox:debian') and mutated:
            if change == 'missing': return SimpleNamespace(returncode=1, stdout='', stderr='No such image: base')
            info = json.loads(real_docker(*a, **kw).stdout)
            if change == 'current': info[0]['Id'] = NEW
            if change == 'owner': info[0]['Config']['Labels'] = {}
            return SimpleNamespace(returncode=0, stdout=json.dumps(info), stderr='')
        return real_docker(*a, **kw)
    monkeypatch.setattr(c, 'docker', docker)
    if when == 'before': plan = mutate()
    else:
        verify = c.verify_image
        def checked(*args):
            nonlocal plan
            verify(*args)
            plan = mutate()  # executor's original plan cannot follow later metadata changes
        monkeypatch.setattr(c, 'verify_image', checked)
    runtime.clear()
    with pytest.raises(c.SandboxError, match='changed|unmanaged|Cannot inspect'):
        v.update_base('2.1.4', 'debian', plan=plan)
    assert not any(a[0] == 'tag' for a in runtime)
    if when == 'before': assert not any(a[0] in ('build', 'run') for a in runtime)


def test_missing_base_becoming_present_after_consent_is_not_overwritten(runtime, monkeypatch):
    real = c.docker
    monkeypatch.setattr(c, 'docker', lambda *a, **k: SimpleNamespace(returncode=1, stdout='', stderr='No such image: base'))
    plan = v.prepare_base_build('2.1.4')
    assert plan.current_id is None
    monkeypatch.setattr(c, 'docker', real)
    with pytest.raises(c.SandboxError, match='changed since confirmation'): v.update_base(plan.target, plan=plan)
    assert not any(a[0] == 'build' for a in runtime)


def test_latest_resolves_only_before_consent_and_explicit_target_never_queries_registry(runtime, monkeypatch):
    monkeypatch.setattr(v, 'latest', lambda: '2.1.4')
    plan = v.prepare_base_build('latest')
    monkeypatch.setattr(v, 'latest', lambda: pytest.fail('moving target substitution'))
    assert v.update_base(plan.target, plan=plan)['version'] == '2.1.4'


def test_candidate_retag_after_verification_neither_publishes_nor_cleans_foreign_identity(runtime, monkeypatch):
    real, verified = c.docker, False
    def verify(*args):
        nonlocal verified
        assert args[1] == NEW
        verified = True
    def docker(*a, **k):
        result = real(*a, **k)
        if verified and a[:2] == ('image', 'inspect') and 'candidate' in a[-1]:
            info = json.loads(result.stdout)
            info[0]['Id'] = OLD
            result.stdout = json.dumps(info)
        return result
    monkeypatch.setattr(c, 'verify_image', verify)
    monkeypatch.setattr(c, 'docker', docker)
    with pytest.raises(c.SandboxError, match='cleanup identity unconfirmed'):
        v.update_base('2.1.4')
    assert not any(a[0] == 'tag' or a[:2] == ('image', 'rm') for a in runtime)


@pytest.mark.parametrize('refresh', [False, True])
@pytest.mark.parametrize('keep', [False, True])
def test_same_content_reports_verified_unchanged_without_swap_or_copy(runtime, monkeypatch, refresh, keep):
    monkeypatch.setattr(c, 'docker', fake_docker(runtime, same=True))
    result = v.update_base('2.1.4', refresh=refresh, keep_previous=keep)
    assert result['unchanged'] and result['previous_image'] is None
    assert not any(a[0] == 'tag' or a == ('image', 'rm', OLD) for a in runtime)
    assert any(a[0] == 'run' for a in runtime)


@pytest.mark.parametrize('refresh', [False, True])
@pytest.mark.parametrize('accept', [False, True])
def test_cli_update_base_confirms_exact_identity_target_and_mode(runtime, monkeypatch, refresh, accept):
    monkeypatch.setattr(v, 'latest', lambda: '2.1.4')
    def confirm(question, **kw):
        assert OLD in question and '2.1.4' in question and ('Refresh & Rebuild' if refresh else 'Cached rebuild') in question
        monkeypatch.setattr(v, 'latest', lambda: pytest.fail('must not resolve again'))
        return accept
    monkeypatch.setattr(cli, '_confirm', confirm)
    result = CliRunner().invoke(cli.app, ['opencode', 'update-base', *(['--refresh'] if refresh else [])])
    assert (result.exit_code == 0) == accept, result.output
    assert 'Existing containers and writable layers are unchanged' in result.output
    assert 'kept as a rollback copy' in result.output
    assert any(a[0] == 'build' for a in runtime) == accept


@pytest.mark.parametrize('refresh', [False, True])
def test_cli_build_discloses_no_copy_and_explicit_refresh(runtime, refresh):
    result = CliRunner().invoke(cli.app, ['build', '--opencode-version', '2.1.4', *(['--refresh'] if refresh else [])])
    assert result.exit_code == 0, result.output
    assert 'NO rollback copy' in result.output and 'opencode update-base' in result.output
    build = next(a for a in runtime if a[0] == 'build')
    assert ('--pull' in build) == refresh and ('--no-cache' in build) == refresh
    assert ('image', 'rm', OLD) in runtime


@pytest.mark.parametrize('refresh', [False, True])
def test_failed_binary_verification_preserves_base_and_cleans_only_owned_candidate(runtime, monkeypatch, refresh):
    monkeypatch.setattr(c, 'docker', fake_docker(runtime, installed='2.2.0'))
    with pytest.raises(c.SandboxError, match='expected 2.1.4'):
        v.update_base('2.1.4', refresh=refresh)
    assert not any(a[0] == 'tag' for a in runtime)
    removed = [a[-1] for a in runtime if a[:2] == ('image', 'rm')]
    assert len(removed) == 1 and 'candidate' in removed[0] and OLD not in removed


def test_newer_managed_definition_is_explicitly_disclosed_not_silently_assumed_current(runtime, monkeypatch):
    real = c.docker
    def docker(*a, **k):
        result = real(*a, **k)
        if a == ('image', 'inspect', 'opencode-sandbox:debian'):
            value = json.loads(result.stdout)
            value[0]['Config']['Labels']['org.opencode-sandbox.image-revision'] = '99'
            result.stdout = json.dumps(value)
        return result
    monkeypatch.setattr(c, 'docker', docker)
    plan = v.prepare_base_build('2.1.4')
    text = v.describe_base_build(plan)
    assert 'Current definition: debian 13, revision 99' in text
    assert f'Selected definition: Debian 13, revision {distros.get("debian").revision}' in text and OLD in text
    assert not any(a[0] == 'build' for a in runtime)
