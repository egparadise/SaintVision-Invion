import json
import os
from pathlib import Path

import pytest

import generate_intranet_storage_secrets as subject


def test_creates_two_bound_credentials_without_printing_values(tmp_path, capsys):
    assert subject.main(["--directory", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    env_path = tmp_path / "pitr-service-user.env"
    json_path = tmp_path / "pitr-object-store-credential.json"
    values = dict(
        line.split("=", 1)
        for line in env_path.read_text(encoding="ascii").splitlines()
    )
    credential = json.loads(json_path.read_text(encoding="ascii"))

    assert set(values) == {"PITR_KEY", "PITR_SECRET"}
    assert credential == {
        "accessKeyId": values["PITR_KEY"],
        "secretAccessKey": values["PITR_SECRET"],
    }
    assert values["PITR_KEY"] not in output
    assert values["PITR_SECRET"] not in output
    if os.name != "nt":
        assert env_path.stat().st_mode & 0o077 == 0
        assert json_path.stat().st_mode & 0o077 == 0


def test_existing_secret_file_refuses_without_overwrite(tmp_path, capsys):
    protected = tmp_path / "pitr-service-user.env"
    protected.write_text("sentinel\n", encoding="ascii")

    assert subject.main(["--directory", str(tmp_path)]) == 2
    assert protected.read_text(encoding="ascii") == "sentinel\n"
    assert not (tmp_path / "pitr-object-store-credential.json").exists()
    assert "sentinel" not in capsys.readouterr().out


def test_second_file_failure_removes_new_first_file(tmp_path, monkeypatch):
    real = subject._exclusive_private_file
    calls = 0

    def fail_second(path: Path, body: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        real(path, body)

    monkeypatch.setattr(subject, "_exclusive_private_file", fail_second)
    with pytest.raises(OSError):
        subject.create_pitr_credentials(tmp_path)
    assert not (tmp_path / "pitr-service-user.env").exists()
