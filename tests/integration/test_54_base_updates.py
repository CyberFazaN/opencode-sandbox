"""Actual cached/full-refresh packaged builds, immutable publication and Base Images terminals.

Only run-owned image namespaces; the Docker Hub registry hostname is explicit in copied FROM
lines so --pull cannot move the retained original upstream tag. No package/tool checks weakened,
no prune, model-provider calls or host/service changes. Existing test image-namespace technique.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest
from campaign import DISTROS, ROOT
from test_66_manager_inventory import exclusion

pytest.importorskip('pyte')
from pty_term import DOWN, ENTER, ESC, TAB, Term

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]

HARNESS = r'''
import json, os, re, sys, time
from pathlib import Path
from opencode_sandbox import core as c, distros, probes, build_output
cfg = json.loads(Path(sys.argv.pop(1)).read_text())
assert re.fullmatch(r'ocs-test-[a-z0-9-]+', cfg['repo'])
distros.REPOSITORY = cfg['repo']
distros.IMAGES = Path(cfg['assets'])
probes.PREFIX = 'ocs-test-' + cfg['run'] + '-probe-'
def note(text):
    with open(cfg['manifest'], 'a') as stream: stream.write(text + '\n')
actual = c.docker
def docker(*args, **kwargs):
    if args[0] in ('build', 'tag'):
        ref = args[args.index('-t') + 1] if args[0] == 'build' else args[-1]
        note('image ' + ref)
        if args[0] == 'build':
            note('build argv ' + json.dumps(args))
            args = (args[0], '--label', 'org.opencode-sandbox.test=' + cfg['run'], *args[1:])
    if args[0] == 'run' and '--name' in args:
        note('container ' + args[args.index('--name') + 1] + ' test=' + cfg['run'])
        args = (args[0], '--label', 'org.opencode-sandbox.test=' + cfg['run'], *args[1:])
    result = actual(*args, **kwargs)
    if args[0] in ('build', 'tag'):
        note('image-id ' + actual('image','inspect','--format','{{.Id}}',ref,capture=True).stdout.strip())
    return result
c.docker = docker
real_verify = c.verify_image
def verify(*args):
    real_verify(*args)
    if os.environ.get('OCS_TEST_FAIL_BASE_VERIFY') == '1':
        raise c.SandboxError('test failure after actual candidate verification')
c.verify_image = verify
real_build = c.build_image
def build(*args, **kwargs):
    image_id = real_build(*args, **kwargs)
    hold = os.environ.get('OCS_TEST_BASE_HOLD')
    if hold:
        ready, release = Path(hold + '.ready'), Path(hold + '.release')
        ready.write_text(image_id)
        build_output.phase('Test hold after actual build; verification/publication pending')
        end = time.monotonic() + 90
        while not release.exists():
            if time.monotonic() > end: raise c.SandboxError('test release deadline')
            time.sleep(.05)
    return image_id
c.build_image = build
if sys.argv[1:] == ['cleanup-bases']:
    from opencode_sandbox import cleanup as cl
    c.ensure_runtime()
    lines = Path(cfg['manifest']).read_text().splitlines()
    refs = {line[6:] for line in lines if line.startswith('image ')}
    ids = {line[9:] for line in lines if line.startswith('image-id ')}
    inv = cl.inventory()
    assert not inv.errors, inv.errors
    items = [item for item in inv.eligible(True) if item.ref.startswith(cfg['repo'] + ':') or item.image_id in ids]
    assert all(item.ref in refs or item.ref in ids for item in items)
    result = cl.apply([item.key for item in items],superseded=True)
    assert all(error is None for _,error in result), result
    d = distros.get(cfg['distro'])
    info = c.inspect_base_image(d,d.image,missing=True)
    if info:
        assert d.image in refs and info['Id'] in ids and info['Config']['Labels']['org.opencode-sandbox.test'] == cfg['run']
        c.docker('image','rm',d.image,capture=True)
    assert not c.docker('image','ls','-q',cfg['repo'],capture=True).stdout.strip()
    print('CLEAN test bases')
else:
    from opencode_sandbox.cli import main
    main()
'''


def consent(term, ck, label):
    assert ck(term.wait_for('Review Base Images operation', 30), label + ': exact consent visible')
    ck('Cancel' in term.text() and 'Confirm' in term.text(), label + ': buttons visible')
    term.snap(label)


@pytest.mark.parametrize('distro', DISTROS)
def test_cached_refresh_safety_and_base_actions_terminals(campaign, checks, distro):
    camp, ck = campaign, checks
    repo = f'ocs-test-{camp.run}-{distro}'
    work = camp.tmp('base-actions-' + distro)
    assets = work / 'images'
    shutil.copytree(ROOT / 'src/opencode_sandbox/assets/images', assets)
    upstream = {'arch': 'archlinux:base-devel', 'debian': 'node:24-trixie'}[distro]
    alias = 'registry-1.docker.io/library/' + upstream
    dockerfile = assets / distro / 'Dockerfile'
    original = dockerfile.read_text()
    dockerfile.write_text(original.replace('FROM ' + upstream, 'FROM ' + alias))
    assert dockerfile.read_text().replace(alias, upstream) == original
    assert camp.docker('image', 'inspect', alias, check=False).returncode != 0, 'Test alias already exists; do not take it over'
    camp.note(f'upstream alias {alias} initially absent; only copied FROM hostname differs, original {upstream} stays read-only')
    if distro == 'arch': camp.docker('tag', upstream, alias)
    camp.note('upstream alias ' + alias + ' created/pulled only by this run; safe untag after test, no cache prune')
    cfg = work / 'harness.json'
    cfg.write_text(json.dumps({'repo': repo, 'assets': str(assets), 'run': camp.run, 'manifest': str(camp.manifest_path), 'distro': distro}))
    script = work / 'base_cli.py'
    script.write_text(HARNESS)
    def run(*args, check=True, env=None):
        return camp._run([sys.executable, str(script), str(cfg), *args], check=check, env=env, timeout=2400)
    def current():
        return camp.docker('image', 'inspect', '--format', '{{.Id}}', repo + ':' + distro).stdout.strip()
    names = []
    try:
        package = 'apt-get update' if distro == 'debian' else 'pacman-retry -Syu'
        first = run('opencode', 'update-base', '--distro', distro, '--version', '2.1.4', '--yes')
        first_image = current()
        ck('Mode: Cached rebuild' in first.stdout and 'always refreshed and upgraded in both modes' in first.stdout,
           'Cached: explicit mode, exact target and mandatory package upgrade disclosed')
        second = run('opencode', 'update-base', '--distro', distro, '--version', '2.1.4', '--yes')
        initial = current()
        ck("'unchanged': True" not in second.stdout and initial != first_image, 'Cached: repeated build upgraded packages and published a new verified image')
        builds = [json.loads(line[len('build argv '):]) for line in camp.manifest_path.read_text().splitlines() if line.startswith('build argv ')]
        nonces = [next(arg for arg in args if arg.startswith('SYSTEM_PACKAGE_REFRESH=')) for args in builds[-2:]]
        ck(len(set(nonces)) == 2 and not any(flag in builds[-1] for flag in ('--pull', '--no-cache')),
           'Cached: fresh package nonce per build, without pull/no-cache')
        step = re.search(r'(#\d+) \[[^\n]+RUN [^\n]*' + re.escape(package), second.stderr)
        ck(step is not None and step.group(1) + ' CACHED' not in second.stderr, 'Cached: package layer ran instead of using cached result')
        ck('CACHED' in second.stderr, 'Cached: actual Docker build reused earlier cached layers')
        name = f'ocs-test-{camp.run}-{distro}-retained'
        run('create', name, '--distro', distro, '--no-integrations')
        camp.adopt(name); names.append(name)
        run('opencode', 'policy-set', name, 'pinned', '--version', '2.1.4')
        run('start', name)
        eid = camp.ids[name]
        camp.sh(eid, 'echo retained-layer > /etc/ocs-test-base-update; echo retained-home > /root/ocs-test-base-update; echo retained-workspace > /workspace/ocs-test-base-update')
        before = camp.inspect(eid)
        metadata = camp.metadata(name)
        refreshed = run('opencode', 'update-base', '--distro', distro, '--version', '2.1.4', '--yes', '--refresh')
        new = current()
        ck('Mode: Refresh & Rebuild' in refreshed.stdout and new != initial, 'Refresh: actual full rebuild verified/published a distinct image')
        builds = [json.loads(line[len('build argv '):]) for line in camp.manifest_path.read_text().splitlines() if line.startswith('build argv ')]
        ck('--pull' in builds[-1] and '--no-cache' in builds[-1] and not any('prune' in args for args in builds), 'Refresh: explicit pull/no-cache, never prune')
        step = re.search(r'(#\d+) \[[^\n]+RUN [^\n]*' + re.escape(package), refreshed.stderr)
        ck(step is not None and step.group(1) + ' CACHED' not in refreshed.stderr, 'Refresh: package layer ran instead of using cached result')
        after = camp.inspect(eid)
        ck(after['Id'] == before['Id'] and after['Image'] == initial and after['State']['Running']
           and camp.metadata(name) == metadata, 'Refresh: retained running container/image/pin/metadata unchanged')
        ck('retained-layer' in camp.sh(eid, 'cat /etc/ocs-test-base-update').stdout, 'Refresh: retained writable layer preserved')
        fresh = f'ocs-test-{camp.run}-{distro}-fresh'
        run('create', fresh, '--distro', distro, '--no-integrations'); camp.adopt(fresh); names.append(fresh)
        run('opencode', 'policy-set', fresh, 'pinned', '--version', '2.1.4'); run('start', fresh)
        ck(camp.inspect(camp.ids[fresh])['Image'] == new and '2.1.4' in camp.sh(camp.ids[fresh], 'opencode --version').stdout,
           'Refresh: future pinned creation uses exactly the new verified base')
        fail = run('opencode', 'update-base', '--distro', distro, '--version', '2.1.4', '--yes',
                   check=False, env=dict(camp.env, OCS_TEST_FAIL_BASE_VERIFY='1'))
        ck(fail.returncode != 0 and 'test failure after actual candidate verification' in fail.stderr and current() == new,
           'Failed candidate: actual build/verification failure leaves current base unchanged')
        ck(not camp.docker('image', 'ls', '-q', '--filter', f'reference={repo}:{distro}-candidate-*').stdout.strip(),
           'Failed candidate: only owned candidate cleaned, no candidate leak')
        # Real TUI mode selection at both sizes; approved cached rebuild held after the actual
        # build to prove responsiveness/Close/Quit semantics without replacing Docker results.
        for size in ((80, 24), (120, 40)):
            hold = work / f'hold-{size[0]}'
            term = Term([sys.executable, str(script), str(cfg), 'tui'], *size,
                        env=dict(camp.env, OCS_TEST_BASE_HOLD=str(hold)), log=camp.log)
            try:
                ck(term.wait_for(name, 30), 'Base terminal: dashboard ready')
                term.send('v', .3); term.send('2', .3)
                term.send(DOWN if distro == 'arch' else '', .2)
                term.send('b', .3)
                ck(term.wait_for('Build / Rebuild', 15), 'Base terminal: target/mode form visible')
                ck('always upgrade system packages' in term.text() and 'Update system packages' not in term.text(),
                   'Base terminal: mandatory package upgrade disclosed, no opt-out control')
                term.send('\x05', .1); term.send('\x15', .1); term.send('2.1.4', .2)
                term.send(TAB, .1); term.send(ENTER, .2); term.send(DOWN, .1); term.send(ENTER, .2)
                term.send(TAB * 2 + ENTER, .3)
                consent(term, ck, 'Refresh mode consent')
                ck(term.wait_for('Refresh & Rebuild', 10), 'Base terminal: exact full-refresh mode disclosed before consent')
                term.send(ESC, .2)
                ck(not Path(str(hold) + '.ready').exists(), 'Base terminal: Cancel never built/refreshed')
                term.send('b', .3)
                term.send('\x05', .1); term.send('\x15', .1); term.send('2.1.4', .2)
                term.send(TAB * 3 + ENTER, .3)  # target -> mode -> Cancel -> Review
                consent(term, ck, 'Cached mode consent')
                ck('Cached rebuild' in term.text(), 'Base terminal: cached mode is independent and explicit')
                term.send(TAB + ENTER, .3)
                # Every build reruns the package step (and paru on Arch), even in cached mode. Keep
                # draining the pty: unread progress redraws would block Textual, and the build with it.
                if not camp.wait_for(lambda hold=hold, term=term: term.pump(.2) or Path(str(hold) + '.ready').exists(), timeout=1800):
                    term.snap('Build hold not reached'); term.send('d', .5); term.snap('Build hold not reached: Details')
                assert ck(Path(str(hold) + '.ready').exists(), 'Base terminal: actual build completes before test hold')
                ck(exclusion(camp, sys.prefix, busy=True), 'Base terminal: live approved mutation blocks exclusive installation access')
                term.send('d', .3)
                ck(term.wait_for('Bounded build output tail', 15), 'Base terminal: build output disclosed in scrollable Details')
                term.send(ESC, .2); term.send(ESC, .2); term.send('q', .3)
                assert ck(term.alive and os.waitid(os.P_PID, term.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None,
                          'Base terminal: normal Quit refuses active approved build')
                Path(str(hold) + '.release').write_text('release actual verification/publication')
                term.send('v', .3); term.send('2', .3)
                term.send(DOWN if distro == 'arch' else '', .1)
                ck(term.wait_for(r'Base (?:build verified and published|verified unchanged)', 60), 'Base terminal: closed screen did not cancel mutation; result adopted')
                # A content-equivalent cached build may leave the original image current. It
                # then is not a rollback copy: explicitly swap back to the known refreshed ID.
                rollback_target = new if current() == initial else initial
                term.send('r', .4)
                assert ck(term.wait_for(r'Review Base Images operation|Choose rollback copy', 20), 'Base terminal: rollback review available')
                if 'Choose rollback copy' in term.text():
                    choices = re.findall(r'^sha256:[0-9a-f]{64}', run('opencode', 'rollback-base', '--distro', distro, '--list').stdout, re.MULTILINE)
                    assert rollback_target in choices
                    term.send(ENTER, .2); term.send(DOWN * (choices.index(rollback_target) + 1), .2); term.send(ENTER, .2)
                    term.send(TAB * 3 + ENTER, .3)
                    ck(True, 'Base terminal: multiple distinct copies explicitly selected, no default')
                consent(term, ck, 'Immutable rollback consent')
                term.send(TAB + ENTER, .4)
                ck(term.wait_for('Base rollback verified and published', 60) and current() == rollback_target,
                   'Base terminal: exact selected image actually restored through existing handler')
                term.send(ESC, .2); term.send('q', .3)
                ck(term.exit_code(15) == 0 and term.restored(), 'Base terminal: normal completion/quit restores terminal')
            finally:
                Path(str(hold) + '.release').write_text('release before harness shutdown')
                term.close()
        # Real immutable rollback still keeps the replaced base; multiple copies never default.
        listed = run('opencode', 'rollback-base', '--distro', distro, '--list')
        final_target = initial if current() == new else new
        ck(final_target in listed.stdout, 'Rollback: replaced image retained with exact immutable identity')
        rolled = run('opencode', 'rollback-base', '--distro', distro, '--copy', final_target, '--yes')
        ck(current() == final_target and 'replaced image kept as' in rolled.stdout, 'Rollback: actual selected image verified/swapped, replaced current retained')
        ck(camp.inspect(eid)['Id'] == before['Id'] and 'retained-layer' in camp.sh(eid, 'cat /etc/ocs-test-base-update').stdout,
           'Rollback: existing running container and writable layer still unchanged')
    finally:
        for name in names:
            if name in camp.ids: camp.delete(name)
        run('cleanup-bases')
        camp.docker('image', 'rm', alias, check=False)
        ck(not camp.docker('image', 'ls', '-q', repo).stdout.strip(), 'Base actions: no test base/candidate/rollback tags leaked')
