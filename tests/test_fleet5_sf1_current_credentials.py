"""Owning SF1 rechecks use only temporary signed Python fixtures.

The fixture changes a credential after the real archived-bundle validation.
This isolates the final byte recheck, including CA's otherwise masking earlier
pin check, without replacing validation or weakening any production predicate.
"""

from pathlib import Path

import pytest

from test_lan_leaf_rotation import _plain_unit_transport, _fixture, rotation
from test_fleet5_plain_reentry import finish, snapshot
import worker_plain_rotation as plain


@pytest.mark.parametrize("name", ["node-cert.pem", "ca.pem"])
def test_sf1_owning_verifier_refuses_credential_drift_after_bundle_validation(tmp_path, monkeypatch, name):
    f = _fixture(tmp_path)
    finish(f, tmp_path)
    before = snapshot(f.worker)
    assert plain.verify_settled(f.worker, now=f.now)["verified"] is True
    assert snapshot(f.worker) == before

    credential = f.worker / name
    original = credential.read_bytes()
    # Same PEM certificates and keys; only the byte identity changes.
    changed = original + b"\n"
    assert rotation._certificates(changed) == rotation._certificates(original)
    original_validate = rotation.validate_bundle
    injected = []

    def validate_then_change(*args, **kwargs):
        assert args[0] is None and Path(args[1]).resolve() == f.worker.resolve()
        assert kwargs["installed"] is True and kwargs["finalized"] is True
        assert kwargs["_archived_public_material"] is not None
        validated = original_validate(*args, **kwargs)  # Real signature/CA pin validation.
        assert credential.read_bytes() == original and not injected
        credential.write_bytes(changed)  # Deliberate tmp_path-only race injection.
        injected.append(snapshot(f.worker))
        return validated

    monkeypatch.setattr(rotation, "validate_bundle", validate_then_change)
    with pytest.raises(ValueError, match="SF1 current credentials differ from the settled final bytes"):
        plain.verify_settled(f.worker, now=f.now)
    assert len(injected) == 1
    expected = dict(before)
    expected[name] = changed
    assert injected[0] == expected
    assert snapshot(f.worker) == expected, "Verifier must not mutate the injected fixture state"
