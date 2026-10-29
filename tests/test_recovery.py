import multiprocessing as mp
import time
from types import SimpleNamespace

import pytest

from opencode_sandbox import core as c


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(c,'BASE',tmp_path/'data')
    monkeypatch.setattr(c,'CONFIG',tmp_path/'config')
    monkeypatch.setattr(c,'ensure_runtime',lambda image=True: None)

def hold_lock(base, config, signal):
    c.BASE=base
    c.CONFIG=config
    with c.lock('busy'):
        signal.send(True)
        time.sleep(.5)

def test_cross_process_lock_timeout():
    recv,send=mp.Pipe(False)
    p=mp.get_context("spawn").Process(target=hold_lock,args=(c.BASE,c.CONFIG,send))
    p.start()
    assert recv.recv() is True
    try:
        with pytest.raises(c.SandboxError,match='busy'), c.lock('busy',timeout=.1): pass
    finally:
        p.join(3)
        if p.is_alive(): p.terminate();p.join()
    assert p.exitcode==0

def test_pending_scan_is_non_destructive(monkeypatch):
    a=c.create('one','scratch');c.create('two','scratch')
    c.mark(a,'creating')
    assert [m['id'] for m in c.pending_repairs()]==[a['id']]
    assert c.resolve(a['id'])['status']=='creating'

def test_repair_all_isolates_errors(monkeypatch):
    a=c.create('one','scratch');b=c.create('two','scratch')
    c.mark(a,'starting');c.mark(b,'error')
    def fake(m,**kw):
        if m['id']==a['id']: raise c.SandboxError('offline')
        return 'repaired'
    monkeypatch.setattr(c,'repair',fake)
    results=c.repair_all()
    assert len(results)==2
    assert any(r[2]=='offline' for r in results)
    assert any(r[1]=='repaired' for r in results)

def test_ownership_mismatch_blocks_stop_and_delete(monkeypatch):
    m=c.create('one','scratch')
    def fake(*args,**kw):
        if args[:2]==('container','inspect') and '--format' in args:
            if '{{json .State}}' in args: return SimpleNamespace(returncode=0,stdout='{"Running":false}',stderr='')
            return SimpleNamespace(returncode=0,stdout='different-id\n',stderr='')
        raise AssertionError('unexpected docker call: '+repr(args))
    monkeypatch.setattr(c,'docker',fake)
    for action in (lambda:c.stop(m),lambda:c.delete(m,force=True)):
        with pytest.raises(c.SandboxError,match='ownership mismatch'):
            action()
    assert (c.env_dir(m['id'])/'workspace').exists()

def test_ownership_matching(monkeypatch):
    m=c.create('one','scratch')
    def fake(*args,**kw):
        if '{{json .State}}' in args: return SimpleNamespace(returncode=0,stdout='{"Running":true}',stderr='')
        return SimpleNamespace(returncode=0,stdout=m['id']+'\n',stderr='')
    monkeypatch.setattr(c,'docker',fake)
    assert c.inspect_container(m)['Running'] is True


@pytest.mark.parametrize("docker_status,removed", [("exited", False), ("created", True), ("dead", True)])
def test_repair_cleanup_only_removes_partial_containers(monkeypatch, docker_status, removed):
    """--cleanup removed any stopped container and its system layer."""
    from types import SimpleNamespace
    m = c.create("ocs-qa-clean", "scratch")
    calls = []
    monkeypatch.setattr(c, "ensure_runtime", lambda image=True: None)
    monkeypatch.setattr(c, "inspect_container", lambda m: {"Running": False, "Status": docker_status, "Dead": docker_status == "dead"})
    monkeypatch.setattr(c, "docker", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    if removed:
        assert "removed" in c.repair(m, cleanup=True)
        assert ("rm", c.cname(m)) in calls
    else:
        with pytest.raises(c.SandboxError, match="Refusing --cleanup"):
            c.repair(m, cleanup=True)
        assert not any(a[0] == "rm" for a in calls)
