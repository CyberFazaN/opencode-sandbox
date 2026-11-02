"""Real parked/exec/group/parent-death processes on owned synthetic pipx, not a real install."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_manager_helper import subreaper, wait_helper
from test_manager_tools import tools as external_tools

from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_handoff as handoff
from opencode_sandbox import manager_network as policy
from opencode_sandbox import manager_operation as operation
from opencode_sandbox import manager_tools

tools = external_tools
EXTERNAL = sys.executable


@pytest.fixture
def prepared(tools, tmp_path, monkeypatch):
    monkeypatch.setattr(locks, '_TMP', Path('/tmp'))
    evidence, launcher, package, _ = tools
    facts = manager_tools.assess(evidence)
    assert facts['supported'], facts
    facts = facts['evidence']
    parent = tmp_path / 'operation'; parent.mkdir(mode=0o700)
    archive = parent / 'helper.pyz'; archive.write_bytes(handoff._bundle()); archive.chmod(0o600)
    value = {'prefix': evidence['evidence']['venv'], 'version': '6.1.0',
             'binding': json.dumps({'installation': {'evidence': {'tag': 'v6.1.0', 'commit': 'a' * 40}}, 'tools': facts}),
             'target': {'tag': 'v6.2.0', 'version': '6.2.0', 'objects': ['b' * 40]}}
    import hashlib
    environment = policy.environment(facts['settings'], {'HOME': str(parent)}, path=os.defpath)
    environment['GIT_CEILING_DIRECTORIES'] = str(parent.parent)
    record = operation.prepare(value, path=parent / operation.RECORD, helper_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                               python_version='Python ' + '.'.join(map(str, sys.version_info[:3])), environment=environment)
    marker = tmp_path / 'installer-executed.json'
    return record, parent / operation.RECORD, archive, package, marker, launcher


def implementation(prepared, *, escape=False, sleep=False):
    record, path, _archive, package, marker, _launcher = prepared
    body = ('import json,os,sys,time,subprocess\nfrom pathlib import Path\n'
            'def cli():\n'
            ' if sys.argv[1:]==["--version"]: print("1.18.7");return 0\n'
            f' Path({str(marker.with_suffix(".entered"))!r}).touch()\n'
            f' assert sys.argv[1:]==["install","--force","--python",{record["settings"]["PIPX_DEFAULT_PYTHON"]!r},'
            '"git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.2.0"]\n'
            f' state=json.loads(Path({str(Path(record["prefix"]).parent.parent / ".opencode-sandbox-updates")!r}).joinpath('
            '__import__("hashlib").sha256(os.fsencode(' + repr(record['prefix']) + ')).hexdigest()+".json").read_text())\n'
            ' assert state["phase"]=="installing" and state["installer"]["pid"]==os.getpid()\n'
            ' assert not any(name in os.environ for name in ("OPENROUTER_API_KEY","GITHUB_TOKEN","PYTHONPATH","LD_PRELOAD"))\n'
            ' value={"pid":os.getpid(),"argv":sys.argv[1:],"phase":state["phase"]}\n')
    if escape:
        body += (f' child=subprocess.Popen([{EXTERNAL!r},"-I","-B","-S","-c","import time;time.sleep(30)"],start_new_session=True)\n'
                 ' value["descendant"]=child.pid\n')
    body += (f' ready=Path({str(marker)!r});partial=ready.with_name(ready.name+".partial")\n'
             ' partial.write_text(json.dumps(value));partial.replace(ready)\n')
    if sleep: body += ' time.sleep(30)\n'
    body += ' return 0\n'
    (package / '__main__.py').write_text(body)
    return path


def owner(prepared, *, fault=None):
    record, path, archive, _package, marker, _launcher = prepared
    environment = policy.environment(record['settings'], {'HOME': str(path.parent)}, path=os.defpath)
    environment['GIT_CEILING_DIRECTORIES'] = str(path.parent.parent)
    code = ('import json,os,signal,sys,time\nfrom pathlib import Path\n'
            f'sys.path.insert(0,{str(archive)!r})\n'
            'import installation_locks as locks,manager_operation as operation,manager_installer as installer\n'
            f'path=Path({str(path)!r});record=operation.read(path)\n'
            'def interrupted(signum,frame): raise InterruptedError("owned test interruption")\n'
            'signal.signal(signal.SIGTERM,interrupted)\n'
            'with locks.exclusive(record["prefix"]):\n'
            ' locks.record_operation(operation.status(record,path),record["prefix"])\n')
    if fault in ('persist', 'unpersisted-go'):
        code += (' actual=locks.record_operation\n'
                 ' def persist(value,prefix=None):\n'
                 + ('  if value["phase"]=="installing": return None\n' if fault == 'unpersisted-go' else
                    '  if value["phase"]=="installing": raise OSError("owned durable admission failure")\n') +
                 '  return actual(value,prefix)\n'
                 ' locks.record_operation=persist\n')
    if fault == 'owner-fd':
        code += (' actual=installer.json.dumps\n'
                 ' def outgoing(value,*args,**kwargs):\n'
                 '  if isinstance(value,dict) and "owner_fd" in value: value={**value,"owner_fd":1000000}\n'
                 '  return actual(value,*args,**kwargs)\n'
                 ' installer.json.dumps=outgoing\n')
    if fault == 'parked':
        code += (' actual=installer.protocol._message\n'
                 ' def parked(*args,**kwargs):\n'
                 '  value=actual(*args,**kwargs)\n'
                 f'  ready=Path({str(marker.with_suffix(".parked"))!r});partial=ready.with_name(ready.name+".partial")\n'
                 '  partial.write_text(json.dumps(value));partial.replace(ready)\n'
                 '  time.sleep(30)\n'
                 '  return value\n'
                 ' installer.protocol._message=parked\n')
    code += (' try:\n'
             f'  status=installer.replace(locks,record,path,{{"environment":{environment!r}}})\n'
             ' except (OSError,RuntimeError): status="interrupted"\n'
             ' print(json.dumps({"status":status,"state":locks.operation_state(record["prefix"]),"children":installer._children()}),flush=True)\n')
    return subprocess.Popen([EXTERNAL, '-I', '-B', '-S', '-c', code], env={'HOME': str(path.parent), 'PATH': os.defpath},
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def wait_marker(path):
    deadline = time.monotonic() + 8
    while not path.exists() and time.monotonic() < deadline: time.sleep(.01)
    assert path.exists(), 'Owned installer did not reach rendezvous'
    return json.loads(path.read_text())


@pytest.mark.parametrize('escape', [False, True])
def test_exact_argv_enters_pipx_only_after_durable_identity_and_reaps_even_escaped_adopted_descendants(prepared, escape):
    implementation(prepared, escape=escape)
    process = owner(prepared)
    out, error = process.communicate(timeout=10)
    assert process.returncode == 0, error
    value = json.loads(out)
    assert value['status'] == 0 and value['state']['phase'] == 'verifying' and value['state']['installer'] is None
    assert value['children'] == []
    assert json.loads(prepared[4].read_text())['phase'] == 'installing'


def test_failed_durable_installing_record_kills_parked_child_before_any_pipx_execution(prepared):
    implementation(prepared)
    process = owner(prepared, fault='persist')
    out, error = process.communicate(timeout=10)
    assert process.returncode == 0, error
    value = json.loads(out)
    assert value['status'] == 'interrupted' and value['state']['phase'] == 'manual-recovery'
    assert value['state']['installer'] is None and value['children'] == [] and not prepared[4].exists()
    assert not prepared[4].with_suffix('.entered').exists()


@pytest.mark.parametrize('fault', ['unpersisted-go', 'owner-fd'])
def test_child_independently_refuses_go_without_durable_admission_and_exact_live_kernel_owner(prepared, fault):
    implementation(prepared)
    process = owner(prepared, fault=fault)
    out, error = process.communicate(timeout=10)
    assert process.returncode == 0, error
    value = json.loads(out)
    assert value['status'] == 2 and value['children'] == [] and value['state']['installer'] is None
    assert not prepared[4].exists() and not prepared[4].with_suffix('.entered').exists()


def test_handled_interruption_reaps_actual_child_and_escaped_descendant_before_verification_state(prepared):
    implementation(prepared, escape=True, sleep=True)
    process = owner(prepared)
    try:
        wait_marker(prepared[4])
        process.send_signal(signal.SIGTERM)
        out, error = process.communicate(timeout=10)
        assert process.returncode == 0, error
        value = json.loads(out)
        assert value['status'] == 'interrupted' and value['children'] == []
        assert value['state']['phase'] == 'verifying' and value['state']['installer'] is None
    finally:
        if process.poll() is None: process.kill()
        process.communicate(timeout=5)


@pytest.mark.parametrize('parked', [False, True])
def test_killed_owner_never_leaves_an_inherited_lock_or_clears_authoritative_pending_state(prepared, parked):
    implementation(prepared, escape=not parked, sleep=True)
    child = descendant = process = None
    with subreaper():
        try:
            process = owner(prepared, fault='parked' if parked else None)
            value = wait_marker(prepared[4].with_suffix('.parked') if parked else prepared[4])
            child = value['pid']; descendant = value.get('descendant')
            if parked:
                # EOF refusal can beat PDEATHSIG during parent exit. Stop this exact parked
                # child after its authenticated rendezvous so the kernel signal, not scheduling,
                # determines the outcome; SIGKILL must still terminate a stopped process.
                descriptor = os.pidfd_open(child)
                try: signal.pidfd_send_signal(descriptor, signal.SIGSTOP)
                finally: os.close(descriptor)
                deadline = time.monotonic() + 2
                while True:
                    fields = Path(f'/proc/{child}/stat').read_text().rsplit(')', 1)[1].split()
                    assert int(fields[1]) == process.pid and fields[19] == value['start']
                    if fields[0] == 'T': break
                    assert time.monotonic() < deadline, 'Owned installer did not enter the stopped rendezvous'
                    time.sleep(.01)
            process.kill(); process.communicate(timeout=5)
            assert wait_helper(child) == -signal.SIGKILL; child = None
            with locks.exclusive(prepared[0]['prefix']): pass
            pending = locks.operation_state(prepared[0]['prefix'])
            assert pending['phase'] == ('prepared' if parked else 'installing')
            if not parked:
                assert Path(f'/proc/{descendant}').exists()  # group absence is NOT descendant quiescence
                before = json.dumps(pending, sort_keys=True)
                completed = subprocess.run([EXTERNAL, '-I', '-B', '-S', str(prepared[2]), 'recover', str(prepared[1])],
                                           env={'HOME': str(prepared[1].parent), 'PATH': os.defpath}, capture_output=True, text=True, timeout=5, check=False)
                assert completed.returncode == 2 and 'quiescence is unknown' in completed.stdout
                assert json.dumps(locks.operation_state(prepared[0]['prefix']), sort_keys=True) == before
            else: assert not prepared[4].exists()
        finally:
            if process is not None:
                if process.poll() is None: process.kill()
                process.communicate(timeout=5)
            for pid in (child, descendant):
                if pid is not None:
                    try:
                        if os.waitpid(pid, os.WNOHANG)[0] == 0: os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
                    except ChildProcessError: pass
