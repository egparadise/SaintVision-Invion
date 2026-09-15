from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import lan_execution as acceptance
from inv.ids import new_id
from inv.node_execution import seal_permit
from inv.contracts import validate_contract


@pytest.mark.parametrize('mode',['isolation','output','fail','sleep'])
def test_acceptance_permits_keep_narrow_process_limits(mode):
    state=dict(tenantId=str(uuid4()),nodeId=new_id('nod'),epoch=str(uuid4()))
    result,allocations=acceptance.permit(state,'sha256:'+'a'*64,mode)
    envelope=seal_permit(result,allocations,Ed25519PrivateKey.generate())
    validate_contract('SignedNodePermit',envelope)
    assert result.launch['cpuMillis']==500
    assert result.launch['memoryBytes']==67108864
    assert result.launch['network']=='none' and result.launch['userId']==65532
    assert result.launch['argv'][0]=='/probe'
    assert result.launch['timeoutSeconds']<=10
