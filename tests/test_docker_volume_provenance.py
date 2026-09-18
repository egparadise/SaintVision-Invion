from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_postgres_pitr_launcher_uses_ephemeral_data_storage():
    source = (ROOT / "tools" / "pitr_rehearsal.sh").read_text(encoding="utf-8")
    assert "--tmpfs /var/lib/postgresql/data:rw,size=536870912" in source

    reverted = source.replace("--tmpfs /var/lib/postgresql/data:rw,size=536870912 ", "", 1)
    assert "--tmpfs /var/lib/postgresql/data:rw,size=536870912" not in reverted


def test_postgres_workspace_and_pilot_launchers_use_named_data_volumes():
    remote = (ROOT / "tools" / "check_remote_workspace.py").read_text(encoding="utf-8")
    pilot = (ROOT / "tools" / "lan_pilot.py").read_text(encoding="utf-8")
    mount = "/var/lib/postgresql/data"
    assert "source='+name+'-db-data,target=" + mount in remote
    assert "source={state[\"container\"]}-data,target=" + mount in pilot
