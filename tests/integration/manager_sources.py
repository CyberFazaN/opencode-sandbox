"""Installed read-only exact source graph checks; private transport is not public authenticity."""
import json

from manager_source_fixture import graph, serve


def exercise(camp, ck, prefix, env, repo, base):
    # Tags/commits exist ONLY in this run's already manifested private Git fixture. No project
    # version/tag/remote is changed. Target code is never installed or executed in this checkpoint.
    git = ['git', '-C', str(repo), '-c', 'user.name=ocs-test', '-c', 'user.email=test@example.invalid']
    version_file = repo / 'src/opencode_sandbox/__init__.py'
    original = version_file.read_bytes()
    version_file.write_text('__version__ = "6.2.0"\n')
    camp._run([*git, 'add', 'src/opencode_sandbox/__init__.py'], check=True)
    camp._run([*git, 'commit', '--quiet', '-m', 'owned exact source fixture target'], check=True)
    camp._run([*git, 'tag', '-a', 'v6.2.0', '-m', 'owned source fixture only'], check=True)
    commit = camp._run([*git, 'rev-parse', 'v6.2.0^{commit}'], check=True).stdout.strip()
    annotation = camp._run([*git, 'rev-parse', 'v6.2.0'], check=True).stdout.strip()
    camp._run([*git, 'commit', '--allow-empty', '--quiet', '-m', 'owned changed source fixture'], check=True)
    changed = camp._run([*git, 'rev-parse', 'HEAD'], check=True).stdout.strip()
    camp._run([*git, 'tag', '-f', '-a', 'v6.2.0', '-m', 'owned moved source fixture only'], check=True)
    changed_annotation = camp._run([*git, 'rev-parse', 'v6.2.0'], check=True).stdout.strip()
    version_file.write_bytes(original)  # preserve the source fixture working file, no installed mutation
    camp.note(f'owned exact-source fixture commit={commit}, annotation={annotation}, changed={changed}; '
              f'private Git tag only, loopback API, source-data/config and source-target.json under {base}; '
              'NOT public GitHub authentication, installation consent or replacement')
    environment = dict(env, OPENCODE_SANDBOX_HOME=str(base / 'source-data'),
                       OPENCODE_SANDBOX_CONFIG=str(base / 'source-config'))
    with serve(graph(commit=commit, tags=(annotation,))) as (endpoint, state):
        code = ('import dataclasses,json,sys\nfrom pathlib import Path\n'
                'from opencode_sandbox import __version__,manager_targets as t,manager_releases as r,core as c\n'
                'assert Path(t.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())\n'
                f't.ENDPOINT={endpoint!r}\nr.API={endpoint + "/releases?per_page=100"!r}\n'
                "mode=sys.argv[1]\ntry:\n"
                " if mode=='resolve': result=dataclasses.asdict(t.resolve('v6.2.0',__version__))\n"
                " elif mode=='revalidate':\n"
                "  value=json.loads(sys.argv[2]);value['objects']=tuple(value['objects'])\n"
                "  result=dataclasses.asdict(t.revalidate(t.Target(**value),__version__))\n"
                " elif mode=='latest': result=r.latest(automatic=True)\n"
                "except c.SandboxError as exc: result={'refused':str(exc)}\n"
                'print(json.dumps(result))\n')
        def run(mode, *args):
            return json.loads(camp._run([str(prefix / 'bin/python'), '-B', '-c', code, mode, *args],
                                       env=environment, check=True).stdout)
        target = run('resolve')
        assert ck(target.get('objects') == [annotation, commit] and target['tag'] == 'v6.2.0',
                  'Manager exact source: installed package observes actual private annotated tag peeled to exact Git commit'), target
        (base / 'source-target.json').write_text(json.dumps(target, indent=2) + '\n')
        before = len(state['requests'])
        fresh = run('revalidate', json.dumps(target))
        ck({key: value for key, value in fresh.items() if key != 'at'} == {key: value for key, value in target.items() if key != 'at'}
           and len(state['requests']) == before * 2,
           'Manager exact source: separate actual installed process revalidates same target from fresh HTTP, not cached selection')
        state['routes'] = graph(commit=changed, tags=(changed_annotation,))
        refused = run('revalidate', json.dumps(target))
        ck('target changed' in refused.get('refused', ''), 'Manager exact source: changed peeled commit refuses instead of replacing consent target')
        state.update(status=429, headers={'Retry-After': '120'})
        ck('HTTP 429' in run('resolve').get('refused', ''), 'Manager exact source: real HTTP rate limit is reported, no source grant')
        before = len(state['requests'])
        ck('rate limited' in run('resolve').get('refused', '') and 'rate limited' in run('latest').get('refused', '')
           and len(state['requests']) == before,
           'Manager exact source: persistent target Retry-After blocks restarted installed source/discovery callers without another request')
        ck(all(not any(key.lower() in ('authorization', 'proxy-authorization', 'cookie') for key in headers)
               for _, headers in state['requests']), 'Manager exact source: actual source requests send no authentication/cookies')
