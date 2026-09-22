"""Self-test for tools/check_anchor_weight.py.

The tool is a static proxy for "does a serving anchor bear rejection weight." A tool that classifies
must itself be shown to discriminate -- so this plants known anchors (one rejection-tested, one
called-only, one untested) and asserts the tiers, then plants a BUG (turns the rejection test into a
recorder) and asserts the tool flips it to called-only. That is the "poison your own tool and check it
catches it" discipline.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "check_anchor_weight.py"
_spec = importlib.util.spec_from_file_location("check_anchor_weight", TOOL)
caw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(caw)


def _tree(root: Path, *, rejection_test_body: str) -> None:
    """Build a minimal repo: 3 serving anchors, named after real SERVING_MODULES so the tool inventories
    them. result_view -> RejType (rejection test), control -> CalledType (recorder test), shards ->
    LonelyType (no test)."""
    inv = root / "services" / "control-plane" / "src" / "inv"
    inv.mkdir(parents=True)
    (inv / "result_view.py").write_text(
        "from .contracts import validate_contract\n"
        "def serve(result):\n    validate_contract(\"RejType\", result)\n    return result\n",
        encoding="utf-8",
    )
    (inv / "control.py").write_text(
        "from .contracts import validate_contract\n"
        "def serve(result):\n    validate_contract(\"CalledType\", result)\n    return result\n",
        encoding="utf-8",
    )
    (inv / "shards.py").write_text(
        "from .contracts import validate_contract\n"
        "def serve(result):\n    validate_contract(\"LonelyType\", result)\n    return result\n",
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    # RejType test: imports result_view, drives serve, asserts it raises -- validator NOT replaced.
    (tests / "test_rej.py").write_text(rejection_test_body, encoding="utf-8")
    # CalledType test: imports control, REPLACES the validator with a recorder, asserts the name only.
    (tests / "test_called.py").write_text(
        "from inv import control\n"
        "def test_called(monkeypatch):\n"
        "    rec = []\n"
        "    monkeypatch.setattr(control, \"validate_contract\", lambda name, value=None: rec.append(name))\n"
        "    control.serve({})\n"
        "    assert \"CalledType\" in rec\n",
        encoding="utf-8",
    )
    # LonelyType: no test at all.


_GOOD_REJECTION = (
    "import pytest\n"
    "from inv.result_view import serve\n"
    "def test_rejects():\n"
    "    # real rejection tests name the contract in the raised message, mirroring match=\"X: invalid contract\"\n"
    "    with pytest.raises(Exception, match=\"RejType\"):\n"
    "        serve({\"bad\": 1})\n"
)
# Planted bug: same file, but now it REPLACES the validator (recorder) instead of letting it reject.
_BUGGED_REJECTION = (
    "from inv import result_view\n"
    "def test_records(monkeypatch):\n"
    "    rec = []\n"
    "    monkeypatch.setattr(result_view, \"validate_contract\", lambda name, value=None: rec.append(name))\n"
    "    result_view.serve({})\n"
    "    assert \"RejType\" in rec\n"
)


def test_tool_discriminates_the_three_tiers(tmp_path):
    _tree(tmp_path, rejection_test_body=_GOOD_REJECTION)
    result = caw.classify(tmp_path)
    assert result["RejType"]["tier"] == "rejection-tested", result["RejType"]
    assert result["CalledType"]["tier"] == "called-only", result["CalledType"]
    assert result["LonelyType"]["tier"] == "no-serving-test", result["LonelyType"]


def test_planted_bug_flips_rejection_to_called_only(tmp_path):
    # Turn the real rejection test into a recorder -- the tool must notice the lost weight.
    _tree(tmp_path, rejection_test_body=_BUGGED_REJECTION)
    result = caw.classify(tmp_path)
    assert result["RejType"]["tier"] == "called-only", (
        "tool failed to catch a rejection test degraded into a recorder: " + repr(result["RejType"])
    )


def test_recorder_helper_does_not_poison_a_sibling_rejection(tmp_path):
    # A file with BOTH a recorder helper and a real rejection function must still read as rejection-tested
    # (function-level, not file-level). This is the false-positive that file-level detection produced.
    mixed = (
        "import pytest\n"
        "from inv import result_view\n"
        "from inv.result_view import serve\n"
        "def _recorder(monkeypatch):\n"
        "    monkeypatch.setattr(result_view, \"validate_contract\", lambda *a, **k: None)\n"
        "def test_rejects():\n"
        "    with pytest.raises(Exception, match=\"RejType\"):\n"
        "        serve({\"bad\": 1})\n"
    )
    _tree(tmp_path, rejection_test_body=mixed)
    result = caw.classify(tmp_path)
    assert result["RejType"]["tier"] == "rejection-tested", result["RejType"]


def test_reports_its_scope_and_out_of_scope_replay(tmp_path):
    # An in-scope module (control.py) with a replay branch -> flagged has_replay_branch.
    # An OUT-of-scope module (containment.py, not in SERVING_MODULES) with a replay branch -> the tool
    # must MEASURE and report it, so the numbers never read broader than what was scanned.
    inv = tmp_path / "services" / "control-plane" / "src" / "inv"
    inv.mkdir(parents=True)
    (inv / "control.py").write_text(
        "from .contracts import validate_contract\n"
        "def serve(prior):\n"
        "    if prior is not None:\n"
        "        validate_contract(\"ReplayType\", prior)\n"
        "        return prior\n",
        encoding="utf-8",
    )
    (inv / "containment.py").write_text(  # NOT in SERVING_MODULES
        "from .contracts import validate_contract\n"
        "def serve(prior):\n"
        "    if prior is not None:\n"
        "        validate_contract(\"OutOfScopeReplay\", prior)\n"
        "        return prior\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    result = caw.classify(tmp_path)
    assert result["ReplayType"]["has_replay_branch"] is True, result["ReplayType"]
    assert "OutOfScopeReplay" not in result, "out-of-scope module must not be inventoried"
    scope = caw.scope_report(inv)
    assert "containment" in scope["out_of_scope_replay"], scope
    assert "OutOfScopeReplay" in scope["out_of_scope_replay"]["containment"], scope
