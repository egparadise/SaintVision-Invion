from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from rehearse_lan_upgrade import assert_preserved, failure_report_path
from rehearse_lan_upgrade import retain_snapshot, read_snapshot
import hashlib
import json
import os


@pytest.mark.parametrize("fault", ["missing", "row-count", "content", "revision-before-upgrade"])
def test_preservation_rejects_loss_or_rewrite(fault):
    before = {"inv.evidence": {"rows": 1, "sha256": "a"}, "public.alembic_version": {"rows": 1, "sha256": "b"}}
    after = {k: dict(v) for k, v in before.items()}
    if fault == "missing":
        del after["inv.evidence"]
    elif fault == "row-count":
        after["inv.evidence"]["rows"] = 0
    elif fault == "content":
        after["inv.evidence"]["sha256"] = "c"
    else:
        after["public.alembic_version"]["sha256"] = "c"
    with pytest.raises(ValueError):
        assert_preserved(before, after)


def test_only_revision_rows_exempted_after_upgrade():
    before = {"inv.evidence": {"rows": 1, "sha256": "a"}, "public.alembic_version": {"rows": 1, "sha256": "b"}}
    after = {**before, "public.alembic_version": {"rows": 1, "sha256": "c"}}
    assert_preserved(before, after, upgraded=True)
    after["inv.evidence"] = {"rows": 1, "sha256": "different"}
    with pytest.raises(ValueError):
        assert_preserved(before, after, upgraded=True)


@pytest.mark.parametrize("fault", ["none", "archive", "manifest", "missing", "hardlink", "existing"])
def test_saved_backup_boundaries(tmp_path, fault):
    directory = tmp_path / "backup"
    raw = b"synthetic postgres archive"
    expected = dict(scope="test", archiveSha256=hashlib.sha256(raw).hexdigest(), archiveBytes=len(raw))
    assert retain_snapshot(directory, raw, {"scope": "test"}) == raw
    if fault == "none":
        assert json.loads((directory / "manifest.json").read_text()) == expected
        return
    if fault == "existing":
        with pytest.raises(FileExistsError):
            retain_snapshot(directory, b"replacement", {})
        assert read_snapshot(directory, expected) == raw
        return
    if fault == "archive":
        (directory / "snapshot.dump").write_bytes(b"different")
    elif fault == "manifest":
        (directory / "manifest.json").write_text('{}')
    elif fault == "missing":
        (directory / "snapshot.dump").unlink()
    elif fault == "hardlink":
        os.link(directory / "snapshot.dump", directory / "alias.dump")
    with pytest.raises((ValueError, FileNotFoundError)):
        read_snapshot(directory, expected)


def test_rehearsal_rejects_existing_success_output(tmp_path, monkeypatch):
    import rehearse_lan_upgrade as subject
    output = tmp_path / "run.json"
    output.write_text("prior-success")
    monkeypatch.setattr(sys, "argv", ["rehearse_lan_upgrade.py", "--state", "state.json", "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        subject.main()
    assert error.value.code == 2
    assert output.read_text() == "prior-success"


def test_failed_rehearsal_writes_separate_failure_receipt(tmp_path, monkeypatch):
    import rehearse_lan_upgrade as subject
    output = tmp_path / "run.json"
    monkeypatch.setattr(subject, "rehearse", lambda *args: (_ for _ in ()).throw(RuntimeError("injected")))
    monkeypatch.setattr(sys, "argv", ["rehearse_lan_upgrade.py", "--state", "state.json", "--output", str(output)])
    assert subject.main() == 2
    assert not output.exists()
    receipt = failure_report_path(output)
    assert receipt.exists()
    data = json.loads(receipt.read_text())
    assert data["status"] == "failed" and data["evidenceStatus"] == "failure-receipt"
