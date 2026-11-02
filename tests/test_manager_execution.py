"""Independent subprocess/source/policy gates, not a pipx replacement or public authenticity proof.

System config filenames are fixture-owned; presence checks and effective Git/pip probes stay real.
"""
import dataclasses
import json
import os
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
from functools import partial
from pathlib import Path

import pytest
from manager_policy_fixture import system_paths
from manager_source_fixture import graph, serve
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_observations import spawn_origin
from test_manager_review import installation as local_installation
from test_manager_review import origin as review_origin
from test_manager_review import tools as local_tools

from opencode_sandbox import manager_execution as execution
from opencode_sandbox import manager_network as policy
from opencode_sandbox import manager_process as processes
from opencode_sandbox import manager_review, manager_tools
from opencode_sandbox import manager_targets as targets

EXTERNAL = sys.executable
SITE = sysconfig.get_path('purelib')
GIT = shutil.which('git')
installation = local_installation
origin = review_origin
tools = local_tools


@pytest.fixture
def setup(origin, tmp_path, monkeypatch):
    # Real shared Python/pip policy, synthetic pipx runtime. No install or network bootstrap.
    prefix = origin[0][3]
    shared = prefix.parent.parent / 'shared'
    subprocess.run([EXTERNAL, '-I', '-B', '-m', 'venv', '--without-pip', str(shared)], check=True, capture_output=True, timeout=10)
    site = next(shared.glob('lib/python*/site-packages'))
    (site / 'ocs_test_external_pip.pth').write_text(SITE + '\n')
    commands = Path(shutil.which('pipx')).parent
    (commands / 'git').symlink_to(GIT)
    system = system_paths(tmp_path / 'system-configs')
    monkeypatch.setattr(policy, 'configurations', partial(policy.configurations, system=system))
    monkeypatch.setattr(manager_review, 'SYSTEM_CONFIGS', system)
    cwd = tmp_path / 'independent-work'; cwd.mkdir(mode=0o700)
    return origin, cwd, system


def facts(setup):
    from opencode_sandbox import manager_installation
    local = manager_installation.classify()
    assert local['verified'], local
    result = manager_tools.assess(local)
    assert result['supported'], result
    context = {**os.environ, 'HOME': str(Path.home())}
    return local['evidence'], result['evidence'], context


def test_effective_public_policy_uses_actual_git_and_external_shared_pip(setup):
    evidence, tool, context = facts(setup)
    result = execution.installer_policy(Path(evidence['venv']), evidence, tool, context, setup[1], time.monotonic() + 8)
    assert result['pip']['ok'] and result['pip']['prefix'] == evidence['locations']['shared_libs']
    assert result['environment']['PIP_INDEX_URL'] == 'https://pypi.org/simple'
    assert result['environment']['PIP_CONFIG_FILE'] == os.devnull
    assert result['environment']['PIP_KEYRING_PROVIDER'] == 'disabled'
    assert result['environment']['PIPX_DEFAULT_PYTHON'] == evidence['source_python']
    assert result['environment']['GIT_CONFIG_VALUE_0'] == 'never'
    assert result['environment']['GIT_CONFIG_VALUE_1'] == 'always'
    assert result['git_identity'] and result['remote_identity']


@pytest.mark.parametrize('kind', ['system-config', 'shared-config', 'home-config', 'credential-link', 'missing-git', 'shared-through-target'])
def test_custom_or_dependent_effective_policy_fails_without_secret_disclosure_or_repair(setup, kind, tmp_path):
    evidence, tool, context = facts(setup)
    prefix = Path(evidence['venv'])
    path = None
    if kind == 'system-config':
        path = Path(setup[2][-1]); path.parent.mkdir(parents=True)
        path.write_text('dummy-secret-system-config'); path.chmod(0)
    if kind in ('shared-config', 'home-config', 'credential-link'):
        path = Path(evidence['locations']['shared_libs']) / 'pip.conf' if kind == 'shared-config' else Path.home() / ('.gitconfig' if kind == 'home-config' else '.netrc')
        if kind == 'credential-link': path.symlink_to(tmp_path / 'unreadable-dummy-secret')
        else: path.write_text('dummy-secret-never-display'); path.chmod(0)
    if kind == 'missing-git': (Path(shutil.which('pipx')).parent / 'git').unlink()
    if kind == 'shared-through-target':
        python = Path(tool['settings']['PIPX_SHARED_LIBS']) / 'bin/python'
        target = python.resolve(); python.unlink()
        alias = prefix / 'outside-python'; alias.symlink_to(target); python.symlink_to(alias)
    try:
        with pytest.raises((policy.Refused, execution.Refused, RuntimeError)) as caught:
            execution.installer_policy(prefix, evidence, tool, context, setup[1], time.monotonic() + 8)
        assert 'dummy-secret' not in str(caught.value)
        if path is not None: assert path.is_symlink() if kind == 'credential-link' else path.stat().st_mode & 0o777 == 0
    finally:
        if path is not None and not path.is_symlink(): path.chmod(0o600)


@pytest.mark.parametrize('fault', ['source-change', 'redirect', 'rate', 'invalid', 'slow'])
def test_independent_fixed_source_reader_refuses_changed_or_unavailable_target_without_cache_or_credentials(tmp_path, monkeypatch, fault):
    with serve() as (endpoint, state):
        monkeypatch.setattr(targets, 'ENDPOINT', endpoint)
        target = targets.resolve('v6.2.0', '6.1.0')
        monkeypatch.setattr(execution, 'SOURCE_API', endpoint)
        if fault == 'source-change': state['routes'] = graph(commit='d' * 40)
        if fault == 'redirect': state.update(status=302, headers={'Location': endpoint + '/redirected'})
        if fault == 'rate': state.update(status=429, headers={'Retry-After': '1000'})
        if fault == 'invalid': state['routes']['/releases/tags/v6.2.0'] = b'{"id":42,"id":43}'
        if fault == 'slow': state['delay'] = .3
        count = len(state['requests'])
        with pytest.raises((execution.Refused, processes.Refused, ValueError, RuntimeError)):
            execution.published(dataclasses.asdict(target), EXTERNAL, tmp_path, time.monotonic() + (.1 if fault == 'slow' else 5))
        assert len(state['requests']) > count and all(not any(key.lower() in ('authorization', 'cookie', 'proxy-authorization') for key in headers) for _, headers in state['requests'])
        if fault in ('redirect', 'rate'): assert len(state['requests']) == count + 1


def test_independent_source_fetch_matches_full_published_graph_not_just_version(tmp_path, monkeypatch):
    with serve() as (endpoint, state):
        monkeypatch.setattr(targets, 'ENDPOINT', endpoint)
        target = targets.resolve('v6.2.0', '6.1.0')
        monkeypatch.setattr(execution, 'SOURCE_API', endpoint)
        value = execution.published(dataclasses.asdict(target), EXTERNAL, tmp_path, time.monotonic() + 5)
        assert value['objects'] == list(target.objects) and value['release_id'] == target.release_id
        assert len(state['requests']) == 12


@pytest.mark.parametrize('fault', ['none', 'lazy-record', 'policy', 'published'])
def test_frozen_independent_validation_waits_for_actual_origin_death_and_rechecks_runtime_policy_source(setup, tmp_path, fault):
    origin, _, system = setup
    prefix = origin[0][3]
    helper = child = None
    with subreaper():
        try:
            child, value = spawn_origin(origin, tmp_path, execution=True, frozen_transport=targets.ENDPOINT, system_configs=system)
            helper = value['helper']; directory = Path(value['directory'])
            assert child.poll() is None and not (directory / 'result.json').exists()
            if fault == 'lazy-record':
                metadata = next(Path(shutil.which('pipx')).parent.parent.glob('external tools/pipx-*.dist-info'))
                with (metadata / 'RECORD').open('a') as stream: stream.write(str(prefix / 'lazy-installer-dependency.py') + ',,\n')
            if fault == 'policy':
                site = next((prefix.parent.parent / 'shared').glob('lib/python*/site-packages'))
                (site / 'ocs_test_policy.py').write_text('import os\nos.environ["PIP_INDEX_URL"]="https://dummy-secret.invalid/simple"\n')
                (site / 'ocs_test_policy.pth').write_text('import ocs_test_policy\n')
            if fault == 'published': origin[1]['routes'] = graph(commit='d' * 40)
            child.communicate(timeout=10)
            assert child.returncode == 0
            assert wait_helper(helper, timeout=20) == 0; helper = None
            result = result_at(directory)
            assert result['review']['ok'] is True  # these faults deliberately escape local replay
            assert result['execution']['ok'] is (fault == 'none'), result
            assert result['outcome'] == ('quiescent' if fault == 'none' else 'execution-failed')
            assert 'dummy-secret' not in json.dumps(result)
            assert not (prefix.parent.parent / '.opencode-sandbox-updates').exists()
        finally:
            if child is not None:
                if child.poll() is None: child.kill()
                child.communicate(timeout=5)
            if helper is not None:
                try: os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except (ProcessLookupError, ChildProcessError): pass


@pytest.mark.parametrize('fault', ['timeout', 'output'])
def test_bounded_independent_diagnostic_reaps_its_exact_group_before_pid_reuse(tmp_path, monkeypatch, fault):
    # Observe our actual leader/descendant, not pytest's unrelated HTTP-server thread lifetimes.
    marker = tmp_path / 'owned-descendant'
    code = ('import subprocess,sys,time\nfrom pathlib import Path\n'
            'child=subprocess.Popen([sys.executable,"-I","-B","-S","-c","import time;time.sleep(20)"])\n'
            f'Path({str(marker)!r}).write_text(str(child.pid))\n'
            + ('time.sleep(20)\n' if fault == 'timeout' else 'print("dummy-secret"*100000)\n'))
    actual, children = subprocess.Popen, []
    def observed(*args, **kwargs):
        process = actual(*args, **kwargs); children.append(process)
        return process
    monkeypatch.setattr(processes.subprocess, 'Popen', observed)
    with subreaper():
        try:
            with pytest.raises(processes.Refused):
                processes.run([EXTERNAL, '-I', '-B', '-S', '-c', code], environment={'PATH': os.defpath}, cwd=tmp_path,
                              deadline=time.monotonic() + (1 if fault == 'timeout' else 3), limit=1024)
            assert len(children) == 1 and children[0].returncode is not None
            assert marker.exists(), 'Owned diagnostic did not reach descendant rendezvous'
            assert wait_helper(int(marker.read_text()), timeout=3) == -signal.SIGKILL
            marker.unlink()  # a reaped PID is never a later signal target
        finally:
            if marker.exists():
                pid = int(marker.read_text())
                try:
                    if os.waitpid(pid, os.WNOHANG)[0] == 0: os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
                except ChildProcessError: pass


def test_ambient_credentials_and_configuration_are_never_forwarded_into_installer_policy(setup):
    evidence, tool, context = facts(setup)
    context.update(OPENROUTER_API_KEY='dummy-secret', GITHUB_TOKEN='dummy-secret', SSH_AUTH_SOCK='dummy-secret')
    result = execution.installer_policy(Path(evidence['venv']), evidence, tool, context, setup[1], time.monotonic() + 8)
    assert 'dummy-secret' not in json.dumps(result)


def test_private_helper_directory_does_not_inherit_an_ancestor_workspace_git_configuration(setup):
    evidence, tool, context = facts(setup)
    cwd = setup[1] / 'ancestor-project'
    cwd.mkdir()
    subprocess.run([GIT, '-C', str(cwd), 'init', '--quiet'], check=True, capture_output=True, env={'PATH': os.defpath})
    config = cwd / '.git/config'
    with config.open('a') as stream: stream.write('\n[http]\n\tproxy = https://dummy-secret.invalid\n')
    private = cwd / 'helper'; private.mkdir(mode=0o700)
    result = execution.installer_policy(Path(evidence['venv']), evidence, tool, context, private, time.monotonic() + 8)
    assert result['environment']['GIT_CEILING_DIRECTORIES'] == str(private.parent)
    assert 'dummy-secret' not in json.dumps(result)
    # Do not ignore a repository placed IN the operation directory itself.
    subprocess.run([GIT, '-C', str(private), 'init', '--quiet'], check=True, capture_output=True, env={'PATH': os.defpath})
    with pytest.raises(execution.Refused, match='Git configuration|Effective Git policy'):
        execution.installer_policy(Path(evidence['venv']), evidence, tool, context, private, time.monotonic() + 8)


def test_unsuppressed_client_keys_reveal_nonstandard_system_git_configuration_without_value_disclosure(setup):
    evidence, tool, context = facts(setup)
    command = Path(shutil.which('git'))
    command.unlink()
    command.write_text(f'#!{EXTERNAL}\nimport os,sys\n'
                       'if sys.argv[1:]==["config","--null","--list","--name-only"]:\n'
                       ' print("dummy-secret-scoped-config-key");raise SystemExit(0)\n'
                       f'os.execve({GIT!r},[{GIT!r},*sys.argv[1:]],dict(os.environ))\n')
    command.chmod(0o700)
    with pytest.raises(execution.Refused, match='manual preservation') as caught:
        execution.installer_policy(Path(evidence['venv']), evidence, tool, context, setup[1], time.monotonic() + 8)
    assert 'dummy-secret' not in str(caught.value)
