"""Registry downgrade and immutable snapshot integrity without a database."""
import base64
import hashlib
from types import SimpleNamespace
from uuid import uuid4
import pytest
from inv.db import Database, BoundDatabase
from inv.errors import DomainError
from inv.ids import new_id

from inv.model_execution_registry import REGISTRY_FILE, current_registry, frozen_registry
from inv.model_manifest import canonical
from inv.model_registry_binding import RegistryBindingPolicy
from inv.workspace_files import FORMAT

WORKSPACE = new_id("wsp")


def snapshot(content):
    return canonical(dict(format=FORMAT,workspaceId=WORKSPACE,directories=['model'],files=[] if content is None else [dict(
        path=REGISTRY_FILE,executable=False,sha256=hashlib.sha256(content).hexdigest(),
        sizeBytes=len(content),dataBase64=base64.b64encode(content).decode())]))


@pytest.mark.parametrize('mode',['missing','changed','partial','malformed','noncanonical'])
def test_frozen_registry_cannot_drop_or_change_binding(monkeypatch,mode):
    saved=dict(registryVersionId='v'*30,manifestHash='a'*64,bindingPolicyHash='b'*64)
    def check(conn,db,principal,binding,registry_id):
        if registry_id is None:raise DomainError('MODEL-0008','Required',403)
        return saved
    monkeypatch.setattr('inv.model_execution_registry.current_registry',check)
    assert frozen_registry(None,None,None,None,snapshot(canonical(saved)),WORKSPACE) == saved
    content=canonical(saved)
    if mode=='missing':content=None
    elif mode=='changed':content=canonical({**saved,'manifestHash':'c'*64})
    elif mode=='partial':content=canonical(dict(registryVersionId='v'*30))
    elif mode=='malformed':content=b'[]'
    else:content=b' '+content
    with pytest.raises(DomainError):frozen_registry(None,None,None,None,snapshot(content),WORKSPACE)


def test_registered_input_does_not_survive_missing_operator_policy():
    with pytest.raises(DomainError):
        current_registry(None,SimpleNamespace(),None,None,'v'*30)


def test_bound_database_preserves_operator_policy():
    policy=RegistryBindingPolicy('operator:1',frozenset({('license','classification')}))
    db=Database('not used',recovery_epoch=str(uuid4()),registry_binding_policy=policy)
    assert BoundDatabase(db,'tenant',object()).registry_binding_policy is policy
    with pytest.raises(ValueError):Database('not used',recovery_epoch=db.recovery_epoch,registry_binding_policy={})
