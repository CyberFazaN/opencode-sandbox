from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c
from opencode_sandbox import readiness


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(c,'BASE',tmp_path/'data')
    monkeypatch.setattr(c,'CONFIG',tmp_path/'config')
    monkeypatch.setattr(c,'ensure_runtime',lambda image=True: None)

def test_recreate_failure_keeps_journal_and_snapshot(monkeypatch):
    m=c.create('demo','scratch')
    state={'exists':True,'running':False}
    monkeypatch.setattr(c,'inspect_container',lambda m: {'Running':state['running']} if state['exists'] else None)
    monkeypatch.setattr(c,'snapshot',lambda m: 'checkpoint:test')
    def docker(*args,**kwargs):
        if args[0]=='rm':
            state['exists']=False
            return SimpleNamespace(returncode=0)
        raise AssertionError(args)
    monkeypatch.setattr(c,'docker',docker)
    def failed_start(m, *, _resume_recreate=False):
        raise c.SandboxError('injected startup failure')
    monkeypatch.setattr(c,'start',failed_start)
    with pytest.raises(c.SandboxError,match='injected'):
        c.recreate(m,confirm=True)
    saved=c.resolve(m['id'])
    assert saved['operation']=='recreate'
    assert saved['image']=='checkpoint:test'
    assert saved['last_snapshot']=='checkpoint:test'
    with pytest.raises(c.SandboxError,match='recreate-recover'):
        c.repair(m)

def test_recreate_recover_uses_snapshot(monkeypatch):
    m=c.create('demo','scratch')
    m['image']='checkpoint:test'
    c.mark(m,'error',operation='recreate',last_snapshot='checkpoint:test')
    monkeypatch.setattr(c,'inspect_container',lambda m: None)
    def fake_start(m, *, _resume_recreate=False):
        saved=c.resolve(m['id'])
        assert saved['image']=='checkpoint:test'
        assert saved['operation']=='recreate'
        assert _resume_recreate
        c.mark(saved,'running',operation=None)
    monkeypatch.setattr(c,'start',fake_start)
    assert c.recreate_recover(m)=='recreated'
    assert c.resolve(m['id'])['status']=='running'

def test_recreate_recover_refuses_stopped_original_container(monkeypatch):
    m=c.create('demo','scratch')
    m['image']='checkpoint:test'
    c.mark(m,'error',operation='recreate',last_snapshot='checkpoint:test')
    monkeypatch.setattr(c,'inspect_container',lambda m: {'Running':False})
    calls=[]
    def docker(*args,**kw):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='opencode-sandbox:debian\n',stderr='')
    monkeypatch.setattr(c,'docker',docker)
    with pytest.raises(c.SandboxError,match='not the recorded replacement'):
        c.recreate_recover(m)
    assert not any(a[0] in ('rm','start') for a in calls)
    assert c.resolve(m['id'])['operation']=='recreate'

def test_recreate_recover_starts_created_replacement(monkeypatch):
    """Replacement created from the snapshot but never started."""
    m=c.create('demo','scratch')
    m['image']='checkpoint:test'
    c.mark(m,'error',operation='recreate',last_snapshot='checkpoint:test')
    monkeypatch.setattr(c,'inspect_container',lambda m: {'Running':False})
    calls=[]
    def docker(*args,**kw):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='checkpoint:test\n',stderr='')
    monkeypatch.setattr(c,'docker',docker)
    assert c.recreate_recover(m)=='replacement started'
    assert ('start',c.cname(m)) in calls and not any(a[0]=='rm' for a in calls)
    saved=c.resolve(m['id'])
    assert saved['status']=='running' and saved['operation'] is None

def test_doctor_does_not_create_app_directories(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    from opencode_sandbox.cli import app
    monkeypatch.setattr(c,'BASE',tmp_path/'not-created-data')
    monkeypatch.setattr(c,'CONFIG',tmp_path/'not-created-config')
    monkeypatch.setattr(c,'ensure_runtime',lambda image=False: None)
    monkeypatch.setattr(c,'docker',lambda *a,**k: SimpleNamespace(returncode=1,stdout='',stderr='daemon unavailable'))
    # Not the host's programs: the Docker CLI need not be installed for the unit suite (hosted CI).
    monkeypatch.setattr(readiness,'host_checks',lambda: [readiness.Check('python','Python',readiness.PASSED,'stub')])
    result=CliRunner().invoke(app,['doctor'])
    assert result.exit_code==0, result.output
    assert not c.BASE.exists() and not c.CONFIG.exists()
