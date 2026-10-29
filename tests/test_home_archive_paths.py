import io
import tarfile

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c


def make_tar(path, members):
    with tarfile.open(path, 'w:gz') as tf:
        for name, typ, target in members:
            m=tarfile.TarInfo(name)
            if typ == 'file':
                data=b'payload'; m.size=len(data); tf.addfile(m, io.BytesIO(data))
            elif typ == 'dir':
                m.type=tarfile.DIRTYPE; tf.addfile(m)
            else:
                m.type=tarfile.SYMTYPE; m.linkname=target; tf.addfile(m)


def test_home_tar_dot_prefix_roundtrip(tmp_path):
    path=tmp_path/'home.tar.gz'
    make_tar(path,[('.', 'dir',None),('./.config','dir',None),('./.config/opencode','file',None)])
    dest=tmp_path/'home'
    b.unpack(path,dest)
    assert (dest/'.config/opencode').read_bytes()==b'payload'


def test_home_tar_rejects_file_parent(tmp_path):
    path=tmp_path/'home.tar.gz'
    make_tar(path,[('dir','file',None),('dir/evil','file',None)])
    with pytest.raises(c.SandboxError,match='non-directory'):
        b.unpack(path,tmp_path/'out')


def test_home_tar_rejects_duplicate_canonical_name(tmp_path):
    path=tmp_path/'home.tar.gz'
    make_tar(path,[('./file','file',None),('file','file',None)])
    with pytest.raises(c.SandboxError,match='Unsafe'):
        b.unpack(path,tmp_path/'out')


def test_home_tar_rejects_symlink_parent(tmp_path):
    path=tmp_path/'home.tar.gz'
    make_tar(path,[('./link','link','target'),('./link/evil','file',None)])
    with pytest.raises(c.SandboxError,match='symlink'):
        b.unpack(path,tmp_path/'out')
