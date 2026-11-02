"""Frozen local-observation replay is not a fresh tool/source grant or installation executor."""
import dataclasses
import hashlib
import json
import os
import select
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest
from manager_policy_fixture import system_source
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_review import installation as local_installation
from test_manager_review import origin as review_origin
from test_manager_review import prepared as prepared_review
from test_manager_review import tools as local_tools

from opencode_sandbox import core as c
from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_handoff as h
from opencode_sandbox import manager_observations as o
from opencode_sandbox import manager_review as r

origin = review_origin
prepared = prepared_review
installation = local_installation
tools = local_tools


def data(prepared):
    return {'origin': prepared.owner, 'prefix': prepared.prefix, 'version': prepared.version, 'identity': prepared.identity,
            'binding': prepared.binding, 'target': dataclasses.asdict(prepared.target),
            'context': {name: os.environ.get(name) for name in o.CONTEXT}}


def test_shared_route_context_and_critical_inventory_match_origin_review(prepared):
    value = json.loads(prepared.binding)
    assert set(o.CONTEXT) == set(r.CONTEXT)
    assert {str(path) for path in o.critical(value['installation']['evidence'])} == set(value['records'])
    for path, rows in value['routes'].items():
        assert o.canonical(o.route(path)) == o.canonical(rows)
    raw = o.capsule(**data(prepared))
    value = o.parse(raw)
    assert value['identity'] == prepared.identity and value['context'] == data(prepared)['context']
    assert 'binding' not in repr(prepared) and 'fixture' in value


@pytest.mark.parametrize('field,value', [('origin', True), ('origin', -1), ('prefix', '/foreign'), ('version', 'main'),
                                      ('identity', 'f' * 64), ('context', {}), ('binding', '{}'), ('target', {})])
def test_changed_or_unbound_capsule_fields_refuse_without_execution(prepared, field, value):
    original = json.loads(o.capsule(**data(prepared)))
    original[field] = value
    with pytest.raises((o.Refused, KeyError, TypeError, ValueError)):
        o._shape(original, prepared.prefix, prepared.owner)


@pytest.mark.parametrize('raw', ['{"a":1,"a":2}', '{"value":NaN}', '{"value":Infinity}'])
def test_duplicate_and_nonfinite_validation_input_refuses(raw):
    with pytest.raises(o.Refused): o.parse(raw)


def test_arbitrary_record_read_is_not_a_supported_validation_operation(prepared, tmp_path):
    value = data(prepared)
    binding = json.loads(value['binding'])
    secret = tmp_path / 'private-credential-file'; secret.write_text('dummy-secret-never-read')
    binding['records'] = {str(secret): hashlib.sha256(secret.read_bytes()).hexdigest()}
    value['binding'] = o.canonical(binding)
    source = {key: item for key, item in value['target'].items() if key != 'at'}
    value['identity'] = o.digest({'source': source, 'binding': value['binding'], 'owner': value['origin']})
    with pytest.raises(o.Refused, match='inventory'): o.capsule(**value)


def test_replay_requires_real_own_kernel_exclusion_even_with_an_approved_input(prepared, tmp_path):
    raw = o.capsule(**data(prepared)); path = tmp_path / 'review.json'; path.write_bytes(raw); path.chmod(0o600)
    info = path.stat()
    expected = {'sha256': hashlib.sha256(raw).hexdigest(), 'identity': prepared.identity, 'file_identity': [info.st_dev, info.st_ino]}
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(locks.Error, match='existing own-process exclusive'):
            o.validate(locks, directory, expected, prefix=prepared.prefix, origin=prepared.owner, deadline=time.monotonic() + 3)
        assert locks._LEASE is not None
    finally: os.close(directory)


@pytest.mark.parametrize('approval', [None, True, {}, 'approved'])
def test_plain_cache_or_boolean_is_not_a_review_receipt_for_staging(tmp_path, approval):
    with pytest.raises(c.SandboxError, match='receipt'): h.prepare_review_fixture(approval, tmp_path)
    assert not list(tmp_path.iterdir())


def test_approved_local_input_is_private_bounded_and_manifested_without_starting_a_helper(prepared, tmp_path):
    staged = h.prepare_review_fixture(r.Approval(prepared), tmp_path)
    assert staged['supported'], staged
    artifact = staged['artifact']
    assert artifact.review_identity == prepared.identity and not artifact.used and artifact.process is None
    assert {path.name for path in artifact.directory.iterdir()} == {'helper.pyz', 'artifact.json', 'review.json'}
    path = artifact.directory / 'review.json'
    assert path.stat().st_mode & 0o777 == 0o600 and path.stat().st_nlink == 1
    assert len(path.read_bytes()) <= o.LIMIT and hashlib.sha256(path.read_bytes()).hexdigest() == artifact.review_sha256
    assert json.loads(path.read_bytes())['identity'] == prepared.identity
    artifact.check(); artifact.discard()
    assert not artifact.directory.exists() and locks._LEASE is not None


@pytest.mark.parametrize('change', ['bytes', 'mode', 'inode', 'extra'])
def test_changed_or_unfamiliar_local_input_is_preserved_not_repaired_or_discarded(prepared, tmp_path, change):
    staged = h.prepare_review_fixture(r.Approval(prepared), tmp_path)
    assert staged['supported'], staged
    artifact = staged['artifact']; path = artifact.directory / 'review.json'
    if change == 'bytes': path.write_text('unfamiliar dummy-secret input')
    if change == 'mode': path.chmod(0o644)
    if change == 'inode':
        raw = path.read_bytes(); path.rename(path.with_suffix('.saved')); path.write_bytes(raw); path.chmod(0o600)
    if change == 'extra': (artifact.directory / 'keep').write_text('unfamiliar dummy-secret file')
    before = {path.name for path in artifact.directory.iterdir()}
    with pytest.raises(c.SandboxError): artifact.discard()
    assert before == {path.name for path in artifact.directory.iterdir()} and artifact.process is None


def spawn_origin(origin, tmp_path, *, budget=30, execution=False, frozen_transport=None, system_configs=None):
    prefix, launcher = origin[0][3:]
    external = Path(shutil.which('pipx')).resolve().read_text().splitlines()[0][2:]
    dist = next(prefix.glob('lib/python*/site-packages/*.dist-info'))
    stage = tmp_path / 'staging'; stage.mkdir()
    from opencode_sandbox import manager_targets
    network_source = None
    if system_configs is not None:
        from opencode_sandbox import manager_network
        network_source = system_source(Path(manager_network.__file__).read_bytes(), system_configs)
    code = ('import json,os,sys,threading\nfrom pathlib import Path\n'
        f'sys.path.insert(0,{str(Path(r.__file__).parents[1])!r})\n'
        f'sys.prefix={str(prefix)!r}\nsys.executable={str(prefix / "bin/python")!r}\nsys.argv=[{str(launcher)!r}]\n'
        'from opencode_sandbox import installation_locks as locks\nlocks.acquire_usage()\n'
        'from opencode_sandbox import core as c,manager_installation as i,manager_targets as t,manager_releases as releases\n'
        'from opencode_sandbox import manager_review as r,manager_handoff as h\n'
        f'c.BASE=Path({str(c.BASE)!r});c.CONFIG=Path({str(c.CONFIG)!r})\n'
        f'i._running_distribution=lambda:(Path({str(dist.parent / "opencode_sandbox/__init__.py")!r}),Path({str(dist)!r}))\n'
        f'r.SYSTEM_CONFIGS={system_configs or ()!r}\n'
        f't.ENDPOINT={manager_targets.ENDPOINT!r};releases.API=t.ENDPOINT+"/releases?per_page=100"\n'
        + (('import io,zipfile\noriginal_bundle=h._bundle\n'
            'def transport_bundle():\n'
            ' buffer=io.BytesIO()\n'
            ' with zipfile.ZipFile(io.BytesIO(original_bundle())) as old,zipfile.ZipFile(buffer,"w") as new:\n'
            '  for name in old.namelist():\n'
            '   raw=old.read(name)\n'
             f'   if name=="manager_execution.py": raw=raw.replace(b"SOURCE_API = source.API",{("SOURCE_API = " + repr(frozen_transport)).encode()!r})\n'
             + (f'   if name=="manager_network.py": raw={network_source!r}\n' if network_source is not None else '') +
             '   new.writestr(name,raw)\n'
            ' return buffer.getvalue()\n'
            'h._bundle=transport_bundle\n') if frozen_transport else '') +
        f'prepared=r.prepare("v6.2.0")\nstaged=h.prepare_review_fixture(r.Approval(prepared),Path({str(stage)!r}))\n'
        f'assert staged["supported"],staged\na=staged["artifact"]\nf=h.start_fixture(a,budget={budget!r},execution={execution!r});f.arm()\n'
        'def drain():\n sys.stdin.read()\n'
        + (' status=f.process.wait(timeout=5)\n print(json.dumps({"origin_reaped_helper":f.process.pid,"status":status}),flush=True)\n' if budget < 1 else '') +
        'threading.Thread(target=drain).start()\n'
        'print(json.dumps({"helper":f.process.pid,"directory":str(a.directory),"identity":a.review_identity}),flush=True)\n')
    process = subprocess.Popen([external, '-B', '-c', code], env=dict(os.environ), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert select.select([process.stdout], [], [], 15)[0], 'Owned origin did not report staged readiness'
    line = process.stdout.readline()
    if not line:
        _, error = process.communicate(timeout=3)
        pytest.fail(error)
    return process, json.loads(line)


@pytest.mark.parametrize('change', ['none', 'record', 'launcher', 'python-route', 'config', 'capsule-bytes',
                                  'capsule-mode', 'capsule-inode', 'capsule-symlink', 'capsule-hardlink', 'capsule-fifo'])
def test_actual_origin_death_precedes_frozen_exclusive_local_replay_or_refusal(origin, tmp_path, change):
    prefix, launcher = origin[0][3:]
    helper = process = None
    with subreaper():
        try:
            process, value = spawn_origin(origin, tmp_path)
            helper = value['helper']; directory = Path(value['directory'])
            assert process.poll() is None and not (directory / 'result.json').exists()
            time.sleep(.1)  # main has returned, but owned non-daemon drain still retains usage
            assert not (directory / 'result.json').exists()
            capsule = directory / 'review.json'
            if change == 'record': (prefix / 'pyvenv.cfg').write_text((prefix / 'pyvenv.cfg').read_text() + '# changed\n')
            if change == 'launcher': launcher.resolve().write_text(launcher.resolve().read_text() + '# changed\n')
            if change == 'python-route':
                path = prefix / 'bin/python'; endpoint = path.resolve(); path.unlink()
                alias = tmp_path / 'python-alias'; alias.symlink_to(endpoint); path.symlink_to(alias)
            if change == 'config': (Path.home() / '.netrc').write_text('dummy-secret-local-config')
            if change == 'capsule-bytes': capsule.write_text('dummy-secret-unfamiliar-input')
            if change == 'capsule-mode': capsule.chmod(0o644)
            if change == 'capsule-inode':
                raw = capsule.read_bytes(); capsule.rename(capsule.with_suffix('.saved')); capsule.write_bytes(raw); capsule.chmod(0o600)
            if change == 'capsule-symlink':
                saved = capsule.with_suffix('.saved'); capsule.rename(saved); capsule.symlink_to(saved)
            if change == 'capsule-hardlink': os.link(capsule, directory / 'unfamiliar-link')
            if change == 'capsule-fifo': capsule.rename(capsule.with_suffix('.saved')); os.mkfifo(capsule, mode=0o600)
            process.communicate(timeout=10)
            assert process.returncode == 0
            assert wait_helper(helper) == 0; helper = None
            result = result_at(directory)
            assert result['review']['identity'] == value['identity']
            assert result['outcome'] == ('quiescent' if change == 'none' else 'review-failed')
            assert result['review']['ok'] is (change == 'none')
            assert 'dummy-secret' not in json.dumps(result)
            assert 'verifier' not in result
            if change != 'none': assert result['review']['reason'] == o.FAILURE
        finally:
            if process is not None:
                if process.poll() is None: process.kill()
                process.communicate(timeout=5)
            if helper is not None:
                try:
                    if os.waitpid(helper, os.WNOHANG)[0] == 0:
                        os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except ChildProcessError: pass


@pytest.mark.parametrize('mode', ['busy', 'expired'])
def test_local_observation_payload_does_not_override_other_usage_or_origin_lifetime(origin, tmp_path, monkeypatch, mode):
    process = helper = None
    if mode == 'busy':
        monkeypatch.setattr(locks, '_TMP', Path('/tmp'))
        locks.acquire_usage()  # a distinct live supported participant, never released for the helper
    with subreaper():
        try:
            process, value = spawn_origin(origin, tmp_path, budget=.3 if mode == 'expired' else 30)
            helper = value['helper']
            if mode == 'busy':
                process.communicate(timeout=10)
                assert wait_helper(helper) == 0; helper = None
            result = result_at(value['directory'])
            assert result['outcome'] == mode and 'review' not in result
            if mode == 'expired':
                assert process.poll() is None
                stdout, _ = process.communicate(timeout=5)
                assert json.loads(stdout) == {'origin_reaped_helper': helper, 'status': 0}
                helper = None  # exact original parent reaped it; never signal an already reaped PID
            else: assert locks._LEASE is not None
        finally:
            if process is not None:
                process.communicate(timeout=5)
            if helper is not None:
                try:
                    if os.waitpid(helper, os.WNOHANG)[0] == 0:
                        os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except ChildProcessError: pass
