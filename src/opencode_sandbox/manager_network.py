"""Conservative public-default installer policy, shared with the independent frozen helper.

Detected custom settings are refused, not edited or silently stripped. The explicit environment
below is used only after that check; it is not an input environment/callback from a review file.
It constrains standard pip/Git clients, not arbitrary host build code or hostile same-UID code.
"""
import os
from pathlib import Path

SYSTEM_CONFIGS = ('/etc/gitconfig', '/usr/etc/gitconfig', '/etc/pip.conf')
KNOWN = {'PIPX_HOME', 'PIPX_BIN_DIR', 'PIPX_MAN_DIR', 'PIPX_COMPLETION_DIR', 'PIPX_SHARED_LIBS', 'PIPX_DEFAULT_PYTHON'}
PIP = {'PIP_CONFIG_FILE': os.devnull, 'PIP_INDEX_URL': 'https://pypi.org/simple', 'PIP_NO_INPUT': '1',
       'PIP_KEYRING_PROVIDER': 'disabled', 'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PIP_NO_CACHE_DIR': '1'}
GIT = {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': os.devnull, 'GIT_CONFIG_GLOBAL': os.devnull,
       'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_COUNT': '7',
       'GIT_CONFIG_KEY_0': 'protocol.allow', 'GIT_CONFIG_VALUE_0': 'never',
       'GIT_CONFIG_KEY_1': 'protocol.https.allow', 'GIT_CONFIG_VALUE_1': 'always',
       'GIT_CONFIG_KEY_2': 'credential.helper', 'GIT_CONFIG_VALUE_2': '',
       'GIT_CONFIG_KEY_3': 'http.sslVerify', 'GIT_CONFIG_VALUE_3': 'true',
       'GIT_CONFIG_KEY_4': 'http.followRedirects', 'GIT_CONFIG_VALUE_4': 'false',
       'GIT_CONFIG_KEY_5': 'http.proxy', 'GIT_CONFIG_VALUE_5': '',
       'GIT_CONFIG_KEY_6': 'http.extraHeader', 'GIT_CONFIG_VALUE_6': ''}


class Refused(RuntimeError):
    pass


def environment_check(environment):
    names = {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
             'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CURL_HOME', 'SSLKEYLOGFILE', 'NETRC', 'SSH_ASKPASS',
             'SSH_ASKPASS_REQUIRE', 'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'BASH_ENV', 'ENV'}
    if any(value and (name.upper() in names or name.upper().startswith(('PIP_', 'GIT_', 'UV_', 'PYTHON', 'LD_', 'DYLD_'))
                     or name.startswith('PIPX_') and name not in KNOWN) for name, value in environment.items()):
        raise Refused('Custom installer/network environment requires manual preservation; values are not displayed')


def configurations(evidence, facts, context, *, system=SYSTEM_CONFIGS):
    def absolute(value):
        if not value or not Path(value).is_absolute(): raise Refused('Custom configuration locations require manual preservation')
        return Path(value)
    home = absolute(context['HOME'])
    config = absolute(context.get('XDG_CONFIG_HOME') or str(home / '.config'))
    directories = (context.get('XDG_CONFIG_DIRS') or '/etc/xdg').split(os.pathsep)
    paths = [Path(value) for value in system]
    paths += [absolute(value) / 'pip/pip.conf' for value in directories]
    paths += [home / name for name in ('.gitconfig', '.git-credentials', '.netrc', '_netrc', '.pip/pip.conf')]
    paths += [config / 'git/config', config / 'pip/pip.conf', home / '.config/git/config', home / '.config/pip/pip.conf']
    paths += [Path(value) / 'pip.conf' for value in (evidence['venv'], evidence['locations']['shared_libs'], facts['pipx_runtime']['runtime']['prefix'])]
    for path in paths:
        try: path.lstat()
        except FileNotFoundError: continue
        raise Refused('Custom pip/Git/credential configuration requires manual preservation; no file is read or changed')
    return sorted(set(paths))


def environment(settings, context, *, path):
    if set(settings) != KNOWN or any(not isinstance(value, str) or not Path(value).is_absolute() for value in settings.values()):
        raise Refused('Installer locations are not the recognized explicit settings')
    if not isinstance(context.get('HOME'), str) or not Path(context['HOME']).is_absolute():
        raise Refused('Installer HOME is not an absolute reviewed location')
    return {**settings, 'HOME': context['HOME'], 'PATH': path, 'LANG': 'C.UTF-8',
            'PYTHONDONTWRITEBYTECODE': '1', **PIP, **GIT}
