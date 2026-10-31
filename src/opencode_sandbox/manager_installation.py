"""Local-only, conservative pipx provenance classification; never runs pipx or changes an install.

This is a dated inspection, not mutation authority. Exclusion, independent updater prerequisites,
source-commit resolution and execution-time revalidation belong to the later handoff gate.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
from importlib import metadata
from pathlib import Path

from . import __version__
from . import core as c
from . import manager_releases as releases

NAME = 'opencode-sandbox'
URL = releases.REPOSITORY + '.git'
LIMIT = 131072
GUIDANCE = ('No installation was changed. Follow docs/install.md for your existing installation. '
            'Inspect command -v opencode-sandbox and pipx list yourself; resolve foreign/shadowed '
            'launchers before any manual replacement. Do not delete a launcher or use force as ownership proof.')


def _read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022 or info.st_size > LIMIT:
            raise c.SandboxError('Installation evidence is unsafe, not owned by this user, or too large')
        raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT: raise c.SandboxError('Installation evidence is too large')
    return raw


def _json(path):
    value = json.loads(_read(path))
    if not isinstance(value, dict): raise c.SandboxError('Installation evidence must be a JSON object')
    return value


def _path(value):
    if isinstance(value, dict) and set(value) == {'__type__', '__Path__'} and value.get('__type__') == 'Path': value = value['__Path__']
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or any(ord(x) < 32 for x in value):
        raise c.SandboxError('Installation evidence has an invalid absolute path')
    return Path(value)


def _own_directory(path):
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise c.SandboxError('Installation directories are not privately controlled by this user')


def _location(name, default):
    value = os.environ.get(name)
    path = Path(value).expanduser() if value else default
    if not path.is_absolute(): raise c.SandboxError('Relative pipx locations are ambiguous; manual review required')
    return path.resolve()


def _source(direct):
    if direct.get('dir_info', {}).get('editable'): raise c.SandboxError('Editable development installation; use your development workflow')
    if direct.get('url') != URL: raise c.SandboxError('Foreign or non-GitHub source; no automatic installation conversion')
    vcs = direct.get('vcs_info')
    if not isinstance(vcs, dict) or vcs.get('vcs') != 'git': raise c.SandboxError('Official Git VCS evidence is missing')
    tag, commit = vcs.get('requested_revision'), vcs.get('commit_id')
    if releases.version(tag) != __version__: raise c.SandboxError('Installed release tag and running package version disagree')
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise c.SandboxError('Installed VCS commit identity is missing or invalid')
    return tag, commit


def _settings(record):
    # Explicitly recognized pipx 0.5/0.6 and current 0.12 wire formats, with conservative defaults
    # for additive fields. Unknown fields/settings are unsupported, not silently dropped.
    allowed = {'main_package', 'python_version', 'source_interpreter', 'venv_args', 'injected_packages',
               'pipx_metadata_version', 'backend', 'environment', 'exposure_enabled', 'pinned'}
    if set(record) - allowed or record.get('pipx_metadata_version') not in ('0.5', '0.6', '0.12'):
        raise c.SandboxError('Unrecognized pipx metadata/settings; preservation cannot be proved')
    if record.get('venv_args') != [] or record.get('injected_packages') != {} or record.get('backend', 'pip') != 'pip' \
            or record.get('environment') not in (None, NAME) or record.get('exposure_enabled', True) is not True or record.get('pinned', False) is not False:
        raise c.SandboxError('Custom pipx venv/backend/injections/pin/exposure settings require manual preservation')
    package = record.get('main_package')
    if not isinstance(package, dict): raise c.SandboxError('Missing pipx main package evidence')
    expected = {'package', 'package_or_url', 'pip_args', 'include_dependencies', 'include_apps', 'apps', 'app_paths',
                'apps_of_dependencies', 'app_paths_of_dependencies', 'package_version', 'suffix', 'pinned',
                'expected_apps', 'lock_file', 'include_resources_from', 'include_apps_from', 'cooldown_days',
                'man_pages', 'man_paths', 'man_pages_of_dependencies', 'man_paths_of_dependencies',
                'completions', 'completion_paths', 'completions_of_dependencies', 'completion_paths_of_dependencies'}
    if set(package) - expected: raise c.SandboxError('Unrecognized pipx package settings; preservation cannot be proved')
    defaults = {'pip_args': [], 'include_dependencies': False, 'include_apps': True, 'suffix': '', 'pinned': False,
                'expected_apps': [], 'lock_file': None,
                'include_resources_from': [], 'include_apps_from': [], 'cooldown_days': None,
                'man_pages': [], 'man_paths': [], 'man_pages_of_dependencies': [], 'man_paths_of_dependencies': {},
                'completions': [], 'completion_paths': [], 'completions_of_dependencies': [], 'completion_paths_of_dependencies': {}}
    if any(package.get(key, value) != value for key, value in defaults.items()):
        raise c.SandboxError('Custom pipx package options/resources/pins require manual preservation (values not displayed)')
    if package.get('pip_args') != [] or package.get('include_dependencies') is not False or package.get('include_apps') is not True:
        raise c.SandboxError('Required pipx installation settings are missing or unsupported')
    if not isinstance(package.get('apps_of_dependencies', []), list) or not isinstance(package.get('app_paths_of_dependencies', {}), dict):
        raise c.SandboxError('Invalid dependency inventory in pipx metadata')
    return package


def _running_distribution():
    import opencode_sandbox
    module = Path(opencode_sandbox.__file__).resolve()
    matches = [d for d in metadata.distributions() if re.sub('[-_.]+', '-', d.metadata.get('Name', '')).lower() == NAME]
    if len(matches) != 1: raise c.SandboxError('Running distribution is missing or ambiguous (multiple metadata records)')
    dist = matches[0]
    if dist.version != __version__: raise c.SandboxError('Distribution version differs from running package')
    files = dist.files or []
    roots = [Path(dist.locate_file(p)).parent for p in files if str(p).endswith('.dist-info/METADATA')]
    if len(roots) != 1: raise c.SandboxError('Distribution metadata location is ambiguous')
    points = [(ep.name, ep.value) for ep in dist.entry_points if ep.group == 'console_scripts']
    if points not in ([(NAME, 'opencode_sandbox.cli:main')], [(NAME, 'opencode_sandbox.launcher:main')]):
        raise c.SandboxError('Distribution console entry point is unexpected')
    return module, roots[0]


def classify():
    """Return safe local evidence/reason even when remote discovery is offline. No cached grant."""
    result = {'version': __version__, 'at': time.time(), 'classification': 'manual review', 'verified': False,
              'reason': '', 'guidance': GUIDANCE, 'execution': 'Unavailable: handoff/replacement gates are not implemented'}
    try:
        module, dist = _running_distribution()
        direct = _json(dist / 'direct_url.json')
        tag, commit = _source(direct)
        if module != dist.parent / 'opencode_sandbox/__init__.py':
            raise c.SandboxError('Running package is shadowed by another source tree')
        prefix = Path(sys.prefix).resolve()
        if sys.prefix == sys.base_prefix or prefix.parent.name != 'venvs' or prefix.name != NAME:
            raise c.SandboxError('Not the recognized standalone pipx application venv')
        if not module.is_relative_to(prefix) or not dist.resolve().is_relative_to(prefix):
            raise c.SandboxError('Package/distribution is outside the running venv')
        for path in (prefix, prefix.parent, prefix.parent.parent, dist): _own_directory(path)
        executable = Path(sys.executable).absolute()
        if executable.parent.resolve() != prefix / 'bin' or not executable.samefile(prefix / 'bin/python'):
            raise c.SandboxError('Running interpreter does not match this venv')
        record_path = prefix / 'pipx_metadata.json'
        raw = _read(record_path)
        record = json.loads(raw)
        if not isinstance(record, dict): raise c.SandboxError('Invalid pipx metadata')
        package = _settings(record)
        if package.get('package') != NAME or package.get('package_version') != __version__ \
                or package.get('package_or_url') != 'git+' + URL + '@' + tag or package.get('apps') != [NAME]:
            raise c.SandboxError('pipx recorded source/tag/package does not match the running distribution')
        app = prefix / 'bin' / NAME
        if not app.is_file() or not os.access(app, os.X_OK) or app.is_symlink():
            raise c.SandboxError('Application executable is missing, redirected or not executable')
        app_paths = package.get('app_paths')
        if not isinstance(app_paths, list) or len(app_paths) != 1 or _path(app_paths[0]) != app:
            raise c.SandboxError('pipx recorded executable is not this venv application')
        source_python = _path(record.get('source_interpreter'))
        if not source_python.samefile(sys._base_executable):
            raise c.SandboxError('pipx source interpreter and actual venv interpreter disagree; no Python switch permitted')
        if record.get('python_version') != 'Python ' + '.'.join(str(n) for n in sys.version_info[:3]):
            raise c.SandboxError('Recorded Python version differs from the running interpreter')
        # Do not execute arbitrary launcher content. Recognize pip's simple shebang and its
        # standard long/space-containing-path shell trampoline as data, never shell evaluation.
        script = _read(app).decode('utf-8')
        lines = script.splitlines()
        if any(char in str(executable) for char in '\"$`\\\n\r'):
            raise c.SandboxError('Interpreter path needs unsupported launcher quoting; manual review required')
        quoted = '"' + str(executable) + '"' if ' ' in str(executable) else str(executable)
        shebang = script.startswith(('#!' + str(executable) + '\n',
                                    '#!/bin/sh\n\'\'\'exec\' ' + quoted + ' "$0" "$@"\n\' \'\'\'\n'))
        if not shebang or not any(line in lines for line in ('from opencode_sandbox.cli import main',
                                                           'from opencode_sandbox.launcher import main')) \
                or '    sys.exit(main())' not in lines:
            raise c.SandboxError('Application launcher template/interpreter is unrecognized')
        data_home = _location('XDG_DATA_HOME', Path.home() / '.local/share')
        fallback = Path.home() / '.local/pipx'
        home = _location('PIPX_HOME', fallback if fallback.exists() else data_home / 'pipx')
        bindir = _location('PIPX_BIN_DIR', Path.home() / '.local/bin')
        recognized = {'PIPX_HOME', 'PIPX_BIN_DIR', 'PIPX_MAN_DIR', 'PIPX_COMPLETION_DIR', 'PIPX_SHARED_LIBS', 'PIPX_DEFAULT_PYTHON'}
        if any(key.startswith('PIPX_') and value and key not in recognized for key, value in os.environ.items()):
            raise c.SandboxError('Unrecognized pipx environment settings require manual preservation (values not displayed)')
        paths = {'man_dir': str(_location('PIPX_MAN_DIR', Path.home() / '.local/share/man')),
                 'completion_dir': str(_location('PIPX_COMPLETION_DIR', Path.home() / '.local/share')),
                 'shared_libs': str(_location('PIPX_SHARED_LIBS', home / 'shared'))}
        default_python = os.environ.get('PIPX_DEFAULT_PYTHON')
        if default_python:
            selected = shutil.which(default_python) if os.sep not in default_python else str(Path(default_python).expanduser())
            if not selected or not Path(selected).samefile(source_python):
                raise c.SandboxError('pipx default Python conflicts with the recorded source interpreter; no Python switch permitted')
        if home != prefix.parent.parent:
            raise c.SandboxError('Current pipx home settings select another installation; custom locations must be explicit')
        launcher = bindir / NAME
        _own_directory(bindir)
        if not launcher.is_symlink() or launcher.resolve() != app:
            raise c.SandboxError('Exposed launcher is missing or foreign; no takeover permitted')
        invoked = Path(sys.argv[0]).absolute() if os.sep in sys.argv[0] else Path(shutil.which(sys.argv[0]) or '')
        found = shutil.which(NAME)
        if invoked != launcher or not found or Path(found).absolute() != launcher:
            raise c.SandboxError('Actual invocation or PATH launcher is shadowed/ambiguous; inspect before replacing')
        result.update(classification='verified official-tag pipx', verified=True,
                      reason='Running package, VCS tag/commit, pipx record, Python and actual exposed launcher agree',
                      evidence={'module': str(module), 'distribution': str(dist), 'venv': str(prefix),
                                'python': str(executable), 'source_python': str(source_python), 'tag': tag, 'commit': commit,
                                'launcher': str(launcher), 'pipx_home': str(home), 'pipx_bin_dir': str(bindir),
                                'locations': paths,
                                'record_sha256': hashlib.sha256(raw).hexdigest(), 'metadata_version': record['pipx_metadata_version']},
                      guidance='Recognized default pipx options and explicit custom locations are retained as evidence only. '
                               'External updater independence, published tag-to-commit identity and execution-time revalidation are not yet assessed.')
    except (c.SandboxError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        # Never echo raw metadata, pip arguments, URLs, paths or OS diagnostics: they can contain
        # credentials. Known reasons are static; unexpected parse/file errors have a safe class.
        result['reason'] = str(exc) if isinstance(exc, c.SandboxError) else f'Local installation evidence unavailable ({type(exc).__name__})'
    return result
