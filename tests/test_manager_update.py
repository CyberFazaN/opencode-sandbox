"""Whole frozen handoff with actual venv/files/runtime and a synthetic pipx implementation.

This is host/process behavior, NOT real pipx replacement or public release authenticity. The
frozen HTTP transport and system-config filenames in the fixture-owned package are substituted;
production independent checks and state remain real. No host system configuration is changed.
"""
import json
import os
import runpy
import select
import shutil
import signal
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest
from manager_policy_fixture import git_wrapper, system_paths, system_source
from manager_source_fixture import graph, serve
from test_manager_helper import result_at, subreaper, wait_helper
from test_manager_installer import wait_marker
from test_manager_tools import tools as external_tools

from opencode_sandbox import installation_locks as locks
from opencode_sandbox import manager_installer

tools = external_tools
EXTERNAL = sys.executable
SITE = sysconfig.get_path('purelib')
GIT = shutil.which('git')
ROOT = Path(__file__).resolve().parents[1]
PUBLISH = '''
import json,os,shutil,sys,time,subprocess
from pathlib import Path
def publish(prefix,version,commit,bindir,source_python):
 prefix=Path(prefix);site=next(prefix.glob('lib/python*/site-packages'))
 old=list(site.glob('opencode_sandbox-*.dist-info'))
 dist=site/('opencode_sandbox-'+version+'.dist-info')
 if old and old[0]!=dist: old[0].rename(dist)
 dist.mkdir(exist_ok=True)
 (dist/'METADATA').write_text('Metadata-Version: 2.1\\nName: opencode-sandbox\\nVersion: '+version+'\\n')
 (dist/'entry_points.txt').write_text('[console_scripts]\\nopencode-sandbox=opencode_sandbox.launcher:main\\n')
 source='https://github.com/CyberFazaN/opencode-sandbox.git'
 (dist/'direct_url.json').write_text(json.dumps({'url':source,'vcs_info':{'vcs':'git','requested_revision':'v'+version,'commit_id':commit}}))
 (site/'opencode_sandbox/__init__.py').write_text('__version__ = '+repr(version)+'\\n')
 python=prefix/'bin/python';app=prefix/'bin/opencode-sandbox'
 body='import sys\\nfrom opencode_sandbox.launcher import main\\n'+'if __name__ == '+repr('__main__')+':\\n    sys.argv[0] = sys.argv[0].removesuffix('+repr('.exe')+')\\n    sys.exit(main())\\n'
 app.write_text('#!/bin/sh\\n'+"\'\'\'exec\' "+('"'+str(python)+'"' if ' ' in str(python) else str(python))+' "$0" "$@"\\n'+"\' \'\'\'\\n"+body);app.chmod(0o700)
 bindir=Path(bindir);bindir.mkdir(exist_ok=True)
 launcher=bindir/'opencode-sandbox'
 if not launcher.is_symlink(): launcher.symlink_to(app)
 record={'main_package':{'package':'opencode-sandbox','package_version':version,'package_or_url':'git+'+source+'@v'+version,'apps':['opencode-sandbox'],'app_paths':[str(app)],'pip_args':[],'include_dependencies':False,'include_apps':True},'source_interpreter':source_python,'python_version':'Python '+'.'.join(map(str,sys.version_info[:3])),'venv_args':[],'injected_packages':{},'pipx_metadata_version':'0.12'}
 (prefix/'pipx_metadata.json').write_text(json.dumps(record))
 files=[app,site/'opencode_sandbox/__init__.py',*(dist/name for name in ('METADATA','entry_points.txt','direct_url.json','RECORD'))]
 (dist/'RECORD').write_text(''.join(os.path.relpath(path,site)+',,\\n' for path in files))
'''


@pytest.fixture
def installed(tools, tmp_path, monkeypatch):
    monkeypatch.setattr(locks, '_TMP', Path('/tmp'))
    evidence, _launcher, package, _metadata = tools
    prefix = Path(evidence['evidence']['venv'])
    home = tmp_path / 'home'; home.mkdir()
    bindir = Path(evidence['evidence']['pipx_bin_dir']); bindir.mkdir()
    dependencies = tmp_path / 'external-dependencies'; dependencies.mkdir()
    for path in Path(SITE).iterdir():
        if path.name.startswith(('opencode_sandbox', '__editable__')) or path.name == '__pycache__': continue
        (dependencies / path.name).symlink_to(path)
    # Use actual target/shared venv interpreters; their dependencies come from the existing test
    # venv via a plain .pth path, not an installation, network bootstrap or editable target import.
    for venv in (prefix, prefix.parent.parent / 'shared'):
        subprocess.run([EXTERNAL, '-I', '-B', '-m', 'venv', '--without-pip', str(venv)], capture_output=True, check=True, timeout=10)
        site = next(venv.glob('lib/python*/site-packages'))
        (site / 'ocs_test_dependencies.pth').write_text(str(dependencies) + '\n')
    site = next(prefix.glob('lib/python*/site-packages'))
    shutil.copytree(ROOT / 'src/opencode_sandbox', site / 'opencode_sandbox', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    network = site / 'opencode_sandbox/manager_network.py'
    system = system_paths(tmp_path / 'system-configs')
    network.write_bytes(system_source(network.read_bytes(), system))
    git_wrapper(Path(shutil.which('pipx')).parent / 'git', EXTERNAL, GIT, system[0])
    # Evaluate test-owned fixture source only, never a source/control file supplied to the product.
    publisher = tmp_path / 'publisher.py'; publisher.write_text(PUBLISH)
    namespace = runpy.run_path(str(publisher))
    namespace['publish'](prefix, '6.1.0', 'a' * 40, bindir, EXTERNAL)
    environment = {'HOME': str(home), 'PATH': str(bindir) + ':' + os.environ['PATH'] + ':/usr/bin:/bin',
                   'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_CONFIG_DIRS': str(tmp_path / 'system-xdg'),
                   'PIPX_HOME': str(prefix.parent.parent), 'PIPX_BIN_DIR': str(bindir), 'PIPX_DEFAULT_PYTHON': EXTERNAL,
                   'OPENCODE_SANDBOX_HOME': str(tmp_path / 'data'), 'OPENCODE_SANDBOX_CONFIG': str(tmp_path / 'config'),
                   'GITHUB_TOKEN': 'dummy-not-forwarded'}
    marker = tmp_path / 'pipx-executed.json'
    return prefix, bindir / 'opencode-sandbox', package, marker, environment, namespace['publish']


def configure(installed, fault):
    prefix, launcher, package, marker, _environment, _publish = installed
    code = PUBLISH + ('\ndef cli():\n'
        ' if sys.argv[1:]==["--version"]: print("1.18.7");return 0\n'
        f' assert sys.argv[1:]==["install","--force","--python",{EXTERNAL!r},"git+https://github.com/CyberFazaN/opencode-sandbox.git@v6.2.0"]\n'
        ' assert os.environ["PIP_INDEX_URL"]=="https://pypi.org/simple" and os.environ["PIP_CONFIG_FILE"]==os.devnull\n'
        ' assert os.environ["GIT_CONFIG_VALUE_0"]=="never" and os.environ["GIT_CONFIG_VALUE_1"]=="always"\n'
        ' assert "GITHUB_TOKEN" not in os.environ\n'
        + ('' if fault == 'pause' else f' Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid()}}))\n'))
    if fault == 'pause':
        code += (f' child=subprocess.Popen([{EXTERNAL!r},"-I","-B","-S","-c","import time;time.sleep(30)"],start_new_session=True)\n'
                 f' partial=Path({str(marker.with_suffix(".partial"))!r})\n'
                 ' partial.write_text(json.dumps({"pid":os.getpid(),"descendant":child.pid}))\n'
                 f' partial.replace({str(marker)!r})\n'
                 ' time.sleep(30)\n return 0\n')
    elif fault == 'before': code += ' return 19\n'
    else:
        code += f' publish(Path({str(prefix)!r}),"6.2.0",{"d" * 40 if fault == "commit" else "b" * 40!r},Path({str(launcher.parent)!r}),{EXTERNAL!r})\n'
        if fault == 'launcher': code += f' Path({str(launcher)!r}).unlink()\n'
        if fault == 'cli':
            bad_cli = 'raise RuntimeError("dummy-secret")\n'
            code += f' next(Path({str(prefix)!r}).glob("lib/python*/site-packages/opencode_sandbox/cli.py")).write_text({bad_cli!r})\n'
        code += ' return ' + ('17' if fault == 'after' else '0') + '\n'
    (package / '__main__.py').write_text(code)


def start(installed, endpoint, tmp_path, *, tag='v6.2.0', admission_failure=False):
    prefix, launcher, _package, _marker, environment, _publish = installed
    log = tmp_path / 'helper.log'
    admission_fault = b'raise OSError("owned admission failure")'
    code = ('import io,json,sys,threading,zipfile\nfrom pathlib import Path\n'
        f'sys.argv=[{str(launcher)!r}]\n'
        'from opencode_sandbox import manager_review as r,manager_targets as t,manager_releases as releases,manager_handoff as h\n'
        f't.ENDPOINT={endpoint!r};releases.API=t.ENDPOINT+"/releases?per_page=100"\n'
        'original=h._bundle\n'
        'def bundle():\n'
        ' output=io.BytesIO()\n'
        ' with zipfile.ZipFile(io.BytesIO(original())) as old,zipfile.ZipFile(output,"w") as new:\n'
        '  for name in old.namelist():\n'
        '   raw=old.read(name)\n'
        f'   if name=="manager_execution.py": raw=raw.replace(b"SOURCE_API = source.API",{("SOURCE_API = " + repr(endpoint)).encode()!r})\n'
        + (f'   if name=="manager_installer.py": raw=raw.replace(b"locks.record_operation(current, prefix)  # durable BEFORE allowing exec",{admission_fault!r})\n' if admission_failure else '') +
        '   new.writestr(name,raw)\n'
        ' return output.getvalue()\n'
        'h._bundle=bundle\n'
        f'review=r.prepare({tag!r});prepared=h.prepare_update(r.Approval(review));assert prepared["supported"],prepared\n'
        'artifact=prepared["artifact"]\n'
        f'log=open({str(log)!r},"w");sys.__stdout__=log;sys.__stderr__=log\n'
        'pending=h.start_update(artifact);pending.arm();pending.control.close()\n'
        'threading.Thread(target=lambda:sys.stdin.read()).start()\n'
        'print(json.dumps({"helper":pending.process.pid,"directory":str(artifact.directory)}),flush=True)\n')
    process = subprocess.Popen([str(prefix / 'bin/python'), '-I', '-B', '-c', code], env=environment, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert select.select([process.stdout], [], [], 20)[0], 'Owned update origin did not report readiness'
    line = process.stdout.readline()
    if not line:
        _out, error = process.communicate(timeout=3)
        pytest.fail(error)
    return process, json.loads(line), log


@pytest.mark.parametrize('fault', ['none', 'before', 'after', 'launcher', 'cli', 'commit'])
def test_real_origin_death_exclusive_frozen_execution_and_independent_outcome_classification(installed, tmp_path, fault):
    configure(installed, fault)
    prefix, launcher, _package, marker, environment, publish = installed
    sentinel = tmp_path / 'user-data'; sentinel.write_bytes(b'preserved-user-workspace-and-configuration')
    helper = origin = None
    with serve(graph(commit='b' * 40)) as (endpoint, _server), subreaper():
        try:
            origin, value, log = start(installed, endpoint, tmp_path)
            helper = value['helper']; directory = Path(value['directory'])
            assert origin.poll() is None and not marker.exists() and not (directory / operation_record()).exists()
            with pytest.raises(locks.Error, match='busy'), locks.exclusive(prefix): pass
            origin.communicate(timeout=10)
            assert origin.returncode == 0
            status = wait_helper(helper, timeout=25); helper = None
            result = result_at(directory)
            expected = 'target-verified' if fault in ('none', 'after') else 'previous-verified' if fault == 'before' else 'target-unverified' if fault == 'cli' else 'unavailable'
            assert result['outcome'] == expected, log.read_text()
            assert status == (0 if fault == 'none' else 2)
            assert result['fixture'] is False and marker.exists()
            state = locks.operation_state(prefix)
            assert state['result'] == expected and state['phase'] == ('complete' if fault in ('none', 'after', 'before') else 'manual-recovery')
            assert state['installer'] is None and state['owner']['pid'] == result['helper']
            assert sentinel.read_bytes() == b'preserved-user-workspace-and-configuration'
            assert 'dummy-secret' not in log.read_text() and 'dummy-not-forwarded' not in log.read_text()
            # Same-boot explicit recovery is possible only with the final quiescence proof, and
            # still must perform fresh full verification. No cache, exit status or file deletion.
            if fault in ('launcher', 'cli', 'commit'):
                refused = subprocess.run([str(prefix / 'bin/python'), '-I', '-B', '-m', 'opencode_sandbox.launcher', '--help'],
                                         env=environment, capture_output=True, text=True, timeout=5, check=False)
                assert refused.returncode == 2 and 'update incomplete' in refused.stderr
                # Test operator repairs only its manifested synthetic installation, not the updater.
                if fault == 'cli':
                    site = next(prefix.glob('lib/python*/site-packages'))
                    shutil.copy2(ROOT / 'src/opencode_sandbox/cli.py', site / 'opencode_sandbox/cli.py')
                publish(prefix, '6.1.0' if fault == 'commit' else '6.2.0', 'a' * 40 if fault == 'commit' else 'b' * 40, launcher.parent, EXTERNAL)
                completed = subprocess.run([EXTERNAL, '-I', '-B', '-S', str(directory / 'helper.pyz'), 'recover', str(directory / operation_record())],
                                           env={'HOME': environment['HOME'], 'PATH': os.defpath}, capture_output=True, text=True, timeout=20, check=False)
                assert completed.returncode == 0, completed.stdout + completed.stderr
                assert locks.operation_state(prefix)['phase'] == 'complete'
                normal = subprocess.run([str(launcher), '--version'], env=environment, capture_output=True, text=True, timeout=5, check=False)
                assert normal.returncode == 0
        finally:
            if origin is not None:
                if origin.poll() is None: origin.kill()
                origin.communicate(timeout=5)
            if helper is not None:
                try:
                    if os.waitpid(helper, os.WNOHANG)[0] == 0: os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except ChildProcessError: pass


def operation_record(): return 'operation.json'


def test_whole_update_failed_durable_admission_keeps_pipx_parked_and_independently_recovers_previous(installed, tmp_path):
    configure(installed, 'none')
    origin = helper = None
    with serve(graph(commit='b' * 40)) as (endpoint, _server), subreaper():
        try:
            origin, value, log = start(installed, endpoint, tmp_path, admission_failure=True)
            helper = value['helper']; origin.communicate(timeout=10)
            assert wait_helper(helper, timeout=20) == 2; helper = None
            assert result_at(value['directory'])['outcome'] == 'previous-verified', log.read_text()
            assert not installed[3].exists() and locks.operation_state(installed[0])['phase'] == 'complete'
        finally:
            if origin is not None:
                if origin.poll() is None: origin.kill()
                origin.communicate(timeout=5)
            if helper is not None:
                try:
                    if os.waitpid(helper, os.WNOHANG)[0] == 0: os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except ChildProcessError: pass


@pytest.mark.parametrize('hard', [False, True])
def test_whole_update_interruption_preserves_or_closes_barrier_only_after_independent_quiescence(installed, tmp_path, hard):
    configure(installed, 'pause')
    prefix, launcher, _package, marker, environment, _publish = installed
    origin = helper = child = descendant = None
    assert not manager_installer._children()  # only this test's subsequently created family may be drained
    with serve(graph(commit='b' * 40)) as (endpoint, _server), subreaper():
        try:
            origin, value, _log = start(installed, endpoint, tmp_path)
            helper = value['helper']; directory = Path(value['directory'])
            origin.communicate(timeout=10)
            parked = wait_marker(marker)
            child, descendant = parked['pid'], parked['descendant']
            descriptor = os.pidfd_open(helper)
            try: signal.pidfd_send_signal(descriptor, signal.SIGKILL if hard else signal.SIGTERM)
            finally: os.close(descriptor)
            status = wait_helper(helper, timeout=15); helper = None
            if hard:
                assert status == -signal.SIGKILL and not (directory / 'result.json').exists()
                state = locks.operation_state(prefix)
                assert state['phase'] == 'installing' and state['installer']['pid'] == child
                # Leader stays unreaped until exact owned group cleanup; the escaped child is
                # separately adopted/reserved. No stale/reaped PID is signaled.
                try: os.killpg(child, signal.SIGKILL)
                except ProcessLookupError: pass
                assert wait_helper(child) == -signal.SIGKILL; child = None
                os.kill(descendant, signal.SIGKILL); wait_helper(descendant); descendant = None
                before = json.dumps(locks.operation_state(prefix), sort_keys=True)
                recovered = subprocess.run([EXTERNAL, '-I', '-B', '-S', str(directory / 'helper.pyz'), 'recover', str(directory / 'operation.json')],
                                           env={'HOME': environment['HOME'], 'PATH': os.defpath}, capture_output=True, text=True, timeout=8, check=False)
                assert recovered.returncode == 2 and 'quiescence is unknown' in recovered.stdout
                assert json.dumps(locks.operation_state(prefix), sort_keys=True) == before
                refused = subprocess.run([str(launcher), '--version'], env=environment, capture_output=True, text=True, timeout=5, check=False)
                assert refused.returncode == 2 and 'update incomplete' in refused.stderr
            else:
                assert status == 2 and result_at(directory)['outcome'] == 'previous-verified'
                child = descendant = None  # the product's own subreaper already reaped both
                assert locks.operation_state(prefix)['phase'] == 'complete'
                normal = subprocess.run([str(launcher), '--version'], env=environment, capture_output=True, text=True, timeout=5, check=False)
                assert normal.returncode == 0 and '6.1.0' in normal.stdout
        finally:
            if origin is not None:
                if origin.poll() is None: origin.kill()
                origin.communicate(timeout=5)
            if helper is not None:
                try:
                    if os.waitpid(helper, os.WNOHANG)[0] == 0: os.kill(helper, signal.SIGKILL); os.waitpid(helper, 0)
                except ChildProcessError: pass
            for pid in (child, descendant):
                if pid is not None:
                    try:
                        if os.waitpid(pid, os.WNOHANG)[0] == 0: os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
                    except ChildProcessError: pass
            assert manager_installer.drain()[0], 'Owned interruption-test descendants must be reaped even if an assertion fails'
