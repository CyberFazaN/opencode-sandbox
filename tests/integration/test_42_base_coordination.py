"""UP-03/UP-04: staged real Docker races and identity-bound rollback selection.

Builds packaged definitions OR explicitly selected network-free retained-image fixtures under
run-owned tags, never replaces the user's bases. The latter is race evidence, not a package/OS
refresh test. No model provider, privileged host operation or context-default change. Pauses are test-only
instrumentation around the real build/verify/start handlers, not substituted Docker results.
"""
import json
import os
import re
import subprocess
import sys

import pytest
from campaign import DISTROS

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]

WORKER = r'''
import json, os, re, sys
from pathlib import Path
from dataclasses import replace
from opencode_sandbox import core as c, cleanup as cl, distros, integrations as ig, opencode_versions as v
repo, distro, action, manifest, run, mode = sys.argv[1:]
assert re.fullmatch(r'ocs-test-[a-z0-9-]+', repo)
retained = distros.get(distro).image
distros.REPOSITORY = repo
d = distros.get(distro)
def note(line):
    with open(manifest, 'a') as f: f.write(line + '\n')
real_docker = c.docker
def docker(*args, **kwargs):
    if args[0] == 'build':
        tag = args[args.index('-t') + 1]
        note('image ' + tag)
        args = (args[0], '--label', 'org.opencode-sandbox.test=' + run,
                '--label', 'org.opencode-sandbox.test-phase=' + action, *args[1:])
    if args[0] == 'tag':
        note('image ' + args[-1])
    result = real_docker(*args, **kwargs)
    if args[0] == 'build' or args[0] == 'tag':
        ref = tag if args[0] == 'build' else args[-1]
        info = real_docker('image','inspect','--format','{{.Id}}',ref,capture=True).stdout.strip()
        note('image-id ' + info)
    return result
c.docker = docker
c.ensure_runtime()
print('ENDPOINT ' + c.docker_endpoint(), flush=True)
note('shared base lock namespace /tmp/opencode-sandbox-locks-' + str(os.getuid()) +
     ' (persistent protocol state, never unlinked by cleanup)')
if mode == 'local-fixture':
    # An explicit retained-OS fixture, not a weakened current-definition check. Verification
    # still executes every promised tool/smoke test and the actual binary in a real container.
    info = c.inspect_base_image(d,retained)
    definition = distros.image_definition(distro,info['Config']['Labels'])
    expected = tuple((key, definition.version if key == 'VERSION_ID' else value) for key,value in d.os_release)
    d = replace(d,version=definition.version,revision=definition.revision,os_release=expected)
    distros.REGISTRY[distro] = d
    root = Path(manifest).parent.parent / run / 'local-image-fixtures'
    (root / distro).mkdir(parents=True,exist_ok=True)
    note('host dir ' + str(root / distro))
    (root / distro / 'Dockerfile').write_text('FROM ' + retained + '\nARG OPENCODE_VERSION\n')
    distros.IMAGES = root
if action in ('build', 'held-build'):
    if action == 'held-build':
        real_build = c.build_image
        def build(*args):
            real_build(*args)
            print('READY build', flush=True)
            input()
        c.build_image = build
    print('RESULT ' + json.dumps(v.update_base('2.2.0',distro)), flush=True)
elif action in ('try-update', 'try-rollback'):
    real_lock = c.base_lock
    c.base_lock = lambda distro, phase, **kw: real_lock(distro, phase, timeout=0)
    try:
        v.update_base('2.2.0',distro) if action == 'try-update' else v.rollback_base(distro)
    except c.SandboxError as exc:
        assert 'Base image busy:' in str(exc), str(exc)
        print('BUSY ' + str(exc), flush=True)
    else:
        raise AssertionError('conflicting mutation was not blocked')
elif action in ('start', 'held-start'):
    name = 'ocs-test-' + run + '-' + distro + '-' + action
    m = c.create(name,'scratch',distro=distro,provisioning=ig.request([]))
    note('environment ' + name + ' id=' + m['id'])
    with c.lock(m['id']):
        m['runtime'] = c.validate_runtime_settings({'cpus':'1','memory':'1g','pids':256,'network':'none','ports':[]})
        c.save(m)
    v.set_policy(m,'pinned','2.2.0')
    if action == 'held-start':
        actual = c.docker
        def pause(*args, **kwargs):
            if args[0] == 'run' and '--name' in args:
                print('READY creation', flush=True)
                input()
            return actual(*args, **kwargs)
        c.docker = pause
    c.start(c.resolve(m['id']))
    info = json.loads(c.docker('container','inspect',c.cname(m),capture=True).stdout)[0]
    expected = c.inspect_base_image(d,d.image)['Id']
    assert info['Image'] == expected
    assert c.docker('exec',c.cname(m),'opencode','--version',capture=True).stdout.strip().endswith('2.2.0')
    print('RESULT ' + json.dumps({'name':name,'id':m['id'],'image':info['Image']}),flush=True)
elif action == 'held-rollback':
    real_verify = c.verify_image
    def verify(*args):
        real_verify(*args)
        print('READY rollback',flush=True)
        input()
    c.verify_image = verify
    print('RESULT ' + json.dumps(v.rollback_base(distro)),flush=True)
elif action == 'selection-checks':
    from typer.testing import CliRunner
    from opencode_sandbox.cli import app
    def ck(test, detail):
        assert test, detail
        print('CHECK ' + detail, flush=True)
    before = v.base_rollback_inventory(distro)
    assert len(before.copies) == 1
    target = before.copies[0].image_id
    alias = distros.previous_tag(d, '1' * 12)
    other = distros.previous_tag(d, '2' * 12)
    with c.base_lock(distro, 'build'), c.base_lock(distro, 'publication'):
        c.docker('tag',target,alias)
        c.docker('tag',before.current_id,other)
    inventory = v.base_rollback_inventory(distro)
    selected = next(item for item in inventory.copies if item.image_id == target)
    ck(len(inventory.copies) == 2 and len(selected.aliases) == 2, 'aliases consolidated into two distinct immutable images')
    runner = CliRunner()
    listed = runner.invoke(app,['opencode','rollback-base','--distro',distro,'--list'])
    ck(listed.exit_code == 0 and listed.output.count(target) == 1 and alias in listed.output,
       'real CLI lists one row per image with full identity and aliases')
    refused = runner.invoke(app,['opencode','rollback-base','--distro',distro,'--yes'])
    ck(refused.exit_code != 0 and 'Several distinct rollback copies' in str(refused.exception),
       'real noninteractive yes refuses ambiguous copy choice')
    plan = v.select_base_rollback(inventory,target)
    with c.base_lock(distro, 'build'), c.base_lock(distro, 'publication'):
        c.docker('tag',before.current_id,alias)
    try:
        v.rollback_base(plan=plan)
    except c.SandboxError as exc:
        ck('changed' in str(exc), 'real retag after consent is refused without publication')
    else:
        raise AssertionError('changed copy accepted')
    ck(c.inspect_base_image(d,d.image)['Id'] == before.current_id, 'refused plan leaves current base untouched')
    with c.base_lock(distro, 'build'), c.base_lock(distro, 'publication'):
        c.docker('tag',target,alias)
    swapped = runner.invoke(app,['opencode','rollback-base','--distro',distro,'--copy',target,'--yes'])
    print(swapped.output,flush=True)
    assert swapped.exit_code == 0, str(swapped.exception)
    ck(c.inspect_base_image(d,d.image)['Id'] == target, 'real explicit immutable CLI choice verifies and publishes exactly that copy')
    after = v.base_rollback_inventory(distro)
    ck(len(after.copies) == 1 and after.copies[0].image_id == before.current_id,
       'selected aliases consumed and replaced current image retained as one distinct rollback image')
elif action in ('cleanup', 'final'):
    listed = Path(manifest).read_text().splitlines()
    refs = {line[6:] for line in listed if line.startswith('image ')}
    ids = {line[9:] for line in listed if line.startswith('image-id ')}
    inv = cl.inventory()
    assert not inv.errors, inv.errors
    items = [i for i in inv.eligible(True) if i.ref.startswith(repo + ':') or i.image_id in ids]
    assert all(i.ref in refs or i.ref in ids for i in items)
    result = cl.apply([i.key for i in items],superseded=True)
    print('RESULT ' + json.dumps([(i if isinstance(i,str) else i.ref,error) for i,error in result]),flush=True)
    if action == 'final':
        assert all(error is None for _,error in result), result
        # The product never removes a current base. This one is test-owned, on the manifest,
        # checked by immutable labels and only untagged here after all environments were deleted.
        if d.image in refs:
            out = c.docker('image','inspect',d.image,capture=True,check=False)
            if out.returncode == 0:
                info = json.loads(out.stdout)[0]
                assert info['Id'] in ids and info['Config']['Labels']['org.opencode-sandbox.test'] == run
                c.docker('image','rm',d.image,capture=True)
        left = c.docker('image','ls','-q','--filter','label=org.opencode-sandbox.test='+run,capture=True).stdout.split()
        assert not left, left
else:
    raise AssertionError(action)
'''


@pytest.mark.parametrize("distro", DISTROS)
@pytest.mark.parametrize("mode", ["packaged", "local-fixture"])
def test_cross_directory_base_build_rollback_cleanup_and_creation(campaign, checks, distro, mode):
    camp, ck = campaign, checks
    # Each distro's fixture is removed before the next one; no retained base/copy is touched.
    repo = "ocs-test-" + re.sub("[^a-z0-9-]", "-", camp.run.lower()) + "-" + distro + "-" + mode
    script = camp.tmp("base-workers") / f"{distro}.py"
    script.write_text(WORKER)
    names, children = [], []
    first = {**camp.env, "OPENCODE_SANDBOX_HOME": str(camp.base / (distro + "-builder-data")),
             "OPENCODE_SANDBOX_CONFIG": str(camp.base / (distro + "-builder-config"))}
    # Two context names, one through a symlink, resolve to the same authenticated endpoint.
    identity = camp.python("from opencode_sandbox import core as c; c.ensure_runtime(); print(c.docker_endpoint())").stdout.strip()
    socket_dir = camp.short_dir("base-" + distro + "-" + mode)
    alias = socket_dir / "docker.sock"
    alias.symlink_to(identity[7:])
    config = camp.tmp("docker-contexts-" + distro + "-" + mode)
    context = "ocs-test-" + distro
    camp._run(["docker", "--config", str(config), "context", "create", context, "--docker", "host=unix://" + str(alias)], check=True)
    other = {**camp.env, "DOCKER_CONFIG": str(config), "OPENCODE_SANDBOX_DOCKER_CONTEXT": context}
    camp.note(f"test image namespace {repo}; mode {mode}; context {context} in {config}; socket alias {alias}")

    def argv(action):
        return [sys.executable, "-B", str(script), repo, distro, action, str(camp.manifest_path), camp.run, mode]

    def run(action, env=None):
        return camp._run(argv(action), check=True, env=env or other, timeout=1200).stdout

    def held(action, ready):
        proc = subprocess.Popen(argv(action), env=first if action == "held-build" else other,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        children.append(proc)
        # A real build can be long; select bounds the wait without buffering the entire output.
        import selectors
        import time
        deadline = time.monotonic() + 1200
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            output = ""
            while time.monotonic() < deadline:
                if not selector.select(timeout=min(1, max(0, deadline - time.monotonic()))):
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    raise AssertionError(output + f"\nworker exited {proc.poll()}")
                output += chunk.decode(errors="replace")
                if ready in output:
                    camp.log(output)
                    return proc
        raise AssertionError("worker readiness deadline exhausted")

    def release(proc):
        out, _ = proc.communicate(input="\n", timeout=120)
        camp.log(out)
        assert proc.returncode == 0, out
        return out

    try:
        run("build", first)
        initial = camp.docker("image", "inspect", "--format", "{{.Id}}", repo + ":" + distro).stdout.strip()
        build = held("held-build", "READY build")
        ck("BUSY" in run("try-update") and "BUSY" in run("try-rollback"), "shared build guard excludes rebuild and rollback across data/context overrides")
        cleanup = run("cleanup")
        ck("busy (an operation holds its lock)" in cleanup, "candidate cleanup leaves an active build alone")
        start = run("start")
        result = json.loads(next(line[7:] for line in start.splitlines() if line.startswith("RESULT ")))
        names.append(result["name"])
        camp.adopt(result["name"])
        camp.sh(result["id"], "printf 'ocs-test-layer-preserved' > /var/tmp/ocs-test-layer")
        ck(result["image"] == initial, "pinned creation remains available during build and uses the checked base")
        release(build)
        current = camp.docker("image", "inspect", "--format", "{{.Id}}", repo + ":" + distro).stdout.strip()
        ck(current != initial, "verified candidate published and replaced image retained")
        creation = held("held-start", "READY creation")
        ck("BUSY" in run("try-update"), "publication guard covers pin check through real Docker creation")
        ck("busy (an operation holds its lock)" in run("cleanup"), "rollback-copy cleanup also takes publication")
        out = release(creation)
        result = json.loads(next(line[7:] for line in out.splitlines() if line.startswith("RESULT ")))
        names.append(result["name"])
        camp.adopt(result["name"])
        camp.sh(result["id"], "printf 'ocs-test-layer-preserved' > /var/tmp/ocs-test-layer")
        ck(result["image"] == current, "new pinned container uses exactly the publication-guarded image")
        rollback = held("held-rollback", "READY rollback")
        ck("busy (an operation holds its lock)" in run("cleanup"), "rollback-copy cleanup cannot race verification/swap")
        release(rollback)
        restored = camp.docker("image", "inspect", "--format", "{{.Id}}", repo + ":" + distro).stdout.strip()
        ck(restored == initial, "real rollback restores original immutable base identity")
        selection = run("selection-checks")
        for line in selection.splitlines():
            if line.startswith("CHECK "): ck(True, line[6:])
        for name in names:
            info = camp.inspect(camp.ids[name])
            marker = camp.sh(camp.ids[name], "cat /var/tmp/ocs-test-layer").stdout
            ck(info["State"]["Running"] and info["Image"] in (initial, current) and marker == "ocs-test-layer-preserved",
               "base replacement/rollback leaves existing containers running and writable-layer marker intact")
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.kill()
            out, _ = proc.communicate(timeout=120)
            camp.log(out)
        # Include a worker that created metadata but failed before returning its RESULT.
        listed = camp.ocs("list").stdout
        for name in re.findall(r"^(ocs-test-[^ ]+) \[", listed, re.MULTILINE):
            if name.startswith("ocs-test-" + camp.run + "-" + distro + "-"):
                if name not in camp.ids:
                    camp.adopt(name)
                camp.delete(name)
        run("final")
        alias.unlink()
        ck(not camp.docker("image", "ls", "-q", repo).stdout.strip(), "no test image tags leaked")
