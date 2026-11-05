"""Fixture-only source proof; no daemon, PKI, or physical-PC operation."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

spec = spec_from_file_location("fleet5_contract_probe", Path(__file__).resolve().parents[1] /
                              "proofs/fleet5_compute_storage_contract_probe.py")
probe = module_from_spec(spec)
spec.loader.exec_module(probe)


def test_current_guard_and_storage_mount_contract_do_not_support_coexistence(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Structural proof must never invoke Docker")
    monkeypatch.setattr(probe.workspace, "docker", forbidden)
    monkeypatch.setattr(probe.storage, "docker", forbidden)
    result = probe.probe(tmp_path)
    assert result["plainStateOnlyAccepted"] and result["plainDefaultSocketAccepted"]
    assert result["storageOnlyAccepted"] and result["policyBytesPreserved"]
    assert result["workspaceStorageRejected"] and result["storageWithWorkspaceSocketRejected"]
    assert result["linuxMountEnforcementAssessed"] is False
