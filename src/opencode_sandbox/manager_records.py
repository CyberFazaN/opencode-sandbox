"""Stdlib pipx record semantics shared by classification and independent installed-result checks."""
from pathlib import Path

NAME = 'opencode-sandbox'


class Refused(RuntimeError):
    pass


def path(value):
    if isinstance(value, dict) and set(value) == {'__type__', '__Path__'} and value.get('__type__') == 'Path': value = value['__Path__']
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or any(not ch.isprintable() for ch in value):
        raise Refused('Installation evidence has an invalid absolute path')
    return Path(value)


def settings(record):
    allowed = {'main_package', 'python_version', 'source_interpreter', 'venv_args', 'injected_packages',
               'pipx_metadata_version', 'backend', 'environment', 'exposure_enabled', 'pinned'}
    if not isinstance(record, dict) or set(record) - allowed or record.get('pipx_metadata_version') not in ('0.5', '0.6', '0.12'):
        raise Refused('Unrecognized pipx metadata/settings; preservation cannot be proved')
    if record.get('venv_args') != [] or record.get('injected_packages') != {} or record.get('backend', 'pip') != 'pip' \
            or record.get('environment') not in (None, NAME) or record.get('exposure_enabled', True) is not True or record.get('pinned', False) is not False:
        raise Refused('Custom pipx venv/backend/injections/pin/exposure settings require manual preservation')
    package = record.get('main_package')
    if not isinstance(package, dict): raise Refused('Missing pipx main package evidence')
    expected = {'package', 'package_or_url', 'pip_args', 'include_dependencies', 'include_apps', 'apps', 'app_paths',
                'apps_of_dependencies', 'app_paths_of_dependencies', 'package_version', 'suffix', 'pinned',
                'expected_apps', 'lock_file', 'include_resources_from', 'include_apps_from', 'cooldown_days',
                'man_pages', 'man_paths', 'man_pages_of_dependencies', 'man_paths_of_dependencies',
                'completions', 'completion_paths', 'completions_of_dependencies', 'completion_paths_of_dependencies'}
    if set(package) - expected: raise Refused('Unrecognized pipx package settings; preservation cannot be proved')
    defaults = {'pip_args': [], 'include_dependencies': False, 'include_apps': True, 'suffix': '', 'pinned': False,
                'expected_apps': [], 'lock_file': None, 'include_resources_from': [], 'include_apps_from': [], 'cooldown_days': None,
                'man_pages': [], 'man_paths': [], 'man_pages_of_dependencies': [], 'man_paths_of_dependencies': {},
                'completions': [], 'completion_paths': [], 'completions_of_dependencies': [], 'completion_paths_of_dependencies': {}}
    if any(package.get(key, value) != value for key, value in defaults.items()):
        raise Refused('Custom pipx package options/resources/pins require manual preservation (values not displayed)')
    if package.get('pip_args') != [] or package.get('include_dependencies') is not False or package.get('include_apps') is not True:
        raise Refused('Required pipx installation settings are missing or unsupported')
    if not isinstance(package.get('apps_of_dependencies', []), list) or not isinstance(package.get('app_paths_of_dependencies', {}), dict):
        raise Refused('Invalid dependency inventory in pipx metadata')
    return package
