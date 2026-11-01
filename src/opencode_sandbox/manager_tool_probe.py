"""Standalone external-interpreter diagnostic, sent as source to -I -c; no product imports.

Only the inspected pipx 1.18.7 --version path is executed. No list, environment, install, Python
download or pipx metadata normalization. This is prerequisite evidence, never a helper/executor.
"""
import csv
import hashlib
import io
import json
import os
import re
import runpy
import stat
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

VERSION = '1.18.7'


class Refused(RuntimeError):
    pass


def path(value):
    if not isinstance(value, str) or not Path(value).is_absolute() or any(not ch.isprintable() for ch in value):
        raise Refused('External-tool evidence has an invalid absolute path')
    return Path(value)


def controlled(value, target):
    nominal = path(str(value)).absolute()
    if nominal.is_relative_to(target): raise Refused('External tool or interpreter belongs to the replaceable installation')
    resolved = Path(outside(str(nominal), target))
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.getuid()) or info.st_mode & 0o022 or not os.access(resolved, os.X_OK):
        raise Refused('External tool/interpreter is not a controlled executable regular file')
    return resolved, [str(resolved), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def launcher(value, target):
    resolved, identity = controlled(value, target)
    fd = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8192: raise Refused('External pipx launcher is not a bounded standard console script')
        raw = stream.read(8193)
    lines = raw.decode('utf-8').splitlines()
    if not lines: raise Refused('External pipx launcher is empty')
    if lines[0] == '#!/bin/sh' and len(lines) >= 3 and lines[2] == "' '''":
        match = re.fullmatch(r"'''exec' (?:\"([^\"$`\\]+)\"|([^\s\"$`\\]+)) \"\$0\" \"\$@\"", lines[1])
        if not match: raise Refused('External pipx shell trampoline is unrecognized; it was not evaluated')
        python, body = path(match[1] or match[2]), lines[3:]
    else:
        if not lines[0].startswith('#!') or any(char.isspace() for char in lines[0][2:]):
            raise Refused('External pipx interpreter/shebang is ambiguous; no PATH Python inference')
        python, body = path(lines[0][2:]), lines[1:]
    if body != ['import sys', 'from pipx.__main__ import cli', "if __name__ == '__main__':",
                "    sys.argv[0] = sys.argv[0].removesuffix('.exe')", '    sys.exit(cli())']:
        raise Refused('External pipx console template is unrecognized; no wrapper execution')
    return python, [*identity, hashlib.sha256(raw).hexdigest()]


def outside(path, target):
    if not path or not Path(path).is_absolute(): raise Refused('External runtime has an ambiguous search or origin path')
    # Check the whole symlink route, not just its endpoint: an outside alias through the target
    # to a shared Python binary would still break when the target venv is replaced/absent.
    pending, current, links, route = list(Path(path).parts[1:]), Path('/'), 0, set()
    while pending:
        part = pending.pop(0)
        if part == '..': current = current.parent; continue
        route.add(current)
        current /= part
        if current.is_relative_to(target): raise Refused('External runtime depends on the replaceable installation')
        if current.is_symlink():
            if current.lstat().st_uid not in (0, os.getuid()):
                raise Refused('External runtime has unsafe ownership or writable paths')
            links += 1
            if links > 40: raise Refused('External runtime has a cyclic or excessive symlink route')
            link = Path(os.readlink(current))
            pending = list(link.parts[1:] if link.is_absolute() else link.parts) + pending
            current = Path('/') if link.is_absolute() else current.parent
    for item in {*route, current, *current.parents}:
        try: info = item.stat()
        except (FileNotFoundError, NotADirectoryError): continue  # optional zip/record paths may not exist
        if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and
                not (stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
            raise Refused('External runtime has unsafe ownership or writable paths')
    return str(current)


def inventory_files(dist, target):
    # CPython 3.14's Distribution.files silently filters missing RECORD entries. We must inspect
    # declared paths even while the target is absent, not infer independence from that filter.
    # Only known filesystem dist-info is supported, never an egg/source/provider guess.
    directory = getattr(dist, '_path', None)
    if not isinstance(directory, Path) or not directory.name.endswith('.dist-info'):
        raise Refused('External dependency metadata format is unsupported')
    record = Path(outside(str(directory / 'RECORD'), target))
    fd = os.open(record, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.getuid()) or info.st_mode & 0o022 or info.st_size > 524288:
            raise Refused('External dependency file inventory is unsafe or too large')
        raw = stream.read(524289)
    if len(raw) > 524288: raise Refused('External dependency file inventory is too large')
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8')), strict=True))
    if not rows or len(rows) > 8192 or any(len(row) != 3 or not row[0] for row in rows):
        raise Refused('External dependency file inventory is missing, invalid or too large')
    return [outside(dist.locate_file(row[0]), target) for row in rows]


def main():
    mode, target, *args = sys.argv[1:]
    target = Path(target).resolve()
    if sys.version_info < (3, 11) or not sys.flags.isolated:
        raise Refused('External helper interpreter must support isolated Python 3.11 or newer')
    # A venv interpreter may resolve to an external binary while retaining an unsafe prefix.
    # Check both its lexical executable and all runtime/search/stdlib locations.
    outside(sys.executable, target)
    if Path(sys.executable).absolute().is_relative_to(target): raise Refused('Interpreter belongs to the replaceable installation')
    runtime = {'python': str(Path(sys.executable).absolute()), 'prefix': outside(sys.prefix, target),
               'base_prefix': outside(sys.base_prefix, target), 'stdlib': outside(sysconfig.get_path('stdlib'), target),
               'version': list(sys.version_info[:3])}
    for path in sys.path: outside(path, target)
    if mode == 'stdlib':
        if not sys.flags.no_site: raise Refused('Helper interpreter probe must disable site initialization')
        print(json.dumps({'ok': True, 'runtime': runtime}))
        return
    if mode != 'pipx' or len(args) != 1: raise Refused('Invalid external probe mode')
    candidate = Path(args[0])
    # Match the standard console interpreter's script-directory search as well as -I's paths.
    sys.path.insert(0, outside(candidate.resolve().parent, target))
    pipx = metadata.distribution('pipx')
    if pipx.version != VERSION: raise Refused('Only the inspected pipx 1.18.7 runtime is supported')
    points = [(entry.name, entry.value) for entry in pipx.entry_points if entry.group == 'console_scripts']
    if points != [('pipx', 'pipx.__main__:cli')]: raise Refused('External pipx entry point is unrecognized')
    # packaging is an existing pipx dependency, not a new manager/helper dependency. Evaluate
    # Linux/default-extra requirements rather than silently dropping marker-qualified deps.
    from packaging.requirements import Requirement
    pending, seen, roots, inventory = ['pipx'], set(), {}, []
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        if len(seen) > 64: raise Refused('External dependency graph exceeds its diagnostic bound')
        dist = metadata.distribution(name)
        roots[name] = {'version': dist.version, 'root': outside(dist.locate_file(''), target)}
        inventory.extend(inventory_files(dist, target))
        if len(inventory) > 16384: raise Refused('External dependency graph exceeds its diagnostic bound')
        for text in dist.requires or []:
            requirement = Requirement(text)
            if requirement.marker is not None and not requirement.marker.evaluate({'extra': ''}): continue
            dependency = metadata.distribution(requirement.name)
            if not requirement.specifier.contains(dependency.version, prereleases=True):
                raise Refused('External pipx dependency versions do not satisfy their records')
            pending.append(requirement.name)
    # Use the actual recognized script and only its fixed --version argv. pipx 1.18.7 exits here
    # before setup_logging, directory creation, listing locks and metadata normalization.
    sys.argv = [str(candidate), '--version']
    try: runpy.run_path(str(candidate), run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (0, None): raise Refused('External pipx version check failed') from None
    from pipx import paths
    from pipx.interpreter import get_default_python
    locations = {key: str(Path(value).resolve()) for key, value in {
        'PIPX_HOME': paths.ctx.home, 'PIPX_BIN_DIR': paths.ctx.bin_dir, 'PIPX_MAN_DIR': paths.ctx.man_dir,
        'PIPX_COMPLETION_DIR': paths.ctx.completion_dir, 'PIPX_SHARED_LIBS': paths.ctx.shared_libs,
        'PIPX_DEFAULT_PYTHON': get_default_python()}.items()}
    if any(locations.get(key) != str(Path(os.environ[key]).resolve()) for key in locations):
        raise Refused('External pipx does not preserve the recognized locations or Python selection')
    origins = set()
    for module in tuple(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path: origins.add(outside(path, target))
        for path in getattr(module, '__path__', ()): outside(path, target)
    for path in sys.path: outside(path, target)
    print(json.dumps({'ok': True, 'runtime': runtime, 'pipx_version': VERSION, 'locations': locations,
                      'dependencies': roots, 'origins': sorted(origins),
                      'inventory_sha256': hashlib.sha256(json.dumps(sorted(inventory)).encode()).hexdigest()}))


if __name__ == '__main__':
    try: main()
    except Refused as exc:
        print(json.dumps({'ok': False, 'reason': str(exc)}))
    except (OSError, ValueError, TypeError, KeyError, ImportError, AttributeError, RecursionError) as exc:
        # Never expose metadata/URL/environment/import diagnostics, which may contain secrets.
        print(json.dumps({'ok': False, 'reason': 'External runtime inspection failed (' + type(exc).__name__ + ')'}))
