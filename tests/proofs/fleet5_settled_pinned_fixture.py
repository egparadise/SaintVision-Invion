"""CI-only default SF1 dispatch through the real installed pinned crypto runtime.

The Node/Docker observation remains an explicitly synthetic CLI fixture. No
production callback, launcher, crypto import, hash or signature check is bypassed.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'deploy/lan'
FILES=('worker_config.py','worker_leaf_rotation.py','peer_policy_phase.py','worker_peer_floor.py',
       'worker_plain_rotation.py','leaf_rotation_standalone_runtime.py','leaf-rotation-runtime-lock.json')
PROBE=r'''
import json,subprocess,sys
from pathlib import Path
assert Path.home().resolve().is_relative_to(Path(sys.argv[3]).resolve())
sys.path.insert(0,sys.argv[1])
import worker_config
assert worker_config._settled_verifier is None
try:
    with worker_config.rotation_mutation_guard(Path(sys.argv[2]),action='idempotent') as token:
        assert token['verified'] is True
except subprocess.CalledProcessError as error:
    sys.stderr.buffer.write(error.stderr)
    raise
print(json.dumps({'verified':True,'defaultSubprocessVerifier':True},sort_keys=True))
'''


def _snapshot(root):
    return {str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}


def prove_default_settled(temporary,runtime,worker,daemon,environment,output):
    if sys.platform!='linux' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('Actual pinned-runtime fixture is restricted to isolated Linux CI')
    temporary=Path(temporary).resolve();worker=Path(worker).resolve();daemon=Path(daemon).resolve()
    if not worker.is_relative_to(temporary) or not daemon.is_relative_to(temporary):
        raise ValueError('Only this disposable fixture may be observed')
    source_bytes={name:(SOURCE/name).read_bytes() for name in FILES}
    installer=temporary/'default-installer';installer.mkdir(mode=0o700)
    for name,raw in source_bytes.items():(installer/name).write_bytes(raw)
    home=temporary/'owned-home';target=home/'.local/share/saintvision/leaf-rotation-runtime'
    target.parent.mkdir(parents=True,mode=0o700)
    shutil.copytree(Path(runtime),target)
    environment={**environment,'HOME':str(home)}  # isolate OS home; pinning remains mandatory
    initial_worker=_snapshot(worker);initial_daemon=_snapshot(daemon)
    report=dict(schemaVersion='saintvision-settled-pinned-launcher-fixture:1',fixtureOnly=True,
                actualGoAcceptanceAssessed=False,defaultVerifierCallbackBypassed=False,
                actualPinnedRuntimeCryptoAssessed=False,privateFixtureKeysUploaded=False,
                recordedAtUTC=datetime.now(timezone.utc).isoformat(),
                installerSourceSHA256={name:hashlib.sha256(raw).hexdigest() for name,raw in source_bytes.items()},
                cases=[],sourceUnchanged=False,fixtureStateUnchanged=False,proofValid=False)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    reasons={'missing-launcher':'reviewed pinned five-module verifier is required',
             'missing-entry':'reviewed pinned five-module verifier is required',
             # The real launcher deliberately reports only the error class.
             'entry-hash':'Standalone leaf-rotation runtime rejected (ValueError)',
             'missing-runtime':'Standalone leaf-rotation runtime rejected (FileNotFoundError)',
             'runtime-module-hash':'Standalone leaf-rotation runtime rejected (ValueError)',
             'crypto-package-hash':'Standalone leaf-rotation runtime rejected (ValueError)',
             'node-signature':'Node leaf rotation rejected (InvalidSignature)',
             'runtime-receipt':'Standalone leaf-rotation runtime rejected (ValueError)'}
    def save():output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    try:
        for fault in ('valid','missing-launcher','missing-entry','entry-hash','missing-runtime','runtime-module-hash',
                      'crypto-package-hash','node-signature','runtime-receipt','valid-after-negatives'):
            restore=[];env=dict(environment)
            try:
                if fault in ('missing-launcher','missing-entry'):
                    name='leaf_rotation_standalone_runtime.py' if fault=='missing-launcher' else 'worker_leaf_rotation.py'
                    path=installer/name;restore.append((path,path.read_bytes()));path.unlink()
                elif fault in ('entry-hash','runtime-module-hash','crypto-package-hash','runtime-receipt'):
                    path={'entry-hash':installer/'worker_leaf_rotation.py',
                          'runtime-module-hash':target/'worker/worker_plain_rotation.py',
                          'crypto-package-hash':target/'cryptography/__init__.py',
                          'runtime-receipt':target/'.saintvision-runtime.json'}[fault]
                    raw=path.read_bytes();restore.append((path,raw))
                    path.write_bytes(b'{}' if fault=='runtime-receipt' else raw+b'\n# owned fixture tamper\n')
                elif fault=='missing-runtime':
                    empty_home=temporary/'missing-runtime-home';empty_home.mkdir(mode=0o700)
                    env['HOME']=str(empty_home)
                elif fault=='node-signature':
                    path=daemon/'meta.json';raw=path.read_bytes();restore.append((path,raw))
                    meta=json.loads(raw);meta['invalidFixtureSignature']=True
                    path.write_bytes(json.dumps(meta,sort_keys=True,separators=(',',':')).encode())
                before_worker=_snapshot(worker);before_daemon=_snapshot(daemon)
                result=subprocess.run([sys.executable,'-I','-B','-c',PROBE,str(installer),str(worker),str(temporary)],
                                      cwd=ROOT,env=env,capture_output=True,timeout=90)
                unchanged=before_worker==_snapshot(worker) and before_daemon==_snapshot(daemon)
                rejected=fault not in ('valid','valid-after-negatives')
                reason_matches=not rejected or reasons[fault] in result.stderr.decode(errors='replace')
                item=dict(name=fault,expectedRejected=rejected,exitCode=result.returncode,stateUnchanged=unchanged,
                          expectedFailureReason=reasons.get(fault),failureReasonMatched=reason_matches,
                          stdoutSHA256=hashlib.sha256(result.stdout).hexdigest(),stderrSHA256=hashlib.sha256(result.stderr).hexdigest())
                report['cases'].append(item);save()
                if not unchanged or not reason_matches or (result.returncode!=0)!=rejected:
                    raise ValueError('Default pinned-path fixture result differs: '+fault+' '+result.stderr[-1200:].decode(errors='replace'))
                if not rejected and json.loads(result.stdout)!=dict(verified=True,defaultSubprocessVerifier=True):
                    raise ValueError('Default pinned verifier did not return its exact success proof')
            finally:
                # Restore only our deliberately damaged disposable fixture inputs.
                for path,raw in restore:path.write_bytes(raw)
        report['sourceUnchanged']=all((SOURCE/name).read_bytes()==raw for name,raw in source_bytes.items())
        report['fixtureStateUnchanged']=initial_worker==_snapshot(worker) and initial_daemon==_snapshot(daemon)
        report['proofValid']=report['sourceUnchanged'] and report['fixtureStateUnchanged'] and len(report['cases'])==10
        report['actualPinnedRuntimeCryptoAssessed']=report['proofValid']
        if not report['proofValid']:raise ValueError('Pinned-path fixture changed protected inputs')
    finally:save()
    return report
