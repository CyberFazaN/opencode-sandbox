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

def test_unowned_volume_is_never_deleted(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda _:None)
    monkeypatch.setattr(c,'docker',lambda *a,**k: response(stdout=json.dumps([{'Labels':{'org.opencode-sandbox.id':'stranger'}}])))
    with pytest.raises(c.SandboxError,match='ownership mismatch'): c.delete(m,force=True)
    # A refused preflight must not journal a deletion that never started.
    saved=c.resolve(m['id'])
    assert saved['status']=='ready' and saved.get('operation') is None
    assert (c.env_dir(m['id'])/'workspace').exists()

def test_retry_delete_after_interrupted_volume_removal(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda _:None)
    events=[]
    fail=[True]
    def fake(*a,**kw):
        events.append(a)
        if a[:2]==('volume','inspect'):
            return response(stdout=json.dumps([{'Labels':{'org.opencode-sandbox.id':m['id']}}]))
        if a[:2]==('volume','rm') and fail[0]:
            fail[0]=False
            raise c.SandboxError('simulated interruption')
        return response()
    monkeypatch.setattr(c,'docker',fake)
    with pytest.raises(c.SandboxError): c.delete(m,force=True)
    assert c.resolve(m['id'])['operation']=='delete'
    with pytest.raises(c.SandboxError,match='Deletion pending'): c.repair(m)
    with pytest.raises(c.SandboxError,match='deletion pending'): c.start(m)
    c.delete(m,force=True)
    assert not c.env_dir(m['id']).exists()

def test_missing_volume_is_not_assumed_on_daemon_error(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'docker',lambda *a,**kw:response(returncode=1,stderr='daemon unavailable'))
    with pytest.raises(c.SandboxError,match='Volume inspect failed'): c.volume_state(m)

def test_start_marks_intent_before_docker_side_effect(monkeypatch):
    m=c.create('demo','scratch')
    monkeypatch.setattr(c,'inspect_container',lambda _:None)
    monkeypatch.setattr(c,'docker',lambda *a,**k:SimpleNamespace(returncode=0,stdout='',stderr=''))  # read-only image check
    def fail(_):
        assert c.resolve(m['id'])['operation']=='start'
        raise c.SandboxError('injected')
    monkeypatch.setattr(c,'ensure_volume',fail)
    with pytest.raises(c.SandboxError,match='injected'): c.start(m)
    assert c.resolve(m['id'])['status']=='error'

def test_repair_never_erases_deletion_intent_when_container_missing(monkeypatch):
    m=c.create('demo','scratch')
    c.mark(m,'deleting',operation='delete')
    monkeypatch.setattr(c,'inspect_container',lambda _:None)
    with pytest.raises(c.SandboxError,match='Deletion pending'): c.repair(m)
    assert c.resolve(m['id'])['status']=='deleting'

@pytest.mark.parametrize("status",["restoring","error"])
def test_interrupted_restore_is_never_started_or_repaired(monkeypatch,status):
    """Start/repair erased the restore journal and published an empty workspace."""
    m=c.create('demo','scratch')
    c.mark(m,status,operation='restore',restore_stage='home')
    monkeypatch.setattr(c,'inspect_container',lambda _:None)
    monkeypatch.setattr(c,'docker',lambda *a,**k: pytest.fail(f'docker called: {a}'))
    with pytest.raises(c.SandboxError,match='backup restore-resume demo .or: opencode-sandbox backup restore-rollback demo --yes'): c.start(m)
    with pytest.raises(c.SandboxError,match='backup restore-resume demo .or: opencode-sandbox backup restore-rollback demo --yes'): c.repair(m)
    saved=c.resolve(m['id'])
    assert saved['operation']=='restore' and saved['status']==status

def test_rollback_accepts_killed_restore(monkeypatch):
    from opencode_sandbox import backup
    m=c.create('demo','scratch')
    c.mark(m,'restoring',operation='restore')
    deleted=[]
    monkeypatch.setattr(c,'delete',lambda m,force,precondition=None: deleted.append(m['id']))
    backup.rollback_restore(m['id'])
    assert deleted==[m['id']]


@pytest.mark.parametrize("op, hint", [("recreate", "container recreate-recover"), ("runtime-recreate", "config recover"),
                                      ("config-update", "config recover"), ("opencode-update", "opencode update-recover"),
                                      ("restore", "backup restore-resume")])
def test_pending_operation_refusal_names_both_causes(monkeypatch, op, hint):
    """Seen in a real concurrency run: while another process was still recreating, a second
    recreate was told to recover. The journal cannot tell running from interrupted; say both."""
    monkeypatch.setattr(c,'inspect_container',lambda m: {'Running': False})
    m=c.create('ocs-qa-pending','scratch')
    c.mark(m,'recreating',operation=op)
    for call in (lambda: c.recreate(c.resolve(m['id']),confirm=True), lambda: c.start(c.resolve(m['id'])),
                 lambda: c.repair(c.resolve(m['id']))):
        with pytest.raises(c.SandboxError) as exc:
            call()
        text=str(exc.value)
        assert f"pending operation ({op})" in text and "still working on it, wait" in text and hint in text, text
