"""UP-05: real bounded probes, cancellation and helper cleanup on both retained bases.

No model provider, network access, current-base replacement or daemon fault injection. Only
this run's disposable environments/helper names are changed/removed; every helper is manifested.
"""
import pytest
from campaign import DISTROS

pytestmark = [pytest.mark.real_session, pytest.mark.real_identity]

WORKER = r'''
import json, os, sys, time
from pathlib import Path
from opencode_sandbox import core as c, probes, opencode_versions as v, runtime_identity as rid
name, distro, manifest, run = sys.argv[1:]
m = c.resolve(name)
c.ensure_runtime()
probes.PREFIX = 'ocs-test-' + run + '-' + distro + '-probe-'
real_docker = c.docker
helpers, clients = [], []
def note(line):
    with open(manifest, 'a') as f: f.write(line+'\n')
def docker(*args, **kwargs):
    if args[0] == 'run' and '--name' in args:
        helper = args[args.index('--name')+1]
        helpers.append(helper)
        note('container ' + helper + ' test=' + run)
        args = (args[0], '--label', 'org.opencode-sandbox.test='+run, *args[1:])
    return real_docker(*args, **kwargs)
c.docker = docker
real_popen = c.diagnostics.subprocess.Popen
def popen(*args, **kwargs):
    p = real_popen(*args, **kwargs)
    clients.append(p)
    return p
c.diagnostics.subprocess.Popen = popen
def ck(value, text):
    assert value, text
    print('CHECK ' + text, flush=True)
def missing_helpers():
    for helper in helpers:
        p=c.docker('container','inspect',helper,capture=True,check=False)
        assert p.returncode != 0 and 'no such' in p.stderr.lower(), p.stdout
    return True
def alive_probe(path):
    script='for pid in $(cat '+path+' 2>/dev/null); do test -r /proc/$pid/stat || continue; state=$(cut -d" " -f3 /proc/$pid/stat); test "$state" = Z || exit 1; done'
    return c.docker('exec',c.cname(m),'sh','-c',script,capture=True,check=False).returncode != 0
ck(v.environment_version(m)['version'] == '2.2.0', 'running OpenCode is verified through a bounded container-side probe')
ck(v.image_version(c.env_image(m)) == '2.2.0' and missing_helpers(), 'image version probe uses a named no-pull helper and leaves none')
try:
    probes.image(c.env_image(m),'sh','-c','sleep 30 & wait',timeout=.5)
except c.SandboxError as exc:
    ck('Container diagnostic timed out' in str(exc) and missing_helpers(), 'image container-side deadline stops the helper and removes it without host cleanup')
else: raise AssertionError('image timeout ignored')
path='/var/tmp/ocs-test-probe-pids'
script='echo $$ > '+path+'; sleep 30 & echo $! >> '+path+'; wait'
try:
    probes.exec(m,'sh','-c',script,timeout=.5)
except c.SandboxError as exc:
    ck('timed out' in str(exc), 'container-side deadline reports timeout, not a verified result')
else: raise AssertionError('unbounded exec succeeded')
ck(not alive_probe(path), 'container-side timeout kills its probe command and ordinary descendants')
start=time.monotonic()
try:
    with c.runtime_feedback(cancelled=lambda: time.monotonic()-start > .2):
        probes.exec(m,'sh','-c',script,timeout=.7)
except rid.Cancelled: pass
else: raise AssertionError('host cancellation ignored')
ck(time.monotonic()-start < 2, 'cancellation terminates and reaps the owned host client promptly')
time.sleep(1)
ck(not alive_probe(path), 'container probe remains bounded after its host client is killed')
start=time.monotonic()
try:
    with c.runtime_feedback(cancelled=lambda: time.monotonic()-start > .4):
        probes.image(c.env_image(m),'sh','-c','sleep 30 & wait',timeout=5)
except rid.Cancelled: pass
else: raise AssertionError('helper cancellation ignored')
ck(missing_helpers(), 'canceled image helper is removed by invocation token, labels and full container ID')
ck(all(p.poll() is not None for p in clients), 'all completed/canceled diagnostic clients have been reaped')
original = c.docker('exec',c.cname(m),'sh','-c','command -v timeout',capture=True).stdout.strip()
assert original.startswith('/')
backup = original + '.ocs-test-up05'
note('container file temporarily renamed ' + original + ' -> ' + backup + ' in ' + c.cname(m))
try:
    c.docker('exec',c.cname(m),'mv',original,backup,capture=True)
    try: probes.exec(m,'opencode','--version')
    except c.SandboxError as exc: ck('unavailable' in str(exc), 'missing timeout tooling refuses the diagnostic without an unbounded fallback')
    else: raise AssertionError('missing timeout tool accepted')
finally:
    c.docker('exec',c.cname(m),'mv',backup,original,capture=True)
before=Path(c.env_dir(m['id'])/'metadata.json').read_bytes()
c.stop(m)
stopped=c.resolve(m['id'])
snapshot=Path(c.env_dir(m['id'])/'metadata.json').read_bytes()
calls=[]
def watch(*args,**kwargs):
    calls.append(args)
    return docker(*args,**kwargs)
c.docker=watch
ck(v.environment_version(stopped)['state'] == 'stopped' and not any(a[0] in ('start','run','exec') for a in calls),
   'ordinary stopped-environment version check starts no container or helper')
ck(Path(c.env_dir(m['id'])/'metadata.json').read_bytes() == snapshot, 'stopped version check leaves metadata byte-identical')
c.start(stopped)
ck(c.inspect_container(stopped)['Running'] and v.environment_version(stopped)['version'] == '2.2.0',
   'explicit restart remains healthy after probe failure/cancellation and tooling restoration')
ck(c.docker('exec',c.cname(m),'cat','/var/tmp/ocs-test-marker',capture=True).stdout == 'preserved',
   'diagnostics leave the environment writable-layer marker intact')
'''


@pytest.mark.parametrize("distro", DISTROS)
def test_owned_bounded_probes_and_cleanup(campaign, checks, distro):
    camp, ck = campaign, checks
    name = "ocs-test-" + camp.run + "-" + distro + "-diagnostics"
    eid = camp.create(name, "--distro", distro, "--no-integrations")
    camp.python(f"from opencode_sandbox import core as c\nm=c.resolve({name!r})\n"
                "with c.lock(m['id']):\n m['runtime']=c.validate_runtime_settings({**c.runtime_settings(m),'network':'none'}); c.save(m)\n")
    try:
        camp.ocs("start", name)
        camp.sh(eid, "printf preserved > /var/tmp/ocs-test-marker")
        script = camp.tmp("diagnostic-workers") / f"{distro}.py"
        script.write_text(WORKER)
        import sys
        out = camp._run([sys.executable, "-B", str(script), name, distro, str(camp.manifest_path), camp.run],
                        check=True, timeout=120).stdout
        for line in out.splitlines():
            if line.startswith("CHECK "): ck(True, line[6:])
    finally:
        camp.delete(name)
    ck(not camp.docker("container", "ls", "-aq", "--filter", f"label=org.opencode-sandbox.test={camp.run}").stdout.strip(),
       "no diagnostic helper with this run's label leaked")
