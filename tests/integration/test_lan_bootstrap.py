"""Pilot provisioning must retain containment despite DB seed triggers."""
from pathlib import Path
import sys
from uuid import uuid4
import psycopg
import pytest
from inv.ids import new_id
from inv.errors import DomainError
from inv.containment import require_execution

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from lan_pilot import provision_observation_node

pytestmark = pytest.mark.postgres


def test_new_observation_pilot_is_contained_without_changing_other_tenants(env):
    state = dict(tenantId=str(uuid4()),nodeId=new_id('nod'),epoch=env.epoch)
    with psycopg.connect(env.owner) as conn:
        provision_observation_node(conn,state)
        assert conn.execute('SELECT kill_switch FROM inv.tenant_controls WHERE tenant_id=%s',(state['tenantId'],)).fetchone()[0]
        assert not conn.execute('SELECT kill_switch FROM inv.tenant_controls WHERE tenant_id=%s',(env.tenant,)).fetchone()[0]
        assert conn.execute('SELECT status FROM inv.nodes WHERE node_id=%s',(state['nodeId'],)).fetchone()[0] == 'offline'
        assert conn.execute('SELECT count(*) FROM inv.project_grants WHERE tenant_id=%s',(state['tenantId'],)).fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM inv.resources WHERE tenant_id=%s',(state['tenantId'],)).fetchone()[0] == 0
    with env.db.transaction(state['tenantId']) as conn:
        with pytest.raises(DomainError):
            require_execution(conn)
