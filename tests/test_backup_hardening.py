import io
import json
import tarfile
from pathlib import Path

import pytest

from opencode_sandbox import backup as b
from opencode_sandbox import core as c


def test_internal_symlink_roundtrip(tmp_path):
    src=tmp_path/'src';src.mkdir()
    (src/'target').write_text('hello')
    (src/'link').symlink_to('target')
    tar=tmp_path/'a.tar.gz';b.archive_directory(src,tar)
    out=tmp_path/'out';b.unpack(tar,out)
    assert (out/'link').is_symlink()
    assert (out/'link').readlink()==Path('target')
    assert (out/'link').read_text()=='hello'

@pytest.mark.parametrize('link',['/usr/bin/python','../../outside','sub/../../x'])
def test_absolute_and_escaping_symlinks_roundtrip_as_links(tmp_path,link):
    """D-022: every Python venv has bin/python -> /usr/bin/python; the backup refused
    the whole workspace. Such links are kept verbatim and never followed."""
    src=tmp_path/'src';(src/'.venv'/'bin').mkdir(parents=True)
    (src/'.venv'/'bin'/'python').symlink_to(link)
    (src/'file.txt').write_text('x')
    tar=tmp_path/'a.tar.gz';b.archive_directory(src,tar)
    out=tmp_path/'out';b.unpack(tar,out)
    restored=out/'.venv'/'bin'/'python'
    assert restored.is_symlink() and str(restored.readlink())==link
    assert (out/'file.txt').read_text()=='x'
    assert not (tmp_path/'outside').exists() and not (tmp_path/'x').exists()

@pytest.mark.parametrize('target',['safe','/ABS','../../escape'])
def test_member_below_any_symlink_is_refused(tmp_path,target):
    """The protection that matters: nothing is ever written through a link, wherever it points."""
    outside=tmp_path/'outside';outside.mkdir()
    p=tmp_path/'bad.tar.gz'
    with tarfile.open(p,'w:gz') as tf:
        link=tarfile.TarInfo('dir');link.type=tarfile.SYMTYPE;link.linkname=target.replace('/ABS',str(outside));tf.addfile(link)
        info=tarfile.TarInfo('dir/payload');info.size=1;tf.addfile(info,io.BytesIO(b'x'))
    with pytest.raises(c.SandboxError,match='through symlink'): b.unpack(p,tmp_path/'out')
    assert list(outside.iterdir())==[]

def test_link_and_file_with_the_same_name_refused(tmp_path):
    outside=tmp_path/'outside';outside.mkdir()
    p=tmp_path/'dup.tar.gz'
    with tarfile.open(p,'w:gz') as tf:
        link=tarfile.TarInfo('x');link.type=tarfile.SYMTYPE;link.linkname=str(outside/'pwned');tf.addfile(link)
        info=tarfile.TarInfo('x');info.size=1;tf.addfile(info,io.BytesIO(b'x'))
    with pytest.raises(c.SandboxError,match='Unsafe archive member'): b.unpack(p,tmp_path/'out')
    assert list(outside.iterdir())==[]

def test_symlink_target_with_nul_or_backslash_refused(tmp_path):
    p=tmp_path/'bs.tar.gz'
    with tarfile.open(p,'w:gz') as tf:
        link=tarfile.TarInfo('x');link.type=tarfile.SYMTYPE;link.linkname='a\\b';tf.addfile(link)
    with pytest.raises(c.SandboxError,match='Unsafe symlink target'): b.unpack(p,tmp_path/'out')
    src=tmp_path/'src';src.mkdir();(src/'x').symlink_to('a\\b')
    with pytest.raises(c.SandboxError,match='backslash'): b.archive_directory(src,tmp_path/'a.tar.gz')

def test_symlink_parent_archive_rejected(tmp_path):
    p=tmp_path/'bad.tar.gz'
    with tarfile.open(p,'w:gz') as tf:
        link=tarfile.TarInfo('dir');link.type=tarfile.SYMTYPE;link.linkname='safe';tf.addfile(link)
        info=tarfile.TarInfo('dir/payload');info.size=1;tf.addfile(info,io.BytesIO(b'x'))
    with pytest.raises(c.SandboxError,match='through symlink'): b.unpack(p,tmp_path/'out')

def test_prune_dry_run_and_keep(tmp_path):
    for i in range(3):
        p=tmp_path/f'{i}.ocsbackup';p.mkdir()
        (p/'manifest.json').write_text(json.dumps({'environment':{'name':'foo'}}))
        import os
        os.utime(p,(i+1,i+1))
    # manifests without checksummed files are not verifiable: never selected
    selected, skipped = b.prune(tmp_path,keep=1)
    assert selected == [] and len(skipped) == 3
    assert len(list(tmp_path.glob('*.ocsbackup')))==3


def _real_backup(tmp_path, name, mtime):
    """A verifiable backup built with the real archive helpers."""
    import os
    src = tmp_path / f"src-{name}-{mtime}"; src.mkdir(); (src / "f").write_text(name)
    d = tmp_path / "bk" / f"{name}-{mtime}.ocsbackup"; d.mkdir(parents=True)
    b.archive_directory(src, d / "workspace.tar.gz")
    (d / "manifest.json").write_text(json.dumps({"format": "opencode-sandbox-backup", "schema": b.SCHEMA,
        "created": f"2026-10-28T00:00:{mtime:02d}+00:00", "workspace": {"mode": "managed", "included": True},
        "environment": {"name": name}, "system_image": False,
        "files": {"workspace.tar.gz": {"sha256": b.digest(d / "workspace.tar.gz"), "size": (d / "workspace.tar.gz").stat().st_size}}}))
    os.utime(d, (mtime, mtime))
    return d


def test_prune_verifies_first_and_never_counts_corrupt_backups(tmp_path):
    """--yes deleted some backups, then aborted on an unverifiable one."""
    old = [_real_backup(tmp_path, "proj", t) for t in (1, 2, 3)]
    corrupt_newest = _real_backup(tmp_path, "proj", 9)
    (corrupt_newest / "workspace.tar.gz").write_bytes(b"garbage")
    other = _real_backup(tmp_path, "other", 5)
    fake = tmp_path / "bk" / "not-a-backup.ocsbackup"; fake.mkdir()
    (fake / "manifest.json").write_text('{"environment":{"name":"proj"}}')
    deleted = []
    selected, skipped = b.prune(tmp_path / "bk", keep=2, dry_run=False, on_delete=deleted.append)
    assert selected == deleted == [old[0]]                      # 2 newest VERIFIED kept
    assert {p for p, _ in skipped} == {corrupt_newest, fake}  # reported, never deleted
    assert all(p.exists() for p in (old[1], old[2], corrupt_newest, other, fake))

def test_restore_check_requires_ready(monkeypatch):
    monkeypatch.setattr(c,'resolve',lambda _: {'id':'abcd','status':'error'})
    with pytest.raises(c.SandboxError,match='not ready'): b.check_restored('abcd')

def test_restore_rollback_rejects_healthy(monkeypatch):
    monkeypatch.setattr(c,'resolve',lambda _: {'id':'abcd','status':'ready','operation':None})
    with pytest.raises(c.SandboxError,match='Not a failed'): b.rollback_restore('abcd')


def test_backup_does_not_repermission_existing_destination(tmp_path, monkeypatch):
    """Hypothesis 5: backup chmod-ed any --destination (e.g. ~/Public) to 0700."""
    import os

    from opencode_sandbox import backup as b
    from opencode_sandbox import core as c
    m = c.create("ocs-qa-dest", "scratch")
    for name, value in (("ensure_runtime", lambda image=True: None), ("inspect_container", lambda m: None),
                        ("assert_volume_owned", lambda m: None), ("volume_state", lambda m: None)):
        monkeypatch.setattr(c, name, value)
    shared = tmp_path / "Public"
    shared.mkdir(mode=0o755)
    os.chmod(shared, 0o755)
    target = b.backup(m, shared)
    assert shared.stat().st_mode & 0o777 == 0o755
    assert target.stat().st_mode & 0o777 == 0o700
    fresh = tmp_path / "new-dir"
    b.backup(m, fresh)
    assert fresh.stat().st_mode & 0o777 == 0o700
