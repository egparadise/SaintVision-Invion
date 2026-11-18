from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from pathlib import Path
import json
import subprocess
import sys

import pytest


def test_interrupted_a1_fence(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "deploy" / "lan"))
    fence = import_module("a1_writer_fence")
    path = tmp_path / "ledger"
    initial = fence.Writer("plan", "first", 1)
    assert fence.interrupted_a1_hold(path, initial) == "HOLD_WRITER_FENCE"
    assert not path.exists()
    fence.initialize(path)
    assert fence.interrupted_a1_hold(path, initial) == "HOLD_WRITER_FENCE"
    assert fence.transfer(path, None, "plan", "first") == initial
    with pytest.raises(ValueError):
        fence.transfer(path, None, "other", "other")
    for different in [fence.Writer("other", "first", 1), fence.Writer("plan", "other", 1),
                      fence.Writer("plan", "first", 2)]:
        assert fence.interrupted_a1_hold(path, different) == "HOLD_WRITER_FENCE"
    with pytest.raises(FileExistsError):
        fence.initialize(path)
    assert fence.interrupted_a1_hold(path, initial) == "HOLD_CUSTODY_UNRESOLVED"

    def attempt(token):
        try:
            return fence.transfer(path, initial, "plan", token)
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as workers:
        winners = [w for w in workers.map(attempt, ["second", "third"]) if w]
    assert len(winners) == 1
    assert winners[0].generation == 2
    assert fence.interrupted_a1_hold(path, initial) == "HOLD_WRITER_FENCE"
    assert fence.interrupted_a1_hold(path, winners[0]) == "HOLD_CUSTODY_UNRESOLVED"
    path.write_bytes(b"damaged fixture")
    assert fence.interrupted_a1_hold(path, winners[0]) == "HOLD_WRITER_FENCE"


def test_inspection_entry_point_reports_hold(tmp_path, monkeypatch):
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps({"holderPlanDigest": "plan", "token": "first", "generation": 1}))
    state = tmp_path / "absent"
    def inspect():
        return subprocess.run(
            [sys.executable, "deploy/lan/inspect_interrupted_a1.py", "--state", str(state),
             "--expected-writer", str(expected)], capture_output=True, text=True, check=False,
        )

    result = inspect()
    assert result.returncode == 2, result.stderr
    assert result.stdout.strip() == "HOLD_WRITER_FENCE"
    assert not state.exists()

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "deploy" / "lan"))
    fence = import_module("a1_writer_fence")
    state.mkdir()
    ledger = state / "a1-writer.sqlite3"
    fence.initialize(ledger)
    fence.transfer(ledger, None, "plan", "first")
    before = ledger.read_bytes()
    result = inspect()
    assert result.returncode == 2, result.stderr
    assert result.stdout.strip() == "HOLD_CUSTODY_UNRESOLVED"
    assert ledger.read_bytes() == before
    expected.write_text("{}")
    result = inspect()
    assert result.returncode == 2
    assert result.stdout.strip() == "HOLD_WRITER_FENCE"

def test_lost_ack_and_concurrent_retries(tmp_path, monkeypatch):
    from threading import Barrier

    module_dir = Path(__file__).resolve().parents[2] / "deploy" / "lan"
    monkeypatch.syspath_prepend(str(module_dir))
    fence = import_module("a1_writer_fence")
    path = tmp_path / "ledger"
    fence.initialize(path)
    first = fence.transfer(path, None, "p", "a")
    assert fence.transfer(path, None, "p", "a") == first
    child = subprocess.run(
        [sys.executable, "-c",
         "import os, sys; from pathlib import Path; from a1_writer_fence import Writer, transfer; "
         "transfer(Path(sys.argv[1]), Writer('p', 'a', 1), 'q', 'b'); os._exit(43)",
         str(path)], cwd=module_dir, check=False,
    )
    assert child.returncode == 43
    second = fence.Writer("q", "b", 2)
    assert fence.transfer(path, first, "q", "b") == second
    with pytest.raises(ValueError):
        fence.transfer(path, fence.Writer("wrong", "a", 1), "q", "b")
    barrier = Barrier(4)

    def same_request(_):
        barrier.wait(timeout=10)
        return fence.transfer(path, second, "p", "a")

    third = fence.Writer("p", "a", 3)
    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(same_request, range(4))) == [third] * 4
    for predecessor, plan, token in [(None, "p", "a"), (first, "q", "b"), (second, "q", "x")]:
        with pytest.raises(ValueError):
            fence.transfer(path, predecessor, plan, token)
    assert fence.interrupted_a1_hold(path, third) == "HOLD_CUSTODY_UNRESOLVED"
