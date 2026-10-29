from opencode_sandbox import core as c


def test_provider_profile_does_not_execute_shell_substitutions(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "BASE", tmp_path / "data")
    monkeypatch.setattr(c, "CONFIG", tmp_path / "config")
    marker = tmp_path / "executed"
    payload = f"$(touch {marker})"
    c.profile_set("probe", {"OPENAI_API_KEY": payload})
    path = c.profile_path("probe")
    assert c.profile_read("probe")["OPENAI_API_KEY"] == payload
    assert not marker.exists() and path.stat().st_mode & 0o777 == 0o600

def test_profile_handles_single_quote_and_dollar(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "BASE", tmp_path / "data")
    monkeypatch.setattr(c, "CONFIG", tmp_path / "config")
    value = "a'b $HOME `id` \u263a"
    c.profile_set("probe", {"OPENAI_API_KEY": value})
    assert c.profile_read("probe")["OPENAI_API_KEY"] == value

def test_non_git_import_ignores_nested_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "BASE", tmp_path / "data")
    monkeypatch.setattr(c, "CONFIG", tmp_path / "config")
    source = tmp_path / "source"
    (source / "sub").mkdir(parents=True)
    (source / "sub" / "safe.txt").write_text("ok")
    external = tmp_path / "secret.txt"
    external.write_text("private")
    (source / "sub" / "leak.txt").symlink_to(external)
    m = c.create("imported", source=source)
    workspace = c.env_dir(m["id"]) / "workspace"
    assert (workspace / "sub" / "safe.txt").read_text() == "ok"
    assert not (workspace / "sub" / "leak.txt").exists()
