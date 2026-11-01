"""Internal origin-side exact manager review. No executor, durable grant or handoff payload.

Fresh classification/tools/source and observed file/routes are bound in an immutable review.
The internal form can record explicit review consent, but neither it nor origin revalidation
authorizes replacement: independent post-exit/exclusive revalidation, expected-result checks and
failure recovery are still absent. Normal installation usage is never released or converted.
"""
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import core as c
from . import installation_locks as locks
from . import manager_installation as installation
from . import manager_network
from . import manager_observations as observations
from . import manager_releases as releases
from . import manager_targets as targets
from . import manager_tools as tools

SYSTEM_CONFIGS = manager_network.SYSTEM_CONFIGS
CONTEXT = observations.CONTEXT
NETWORK = 'public-defaults'


def _json(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value): return hashlib.sha256(_json(value).encode()).hexdigest()


def _environment():
    try: manager_network.environment_check(os.environ)
    except manager_network.Refused as exc: raise c.SandboxError(str(exc)) from None


def _configurations(evidence, facts):
    try: return manager_network.configurations(evidence, facts, {**os.environ, 'HOME': str(Path.home())}, system=SYSTEM_CONFIGS)
    except manager_network.Refused as exc: raise c.SandboxError(str(exc)) from None


def _route(value):
    """The same stdlib route implementation is frozen for independent local replay."""
    try: return observations.route(value)
    except observations.Refused as exc: raise c.SandboxError(str(exc)) from None


def _snapshot(local, facts):
    evidence = local['evidence']
    records = observations.critical(evidence)
    hashes = {str(path): hashlib.sha256(observations.read_record(path)).hexdigest() for path in records}
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
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, locks.Error, observations.Refused):
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
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, locks.Error, observations.Refused):
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
