"""Minimum/current Python gates; real Docker stays in the opt-in release campaign."""
import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("workflow", "job"), [
    ("ci", "tests"), ("ci", "package"), ("ci", "pipx"), ("release", "pipx-tag"),
])
def test_python_endpoints_run_tests_packaging_and_pipx(workflow, job):
    text = (ROOT / f".github/workflows/{workflow}.yml").read_text()
    # Split only at another job, not the indented job fields.
    section = re.split(r"\n  \S", text.split(f"\n  {job}:\n", 1)[1], maxsplit=1)[0]
    assert 'python: ["3.11", "3.14"]' in section
    assert "python-version: ${{ matrix.python }}" in section


def test_current_arch_and_lowest_direct_dependency_coverage_remain():
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "container: archlinux:base-devel" in text
    assert "pacman -Syu" in text and "su ci -c" in text
    assert "dependencies: [current, lowest direct]" in text
    assert "typer==0.16.0 textual==4.0.0" in text


def test_lowest_direct_dependency_pins_match_the_declared_project_bounds():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = {r.name: r for r in map(Requirement, project["dependencies"])}
    pins = dict(re.findall(r"\b(typer|textual)==([\d.]+)", (ROOT / ".github/workflows/ci.yml").read_text()))
    assert set(pins) == set(requirements)
    for name, requirement in requirements.items():
        lower, = [s.version for s in requirement.specifier if s.operator == ">="]
        assert Version(pins[name]) == Version(lower), name


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_ci_validates_stable_and_development_branches(event):
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    section = re.split(r"\n  \S", triggers.split(f"  {event}:\n", 1)[1], maxsplit=1)[0]
    assert "branches: [main, develop]" in section
    assert "pull_request_target:" not in triggers


def test_development_pushes_cannot_trigger_release_automation():
    text = (ROOT / ".github/workflows/release.yml").read_text()
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert triggers.strip() == 'push:\n    tags: ["v*"]'
    assert "permissions: {}" in text


def test_ubuntu_tests_copy_the_complete_python_runtime_without_changing_the_host_cache():
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    section = text.split("\n  tests:\n", 1)[1].split("\n  arch:\n", 1)[0]
    assert 'mktemp -d "$HOME/ocs-ci-python.XXXXXX"' in section
    assert 'cp -a "$pythonLocation/." "$private_python/"' in section
    assert 'chmod -R go-w "$private_python"' in section
    assert 'echo "$private_python/bin" >> "$GITHUB_PATH"' in section
    assert 'echo "pythonLocation=$private_python"' in section
    assert 'echo "LD_LIBRARY_PATH=$private_python/lib"' in section
    assert '} >> "$GITHUB_ENV"' in section
    assert r'patchelf --set-rpath "\$ORIGIN/../lib"' in section
    assert 'cp -a "$GITHUB_WORKSPACE/." "$private_project/"' in section
    assert 'chmod -R go-w "$private_project"' in section
    assert section.count('working-directory: ${{ env.OCS_CI_PROJECT }}') == 3
    assert "sudo" not in section and "/opt/hostedtoolcache" not in section


def test_arch_editable_source_has_owned_ancestors_and_controlled_modes():
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    section = text.split("\n  arch:\n", 1)[1].split("\n  package:\n", 1)[0]
    assert 'cp -a "$GITHUB_WORKSPACE" /home/ci/project' in section
    assert 'chown -R ci: /home/ci/project' in section
    assert 'chmod -R go-w /home/ci/project' in section
    assert 'umask 022 && cd /home/ci/project' in section
    assert 'chown -R ci: "$GITHUB_WORKSPACE"' not in section


def test_private_runtime_step_relocates_only_owned_copies_and_preserves_sources(tmp_path):
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    section = text.split('      - name: Private controlled Python runtime\n', 1)[1].split('      - name: Install\n', 1)[0]
    script = '\n'.join(line[10:] for line in section.split('        run: |\n', 1)[1].splitlines())
    source, home = tmp_path / 'hosted runtime', tmp_path / 'owned home'
    (source / 'bin').mkdir(parents=True)
    (source / 'lib').mkdir()
    home.mkdir(mode=0o700)
    binary, library = source / 'bin/python3', source / 'lib/stdlib.py'
    binary.write_bytes(b'owned executable fixture')
    library.write_bytes(b'owned stdlib fixture')
    (source / 'bin/python').symlink_to('python3')
    unrelated = tmp_path / 'unrelated'
    unrelated.write_bytes(b'not part of this runtime')
    unrelated.chmod(0o666)
    (source / 'outside-alias').symlink_to(unrelated)
    workspace = tmp_path / 'hosted checkout'
    workspace.mkdir()
    document = workspace / 'README.md'
    document.write_bytes(b'owned checkout fixture')
    workspace.chmod(0o777)
    document.chmod(0o666)
    for path in (source, source / 'bin', source / 'lib', binary):
        path.chmod(0o777)
    library.chmod(0o666)
    before = {path: (path.read_bytes(), path.stat().st_mode) for path in (binary, library, unrelated, document)}
    commands = tmp_path / 'commands'; commands.mkdir()
    arguments = tmp_path / 'patchelf-arguments'
    patchelf = commands / 'patchelf'
    # This shell-step contract uses data files, not a Python/ELF runtime. The actual hosted
    # Python's sanitized child startup is exercised separately; never mock a product guard.
    patchelf.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CI_PATCHELF_ARGS"\n'
                        'printf "\\nowned relocation\\n" >> "$3"\n')
    patchelf.chmod(0o700)
    paths, environment = tmp_path / 'github-path', tmp_path / 'github-env'
    subprocess.run(['bash', '-eu', '-c', script], check=True, capture_output=True, text=True,
                   env={**os.environ, 'HOME': str(home), 'pythonLocation': str(source),
                        'GITHUB_PATH': str(paths), 'GITHUB_ENV': str(environment),
                        'GITHUB_WORKSPACE': str(workspace), 'CI_PATCHELF_ARGS': str(arguments),
                        'PATH': str(commands) + os.pathsep + os.environ.get('PATH', os.defpath)})
    exports = dict(line.split('=', 1) for line in environment.read_text().splitlines())
    private = Path(exports['pythonLocation'])
    assert private.parent == home and private != source
    project = Path(exports['OCS_CI_PROJECT'])
    assert project.parent == home and project != workspace and project != private
    assert exports == {'pythonLocation': str(private), 'LD_LIBRARY_PATH': str(private / 'lib'),
                       'PKG_CONFIG_PATH': str(private / 'lib/pkgconfig'),
                       'OCS_CI_PROJECT': str(project),
                       **{name: str(private) for name in ('Python_ROOT_DIR', 'Python2_ROOT_DIR', 'Python3_ROOT_DIR')}}
    assert paths.read_text().splitlines() == [str(private / 'bin')]
    for path in (private, private / 'bin', private / 'lib', private / 'bin/python3', private / 'lib/stdlib.py'):
        assert path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o022
    assert arguments.read_text().splitlines() == ['--set-rpath', '$ORIGIN/../lib', str(private / 'bin/python3')]
    assert (private / 'bin/python3').read_bytes() == binary.read_bytes() + b'\nowned relocation\n'
    assert (private / 'lib/stdlib.py').read_bytes() == library.read_bytes()
    assert (private / 'bin/python').is_symlink() and (private / 'bin/python').readlink() == Path('python3')
    assert (private / 'outside-alias').is_symlink() and (private / 'outside-alias').readlink() == unrelated
    assert (project / 'README.md').read_bytes() == document.read_bytes()
    assert not project.stat().st_mode & 0o022 and not (project / 'README.md').stat().st_mode & 0o022
    assert before == {path: (path.read_bytes(), path.stat().st_mode) for path in before}


@pytest.mark.parametrize('dependencies', ['current', 'lowest direct'])
def test_install_controls_new_metadata_after_the_last_pip_call_without_changing_host_files(tmp_path, dependencies):
    from opencode_sandbox.manager_tool_probe import outside

    text = (ROOT / '.github/workflows/ci.yml').read_text()
    section = text.split('      - name: Install\n', 1)[1].split('      - name: External runtime prerequisite\n', 1)[0]
    script = '\n'.join(line[10:] for line in section.split('        run: |\n', 1)[1].splitlines())
    runtime, project, commands = (tmp_path / name for name in ('private runtime', 'private project', 'commands'))
    for path in (runtime, project, commands): path.mkdir()
    host = tmp_path / 'original host cache'
    host.write_bytes(b'host cache must not change')
    host.chmod(0o777)
    before = (host.read_bytes(), host.stat().st_mode)
    installer = commands / 'python'
    installer.write_text('''#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$CI_INSTALL_ARGUMENTS"
case "$3" in
install)
  mkdir -p "$pythonLocation/lib/python3/site-packages/packaging-26.3.dist-info" "$OCS_CI_PROJECT/src/product.egg-info"
  chmod 777 "$pythonLocation/lib/python3/site-packages/packaging-26.3.dist-info" "$OCS_CI_PROJECT/src/product.egg-info"
  echo 777 >> "$CI_INSTALL_RECORD"
  ;;
list) echo "typer 0.27.3" ;;
esac
''')
    installer.chmod(0o700)
    record = tmp_path / 'install-record'
    arguments = tmp_path / 'install-arguments'
    subprocess.run(['bash', '-eu', '-c', script], check=True, capture_output=True, text=True,
                   env={**os.environ, 'pythonLocation': str(runtime), 'OCS_CI_PROJECT': str(project),
                        'GITHUB_WORKSPACE': str(host), 'DEPENDENCIES': dependencies,
                         'CI_INSTALL_RECORD': str(record), 'CI_INSTALL_ARGUMENTS': str(arguments),
                         'PATH': str(commands) + os.pathsep + os.defpath})
    installs = [line for line in arguments.read_text().splitlines() if line.startswith('-m pip install ')]
    project_install, = [line for line in installs if '.[test]' in line]
    assert ('typer==0.16.0 textual==4.0.0' in project_install) is (dependencies == 'lowest direct')
    assert not any('typer==' in line and '.[test]' not in line for line in installs)
    assert record.read_text().splitlines() == ['777', '777']
    target = tmp_path / 'application-home/venvs/opencode-sandbox'
    for metadata in (runtime / 'lib/python3/site-packages/packaging-26.3.dist-info', project / 'src/product.egg-info'):
        assert outside(str(metadata), target) == str(metadata)
        assert not metadata.stat().st_mode & 0o022
    assert (host.read_bytes(), host.stat().st_mode) == before
