"""Configuration cannot certify durable WAL transport or operating RPO."""

from pathlib import Path
import importlib.util
import sys
import pytest

SPEC = importlib.util.spec_from_file_location(
    "rpo_core", Path(__file__).resolve().parents[2] / "tools/recovery_drill.py"
)
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)


@pytest.mark.parametrize(
    "command", ["/bin/true", "/bin/false", "wal-push %p", "secret-synthetic-token"]
)
@pytest.mark.parametrize("timeout", ["0", "60", "300"])
def test_configured_archiver_never_establishes_delivery_bound(command, timeout):
    configured, bound, basis = drill.rpo_bound_from(
        dict(archive_mode="on", archive_command=command, archive_timeout=timeout)
    )
    assert configured and bound is None
    assert command not in basis


def test_archive_library_is_observed_without_claiming_recovery():
    configured, bound, _ = drill.rpo_bound_from(
        dict(archive_mode="always", archive_library="library", archive_command="")
    )
    assert configured and bound is None


def test_disabled_archiving_does_not_rule_out_other_recovery_methods():
    configured, bound, basis = drill.rpo_bound_from(dict(archive_mode="off"))
    assert not configured and bound is None
    assert "not verified" in basis


@pytest.mark.parametrize("bound", [None, 300, True, float("nan"), float("inf"), -1])
def test_unverified_numbers_cannot_satisfy_target(bound):
    report = {"recoveryCapability": {"operationalRpoBoundSeconds": bound}}
    assert not drill._meets_operational_rpo(report, 900)


@pytest.mark.parametrize("target", [0, -1, True, "900"])
def test_invalid_target_is_refused(target):
    assert not drill._meets_operational_rpo({}, target)


def test_no_operational_target_preserves_functional_drill():
    assert drill._meets_operational_rpo({}, None)


@pytest.mark.parametrize("value", ["0", "-1", "synthetic-private-value"])
def test_cli_rejects_invalid_target_without_echo(monkeypatch, capsys, value):
    monkeypatch.setattr(sys, "argv", ["recovery", "--require-operational-rpo", value])
    with pytest.raises(SystemExit) as raised:
        drill.main()
    assert raised.value.code == 2
    output = capsys.readouterr()
    assert "synthetic-private-value" not in output.err + output.out
