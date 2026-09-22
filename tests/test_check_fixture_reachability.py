"""Self-test for the report-only fixture reachability proxy."""

import importlib.util
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools" / "check_fixture_reachability.py"
SPEC = importlib.util.spec_from_file_location("check_fixture_reachability", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_classifies_runtime_circular_schema_only_and_unreferenced(tmp_path):
    for name in ("live.json", "circular.json", "shape.json", "orphan.json"):
        write(tmp_path, f"contracts/fixtures/{name}", "{}")
    write(
        tmp_path,
        "tests/test_live.py",
        'FIXTURE = "live.json"\ndef test_live(client):\n    assert client.get("/v1/live").status_code == 200\n',
    )
    write(
        tmp_path,
        "tests/test_circular.py",
        'FIXTURE = "circular.json"\ndef test_circular(client, monkeypatch):\n'
        '    monkeypatch.setattr("service.read", lambda: {})\n'
        '    assert client.get("/v1/circular").status_code == 200\n',
    )
    write(
        tmp_path,
        "tests/test_shape.py",
        'FIXTURE = "shape.json"\ndef test_shape():\n    validate_contract("Shape", {})\n',
    )
    assert {finding.fixture: finding.tier for finding in MODULE.classify(tmp_path)} == {
        "circular.json": "circular-witness",
        "live.json": "runtime-witness",
        "orphan.json": "unreferenced",
        "shape.json": "schema-only",
    }


def test_default_is_report_only_but_strict_exposes_backlog(tmp_path):
    write(tmp_path, "contracts/fixtures/shape.json", "{}")
    write(tmp_path, "tests/test_shape.py", 'FIXTURE = "shape.json"\n')
    assert MODULE.main(["--root", str(tmp_path)]) == 0
    assert MODULE.main(["--root", str(tmp_path), "--strict"]) == 1
