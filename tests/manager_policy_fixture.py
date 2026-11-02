"""Test-owned system-configuration filenames, never a product override or installer input."""
from pathlib import Path

SYSTEM_CONFIGS = ('/etc/gitconfig', '/usr/etc/gitconfig', '/etc/pip.conf')


def system_paths(root):
    assert root.is_absolute()
    return tuple(str(root / name.lstrip('/')) for name in SYSTEM_CONFIGS)


def system_source(raw, paths):
    """Relocate only this constant in a fixture-owned source copy; preserve every check."""
    assert len(paths) == len(SYSTEM_CONFIGS) and all(Path(value).is_absolute() for value in paths)
    header = ('SYSTEM_CONFIGS = ' + repr(SYSTEM_CONFIGS)).encode()
    assert raw.count(header) == 1
    return raw.replace(header, ('SYSTEM_CONFIGS = ' + repr(tuple(paths))).encode())


def git_wrapper(path, python, git, system):
    """Execute real Git with an owned system-config namespace, respecting explicit policy."""
    assert all(Path(value).is_absolute() for value in (path, python, git, system))
    path.write_text(f'#!{python}\nimport os,sys\n'
                    'environment=dict(os.environ)\n'
                    f'environment.setdefault("GIT_CONFIG_SYSTEM",{str(system)!r})\n'
                    f'os.execve({str(git)!r},[{str(git)!r},*sys.argv[1:]],environment)\n')
    path.chmod(0o700)
