"""The read-only collector pin must equal the single Alembic head of this tree.

If a later migration (for example 0068_first_workspace_intent) lands, this fails
until the pin is deliberately retargeted and reviewed; the collector itself refuses
any database whose revision differs from the pin.
"""
import ast
import sys
from pathlib import Path

ROOT=Path(__file__).parents[2]
sys.path.insert(0,str(ROOT/"tools/recovery_preflight"))
import common
import cp


def alembic_heads():
    revisions,parents={},set()
    for path in (ROOT/"migrations/versions").glob("*.py"):
        values={}
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                if node.targets[0].id in ("revision","down_revision"):
                    values[node.targets[0].id]=ast.literal_eval(node.value)
        if "revision" not in values:
            continue
        revisions[values["revision"]]=path.name
        down=values.get("down_revision")
        parents.update(down if isinstance(down,(tuple,list)) else [down] if down else [])
    return sorted(set(revisions)-parents)


def test_collector_pin_is_the_single_unified_head():
    assert alembic_heads()==["0067_audit_reader_revoke"]
    assert common.SCHEMA=="0067_audit_reader_revoke"
    assert cp.SCHEMA is common.SCHEMA


def test_pin_does_not_name_the_absent_0068_revision():
    assert not (ROOT/"migrations/versions/0068_first_workspace_intent.py").exists()
    assert "0068" not in common.SCHEMA
