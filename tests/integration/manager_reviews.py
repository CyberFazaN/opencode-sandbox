"""Actual installed origin review/consent/revalidation; no replacement or exclusive gate claim."""
import json
import os
import sys
from pathlib import Path

from campaign import ROOT
from manager_source_fixture import graph, serve
from pty_term import STAB, TAB, Term
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_terminal import read_state


def exercise(camp, ck, prefix, launcher, env, repo, base):
    from test_66_manager_inventory import exclusion
    # Explicit isolated public-default test environment. The original Git URL rewrite was needed
    # for fixture installation only; it is not silently removed by product code or used as consent.
    public = {name: value for name, value in env.items() if not name.upper().startswith(
        ('PIP_', 'GIT_', 'UV_', 'PYTHON', 'LD_', 'DYLD_')) and name.upper() not in {
        'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE',
        'CURL_CA_BUNDLE', 'CURL_HOME', 'SSLKEYLOGFILE', 'NETRC', 'SSH_ASKPASS', 'SSH_ASKPASS_REQUIRE',
        'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'BASH_ENV', 'ENV'}}
    public.update(PATH=str(launcher.parent) + ':' + str(Path(sys.executable).parent) + ':/usr/bin:/bin',
                  DOCKER_CONFIG=camp.env.get('DOCKER_CONFIG', str(Path.home() / '.docker')))
    git = ['git', '-C', str(repo)]
    tag = json.loads((base / 'source-target.json').read_text())['tag']
    commit = camp._run([*git, 'rev-parse', tag + '^{commit}'], check=True).stdout.strip()
    annotation = camp._run([*git, 'rev-parse', tag], check=True).stdout.strip()
    site = next(prefix.glob('lib/python*/site-packages'))
    hook, module = site / 'ocs_test_manager_review.pth', site / 'ocs_test_manager_review.py'
    assert not hook.exists() and not module.exists()
    executable = launcher.resolve()
    original = executable.read_bytes()
    credentials = Path(public['HOME']) / '.netrc'
    assert not credentials.exists()
    try:
        for mode, size in [('confirm', (80, 24)), ('confirm-large', (120, 40)), ('cancel', (80, 24)),
                           ('changed', (120, 40)), ('custom-network', (80, 24)), ('custom-config', (80, 24))]:
            state = base / ('review-' + mode + '.json')
            environment = dict(public, OPENCODE_SANDBOX_HOME=str(base / ('review-data-' + mode)),
                               OPENCODE_SANDBOX_CONFIG=str(base / ('review-config-' + mode)))
            if mode == 'custom-network': environment['PIP_INDEX_URL'] = 'https://user:dummy-secret-review@index.invalid/simple'
            if mode == 'custom-config': credentials.write_text('machine index.invalid login user password dummy-secret-review\n')
            camp.note(f'owned installed review mode={mode}, state/partial/pty={state}, data/config under {base}; '
                      f'test-only injector {hook}, {module}; actual console/bootstrap/identity/tools/source/consent/revalidation; '
                      'original launcher bytes restored after owned changed-body fault; exact hooks/config removed in finally; no helper/install payload')
            with serve(graph(commit=commit, tags=(annotation,), tag=tag)) as (endpoint, server):
                options = {'endpoint': endpoint, 'state': str(state), 'tag': tag}
                module.write_text('import runpy\n' + f"runpy.run_path({str(ROOT / 'tests/manager_review_fixture.py')!r})['install']({options!r})\n")
                hook.write_text('import ocs_test_manager_review\n')
                term = Term([str(launcher), 'tui'], *size, env=environment, log=camp.log)
                try:
                    if mode.startswith('custom-'):
                        value = read_state(state, lambda value: value.get('refused'), timeout=30, pump=term.pump)
                        ck('manual preservation' in value['refused'] and 'dummy-secret' not in json.dumps(value)
                           and not server['requests'], 'Manager review: actual custom network/configuration refuses before source request, without secret output')
                    else:
                        value = read_state(state, lambda value: value.get('prepared') or value.get('refused'), timeout=30, pump=term.pump)
                        assert ck(value.get('prepared') and value['commit'] == commit, 'Manager review: actual installed origin prepares exact source/installation/tool/network binding'), value
                        assert ck(term.wait_for('Review Sandbox Manager', 15), 'Manager review: real internal consent form visible at requested terminal size')
                        assert term.wait_for('Confirm review', 15)
                        ck('Confirm review' in term.text() and 'Cancel' in term.text() and exclusion(camp, prefix, busy=True),
                           'Manager review: compact consent controls visible and original manager still holds installation usage')
                        if mode == 'cancel': term.send('\r', .3)  # default focus is Cancel, not approval
                        else:
                            if mode == 'changed': executable.write_bytes(original + b'\n# owned manager-review changed-file fixture\n')
                            term.send(STAB + ' ', .2)  # let the policy's Changed message enable Confirm
                            term.send(TAB + TAB, .2)
                            term.send('\r', .3)
                        value = read_state(state, lambda value: value.get('cancelled') or value.get('revalidated') or value.get('refused'),
                                           timeout=30, pump=term.pump)
                        if mode == 'cancel': ck(value.get('cancelled') and not value.get('approved') and len(server['requests']) == 6,
                                                'Manager review: keyboard-default Cancel returns no receipt and performs no revalidation/handoff')
                        elif mode == 'changed': ck(value.get('approved') == value['identity'] and 'changed' in value.get('refused', '')
                                                  and len(server['requests']) == 6,
                                                  'Manager review: changed actual installed launcher after consent display refuses before another source request')
                        else: ck(value.get('approved') == value['identity'] and value.get('revalidated') and len(server['requests']) == 12,
                                 'Manager review: explicit policy/target approval binds exact review and fresh actual origin revalidation succeeds')
                    ck(term.exit_code(15) == 0 and term.restored(), 'Manager review: normal actual dashboard shutdown restores terminal; no helper or automatic restart')
                    ck('dummy-secret-review' not in term.raw.decode(errors='replace'), 'Manager review: no secret setting/configuration value leaked to real terminal')
                finally:
                    term.pump(.1); state.with_suffix('.pty').write_bytes(term.raw)
                    term.close()
                    if executable.read_bytes() != original: executable.write_bytes(original)
                    if mode == 'custom-config': credentials.unlink()
                    hook.unlink(); module.unlink()
        ck(exclusion(camp, prefix, busy=False), 'Manager review: all exact origin processes finished, exclusion free, persistent inode preserved')
        local_replay(camp, ck, prefix, launcher, public, base, commit, annotation, hook, module, tag)
    finally:
        if hook.exists(): hook.unlink()
        if module.exists(): module.unlink()
        if credentials.exists(): credentials.unlink()
        if executable.read_bytes() != original: executable.write_bytes(original)


def local_replay(camp, ck, prefix, launcher, public, base, commit, annotation, hook, module, tag):
    import signal

    from test_66_manager_inventory import exclusion
    executable = launcher.resolve()
    original = executable.read_bytes()
    unusable = hook.parent / 'ocs_test_local_unusable.pth'
    assert not unusable.exists()
    for mode, size in [('unchanged', (80, 24)), ('changed', (120, 40)), ('no-runtime', (80, 24)),
                       ('execution', (80, 24)), ('execution-policy-fault', (120, 40)), ('execution-source-fault', (80, 24))]:
        state = base / ('local-replay-' + mode + '.json')
        stage = base / ('local-replay-staging-' + mode); stage.mkdir()
        environment = dict(public, OPENCODE_SANDBOX_HOME=str(base / ('local-data-' + mode)),
                           OPENCODE_SANDBOX_CONFIG=str(base / ('local-config-' + mode)))
        camp.note(f'owned non-mutating local replay mode={mode}, state/release/partial/pty={state}, recursive artifacts/results={stage}; '
                  f'exact owned launcher fault restored and startup-refusal hook {unusable} removed in finally; '
                  'stdlib helper local observations only, no fresh tool/dependency/source/network or installation-success claim')
        helper = None
        pip_site = next((prefix.parent.parent / 'shared').glob('lib/python*/site-packages'))
        pip_hook, pip_module = pip_site / 'ocs_test_policy.pth', pip_site / 'ocs_test_policy.py'
        assert not pip_hook.exists() and not pip_module.exists()
        with serve(graph(commit=commit, tags=(annotation,), tag=tag)) as (endpoint, server), subreaper():
            options = {'endpoint': endpoint, 'state': str(state), 'local_validate': True, 'staging': str(stage), 'tag': tag}
            if mode.startswith('execution'):
                options['execution_validate'] = True
                camp.note('owned execution validation transport is substituted in frozen source only; actual pipx/Python/dependency/shared-pip/Git probes, '
                          'not public release authenticity or an installer; private policy hook and source mutation only on named fixtures')
            module.write_text('import runpy\n' + f"runpy.run_path({str(ROOT / 'tests/manager_review_fixture.py')!r})['install']({options!r})\n")
            hook.write_text('import ocs_test_manager_review\n')
            term = Term([str(launcher), 'tui'], *size, env=environment, log=camp.log)
            try:
                assert ck(term.wait_for('Confirm review', 30), 'Manager local replay: real installed consent controls visible')
                term.send(STAB + ' ', .2); term.send(TAB + TAB, .2); term.send('\r', .3)
                value = read_state(state, lambda value: value.get('armed'), timeout=30, pump=term.pump)
                helper = value['helper']; directory = Path(value['directory'])
                ck(value['approved'] == value['identity'] == value['local_identity'] and value['revalidated'],
                   'Manager local replay: exact approved review staged in private bounded fixture, real terminal checks precede arming')
                ck(not (directory / 'result.json').exists() and exclusion(camp, prefix, busy=True),
                   'Manager local replay: restored dashboard/main return is not origin death; drain retains shared usage and helper cannot validate')
                if mode == 'changed': executable.write_bytes(original + b'\n# owned post-arming local-observation change\n')
                if mode == 'no-runtime':
                    unusable.write_text('import os; os._exit(73)\n')
                    refused = camp._run([str(prefix / 'bin/python'), '-c', 'pass'], env=environment, check=False)
                    ck(refused.returncode == 73, 'Manager local replay: owned late startup hook proves target runtime unavailable, not patched verifier reply')
                if mode == 'execution-policy-fault':
                    pip_module.write_text('import os\nos.environ["PIP_INDEX_URL"]="https://dummy-secret.invalid/simple"\n')
                    pip_hook.write_text('import ocs_test_policy\n')
                if mode == 'execution-source-fault': server['routes'] = graph(commit='d' * 40, tags=(annotation,), tag=tag)
                requests = len(server['requests'])
                state.with_suffix('.release').touch()
                ck(term.exit_code(15) == 0 and term.restored(), 'Manager local replay: actual originating installed process exits after real terminal restoration')
                status = wait_helper(helper, timeout=15); helper = None
                ck(status == 0, 'Manager local replay: exact adopted frozen helper finishes and is reaped')
                result = result_at(directory)
                expected = 'review-failed' if mode == 'changed' else 'execution-failed' if mode.endswith('-fault') else 'quiescent'
                ck(result.get('review', {}).get('identity') == value['identity']
                   and result['outcome'] == expected
                   and result['review']['ok'] is (mode != 'changed'),
                   'Manager local replay: helper-owned kernel exclusion replays only approved local observations, changed launcher refuses')
                if mode.startswith('execution'):
                    ck(result.get('execution', {}).get('ok') is (mode == 'execution')
                       and len(server['requests']) == requests + (0 if mode == 'execution-policy-fault' else 6),
                       'Manager execution validation: actual frozen external runtime/dependencies/effective pip/Git policy and fresh exact source checked; independent faults refuse')
                    ck('dummy-secret' not in json.dumps(result), 'Manager execution validation: no effective policy/credential diagnostics disclosed')
                else:
                    ck(len(server['requests']) == requests and 'verifier' not in result,
                       'Manager local replay: no target package/runtime/normal CLI, external tool or network execution is inferred from local replay')
                ck(exclusion(camp, prefix, busy=False), 'Manager local replay: helper exit releases exclusion, no witness/lease leak or lock-file deletion')
            finally:
                state.with_suffix('.release').touch()
                term.pump(.1); state.with_suffix('.pty').write_bytes(term.raw)
                term.close()
                if helper is not None:
                    try:
                        if os.waitpid(helper, os.WNOHANG)[0] == 0:
                            os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                    except ChildProcessError: pass
                if unusable.exists(): unusable.unlink()
                if pip_hook.exists(): pip_hook.unlink()
                if pip_module.exists(): pip_module.unlink()
                if executable.read_bytes() != original: executable.write_bytes(original)
                hook.unlink(); module.unlink()
