"""Real local Python subprocesses; no provider credentials or model calls."""

import sys
import tracemalloc

from saintvision.adapters.cli import CliAdapter, CliTool, _run_quietly


def adapter(script, monkeypatch):
    instance = CliAdapter(
        CliTool(name="bounded-test", executable=sys.executable, prompt_args=("-c", script))
    )
    monkeypatch.setattr(instance, "resolve", lambda: sys.executable)
    return instance


def test_large_stdout_and_stderr_are_drained_before_collection_with_bounded_memory(monkeypatch):
    import saintvision.adapters.cli as cli

    monkeypatch.setattr(cli, "MAX_OUTPUT_BYTES", 1024)
    instance = adapter(
        "import os\nfor i in range(256):\n os.write(1,b'x'*65536)\n os.write(2,b'y'*65536)",
        monkeypatch,
    )
    tracemalloc.start()
    try:
        handle = instance.run({"input": ""})
        # Both pipes exceed OS capacity; the child must finish without collect().
        instance._runs[handle.handle_id]["process"].wait(timeout=10)
        result = instance.collect(handle)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert result.completed and len(result.content) == 1024
    assert len(instance._runs[handle.handle_id]["stderr"]) == 1024
    assert peak < 4 * 1024 * 1024
    assert instance.attest(handle).provider_claims["truncatedOutput"]
    assert instance.collect(handle) == result


def test_timeout_is_distinct_from_process_exit(monkeypatch):
    import saintvision.adapters.cli as cli

    monkeypatch.setattr(cli, "PROBE_TIMEOUT_SECONDS", 0.025)
    monkeypatch.setattr(cli, "TERMINATE_GRACE_SECONDS", 0.2)
    instance = adapter("import time; time.sleep(10)", monkeypatch)
    result = instance.collect(instance.run({"input": ""}))
    assert not result.completed
    assert result.error_code == "RUN-TIMEOUT" and result.stop_reason == "timeout"


def test_descendant_holding_pipe_cannot_hold_collection_forever(monkeypatch):
    import saintvision.adapters.cli as cli

    monkeypatch.setattr(cli, "TERMINATE_GRACE_SECONDS", 0.1)
    instance = adapter(
        "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time;time.sleep(1)'])",
        monkeypatch,
    )
    handle = instance.run({"input": ""})
    result = instance.collect(handle)
    assert not result.completed and result.error_code == "RUN-OUTPUT-INCOMPLETE"
    capture = instance._runs[handle.handle_id]["capture"]
    assert not capture.stdout.thread.is_alive() and not capture.stderr.thread.is_alive()
    # The fixture descendant exits itself. No process-tree stop is claimed.


def test_stderr_alone_marks_truncation(monkeypatch):
    import saintvision.adapters.cli as cli

    monkeypatch.setattr(cli, "MAX_OUTPUT_BYTES", 32)
    instance = adapter("import os;os.write(2,b'x'*1000)", monkeypatch)
    handle = instance.run({"input": ""})
    assert instance.collect(handle).completed
    assert instance.attest(handle).provider_claims["truncatedOutput"]


def test_oversize_probe_cannot_claim_success_from_retained_prefix(monkeypatch):
    import saintvision.adapters.cli as cli

    monkeypatch.setattr(cli, "MAX_OUTPUT_BYTES", 32)
    assert _run_quietly([sys.executable, "-c", "print('logged in'+'x'*1000)"]) == (None, "")


def test_invalid_output_encoding_does_not_crash_collection(monkeypatch):
    instance = adapter("import os;os.write(1,b'good\\xffbytes')", monkeypatch)
    result = instance.collect(instance.run({"input": ""}))
    assert result.completed and result.content == "good\ufffdbytes"
