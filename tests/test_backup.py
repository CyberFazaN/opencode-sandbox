import io
import json
import tarfile

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c


def test_archive_and_verify(tmp_path):
    source=tmp_path/'src';source.mkdir();(source/'hello.txt').write_text('hello')
    target=tmp_path/'saved.ocsbackup';target.mkdir()
    b.archive_directory(source,target/'workspace.tar.gz')
    (target/'manifest.json').write_text(json.dumps({'format':'opencode-sandbox-backup','schema':b.SCHEMA,'workspace':{'mode':'managed','included':True},'created':'now','files':{'workspace.tar.gz':b.digest(target/'workspace.tar.gz')}}))
    assert b.verify(target)['schema']==b.SCHEMA
    out=tmp_path/'out';out.mkdir();b.unpack(target/'workspace.tar.gz',out)
    assert (out/'hello.txt').read_text()=='hello'

def test_checksum_detects_corruption(tmp_path):
    p=tmp_path/'b';p.mkdir();(p/'workspace.tar.gz').write_bytes(b'bad')
    (p/'manifest.json').write_text(json.dumps({'format':'opencode-sandbox-backup','schema':b.SCHEMA,'workspace':{'mode':'managed','included':True},'created':'now','files':{'workspace.tar.gz':'0'*64}}))
    with pytest.raises(c.SandboxError,match='Checksum'): b.verify(p)

def test_path_traversal_rejected(tmp_path):
    tar=tmp_path/'evil.tar.gz'
    with tarfile.open(tar,'w:gz') as f:
        payload=b'attack';info=tarfile.TarInfo('../outside');info.size=len(payload);f.addfile(info,io.BytesIO(payload))
    with pytest.raises(c.SandboxError,match='Unsafe'): b.unpack(tar,tmp_path)

def test_absolute_symlink_archived_as_a_link(tmp_path):
    source=tmp_path/'src';source.mkdir();(source/'abs').symlink_to('/etc/passwd')
    b.archive_directory(source,tmp_path/'out.tar.gz')
    with tarfile.open(tmp_path/'out.tar.gz') as tf:
        member=tf.getmember('abs')
    assert member.issym() and member.linkname=='/etc/passwd'  # the target's content is not read

def test_restore_verifies_before_create(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'verify',lambda p: (_ for _ in ()).throw(c.SandboxError('bad backup')))
    monkeypatch.setattr(c,'create',lambda *a,**kw: pytest.fail('created before verification'))
    with pytest.raises(c.SandboxError,match='bad backup'): b.restore(tmp_path,'new')
