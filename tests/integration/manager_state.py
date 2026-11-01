"""Actual installed startup barrier after an independent frozen writer exits; not updater proof."""
import sys

from opencode_sandbox import manager_handoff


def exercise(camp, ck, prefix, launcher, environment, previous, base):
    archive = base / 'ocs-test-state-helper.pyz'
    archive.write_bytes(manager_handoff._bundle()); archive.chmod(0o600)
    operation = base / 'ocs-test-state-operation'; operation.mkdir(mode=0o700)
    record = operation / 'operation.json'; record.write_text('{"fixture":true}\n'); record.chmod(0o600)
    source = {'version': previous['version'], 'tag': previous['evidence']['tag'],
              'commit': previous['evidence']['commit'], 'source': 'https://github.com/CyberFazaN/opencode-sandbox.git'}
    camp.note(f'owned operation-barrier fixture archive={archive}, record={record}; authoritative private state below '
              f'{prefix.parent.parent}/.opencode-sandbox-updates; no installer, exact schema-1 record retained across test uninstall')
    code = ('import json,sys,time\nfrom pathlib import Path\n'
            'sys.path.insert(0,sys.argv[1])\nimport installation_locks as locks,installation_state as state\n'
            f'prefix={str(prefix)!r}\nsource={source!r}\n'
            'with locks.exclusive(prefix):\n'
            ' if sys.argv[2]=="prepare":\n'
            f'  value={{"format":1,"prefix":prefix,"operation":"f"*64,"phase":"prepared","record":{str(record)!r},'
            '"owner":state.owner(),"installer":None,"previous":source,"target":dict(source,version="6.2.0",tag="v6.2.0",commit="a"*40),"result":None,"at":time.time()}\n'
            '  locks.record_operation(value,prefix)\n'
            ' else:\n'
            '  value=locks.operation_state(prefix)\n'
            '  from manager_verifier import run\n'
            '  observed=run(locks,prefix,deadline=time.monotonic()+8)\n'
            '  assert observed["version"]==source["version"] and observed["prefix"]==prefix\n'
            '  value.update(owner=state.owner(),phase="manual-recovery",result="interrupted",at=time.time())\n'
            '  locks.record_operation(value,prefix)\n'
            '  value.update(phase="verifying",result=None);locks.record_operation(value,prefix)\n'
            '  value.update(phase="complete",result="previous-verified");locks.record_operation(value,prefix)\n'
            'print("owned barrier fixture finished")\n')
    def writer(mode):
        return camp._run([sys.executable, '-I', '-B', '-S', '-c', code, str(archive), mode], env=environment, check=True)
    writer('prepare')
    for arguments in (['--help'], ['--version'], ['manager', 'status']):
        refused = camp._run([str(launcher), *arguments], env=environment, check=False)
        ck(refused.returncode == 2 and 'update incomplete' in refused.stderr,
           'Manager operation state: actual installed startup refuses ' + ' '.join(arguments) + ' after writer exit, not just a live flock')
    alternate = dict(environment, OPENCODE_SANDBOX_HOME=str(base / 'state-other-data'),
                     OPENCODE_SANDBOX_CONFIG=str(base / 'state-other-config'), HOME=str(base / 'state-other-home'))
    refused = camp._run([str(launcher), '--help'], env=alternate, check=False)
    ck(refused.returncode == 2 and 'update incomplete' in refused.stderr,
       'Manager operation state: HOME/data/configuration overrides cannot hide pending installation state')
    ck(not (base / 'state-other-data').exists() and not (base / 'state-other-config').exists(),
       'Manager operation state: blocked bootstrap did not enter application dispatch or create product data')
    writer('complete')
    healthy = camp._run([str(launcher), '--version'], env=environment, check=True)
    ck(healthy.stdout.strip() == 'opencode-sandbox ' + source['version'],
       'Manager operation state: explicit frozen fixture verifies previous runtime and terminal state permits ordinary startup again')
