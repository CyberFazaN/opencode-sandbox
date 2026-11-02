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
