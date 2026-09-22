"""Operator startup policy validation and propagation; no DB or Docker required."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import json
import pytest
from inv.model_registry_config import configured_model_roots, configured_registry_policy
from inv.model_registry_binding import RegistryBindingPolicy

VALID = {"version": "operator:1", "allowed": [{"licensePolicy": "synthetic", "classification": "internal"}]}


def test_policy_matches_trusted_worker_policy_and_is_order_independent():
    value = deepcopy(VALID)
    value["allowed"].append({"licensePolicy": "second", "classification": "public"})
    policy = configured_registry_policy(value)
    value["allowed"].reverse()
    assert policy.digest == configured_registry_policy(value).digest
    assert policy == RegistryBindingPolicy('operator:1',frozenset({('synthetic','internal'),('second','public')}))


# Per-case rejection messages confirmed by running configured_registry_policy against each
# input; pinning them stops a malformed policy being rejected for the wrong reason.
@pytest.mark.parametrize('value,expected', [
    (None, 'Explicit registry policy object required'),
    (False, 'Explicit registry policy object required'),
    ({}, 'Explicit registry policy object required'),
    ({**VALID,'extra':True}, 'Explicit registry policy object required'),
    ({**VALID,'version':True}, 'Explicit bounded registry binding policy required'),
    ({**VALID,'version':''}, 'Explicit bounded registry binding policy required'),
    ({**VALID,'version':'v'*129}, 'Explicit bounded registry binding policy required'),
    ({**VALID,'allowed':[]}, 'Bounded registry policy allowlist required'),
    ({**VALID,'allowed':{}}, 'Bounded registry policy allowlist required'),
    ({**VALID,'allowed':[VALID['allowed'][0]]*65}, 'Bounded registry policy allowlist required'),
    ({**VALID,'allowed':VALID['allowed']*2}, 'Duplicate registry policy pair'),
    ({**VALID,'allowed':[{}]}, 'Exact license/classification pair required'),
    ({**VALID,'allowed':[{'licensePolicy':[], 'classification':'internal'}]}, 'Bounded license/classification strings required'),
    ({**VALID,'allowed':[{'licensePolicy':'synthetic', 'classification':False}]}, 'Bounded license/classification strings required'),
    ({**VALID,'allowed':[{'licensePolicy':'synthetic', 'classification':'x'*257}]}, 'Bounded license/classification strings required'),
    ({**VALID,'allowed':[{'licensePolicy':'synthetic', 'classification':'internal','executionAuthorized':True}]}, 'Exact license/classification pair required')])
def test_invalid_policy_rejected(value, expected):
    with pytest.raises(ValueError, match=expected):configured_registry_policy(value)


@pytest.fixture
def factory(monkeypatch,tmp_path):
    import inv.app as module
    config = tmp_path/'operator.json'
    monkeypatch.setenv('INV_API_CONFIG',str(config))
    monkeypatch.setenv('INV_RUNTIME_DSN','synthetic-not-used')
    monkeypatch.setenv('INV_RECOVERY_EPOCH',str(uuid4()))
    monkeypatch.setattr(module,'AccessTokens',lambda **kw:SimpleNamespace(tenant_id=str(uuid4())))
    seen = {}
    def app(database,identity,**kwargs):
        seen['database']=database
        seen['kwargs']=kwargs
        return database
    monkeypatch.setattr(module,'create_app',app)
    def start(settings):
        config.write_text(json.dumps({'identity':{},**settings}))
        return module.create_configured_app()
    return start,seen


def test_factory_passes_policy_to_shared_database(factory):
    start,seen=factory
    db=start({'modelRegistryPolicy':VALID})
    assert db.registry_binding_policy==configured_registry_policy(VALID)
    assert seen['database'] is db


def test_factory_keeps_unconfigured_legacy_mode_explicit(factory):
    start,_=factory
    assert start({}).registry_binding_policy is None


def test_model_verifier_roots_are_explicit_and_bounded(tmp_path):
    root = tmp_path / "models"
    root.mkdir()
    result = configured_model_roots(
        {
            "roots": [
                {
                    "nodeId": "nod_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                    "contributionId": "stc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                    "contributionVersion": 1,
                    "path": str(root),
                }
            ],
            "maxReadBytes": 4096,
        }
    )
    assert result["max_read_bytes"] == 4096
    assert result["roots"][0].root.path == root.resolve()


def test_factory_wires_model_retry_only_with_explicit_verifier(factory, tmp_path):
    root = tmp_path / "configured-models"
    root.mkdir()
    start, seen = factory
    start(
        {
            "modelVerifier": {
                "roots": [
                    {
                        "nodeId": "nod_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                        "contributionId": "stc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                        "contributionVersion": 1,
                        "path": str(root),
                    }
                ],
                "maxReadBytes": 4096,
            }
        }
    )
    assert type(seen["kwargs"]["model_retry"]).__name__ == "ModelRetryStore"


@pytest.mark.parametrize("value", [None, {}, {"roots": [], "maxReadBytes": 1}])
def test_invalid_model_verifier_configuration_is_rejected(value):
    with pytest.raises(ValueError):
        configured_model_roots(value)


@pytest.mark.parametrize('value',[None,{}, {**VALID,'allowed':[]}, {**VALID,'unexpected':'sensitive-sentinel'}])
def test_invalid_present_policy_never_falls_back_or_starts_service(factory,value):
    start,seen=factory
    with pytest.raises(RuntimeError,match='configuration unavailable') as exc:
        start({'modelRegistryPolicy':value})
    assert 'sensitive-sentinel' not in str(exc.value)
    assert not seen
