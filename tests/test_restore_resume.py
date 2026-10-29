import pytest

from opencode_sandbox import backup


def test_resume_rejects_normal_environment(monkeypatch):
    monkeypatch.setattr(backup.c, 'resolve', lambda _: {'id':'abc','status':'ready','operation':None})
    with pytest.raises(backup.c.SandboxError, match='Not an interrupted restore'):
        backup.resume_restore('abc')


def test_resume_verifies_archive_before_modification(monkeypatch, tmp_path):
    record={'id':'abc','status':'error','operation':'restore','restored_from':str(tmp_path/'missing')}
    monkeypatch.setattr(backup.c,'resolve',lambda _:record)
    with pytest.raises(backup.c.SandboxError):
        backup.resume_restore('abc')


def test_restore_into_rejects_nonempty_workspace(monkeypatch, tmp_path):
    m={'id':'abc','operation':'restore','status':'error','workspace':{'mode':'managed','path':None}}
    workspace=tmp_path/'workspace';workspace.mkdir();(workspace/'important').write_text('keep')
    monkeypatch.setattr(backup.c,'lock',lambda _: __import__('contextlib').nullcontext())
    monkeypatch.setattr(backup.c,'resolve',lambda _:m)
    monkeypatch.setattr(backup.c,'inspect_container',lambda _:None)
    monkeypatch.setattr(backup.c,'mark',lambda obj,state,**kw:obj.update(status=state,**kw))
    monkeypatch.setattr(backup.c,'env_dir',lambda _:tmp_path)
    with pytest.raises(backup.c.SandboxError,match='not empty'):
        backup._restore_into(m,tmp_path,{'environment':{},'files':{}},restore_system=False)
    assert (workspace/'important').read_text()=='keep'
