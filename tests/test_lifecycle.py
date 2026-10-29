import json
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'BASE',tmp_path/'data')
    monkeypatch.setattr(c,'CONFIG',tmp_path/'config')
    monkeypatch.setattr(c,'ensure_runtime',lambda image=True: None)

def response(stdout='',stderr='',returncode=0):
    return SimpleNamespace(stdout=stdout,stderr=stderr,returncode=returncode)

def test_start_creation_failure_recoverable(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda m:None)
    def fake(*args,**kw):
        if args[0]=='run': raise c.SandboxError('simulated failure')
        return response()
    monkeypatch.setattr(c,'docker',fake)
    monkeypatch.setattr(c,'ensure_volume',lambda m: None)
    with pytest.raises(c.SandboxError,match='simulated'): c.start(m)
    assert c.resolve(m['id'])['status']=='error'
    assert (c.env_dir(m['id'])/'workspace').exists()

def test_repair_missing_container_retains_workspace(monkeypatch):
    m=c.create('demo','scratch')
    c.mark(m,'creating')
    monkeypatch.setattr(c,'inspect_container',lambda m:None)
    assert 'retained' in c.repair(m)
    assert c.resolve(m['id'])['status']=='ready'

def test_repair_running(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda m:{'Running':True})
    assert c.repair(m)=='reconciled: running'
    assert c.resolve(m['id'])['status']=='running'

def test_stop_failure_preserves_metadata(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda m:{'Running':True})
    def fail(*args,**kwargs): raise c.SandboxError('daemon down')
    monkeypatch.setattr(c,'docker',fail)
    with pytest.raises(c.SandboxError): c.stop(m)
    assert c.resolve(m['id'])['status']=='error'

def test_delete_volume_failure_does_not_erase_workspace(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda m:None)
    def fake(*args,**kw):
        if args[:2]==('volume','rm'): raise c.SandboxError('busy volume')
        return response()
    monkeypatch.setattr(c,'docker',fake)
    monkeypatch.setattr(c,'assert_volume_owned',lambda m: {'Labels':{'org.opencode-sandbox.id':m['id']}})
    with pytest.raises(c.SandboxError,match='busy volume'): c.delete(m,force=True)
    assert (c.env_dir(m['id'])/'workspace').exists()
    assert c.resolve(m['id'])['status']=='deleting'

def test_metadata_atomic_no_temp_left():
    m=c.create('demo','scratch')
    c.mark(m,'stopped')
    d=c.env_dir(m['id'])
    assert not list(d.glob('.metadata-*'))
    assert json.loads((d/'metadata.json').read_text())['status']=='stopped'
