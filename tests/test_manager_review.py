"""Manager review is exact non-mutating origin evidence, never an installation capability."""
import dataclasses
import json
import os
import sys
from pathlib import Path

import pytest
from manager_source_fixture import serve
from test_manager_installation import installation as local_installation
from test_manager_tools import tools as tools_fixture

from opencode_sandbox import core as c
from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_handoff as handoff
from opencode_sandbox import manager_releases as releases
from opencode_sandbox import manager_targets as targets


@pytest.fixture
def origin(request, tmp_path, monkeypatch):
    # Synthetic local distribution identity + actual synthetic external version-only subprocesses.
    # The opt-in installed campaign separately proves actual pipx/launcher/metadata behavior.
    request.getfixturevalue('tools')
    value = request.getfixturevalue('installation')
    from opencode_sandbox import manager_review as r
    home = tmp_path / 'review-home'; home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    for name in list(os.environ):
        if name.upper().startswith(('PIP_', 'GIT_', 'UV_', 'PYTHON', 'LD_', 'DYLD_')) or name.upper() in {
                'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE',
                'CURL_CA_BUNDLE', 'CURL_HOME', 'SSLKEYLOGFILE', 'NETRC', 'SSH_ASKPASS', 'SSH_ASKPASS_REQUIRE',
                'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'BASH_ENV', 'ENV'}:
            monkeypatch.delenv(name)
    monkeypatch.setattr(r, 'SYSTEM_CONFIGS', ())
    monkeypatch.setenv('XDG_CONFIG_DIRS', str(tmp_path / 'system-config'))
    prefix = value[3]
    dist = next(prefix.glob('lib/python*/site-packages/*.dist-info'))
    (prefix / 'pyvenv.cfg').write_text('home = ' + str(Path(sys._base_executable).parent) + '\n')
    (dist / 'METADATA').write_text('Name: opencode-sandbox\nVersion: 6.1.0\n')
    (dist / 'entry_points.txt').write_text('[console_scripts]\nopencode-sandbox = opencode_sandbox.launcher:main\n')
    (dist / 'RECORD').write_text('opencode_sandbox/__init__.py,,\n')
    with serve() as (endpoint, state):
        monkeypatch.setattr(targets, 'ENDPOINT', endpoint)
        monkeypatch.setattr(releases, 'API', endpoint + '/releases?per_page=100')
        yield value, state


@pytest.fixture
def prepared(origin):
    from opencode_sandbox import manager_review as r
    return r.prepare('v6.2.0')


# Register existing fixtures, but origin explicitly resolves the external tool before replacing
# the synthetic running interpreter identity. Never mistake this for actual installed-pipx proof.
installation = local_installation
tools = tools_fixture


def test_review_preparation_is_distinct_from_source_evidence_or_cached_classification():
    from opencode_sandbox import manager_review
    assert callable(manager_review.prepare) and callable(manager_review.revalidate)


def test_preparation_binds_fresh_installation_tools_source_routes_and_no_helper(prepared, origin, monkeypatch):
    from opencode_sandbox import manager_review as r
    _, state = origin
    monkeypatch.setattr(handoff, 'prepare', lambda *a, **k: pytest.fail('review staged a helper'))
    monkeypatch.setattr(c, 'docker', lambda *a, **k: pytest.fail('review contacted Docker'))
    assert prepared.target.commit == 'c' * 40 and prepared.target.tag == 'v6.2.0'
    assert prepared.version == '6.1.0' and prepared.prefix == locks.identity()
    binding = json.loads(prepared.binding)
    assert binding['network'] == r.NETWORK and binding['tools']['settings']['PIPX_HOME']
    assert binding['records'] and binding['routes'] and len(prepared.identity) == 64
    assert len(state['requests']) == 6
    assert r.revalidate(prepared) is prepared and len(state['requests']) == 12
    with pytest.raises(dataclasses.FrozenInstanceError): prepared.prefix = '/foreign'
    binding['network'] = 'changed-copy'
    assert json.loads(prepared.binding)['network'] == r.NETWORK


@pytest.mark.parametrize('name', ['PIP_INDEX_URL', 'PIP_CONFIG_FILE', 'PIP_EXTRA_INDEX_URL', 'PIP_TRUSTED_HOST',
    'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_COUNT', 'GIT_SSH_COMMAND', 'HTTPS_PROXY', 'http_proxy', 'ALL_PROXY', 'NO_PROXY',
    'REQUESTS_CA_BUNDLE', 'NETRC', 'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'UV_INDEX_URL', 'BASH_ENV',
    'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'SSLKEYLOGFILE', 'CURL_HOME'])
def test_custom_environment_refuses_before_tools_or_network_without_echoing_values(origin, monkeypatch, name):
    from opencode_sandbox import manager_review as r
    secret = 'dummy-secret-network-setting'
    monkeypatch.setenv(name, secret)
    with pytest.raises(c.SandboxError) as caught: r.prepare('v6.2.0')
    assert 'manual preservation' in str(caught.value) and secret not in str(caught.value)
    assert not origin[1]['requests'] and locks._LEASE is None


@pytest.mark.parametrize('kind', ['git', 'pip', 'netrc', 'credentials', 'xdg-git', 'xdg-pip', 'system', 'shared', 'venv', 'broken-link'])
def test_custom_configuration_presence_refuses_without_reading_or_modifying_contents(origin, monkeypatch, tmp_path, kind):
    from opencode_sandbox import manager_review as r
    prefix = origin[0][3]
    paths = {'git': Path.home() / '.gitconfig', 'pip': Path.home() / '.pip/pip.conf', 'netrc': Path.home() / '.netrc',
             'credentials': Path.home() / '.git-credentials',
             'xdg-git': Path.home() / '.config/git/config', 'xdg-pip': Path.home() / '.config/pip/pip.conf',
             'system': tmp_path / 'system.conf', 'shared': prefix.parent.parent / 'shared/pip.conf',
             'venv': prefix / 'pip.conf', 'broken-link': Path.home() / '.netrc'}
    path = paths[kind]; path.parent.mkdir(parents=True, exist_ok=True)
    if kind == 'system': monkeypatch.setattr(r, 'SYSTEM_CONFIGS', (str(path),))
    if kind == 'broken-link': path.symlink_to(tmp_path / 'absent-secret-target')
    else: path.write_text('dummy-secret-config-contents'); path.chmod(0)
    try:
        with pytest.raises(c.SandboxError) as caught: r.prepare('v6.2.0')
        assert 'manual preservation' in str(caught.value) and 'dummy-secret' not in str(caught.value)
        assert not origin[1]['requests']
    finally:
        if kind != 'broken-link': path.chmod(0o600)
    assert path.is_symlink() if kind == 'broken-link' else path.read_text() == 'dummy-secret-config-contents'


@pytest.mark.parametrize('change', ['pipx-record', 'direct-source', 'metadata', 'record', 'entrypoint', 'module', 'launcher-body',
                                  'python-route', 'launcher-route', 'path', 'xdg', 'network', 'config', 'tool-route'])
def test_changed_installation_tools_routes_settings_or_network_refuse_without_reusing_source(prepared, origin, monkeypatch, tmp_path, change):
    from opencode_sandbox import manager_review as r
    record, direct, save, prefix, launcher = origin[0]
    dist = next(prefix.glob('lib/python*/site-packages/*.dist-info'))
    if change == 'pipx-record': record['main_package']['pinned'] = True; save()
    if change == 'direct-source': direct['vcs_info']['commit_id'] = 'e' * 40; save()
    if change == 'metadata': (dist / 'METADATA').write_text((dist / 'METADATA').read_text() + 'Summary: changed\n')
    if change == 'record': (dist / 'RECORD').write_text((dist / 'RECORD').read_text() + 'additional,,\n')
    if change == 'entrypoint': (dist / 'entry_points.txt').write_text((dist / 'entry_points.txt').read_text() + '# changed\n')
    if change == 'module': (dist.parent / 'opencode_sandbox/__init__.py').write_text('__version__="6.1.0"\n# changed\n')
    if change == 'launcher-body': launcher.resolve().write_text(launcher.resolve().read_text() + '# changed\n')
    if change == 'python-route':
        python = prefix / 'bin/python'; endpoint = python.resolve(); python.unlink()
        alias = tmp_path / 'new-python-alias'; alias.symlink_to(endpoint); python.symlink_to(alias)
    if change == 'launcher-route':
        app = launcher.resolve(); launcher.unlink(); alias = tmp_path / 'new-launcher-alias'; alias.symlink_to(app); launcher.symlink_to(alias)
    if change == 'path': monkeypatch.setenv('PATH', os.environ['PATH'] + ':' + str(tmp_path / 'new-unused-path'))
    if change == 'xdg': monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'new-config-location'))
    if change == 'network': monkeypatch.setenv('PIP_INDEX_URL', 'dummy-secret-index')
    if change == 'config': (Path.home() / '.netrc').write_text('dummy-secret-credentials')
    if change == 'tool-route':
        command = Path(json.loads(prepared.binding)['tools']['pipx']); endpoint = command.resolve(); command.unlink()
        alias = tmp_path / 'new-tool-alias'; alias.symlink_to(endpoint); command.symlink_to(alias)
    count = len(origin[1]['requests'])
    with pytest.raises(c.SandboxError) as caught: r.revalidate(prepared)
    assert 'dummy-secret' not in str(caught.value) and len(origin[1]['requests']) == count


def test_source_movement_during_same_origin_revalidation_does_not_change_the_review(prepared, origin):
    from manager_source_fixture import graph

    from opencode_sandbox import manager_review as r
    origin[1]['routes'] = graph(commit='d' * 40, tags=('b' * 40,))
    with pytest.raises(c.SandboxError, match='target changed'): r.revalidate(prepared)
    assert prepared.target.commit == 'c' * 40


def test_local_change_during_source_resolution_is_refused_instead_of_mixing_identities(origin):
    from opencode_sandbox import manager_review as r
    launcher = origin[0][4].resolve()
    def before(path, state):
        if len(state['requests']) == 1: launcher.write_text(launcher.read_text() + '# changed during source query\n')
    origin[1]['before'] = before
    with pytest.raises(c.SandboxError, match='changed during review'): r.prepare('v6.2.0')


@pytest.mark.parametrize('bad', [None, {}, True, 'source-target'])
def test_plain_cache_boolean_or_foreign_records_are_not_reviews(origin, bad):
    from opencode_sandbox import manager_review as r
    with pytest.raises(c.SandboxError): r.revalidate(bad)
    assert not origin[1]['requests']


@pytest.mark.parametrize('change', ['owner', 'prefix', 'version'])
def test_review_is_origin_and_installation_bound_without_early_release(prepared, origin, change):
    from opencode_sandbox import manager_review as r
    assert locks._LEASE is not None
    changed = dataclasses.replace(prepared, **{'owner': {'owner': -1}, 'prefix': {'prefix': '/foreign'},
                                             'version': {'version': '0.0.0'}}[change])
    count = len(origin[1]['requests'])
    with pytest.raises(c.SandboxError): r.revalidate(changed)
    assert len(origin[1]['requests']) == count and locks._LEASE is not None


def test_review_shows_exact_impact_and_no_secret_environment_or_configuration_dump(prepared, monkeypatch):
    from opencode_sandbox import manager_review as r
    monkeypatch.setenv('OPENROUTER_API_KEY', 'dummy-secret-provider-key')
    rendered = r.text(prepared)
    for text in (prepared.target.commit, prepared.target.tag, prepared.identity, prepared.prefix,
                 'public defaults', 'host as this user', 'force is not a backup', 'Manager Update remains disabled',
                 'Independent exclusive revalidation', 'no switch', '1.18.7'):
        assert text.lower() in rendered.lower()
    assert 'dummy-secret' not in rendered and 'dummy-secret' not in prepared.binding


def test_unrelated_directory_cache_creation_does_not_change_review_identity(prepared, origin):
    from opencode_sandbox import manager_review as r
    directory = origin[0][3] / 'bin/unrelated-owned-cache'
    directory.mkdir(); (directory / 'new-file').write_text('owned irrelevant cache')
    assert r.revalidate(prepared) is prepared


@pytest.mark.parametrize('tag', ['latest', 'main', 'v6.2.0;execute', None])
def test_only_exact_strict_tags_can_prepare_a_review_before_any_inspection(origin, monkeypatch, tag):
    from opencode_sandbox import manager_review as r
    monkeypatch.setattr(r, '_inspect', lambda: pytest.fail('invalid tag triggered inspection'))
    with pytest.raises(c.SandboxError): r.prepare(tag)


@pytest.mark.parametrize('kind', ['fifo', 'cycle', 'unsafe'])
def test_route_inventory_refuses_special_cyclic_or_uncontrolled_paths(tmp_path, kind):
    from opencode_sandbox import manager_review as r
    path = tmp_path / 'route'
    if kind == 'fifo': os.mkfifo(path)
    if kind == 'cycle': path.symlink_to(path)
    if kind == 'unsafe': path.write_text('owned'); path.chmod(0o666)
    with pytest.raises(c.SandboxError): r._route(path)
