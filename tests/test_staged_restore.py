import contextlib
import tarfile

import pytest

from opencode_sandbox import backup


def test_hardlink_roundtrip(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'first').write_text('payload')
    (source/'second').hardlink_to(source/'first')
    archive=tmp_path/'workspace.tar.gz'
    backup.archive_directory(source,archive)
    target=tmp_path/'target'
    backup.unpack(archive,target)
    assert (target/'first').read_text()=='payload'
    assert (target/'first').stat().st_ino==(target/'second').stat().st_ino


def test_hardlink_traversal_rejected(tmp_path):
    archive=tmp_path/'bad.tar.gz'
    with tarfile.open(archive,'w:gz') as tf:
        m=tarfile.TarInfo('safe');m.type=tarfile.LNKTYPE;m.linkname='../outside'
        tf.addfile(m)
    with pytest.raises(backup.c.SandboxError,match='hardlink'):
        backup._validate_archive(archive)


def test_staged_volume_published_only_after_success(monkeypatch,tmp_path):
    m={'id':'a'*16,'name':'recovered','operation':'restore','status':'restoring','workspace':{'mode':'managed','path':None}}
    home=tmp_path/'env';home.mkdir();(home/'workspace').mkdir()
    src=tmp_path/'src';src.mkdir();(src/'hello').write_text('world')
    archive=tmp_path/'workspace.tar.gz';backup.archive_directory(src,archive)
    (tmp_path/'home.tar.gz').write_bytes(b'fake archive')
    monkeypatch.setattr(backup.c,'lock',lambda _:contextlib.nullcontext())
    monkeypatch.setattr(backup.c,'resolve',lambda _:dict(m))
    monkeypatch.setattr(backup.c,'env_dir',lambda _:home)
    monkeypatch.setattr(backup.c,'inspect_container',lambda _:None)
    monkeypatch.setattr(backup.c,'volume_state',lambda _:None)
    monkeypatch.setattr(backup.c,'mark',lambda obj,status,**kw:(obj.update(status=status,**kw),m.update(obj)))
    monkeypatch.setattr(backup.c,'save',lambda obj:m.update(obj))
    monkeypatch.setattr(backup.c,'ensure_volume',lambda obj:None)
    monkeypatch.setattr(backup,'_volume_tar',lambda *args,**kwargs:None)
    result=backup._restore_into(m,tmp_path,{'environment':{'kind':'scratch'},'files':{'workspace.tar.gz':{},'home.tar.gz':{}}},restore_system=False)
    assert result['status']=='ready'
    assert result['home_volume'].startswith('ocs-stage-')
    assert (home/'workspace'/'hello').read_text()=='world'
    assert not (home/'.workspace-stage').exists()


def test_staged_failure_does_not_publish(monkeypatch,tmp_path):
    m={'id':'b'*16,'name':'recovered','operation':'restore','status':'restoring','workspace':{'mode':'managed','path':None}}
    home=tmp_path/'env';home.mkdir();(home/'workspace').mkdir()
    src=tmp_path/'src';src.mkdir();(src/'hello').write_text('world')
    backup.archive_directory(src,tmp_path/'workspace.tar.gz')
    monkeypatch.setattr(backup.c,'lock',lambda _:contextlib.nullcontext())
    monkeypatch.setattr(backup.c,'resolve',lambda _:dict(m))
    monkeypatch.setattr(backup.c,'env_dir',lambda _:home)
    monkeypatch.setattr(backup.c,'inspect_container',lambda _:None)
    monkeypatch.setattr(backup.c,'volume_state',lambda _:None)
    monkeypatch.setattr(backup.c,'mark',lambda obj,status,**kw:(obj.update(status=status,**kw),m.update(obj)))
    monkeypatch.setattr(backup.c,'save',lambda obj:m.update(obj))
    monkeypatch.setattr(backup.c,'ensure_volume',lambda obj:None)
    def fail(*args,**kwargs):raise RuntimeError('injected volume failure')
    monkeypatch.setattr(backup,'_volume_tar',fail)
    with pytest.raises(RuntimeError,match='injected'):
        backup._restore_into(m,tmp_path,{'environment':{},'files':{'workspace.tar.gz':{},'home.tar.gz':{}}},restore_system=False)
    assert not any((home/'workspace').iterdir())
    assert (home/'.workspace-stage'/'hello').read_text()=='world'
    assert m['restore_stage']=='home'
