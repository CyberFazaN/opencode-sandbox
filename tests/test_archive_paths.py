import io
import tarfile

import pytest

from opencode_sandbox import backup, core


def make_archive(path, name, kind='file', target=None):
    with tarfile.open(path, 'w:gz') as tf:
        info=tarfile.TarInfo(name)
        if kind=='symlink':
            info.type=tarfile.SYMTYPE
            info.linkname=target
        else:
            info.size=1
        tf.addfile(info, io.BytesIO(b'x') if kind=='file' else None)


@pytest.mark.parametrize('name', ['a//b', 'a/./b', 'a/../b', 'a\\b', '/absolute'])
def test_noncanonical_archive_paths(tmp_path, name):
    archive=tmp_path/'bad.tar.gz'
    make_archive(archive, name)
    with pytest.raises(core.SandboxError):
        backup._validate_archive(archive)


def test_symlink_target_with_backslash_rejected(tmp_path):
    archive=tmp_path/'bad.tar.gz'
    make_archive(archive, 'link', 'symlink', '..\\outside')
    with pytest.raises(core.SandboxError):
        backup._validate_archive(archive)


def test_manifest_symlink_rejected(tmp_path):
    root=tmp_path/'copy.ocsbackup'; root.mkdir()
    (root/'manifest.json').symlink_to(tmp_path/'external.json')
    with pytest.raises(core.SandboxError, match='manifest'):
        backup.verify(root)


def test_missing_executable_is_actionable():
    with pytest.raises(core.SandboxError, match='Required executable not found'):
        core.call(['/this/path/cannot/exist/ocs-executable'])
