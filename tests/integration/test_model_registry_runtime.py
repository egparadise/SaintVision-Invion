"""PG-backed registry authority at freeze, approval, dispatch and delivery."""
import base64
import hashlib
import json
from uuid import uuid4
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.errors import DomainError
from inv.model_registry_binding import ModelRegistryBindingStore, RegistryBindingPolicy
from inv.model_manifest import canonical
from inv.model_execution_registry import REGISTRY_FILE
from inv.policy import action_digest
from inv.sandbox import SandboxProfile
from inv.tooling import ToolGateway, NodePrincipal
from inv.dispatch import DeliveryQueue
from inv.workspace_files import decode_snapshot
from saintvision.ids import new_id
from test_model_runtime import runtime, locality, model, sample, storage_subject, approval, claim
from test_model_remote_runtime import remote_runtime
from test_approvals import request, approved, dispatch

pytestmark = pytest.mark.postgres


@pytest.fixture(params=['local', 'remote'])
def registered_runtime(request, runtime, remote_runtime):
    a = runtime
    # remote fixture sets the remote store; select the explicit provider.
    from inv.model_runtime import ModelRuntimeStore
    a.runtime_store = ModelRuntimeStore(a.e.db, a.verifier if request.param == 'local' else a.remote_reader)
    a.registry_version = new_id('model_version')
    registry_model = new_id('model')
    with psycopg.connect(a.e.owner) as c:
        c.execute('INSERT INTO public.models(tenant_id,project_id,model_id,name) VALUES(%s,%s,%s,%s)',
                  (a.e.tenant,a.e.project,registry_model,uuid4().hex))
        c.execute("""INSERT INTO public.model_versions(tenant_id,model_id,model_version_id,version,
            stage,content_sha256,byte_size,uri,verified_at,retention_pinned_until)
            VALUES(%s,%s,%s,'registered','released',%s,%s,'inv://synthetic',
            clock_timestamp()-interval '1 second',clock_timestamp()+interval '1 hour')""",
            (a.e.tenant,registry_model,a.registry_version,a.body['contentHash'],a.body['totalBytes']))
    a.policy = RegistryBindingPolicy('execution:1',frozenset({(a.body['licensePolicy'],a.body['classification'])}))
    a.e.db.registry_binding_policy = a.policy
    a.registry_binding = ModelRegistryBindingStore(a.e.db,a.policy).bind(a.principal,a.e.project,
        a.registry_version,a.body['modelId'],a.body['version'],manifest_hash=hashlib.sha256(canonical(a.body)).hexdigest())
    yield a
    a.e.db.registry_binding_policy = None


def freeze(a, **kwargs):
    return a.runtime_store.prepare(a.principal,a.e.project,a.target,a.raw_workload,a.runtime_proofs,
                                   key='registered-freeze',registry_version_id=a.registry_version,**kwargs)


def ready(a):
    g=a.approval
    g.workload=freeze(a)['workload']
    g.run=a.e.runs.get(a.e.tenant,a.target)
    g.policy['actionDigest']=action_digest(g.workload)
    return g


def authorize(a):
    g=ready(a)
    g.command=dispatch(g,approved(g))
    g.profile=SandboxProfile('restricted:test:1',frozenset({g.workload['imageDigest']}),frozenset({g.workload['command'][0]}))
    g.gateway=ToolGateway(a.e.db,g.profile)
    g.node=NodePrincipal(a.e.tenant,a.e.node)
    g.proofs=a.runtime_proofs
    return g


def retire(a):
    with psycopg.connect(a.e.owner) as c:
        c.execute("SET LOCAL lock_timeout='500ms'")
        c.execute("UPDATE public.model_versions SET stage='retired' WHERE model_version_id=%s",(a.registry_version,))


def test_bound_registry_reaches_signed_launch(registered_runtime):
    a=registered_runtime
    g=authorize(a)
    launch=claim(g).launch
    raw=base64.b64decode(launch['workspaceInput']['dataBase64'])
    _,files=decode_snapshot(raw,g.workload['workspaceId'])
    assert json.loads(files[REGISTRY_FILE])==a.registry_binding
    assert hashlib.sha256(raw).hexdigest()==g.workload['modelInput']['inputSha256']


def test_retirement_during_read_prevents_commit(registered_runtime,monkeypatch):
    a=registered_runtime
    provider=a.runtime_store.verifier
    method='read' if provider is a.remote_reader else 'freeze'
    original=getattr(provider,method)
    def read(*args,**kwargs):
        result=original(*args,**kwargs)
        retire(a)
        return result
    monkeypatch.setattr(provider,method,read)
    with pytest.raises(DomainError, match="MODEL-0001"):freeze(a)  # code confirmed vs real PG (ZZPROBE)
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute('SELECT 1 FROM inv.model_runtime_inputs WHERE run_id=%s',(a.target,)).fetchone()


@pytest.mark.parametrize('stage',['replay','approval','dispatch','claim','delivery'])
def test_retired_registry_cannot_cross_execution_gate(registered_runtime,stage):
    a=registered_runtime
    if stage in {'claim','delivery'}:
        g=authorize(a)
        if stage=='delivery':assert not claim(g,queue_signing_key=Ed25519PrivateKey.generate()).may_start
    else:
        g=ready(a)
        if stage=='dispatch':row=approved(g)
    retire(a)
    if stage=='delivery':
        attempt=DeliveryQueue(a.e.db).acquire(a.e.tenant,command_id=g.command['commandId'])
        assert attempt is not None and attempt.operation!='execute'
    else:
        # A retired registry blocks every execution gate via the same code MODEL-0001
        # (manifest/verified bytes unavailable); confirmed against real PostgreSQL for all
        # stages. Pin it so a stage that slipped through with a different DomainError fails.
        with pytest.raises(DomainError, match="MODEL-0001"):
            if stage=='replay':freeze(a)
            elif stage=='approval':request(g)
            elif stage=='dispatch':dispatch(g,row)
            else:claim(g)


@pytest.mark.parametrize('policy',['removed','changed'])
def test_policy_change_after_approval_prevents_claim(registered_runtime,policy):
    a=registered_runtime
    g=authorize(a)
    a.e.db.registry_binding_policy=None if policy=='removed' else RegistryBindingPolicy('execution:2',a.policy.allowed)
    with pytest.raises(DomainError, match="MODEL-0008"):claim(g)  # code confirmed vs real PG (ZZPROBE)


def test_configured_policy_requires_registry_identity(registered_runtime):
    a=registered_runtime
    with pytest.raises(DomainError, match="MODEL-0008"):  # code confirmed vs real PG (ZZPROBE)
        a.runtime_store.prepare(a.principal,a.e.project,a.target,a.raw_workload,a.runtime_proofs,key='missing')


def test_enabling_policy_cannot_replay_legacy_freeze(registered_runtime):
    a=registered_runtime
    a.e.db.registry_binding_policy=None
    a.runtime_store.prepare(a.principal,a.e.project,a.target,a.raw_workload,a.runtime_proofs,key='legacy')
    a.e.db.registry_binding_policy=a.policy
    with pytest.raises(DomainError, match="MODEL-0008"):  # code confirmed vs real PG (ZZPROBE)
        a.runtime_store.prepare(a.principal,a.e.project,a.target,a.raw_workload,a.runtime_proofs,key='legacy')
