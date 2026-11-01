"""Frozen installed-result filesystem verification; never infer success from installer exit/code.

Runtime and fixed CLI-help checks are separate fresh processes. These metadata/launcher checks
are not cryptographic authentication of installed code and do not execute launchers as text.
"""
import configparser
import csv
import io
import os
import re
import shlex
import stat
from email.parser import BytesParser
from pathlib import Path

if __package__:
    from . import manager_observations as observations
    from . import manager_records as records
    from . import manager_source as source
else:
    import manager_observations as observations
    import manager_records as records
    import manager_source as source


class Refused(RuntimeError):
    pass


def _json(path):
    value = observations.parse(observations.read_record(path))
    if not isinstance(value, dict): raise Refused('Expected an installed-result JSON record')
    return value


def _launcher(app, python, entry):
    raw = observations.read_record(app).decode('utf-8')
    if app.is_symlink() or not os.access(app, os.X_OK): raise Refused('Installed application script is redirected or not executable')
    body = ('import sys\nfrom ' + entry.rsplit(':', 1)[0] + ' import main\n'
            "if __name__ == '__main__':\n    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n    sys.exit(main())\n")
    if any(char in str(python) for char in "\"'$`\\\n\r"): raise Refused('Installed launcher interpreter quoting is unsupported')
    # Long-path launchers are shell trampolines. A metacharacter-bearing path must be quoted
    # even without spaces; recognizing an unquoted standard-looking script is not shell safety.
    quoted = '"' + str(python) + '"' if shlex.quote(str(python)) != str(python) else str(python)
    templates = ['#!/bin/sh\n' + "'''exec' " + quoted + ' "$0" "$@"\n' + "' '''\n" + body]
    if len(os.fsencode(str(python))) + 3 <= 127 and not any(ch.isspace() for ch in str(python)):
        templates.append('#!' + str(python) + '\n' + body)
    if raw not in templates:
        raise Refused('Installed launcher is not the exact recognized template/interpreter')


def inspect(prefix, settings, expected, *, python_version):
    """Fresh source/tag/commit/version/pipx/launcher/default-settings agreement, with no imports.

    The entire manager RECORD must stay within its own prefix, including symlink routes, before
    any future pip uninstall may use it. Do not traverse or normalize foreign metadata.
    """
    prefix = records.path(str(prefix))
    if not isinstance(expected, dict) or set(expected) != {'version', 'tag', 'commit', 'source'} \
            or not isinstance(expected['commit'], str) or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', expected['commit']):
        raise Refused('Expected installed source identity is invalid')
    if prefix.resolve() != prefix or prefix.name != records.NAME or prefix.parent.name != 'venvs' \
            or Path(settings['PIPX_HOME']) / 'venvs' / records.NAME != prefix \
            or source.version(expected['tag']) != expected['version'] or expected['source'] != source.REPOSITORY + '.git':
        raise Refused('Installed-result prefix/source identity is invalid')
    for path in (prefix, prefix.parent, prefix.parent.parent, Path(settings['PIPX_BIN_DIR'])):
        observations.route(path)
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise Refused('Installed-result directories are not controlled by this user')
    found = list(prefix.glob('lib/python*/site-packages/opencode_sandbox-*.dist-info'))
    if len(found) != 1: raise Refused('Installed distribution is missing or ambiguous')
    dist = found[0]
    observations.route(dist)
    if dist.resolve() != dist: raise Refused('Installed distribution metadata is redirected')
    meta = BytesParser().parsebytes(observations.read_record(dist / 'METADATA'))
    if meta.get_all('Name') != [records.NAME] or meta.get_all('Version') != [expected['version']]:
        raise Refused('Installed distribution name/version differs from the expected result')
    direct = _json(dist / 'direct_url.json')
    if direct != {'url': expected['source'], 'vcs_info': {'vcs': 'git', 'requested_revision': expected['tag'], 'commit_id': expected['commit']}}:
        raise Refused('Installed PEP 610 source/tag/commit differs from the expected result')
    record = _json(prefix / 'pipx_metadata.json')
    package = records.settings(record)
    app, python = prefix / 'bin' / records.NAME, prefix / 'bin/python'
    if package.get('package') != records.NAME or package.get('package_version') != expected['version'] \
            or package.get('package_or_url') != 'git+' + expected['source'] + '@' + expected['tag'] or package.get('apps') != [records.NAME] \
            or not isinstance(package.get('app_paths'), list) or len(package['app_paths']) != 1 or records.path(package['app_paths'][0]) != app \
            or str(records.path(record.get('source_interpreter'))) != settings['PIPX_DEFAULT_PYTHON'] \
            or record.get('python_version') != python_version or not python.samefile(settings['PIPX_DEFAULT_PYTHON']):
        raise Refused('Installed pipx source/version/Python/executable/settings disagree')
    config = configparser.ConfigParser(interpolation=None)
    try: config.read_string('[venv]\n' + observations.read_record(prefix / 'pyvenv.cfg').decode())
    except configparser.Error: raise Refused('Installed Python environment configuration is invalid') from None
    if config.get('venv', 'include-system-site-packages', fallback='') != 'false' \
            or config.get('venv', 'version', fallback='') != python_version.removeprefix('Python ') \
            or not records.path(config.get('venv', 'executable', fallback='')).samefile(settings['PIPX_DEFAULT_PYTHON']):
        raise Refused('Installed Python environment changed its source/version/isolation')
    if app.resolve() != app or python.parent.resolve() != prefix / 'bin': raise Refused('Installed executable paths are redirected')
    entries = observations.read_record(dist / 'entry_points.txt').decode()
    parser = configparser.ConfigParser(interpolation=None)
    try: parser.read_string(entries)
    except configparser.Error: raise Refused('Installed console entry point data is invalid') from None
    entry = parser.get('console_scripts', records.NAME, fallback='')
    if set(parser.sections()) != {'console_scripts'} or set(parser['console_scripts']) != {records.NAME} \
            or entry not in ('opencode_sandbox.launcher:main', 'opencode_sandbox.cli:main'):
        raise Refused('Installed console entry point is unsupported')
    _launcher(app, python, entry)
    launcher = Path(settings['PIPX_BIN_DIR']) / records.NAME
    observations.route(launcher)
    if not launcher.is_symlink() or launcher.resolve() != app: raise Refused('Exposed launcher is missing or foreign')
    rows = list(csv.reader(io.StringIO(observations.read_record(dist / 'RECORD').decode('utf-8')), strict=True))
    if not rows or len(rows) > 8192 or any(len(row) != 3 or not row[0] for row in rows):
        raise Refused('Installed manager file inventory is missing, invalid or excessive')
    inventory = set()
    for name, _, _ in rows:
        path = dist.parent / name
        observations.route(path)
        resolved = path.resolve()
        if not resolved.is_relative_to(prefix): raise Refused('Installed manager inventory escapes its prefix')
        inventory.add(resolved)
    module = dist.parent / 'opencode_sandbox/__init__.py'
    if module.resolve() != module: raise Refused('Installed package module is redirected')
    if not {module, app, dist / 'METADATA', dist / 'RECORD', dist / 'direct_url.json', dist / 'entry_points.txt'} <= inventory:
        raise Refused('Installed manager critical inventory is incomplete')
    return {'version': expected['version'], 'prefix': str(prefix), 'module': str(module),
            'distribution': str(dist), 'launcher': str(launcher), 'commit': expected['commit']}


def verify(locks, prefix, settings, expected, *, python_version, deadline):
    """Verify exact installed files plus separate fresh runtime and CLI-help construction.

    No ordinary CLI entry is called or exempted. This returns facts only; the lock owner must
    separately prove installer quiescence before it may close an authoritative operation record.
    """
    if __package__:
        from . import manager_health, manager_verifier
    else:
        import manager_health
        import manager_verifier
    with locks._verification(prefix) as (witness, owner_fd): locks._verify_descriptor(witness, os.getpid(), owner_fd, prefix)
    before = inspect(prefix, settings, expected, python_version=python_version)
    runtime = manager_verifier.run(locks, prefix, deadline=deadline)
    if runtime != {key: before[key] for key in ('prefix', 'module', 'version')}:
        raise Refused('Fresh runtime does not match the expected installed result')
    health = manager_health.run(locks, prefix, deadline=deadline)
    if health != {'version': expected['version'], 'prefix': str(prefix), 'cli_help': True}:
        raise Refused('Fresh CLI-health query does not match the expected installed result')
    if inspect(prefix, settings, expected, python_version=python_version) != before:
        raise Refused('Installed result changed during fresh verification')
    with locks._verification(prefix) as (witness, owner_fd): locks._verify_descriptor(witness, os.getpid(), owner_fd, prefix)
    return before
