"""The emitted standalone result is versioned and strictly typed, never native."""
import ast
import copy
import pytest
from check_leaf_rotation_standalone_lifecycle import validate_result, FAKE_DOCKER
import peer_policy_phase as phase


def result():
    return dict(schemaVersion='saintvision-leaf-rotation-standalone-lifecycle:3',fixtureOnly=True,actualGoAcceptanceAssessed=False,
        completedNormalCycles=2,installRestartReceipt=True,finalized=True,finalizedAttestationVerified=True,
        rollbackRejected=True,rolledBack=False,restartCount=4,bytecodeCacheCount=0)


def test_versioned_standalone_result_has_truthful_rollback_negative():
    assert validate_result(result())['rolledBack'] is False
    tree=ast.parse(FAKE_DOCKER)
    assert phase.DOMAIN in [node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,bytes)]


@pytest.mark.parametrize('key',list(result()))
def test_standalone_schema_rejects_missing_or_extra_fields(key):
    value=result();value.pop(key)
    with pytest.raises(ValueError):validate_result(value)
    value=result();value['extra']=True
    with pytest.raises(ValueError):validate_result(value)


@pytest.mark.parametrize('key,value',[('rolledBack',True),('rollbackRejected',1),('finalized',1),('restartCount',True),('bytecodeCacheCount',False),('completedNormalCycles',2.0),('actualGoAcceptanceAssessed',True),('schemaVersion','legacy')])
def test_standalone_result_rejects_bool_int_coercion_or_native_claims(key,value):
    observed=result();observed[key]=value
    with pytest.raises(ValueError):validate_result(observed)
