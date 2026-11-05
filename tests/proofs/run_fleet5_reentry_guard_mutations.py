"""Run T1/T2 guard mutations in disposable module copies and isolated pytest children."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
LAN=ROOT/'deploy/lan'
TEST='tests/test_fleet5_reentry_guard_negatives.py'
MUTATIONS=[
    ('rs1-no-post-ack-match','worker_plain_rotation.py',
     "        phase.match_floor(actual, manifest, phase_name)\n        if actual['servingExecutableSHA256'] != record['prePeerFloor']['servingExecutableSHA256']:\n            raise ValueError('RS1 serving executable changed')\n",
     "        pass  # disposable missing post-start acknowledgement checks\n",
     'test_rs1_rejects_fresh_correctly_signed_wrong_post_start_ack'),
    ('rs1-skip-stopped-reread','worker_plain_rotation.py',
     "            if transport.stopped_entries(root, expected) != entries or _target(root, record) != expected:\n                raise ValueError('RS1 stopped state changed before start')\n",
     "            pass  # disposable missing stopped pre-start recheck\n",
     'test_rs1_rechecks_stopped_volume_and_context_before_any_start'),
    ('rs1-allow-current-in-final','worker_plain_rotation.py',
     "else ('overlap','final'))", "else ('current','overlap','final'))",
     'test_rs1_finalizing_accepts_only_overlap_or_final_durable_floor'),
    ('guard-no-post-recheck','worker_config.py',
     "        if token is not None and _stable_settled(_settled(root)) != _stable_settled(token):\n            raise ValueError('Same-byte/idempotent action changed settled identity, history or ownership')\n",
     "        pass  # disposable missing post-operation settled recheck\n",
     'test_generic_guard_rechecks_settled_state_after_operation_and_never_restores'),
    ('exec-field-optional','peer_policy_phase.py',
     'for key in ("nonce", "certificateDER_SHA256", "peerPolicySHA256", "floorSHA256", "journalIdentitySHA256", "servingProcessSHA256", "servingExecutableSHA256"):',
     'for key in ("nonce", "certificateDER_SHA256", "peerPolicySHA256", "floorSHA256", "journalIdentitySHA256", "servingProcessSHA256"):',
     'test_signed_malformed_executable_digest_is_rejected_independently'),
]


def digest(raw):return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    originals={name:(LAN/name).read_bytes() for name in {m[1] for m in MUTATIONS}}
    report=dict(schemaVersion='fleet5-t1-t2-guard-mutations:1',fixtureOnly=True,
                productionSourceModified=False,actualGoDockerAcceptanceAssessed=False,
                recordedAtUTC=datetime.now(timezone.utc).isoformat(),
                originalSourceSHA256={name:digest(raw) for name,raw in originals.items()},
                baseline=None,mutants=[],proofValid=False)
    try:
        with tempfile.TemporaryDirectory(prefix='fleet5-t123-mutants-') as temporary:
            temporary=Path(temporary)
            for name,filename,old,new,expected in [('baseline',None,None,None,None),*MUTATIONS]:
                module_dir=temporary/name;module_dir.mkdir()
                if filename:
                    source=originals[filename].decode('utf-8')
                    if source.count(old)!=1:raise ValueError('Mutation anchor is not unique: '+name)
                    mutated=source.replace(old,new)
                    (module_dir/filename).write_bytes(mutated.encode())
                xml=module_dir/'result.xml'
                code=("import sys; from pathlib import Path; "
                      +f"sys.path[:0]={[str(module_dir),str(LAN),str(ROOT/'tools'),str(ROOT/'tests')]!r}; "
                      +"import pytest, worker_config, peer_policy_phase, worker_plain_rotation, worker_leaf_rotation; "
                      +f"raise SystemExit(pytest.main({['-q',TEST,'--tb=short','-p','no:cacheprovider','--junitxml='+str(xml)]!r}))")
                child=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,timeout=120)
                log=args.output/(name+'.log');log.write_bytes(child.stdout+child.stderr)
                document=ET.parse(xml);cases=document.findall('.//testcase')
                failures=[case for case in cases if case.find('failure') is not None]
                errors=document.findall('.//error');skips=document.findall('.//skipped')
                item=dict(name=name,exitCode=child.returncode,total=len(cases),failed=len(failures),errors=len(errors),skipped=len(skips),
                          failingCases=[case.attrib['name'] for case in failures],log=log.name,logSHA256=digest(log.read_bytes()))
                if filename:
                    item.update(source=filename,mutatedSourceSHA256=digest((module_dir/filename).read_bytes()),
                                expectedKilledTest=expected)
                    killed=(child.returncode==1 and bool(failures) and not errors and not skips
                            and all(case.attrib['name'].startswith(expected) and 'DID NOT RAISE' in case.find('failure').text for case in failures))
                    item['killed']=killed;report['mutants'].append(item)
                    if not killed:raise ValueError('Mutant was not killed by its expected missing-guard assertion: '+name)
                else:
                    report['baseline']=item
                    if child.returncode or failures or errors or skips or len(cases)!=13:
                        raise ValueError('Baseline must execute all thirteen T1/T2 cases without skips/errors')
                print(json.dumps(item),flush=True)
        report['proofValid']=True
    finally:
        for name,raw in originals.items():
            if (LAN/name).read_bytes()!=raw:
                report['productionSourceModified']=True
                report['proofValid']=False
        (args.output/'mutation-result.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    if not report['proofValid'] or report['productionSourceModified']:raise ValueError('Mutation proof failed')
    return 0


if __name__=='__main__':raise SystemExit(main())
