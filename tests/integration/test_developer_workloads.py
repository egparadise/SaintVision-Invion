"""Actual starter programs through JWT/approval/lease/mTLS/checkpoint.

Identities, DB and PKI are isolated fixtures. This is a kernel integration test,
not an assertion that local Studio already has production identity/admission.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys

import psycopg
import pytest
from inv.dispatch import DeliveryWorker
from inv.node_channels import provision_channel
from inv.output_ingestion import OutputIngestion, output_bytes
from inv.workspace_files import decode_snapshot
from tools.studio_templates import AI, GENERAL
from test_workspace_api import workspace_http, prepare, approve, enqueue
from test_workspace_resume import build_resume
from test_node_delivery import remote, start
from test_node_runtime import node_runtime, active, container
from test_tool_admission import gateway
from test_snapshots import storage
from test_approvals import approval, count

pytestmark = [pytest.mark.postgres,
              pytest.mark.skipif(sys.platform != 'linux', reason='Linux Python Node execution')]
PYTHON = '/usr/local/bin/python3'


def python_workspace(a, kind):
    # Initial fixture's /probe has stopped and all leases are returned. Change
    # the explicit local allowlist while keeping the same owned journal/epoch.
    assert active(a) == 0 and container(a) is None
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    a.args[a.args.index('--executable')+1] = PYTHON
    a.args[a.args.index('--profile')+1] = 'restricted:python-test:1'
    python_image = os.environ['INV_PYTHON_NODE_IMAGE']
    a.args[a.args.index('--image')+1] = python_image
    a.profile = replace(a.profile, version='restricted:python-test:1', images=frozenset({python_image}), executables=frozenset({PYTHON}))
    a.runtime.profile = a.profile
    start(a)
    with psycopg.connect(a.e.owner) as conn:
        provision_channel(conn, a.node, epoch=a.e.epoch, endpoint=a.endpoint,
                          certificate_der=a.server_cert.der, expected_version=1)
    files = dict(AI if kind == 'ai' else GENERAL)
    entry = 'src/train.py' if kind == 'ai' else 'src/app.py'
    root = a.working.root / a.checkout['generation'] / 'files'
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_text(text, encoding='utf-8')
        target.chmod(0o600)
    a.workload.update(command=[PYTHON, '-B', entry], imageDigest=python_image, timeoutSeconds=10)
    return root, entry


def receipt(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute('SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s',
                            (a.enqueued['commandId'],)).fetchone()['envelope']


def dispatch(a):
    prepare(a)
    approve(a)
    response = enqueue(a)
    assert response.status_code == 202, response.text
    a.enqueued = response.json()
    a.command = {'commandId':a.enqueued['commandId']}
    assert active(a) == 2


def record_evidence(a, case, *, snapshot=None):
    folder = os.getenv('INV_TEST_EVIDENCE_DIR')
    if not folder:
        return
    stop = receipt(a)
    run = a.e.runs.get(a.e.tenant,a.run['runId'])
    with a.e.db.transaction(a.e.tenant) as conn:
        completed = conn.execute('SELECT evidence_id FROM inv.result_completions WHERE command_id=%s',
                                 (a.enqueued['commandId'],)).fetchone()
    value = dict(scope='synthetic-starter-kernel-integration',case=case,
                 runId=run['runId'],state=run['state'],attempt=run['attempt'],
                 commandId=a.enqueued['commandId'],receiptId=stop['receiptId'],
                 evidenceId=completed['evidence_id'] if completed else None,
                 nodeId=stop['nodeId'],imageDigest=a.workload['imageDigest'],
                 exitCode=stop['exitCode'],stopped=stop['stopped'],
                 activeLeases=active(a),containerAbsent=container(a) is None,
                 outputSHA256=stop.get('output',{}).get('sha256'))
    if snapshot is not None:
        content = decode_snapshot(snapshot,a.workspace_id)[1]
        value['snapshotSHA256'] = hashlib.sha256(snapshot).hexdigest()
        value['fileSHA256'] = {p:hashlib.sha256(data).hexdigest() for p,data in content.items()}
        if 'outputs/metrics.json' in content:
            value['metrics'] = json.loads(content['outputs/metrics.json'])
            value['model'] = json.loads(content['outputs/model.json'])
    path = Path(folder)/('developer-'+a.enqueued['commandId']+'.json')
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2)


@pytest.mark.parametrize('kind', ['python', 'ai'])
def test_actual_starter_uses_frozen_code_and_publishes_kernel_result(workspace_http, kind):
    a = workspace_http
    root, entry = python_workspace(a, kind)
    dispatch(a)
    # Editing after approval must not replace the immutable execution input.
    (root/entry).write_text('raise RuntimeError("unapproved edit")\n', encoding='utf-8')
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == 'stopped'
    run = a.e.runs.get(a.e.tenant, a.run['runId'])
    assert run['state'] == 'succeeded' and run['attempt'] == 2
    assert active(a) == 0 and container(a) is None
    output = receipt(a)
    raw = output_bytes(output)
    assert hashlib.sha256(raw).hexdigest() == output['output']['sha256']
    artifact = json.loads(raw)
    stdout = json.loads(base64.b64decode(artifact['stdout']))
    snapshot = a.storage.restore(a.e.tenant, a.e.project, run['runId'], 2, 'public-step')
    content = decode_snapshot(snapshot, a.workspace_id)[1]
    assert content[entry] == (AI if kind=='ai' else GENERAL)[entry].encode()
    if kind == 'python':
        assert stdout == {'count':3,'total':54,'average':18.0}
    else:
        metrics = json.loads(content['outputs/metrics.json'])
        model = json.loads(content['outputs/model.json'])
        assert metrics == stdout and metrics['evaluationMSE'] < 1e-8
        assert metrics['trainingRows'] == 51 and metrics['evaluationRows'] == 50
        assert abs(model['weight']-3) < 1e-4 and abs(model['bias']-2) < 1e-4
        assert len(content['outputs/loss.csv'].splitlines()) == 401
    assert count(a,'result_completions') == 1
    assert enqueue(a).json() == a.enqueued
    assert worker.once(a.e.tenant) == 'idle'
    assert count(a,'execution_attempts') == 2
    record_evidence(a,kind,snapshot=snapshot)


def test_training_result_recovers_after_worker_restart_without_retraining(workspace_http):
    a = workspace_http
    python_workspace(a,'ai')
    dispatch(a)
    # A worker without output storage records the physical stop first. A new
    # worker reconciles that durable output; it never issues another execution.
    assert DeliveryWorker(a.e.db,a.delivery).once(a.e.tenant) == 'stopped'
    before = receipt(a)
    assert a.e.runs.get(a.e.tenant,a.run['runId'])['state'] == 'running'
    assert active(a) == 0 and container(a) is None
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: OutputIngestion(a.e.db,a.storage.provider).once(a.e.tenant),range(3)))
    assert a.e.runs.get(a.e.tenant,a.run['runId'])['state'] == 'succeeded'
    assert receipt(a) == before
    assert count(a,'execution_attempts') == 2 and count(a,'result_completions') == 1
    raw = a.storage.restore(a.e.tenant,a.e.project,a.run['runId'],2,'public-step')
    assert json.loads(decode_snapshot(raw,a.workspace_id)[1]['outputs/metrics.json'])['evaluationMSE'] < 1e-8
    record_evidence(a,'ai-output-recovery',snapshot=raw)


def test_python_failure_releases_resources_without_success_evidence(workspace_http):
    a = workspace_http
    root, entry = python_workspace(a,'python')
    (root/entry).write_text('raise SystemExit(7)\n',encoding='utf-8')
    dispatch(a)
    assert DeliveryWorker(a.e.db,a.delivery,output_provider=a.storage.provider).once(a.e.tenant) == 'stopped'
    assert a.e.runs.get(a.e.tenant,a.run['runId'])['state'] == 'failed'
    assert receipt(a)['exitCode'] == 7
    assert active(a) == 0 and container(a) is None and count(a,'result_completions') == 0
    record_evidence(a,'python-failure')
