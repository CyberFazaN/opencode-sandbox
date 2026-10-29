import os

import pytest

from opencode_sandbox import core as c


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(c,"BASE",tmp_path/"data")
    monkeypatch.setattr(c,"CONFIG",tmp_path/"config")

def test_create_scratch_and_promote():
    m=c.create("scratch","quick")
    assert c.resolve(m["id"])["kind"]=="quick"
    c.promote(m,"scratch","persistent")
    assert c.resolve("persistent")["kind"]=="scratch"
    assert (c.env_dir(m["id"])/"workspace").is_dir()

def test_duplicate_names_are_rejected_and_legacy_duplicates_stay_resolvable():
    """Duplicate names made every name-based command fail."""
    first=c.create("backend","scratch")
    with pytest.raises(c.SandboxError,match="already exists"): c.create("backend","scratch")
    other=c.create("other","scratch")
    with pytest.raises(c.SandboxError,match="already exists"): c.promote(other,"scratch","backend")
    # Legacy duplicates created by older versions: name is ambiguous, ID still works.
    legacy=dict(first,id="f"*16); c.save(legacy)
    with pytest.raises(c.SandboxError,match="ambiguous"): c.resolve("backend")
    assert c.resolve("f"*16)["name"]=="backend"

def test_non_git_copy_excludes_hidden_and_symlinks(tmp_path):
    src=tmp_path/"source"; src.mkdir()
    (src/"file.py").write_text("ok")
    (src/".env").write_text("SECRET")
    (src/"link").symlink_to(src/".env")
    m=c.create("test","project",src)
    w=c.env_dir(m["id"])/"workspace"
    assert (w/"file.py").read_text()=="ok"
    assert not (w/".env").exists()
    assert not (w/"link").exists()

def test_profile_permissions_and_redaction():
    c.profile_set("default",{"OPENAI_API_KEY":"sensitive secret"})
    p=c.profile_path("default")
    assert p.stat().st_mode & 0o777==0o600
    assert c.profile_keys("default")==["OPENAI_API_KEY"]
    assert "sensitive secret" not in str(c.profile_keys("default"))

def test_git_committed_and_untracked_export(tmp_path):
    repo=tmp_path/"repo"; repo.mkdir()
    def git(*args): return c.call(["git","-C",repo,*args],capture=True)
    git("init"); git("config","user.email","test@example.org"); git("config","user.name","Test")
    (repo/"main.txt").write_text("one\n")
    git("add","."); git("commit","-m","initial")
    m=c.create("repo","project",repo)
    w=c.env_dir(m["id"])/"workspace"
    c.call(["git","-C",w,"config","user.email","test@example.org"])
    c.call(["git","-C",w,"config","user.name","Test"])
    (w/"main.txt").write_text("two\n")
    c.call(["git","-C",w,"add","main.txt"])
    c.call(["git","-C",w,"commit","-m","updated"])
    (w/"new.txt").write_text("new")
    out=c.export(m,tmp_path/"exports")
    import tarfile
    with tarfile.open(out) as tf:
        assert "changes.patch" in tf.getnames()
        assert "untracked/new.txt" in tf.getnames()
        assert b"+two" in tf.extractfile("changes.patch").read()

def test_recreate_requires_acknowledgement():
    m=c.create("x","scratch")
    with pytest.raises(c.SandboxError,match="apt"): c.recreate(m)

def test_import_errors_are_actionable(tmp_path):
    """Empty repo, repo subdirectory and missing source give clear errors, leave nothing behind."""
    empty=tmp_path/"empty"; empty.mkdir(); c.call(["git","-C",empty,"init","-q"])
    with pytest.raises(c.SandboxError,match="no commits"): c.create("e","project",empty)
    repo=tmp_path/"repo"; (repo/"sub").mkdir(parents=True); c.call(["git","-C",repo,"init","-q"])
    (repo/"sub"/"f").write_text("x")
    c.call(["git","-C",repo,"add","-A"]); c.call(["git","-C",repo,"-c","user.email=q@x","-c","user.name=q","commit","-qm","i"])
    with pytest.raises(c.SandboxError,match="repository root"): c.create("s","project",repo/"sub")
    with pytest.raises(c.SandboxError,match="not accessible"): c.create("m","project",tmp_path/"missing")
    assert c.all_envs()==[]

def test_non_git_import_skips_special_files(tmp_path):
    src=tmp_path/"src"; (src/"sub").mkdir(parents=True)
    (src/"sub"/"ok.txt").write_text("ok"); os.mkfifo(src/"sub"/"pipe"); os.mkfifo(src/"toplevel-pipe")
    m=c.create("fifo","project",src)
    w=c.env_dir(m["id"])/"workspace"
    assert (w/"sub"/"ok.txt").read_text()=="ok"
    assert not (w/"sub"/"pipe").exists() and not (w/"toplevel-pipe").exists()
