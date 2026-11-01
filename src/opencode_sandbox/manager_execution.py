"""Independent read-only execution preconditions, also frozen outside the replaceable venv.

No installer or ordinary-manager dispatch. A successful diagnostic is not durable consent and
does not reopen a pending operation. All probes are fresh; published source is never cached.
"""
import os
import shutil
import time
from pathlib import Path

if __package__:
    from . import manager_network as policy
    from . import manager_observations as observations
    from . import manager_process as processes
    from . import manager_source as source
    from . import manager_tool_probe as tools
else:
    import manager_network as policy
    import manager_observations as observations
    import manager_process as processes
    import manager_source as source
    import manager_tool_probe as tools

LIMIT = 131072
SOURCE_API = source.API  # tests may replace transport in frozen SOURCE, never in a request


class Refused(RuntimeError):
    pass


def _probe(python, prefix, mode, environment, cwd, deadline, candidate=None):
    argv = [str(python), '-I', '-B', *(['-S'] if mode == 'stdlib' else []), '-c',
            processes.source('manager_tool_probe.py'), mode, str(prefix)]
    if candidate is not None: argv.append(str(candidate))
    code, stdout, _ = processes.run(argv, environment=environment, cwd=cwd, deadline=deadline, limit=LIMIT)
    lines = stdout.splitlines()
    if code or not lines or (mode == 'pipx' and lines[:-1] != [b'1.18.7']) or (mode == 'stdlib' and len(lines) != 1):
        raise Refused('Independent external runtime probe failed')
    value = observations.parse(lines[-1])
    if not isinstance(value, dict) or value.get('ok') is not True: raise Refused('Independent external runtime could not be proved')
    return value


def _external(prefix, facts, context, cwd, deadline):
    candidate, python = tools.path(facts['pipx']), tools.path(facts['python'])
    if tools.launcher(candidate, prefix) != (python, facts['launcher_identity']) or tools.controlled(python, prefix)[1] != facts['python_identity']:
        raise Refused('Reviewed external pipx or Python identity changed')
    settings = facts['settings']
    for path in settings.values(): tools.outside(path, prefix)
    tools.controlled(settings['PIPX_DEFAULT_PYTHON'], prefix)
    # These are fresh external runtime/dependency executions, not a replay of JSON/tool files.
    environment = {**settings, 'HOME': context['HOME'], 'PATH': context.get('PATH') or os.defpath,
                   'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    helper = _probe(python, prefix, 'stdlib', environment, cwd, deadline)
    pipx = _probe(python, prefix, 'pipx', environment, cwd, deadline, candidate)
    if helper['runtime'] != facts['helper_runtime'] or pipx != facts['pipx_runtime']:
        raise Refused('Independent external runtime/dependency/settings evidence changed')
    if tools.launcher(candidate, prefix) != (python, facts['launcher_identity']) or tools.controlled(python, prefix)[1] != facts['python_identity']:
        raise Refused('External tool changed during independent validation')
    return environment


def installer_policy(prefix, evidence, facts, context, cwd, deadline):
    """Refuse custom files, then prove effective fixed Git/pip settings with actual processes."""
    configs = policy.configurations(evidence, facts, context)
    for path in configs: observations.route(path, deadline=deadline)
    git = shutil.which('git', path=context.get('PATH') or os.defpath)
    if not git: raise Refused('Independent Git prerequisite is unavailable')
    git = Path(git).absolute()
    _, git_identity = tools.controlled(git, prefix)
    # Do not use an arbitrary reviewed PATH to find installer subprocesses or remote helpers.
    path = os.pathsep.join(dict.fromkeys((str(git.parent), str(Path(facts['python']).parent), os.defpath)))
    environment = policy.environment(facts['settings'], context, path=path)
    # A private artifact directory may itself be below a project checkout. Its ancestors are
    # not the source repository or installer configuration; never inherit their local Git config.
    # A .git inside the helper directory still appears in the effective query and refuses.
    ceiling = str(Path(cwd).resolve().parent)
    if os.pathsep in ceiling: raise Refused('Helper directory has an ambiguous Git discovery boundary')
    environment['GIT_CEILING_DIRECTORIES'] = ceiling
    code, out, _ = processes.run([str(git), 'config', '--null', '--list'], environment=environment, cwd=cwd, deadline=deadline)
    expected = [(policy.GIT[f'GIT_CONFIG_KEY_{n}'].lower() + '\n' + policy.GIT[f'GIT_CONFIG_VALUE_{n}']).encode() for n in range(7)]
    if code or out.split(b'\0') != [*expected, b'']: raise Refused('Effective Git policy differs from public defaults')
    code, out, _ = processes.run([str(git), '--exec-path'], environment=environment, cwd=cwd, deadline=deadline)
    if code: raise Refused('Independent Git remote helper route is unavailable')
    remote = tools.path(out.decode().strip()) / 'git-remote-https'
    _, remote_identity = tools.controlled(remote, prefix)
    shared = tools.path(facts['settings']['PIPX_SHARED_LIBS'])
    python = shared / 'bin/python'
    tools.controlled(python, prefix)
    bundle = str(Path(__file__).parent)
    code, out, _ = processes.run([str(python), '-I', '-B', '-c', processes.source('manager_pip_probe.py'), bundle, str(prefix), str(shared)],
                                  environment=environment, cwd=cwd, deadline=deadline)
    pip = observations.parse(out)
    if code or not isinstance(pip, dict) or pip.get('ok') is not True or pip.get('policy') != 'public-defaults':
        raise Refused('Effective shared pip policy or independence could not be proved')
    policy.configurations(evidence, facts, context)
    if tools.controlled(git, prefix)[1] != git_identity or tools.controlled(remote, prefix)[1] != remote_identity:
        raise Refused('Installer Git routes changed during validation')
    return {'environment': environment, 'git': str(git), 'git_identity': git_identity,
            'remote': str(remote), 'remote_identity': remote_identity, 'pip': pip}


def published(target, python, cwd, deadline):
    """Same fixed official HTTPS source graph, using the frozen reader and no application/cache."""
    deadline = min(deadline, time.monotonic() + 8)
    def get(path):
        left = deadline - time.monotonic()
        if left <= 0: raise Refused('Independent published-source check timed out')
        code, out, _ = processes.run([str(python), '-I', '-B', '-S', '-c', processes.source('http_probe.py'),
                                     SOURCE_API + path, str(left), str(LIMIT), 'github'],
                                    environment={'PATH': os.defpath, 'LANG': 'C.UTF-8'}, cwd=cwd, deadline=deadline, limit=LIMIT + 1024)
        if code: raise Refused('Independent published-source request failed; no cached authority or retry')
        value = observations.parse(out)
        if not isinstance(value, dict): raise Refused('Invalid independent published-source object')
        return value
    observed = source.resolve(target['tag'], get)
    expected = {key: item for key, item in target.items() if key != 'at'}
    if observations.canonical(observed) != observations.canonical(expected):
        raise Refused('Published manager target changed; a new review is required')
    return observed


def validate(locks, value, *, cwd, deadline):
    """Caller first proves actual origin death/replays local observations under own exclusion.

    Check own exclusion again; no origin lease conversion or exported exclusive descriptor. A
    separate mutation gate must persist recovery state and recheck observations before install.
    """
    prefix = Path(locks.identity(value['prefix']))
    with locks._verification(prefix) as (witness, owner_fd): locks._verify_descriptor(witness, os.getpid(), owner_fd, prefix)
    binding, _ = observations._shape(value, str(prefix), value['origin'])
    target_version = source.version(value['target']['tag'])
    if value['target']['version'] != target_version or tuple(map(int, target_version.split('.'))) <= tuple(map(int, value['version'].split('.'))):
        raise Refused('Independent manager target is not the reviewed strictly newer release')
    evidence, facts = binding['installation']['evidence'], binding['tools']
    context = value['context']
    if evidence['source_python'] != facts['settings']['PIPX_DEFAULT_PYTHON'] or Path(facts['settings']['PIPX_HOME']) / 'venvs/opencode-sandbox' != prefix:
        raise Refused('Reviewed installation and preserved installer locations disagree')
    _external(prefix, facts, context, cwd, deadline)
    effective = installer_policy(prefix, evidence, facts, context, cwd, deadline)
    target = published(value['target'], facts['python'], cwd, deadline)
    return {'policy': effective, 'target': target}
