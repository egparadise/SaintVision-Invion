"""Self-tests for the non-mutating Tier-A PITR opt-in rehearsal."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pitr_opt_in_dry_run as harness  # noqa: E402


NOW = datetime(2026, 9, 23, 1, 30, tzinfo=timezone.utc)
POSSIBLE = {
    "archive_mode": "on",
    "archive_command": "cp %p /wal_archive/%f",
    "archive_library": "",
    "wal_level": "replica",
}


def _fixture_tree(tmp_path: Path) -> tuple[Path, Path]:
    archive = tmp_path / "archive"
    backups = tmp_path / "backups"
    archive.mkdir()
    backups.mkdir()
    (archive / "000000010000000000000001").write_bytes(b"wal-before")
    (archive / "000000010000000000000002").write_bytes(b"wal-boundary")
    backup = backups / "base-001"
    backup.mkdir()
    (backup / "backup_label").write_text(
        "START WAL LOCATION: 0/2000028 (file 000000010000000000000002)\n"
        "START TIME: 2026-09-22 01:30:00+00\n",
        encoding="utf-8",
    )
    return archive, backups


def test_rehearsal_joins_readiness_and_retention_without_mutating(tmp_path: Path):
    archive, backups = _fixture_tree(tmp_path)
    before = sorted((p.relative_to(tmp_path), p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file())

    report = harness.rehearse(POSSIBLE, archive, backups, now=NOW)

    after = sorted((p.relative_to(tmp_path), p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file())
    assert report["harnessVerdict"] == "observed"
    assert report["readiness"]["verdict"] == "possible"
    assert report["retention"]["deleteArchive"] == ["000000010000000000000001"]
    assert report["mutations"] == {
        "postgresRestarted": False,
        "postgresSettingsChanged": False,
        "composeApplied": False,
        "retentionApplied": False,
    }
    assert report["acceptance"]["pitrVerified"] is False
    assert report["acceptance"]["ac12Satisfied"] is False
    assert before == after


def test_absent_is_an_honest_observation_not_acceptance(tmp_path: Path):
    archive, backups = _fixture_tree(tmp_path)
    settings = {**POSSIBLE, "archive_mode": "off", "archive_command": "(disabled)"}

    report = harness.rehearse(settings, archive, backups, now=NOW)

    assert report["harnessVerdict"] == "observed"
    assert report["readiness"]["verdict"] == "absent"
    assert report["acceptance"]["ac12Satisfied"] is False


def test_missing_directory_or_unread_settings_is_inconclusive(tmp_path: Path):
    archive = tmp_path / "missing-archive"
    backups = tmp_path / "backups"
    backups.mkdir()

    report = harness.rehearse({}, archive, backups, now=NOW)

    assert report["harnessVerdict"] == "inconclusive"
    assert report["inputs"]["archiveDirectoryReadable"] is False
    assert report["readiness"]["verdict"] == "inconclusive"


def test_cli_writes_sanitized_json_and_require_possible_is_only_a_precondition(
    tmp_path: Path, monkeypatch, capsys
):
    archive, backups = _fixture_tree(tmp_path)
    output = tmp_path / "report.json"
    monkeypatch.setenv("TEST_PITR_DSN", "postgresql://secret@example.invalid/db")
    monkeypatch.setattr(harness, "read_settings", lambda _dsn: POSSIBLE)

    rc = harness.main(
        [
            "--dsn-env",
            "TEST_PITR_DSN",
            "--archive",
            str(archive),
            "--backups",
            str(backups),
            "--now",
            NOW.isoformat(),
            "--output",
            str(output),
            "--require-possible",
        ]
    )

    stdout_report = json.loads(capsys.readouterr().out)
    saved_report = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert stdout_report == saved_report
    assert "secret" not in output.read_text(encoding="utf-8")
    assert saved_report["readiness"]["settings"]["archive_command"] == "configured"
    assert saved_report["acceptance"]["pitrVerified"] is False


def test_cli_require_possible_fails_for_deferred_absent_state(tmp_path: Path, monkeypatch, capsys):
    archive, backups = _fixture_tree(tmp_path)
    monkeypatch.setenv("TEST_PITR_DSN", "private")
    monkeypatch.setattr(
        harness,
        "read_settings",
        lambda _dsn: {**POSSIBLE, "archive_mode": "off", "archive_command": ""},
    )

    rc = harness.main(
        [
            "--dsn-env",
            "TEST_PITR_DSN",
            "--archive",
            str(archive),
            "--backups",
            str(backups),
            "--now",
            NOW.isoformat(),
            "--require-possible",
        ]
    )

    assert rc == 3
    assert json.loads(capsys.readouterr().out)["readiness"]["verdict"] == "absent"
