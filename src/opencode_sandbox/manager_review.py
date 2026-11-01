"""Internal origin-side exact manager review. No executor, durable grant or handoff payload.

Fresh classification/tools/source and observed file/routes are bound in an immutable review.
The internal form can record explicit review consent, but neither it nor origin revalidation
authorizes replacement: independent post-exit/exclusive revalidation, expected-result checks and
failure recovery are still absent. Normal installation usage is never released or converted.
"""
import hashlib
import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import core as c
from . import installation_locks as locks
from . import manager_installation as installation
from . import manager_releases as releases
from . import manager_targets as targets
from . import manager_tools as tools

SYSTEM_CONFIGS = ('/etc/gitconfig', '/usr/etc/gitconfig', '/etc/pip.conf')
CONTEXT = ('HOME', 'PATH', 'XDG_CONFIG_HOME', 'XDG_CONFIG_DIRS', 'XDG_DATA_HOME', *sorted(tools.KNOWN))
NETWORK = 'public-defaults'


def _json(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value): return hashlib.sha256(_json(value).encode()).hexdigest()


def _environment():
    names = {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
             'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CURL_HOME', 'SSLKEYLOGFILE', 'NETRC', 'SSH_ASKPASS',
             'SSH_ASKPASS_REQUIRE', 'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'BASH_ENV', 'ENV'}
    if any(value and (name.upper() in names or name.upper().startswith(('PIP_', 'GIT_', 'UV_', 'PYTHON', 'LD_', 'DYLD_')))
           for name, value in os.environ.items()):
        raise c.SandboxError('Custom installer/network environment requires manual preservation; values are not displayed')


def _configurations(evidence, facts):
    home = tools._path(str(Path.home()))
    config = tools._path(os.environ.get('XDG_CONFIG_HOME') or str(home / '.config'))
    directories = (os.environ.get('XDG_CONFIG_DIRS') or '/etc/xdg').split(os.pathsep)
    paths = [Path(value) for value in SYSTEM_CONFIGS]
    paths += [tools._path(value) / 'pip/pip.conf' for value in directories]
    paths += [home / name for name in ('.gitconfig', '.git-credentials', '.netrc', '_netrc', '.pip/pip.conf')]
    paths += [config / 'git/config', config / 'pip/pip.conf', home / '.config/git/config', home / '.config/pip/pip.conf']
    paths += [Path(value) / 'pip.conf' for value in (evidence['venv'], evidence['locations']['shared_libs'],
              facts['pipx_runtime']['runtime']['prefix'])]
    for path in paths:
        try: path.lstat()
        except FileNotFoundError: continue
        raise c.SandboxError('Custom pip/Git/credential configuration requires manual preservation; no file is read or changed')
    return sorted(set(paths))


def _route(value):
    """Bind every observed symlink-route node, not just the canonical binary endpoint.

    Directory timestamps are intentionally excluded: unrelated cache/pyc/log creation is not a
    replacement. File/symlink ctime, identity, ownership and mode are retained. Missing config
    routes are evidence too. This is a dated race detector, not protection from trusted local code.
    """
    path = tools._path(str(value))
    pending, current, rows, links = list(path.parts[1:]), Path('/'), [], 0
    while True:
        try: info = current.lstat()
        except FileNotFoundError:
            rows.append((str(current), 'missing', tuple(pending)))
            return rows
        kind = stat.S_IFMT(info.st_mode)
        if kind not in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK):
            raise c.SandboxError('Manager review encountered a special path; manual review required')
        if info.st_uid not in (0, os.getuid()) or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022
                and not (stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
            raise c.SandboxError('Manager review paths are not controlled; manual review required')
        extra = () if stat.S_ISDIR(info.st_mode) else (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
        link = os.readlink(current) if stat.S_ISLNK(info.st_mode) else None
        rows.append((str(current), kind, info.st_dev, info.st_ino, info.st_uid, info.st_mode, extra, link))
        if link is not None:
            links += 1
            if links > 40: raise c.SandboxError('Manager review has a cyclic or excessive symlink route')
            target = Path(link)
            pending = list(target.parts[1:] if target.is_absolute() else target.parts) + pending
            current = Path('/') if target.is_absolute() else current.parent
            continue
        if not pending: return rows
        part = pending.pop(0)
        current = current.parent if part == '..' else current / part


def _snapshot(local, facts):
    evidence = local['evidence']
    prefix, dist = Path(evidence['venv']), Path(evidence['distribution'])
    records = [prefix / 'pipx_metadata.json', prefix / 'pyvenv.cfg', Path(evidence['module']), prefix / 'bin/opencode-sandbox',
               *(dist / name for name in ('direct_url.json', 'METADATA', 'entry_points.txt', 'RECORD'))]
    hashes = {str(path): hashlib.sha256(installation._read(path)).hexdigest() for path in records}
    paths = [*records, evidence['launcher'], evidence['python'], evidence['source_python'], facts['pipx'], facts['python'],
             *facts['settings'].values(), *facts['pipx_runtime']['origins'], *_configurations(evidence, facts)]
    # Preserve lexical routes of explicit locations as well as their reconciled effective paths.
    paths += [Path(value).expanduser() for name in tools.KNOWN if (value := os.environ.get(name)) and
              (name != 'PIPX_DEFAULT_PYTHON' or os.sep in value)]
    if len(paths) > 2048: raise c.SandboxError('Manager review path inventory exceeds its bound')
    routes = {str(path): _route(path) for path in sorted({Path(path) for path in paths})}
    context = _digest({name: os.environ.get(name) for name in CONTEXT})
    value = _json({'installation': {'version': local['version'], 'evidence': evidence}, 'tools': facts,
                   'records': hashes, 'routes': routes, 'context': context, 'network': NETWORK})
    if len(value.encode()) > 524288: raise c.SandboxError('Manager review evidence exceeds its bound')
    return value


def _inspect():
    _environment()
    local = installation.classify()
    if not local['verified']: raise c.SandboxError('Manager review requires a fresh recognized installation; use manual guidance')
    if local['evidence']['venv'] != locks.identity(): raise c.SandboxError('Manager review does not match the originating installation')
    locks.acquire_usage()  # retained until actual process exit, NEVER converted/released for review
    facts = tools.assess(local)
    if not facts['supported']: raise c.SandboxError('Manager review external tools are unsupported; use manual guidance')
    return local, _snapshot(local, facts['evidence'])


@dataclass(frozen=True)
class Review:
    target: targets.Target
    version: str
    prefix: str
    binding: str = field(repr=False)
    owner: int = field(default_factory=os.getpid)

    @property
    def identity(self):
        source = asdict(self.target); source.pop('at')
        return _digest({'source': source, 'binding': self.binding, 'owner': self.owner})


@dataclass(frozen=True)
class Approval:
    """Internal UI receipt, not an executable capability, serialization format or durable grant."""
    review: Review = field(repr=False)


def prepare(tag):
    """Explicit fresh origin preparation only. Never accepts caller-supplied classifier/cache facts."""
    releases.version(tag)
    try:
        local, binding = _inspect()
        target = targets.resolve(tag, local['version'])
        if _inspect()[1] != binding: raise c.SandboxError('Manager installation/tools/settings changed during review; review again')
        return Review(target, local['version'], local['evidence']['venv'], binding)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, locks.Error):
        raise c.SandboxError('Manager review evidence unavailable; no installation was changed') from None


def revalidate(review):
    """Fresh same-process check before future handoff; NOT independent/exclusive revalidation."""
    if type(review) is not Review or review.owner != os.getpid() or review.prefix != locks.identity():
        raise c.SandboxError('Manager review belongs to another origin or installation')
    try:
        local, binding = _inspect()
        if local['version'] != review.version or binding != review.binding:
            raise c.SandboxError('Manager installation/tools/settings changed; review again')
        targets.revalidate(review.target, review.version)
        if _inspect()[1] != review.binding: raise c.SandboxError('Manager installation/tools/settings changed; review again')
        return review
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, locks.Error):
        raise c.SandboxError('Manager review evidence unavailable; no installation was changed') from None


def text(review):
    """Plain scrollable impact/identity review. No raw environment, configuration or metadata dump."""
    value = json.loads(review.binding)
    old, tool = value['installation']['evidence'], value['tools']
    return '\n'.join([
        f'Exact Sandbox Manager review: {review.version} -> {review.target.version}',
        f'Review identity: {review.identity}', f'Installation: {review.prefix}',
        f'Previous local release: {old["tag"]} | commit {old["commit"]}',
        f'Target release: {review.target.tag} | commit {review.target.commit}',
        f'Git objects: {" -> ".join(review.target.objects)}', f'Official source: {review.target.source}',
        f'Published: {review.target.published_at} | release ID {review.target.release_id}',
        f'Release: {review.target.url}', f'Launcher: {old["launcher"]}',
        f'Existing source Python (no switch): {old["source_python"]}',
        f'External pipx: {tool["pipx"]} | 1.18.7', f'External helper Python: {tool["python"]}',
        *[f'{name}: {path}' for name, path in sorted(tool['settings'].items())], '',
        'Network policy: public defaults only. Download the exact GitHub tag plus PyPI/build dependencies.',
        'Package/build code runs on the host as this user, not in a Docker sandbox.',
        'No ambient proxy/index/pip/Git/credential configuration is silently discarded: detected custom settings refuse.',
        'A future executor must apply and independently verify this network policy; no installer exists here.',
        'Replace only this manager installation. Do not migrate environments, user configuration, workspaces or volumes.',
        'Close the dashboard and restore the terminal before any future replacement. Never restart automatically.',
        'Other supported manager sessions/workers must finish; the usage lease lasts through actual process exit.',
        'Old managers and arbitrary external pipx do not honor these locks. pipx force is not a backup.',
        'Previous-tag reinstall is recovery guidance, not identical dependencies or guaranteed offline recovery.',
        'GitHub HTTPS source observations are not signed-tag authentication; tags can move after a read.',
        'Changed source, files, routes, tools or settings require a new review. Fresh installed-result checks are mandatory.',
        'This internal consent fixture changes nothing. Independent exclusive revalidation, replacement and recovery are pending.',
        'Manager Update remains disabled. Approval alone cannot launch or arm a helper.', '',
        'Release notes (plain text; full bounded notes hash retained):', review.target.notes,
        '[Notes truncated]' if review.target.notes_truncated else '',
    ])
