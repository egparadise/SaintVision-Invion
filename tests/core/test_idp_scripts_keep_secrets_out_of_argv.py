"""A password passed on a command line is a password anyone on the host can read.

`docker run -e KC_DB_PASSWORD="$SECRET"` leaks twice: into the host process list
while the command runs, and then permanently into `docker inspect`, which anyone who
can reach the daemon can read. `kcadm --password "$SECRET"` and
`kcadm set-password --new-password "$SECRET"` leak into the process list inside the
container. None of that is fixed by tightening file permissions afterwards.

These tests read the shipped scripts and fail if a secret-looking variable reappears
in any of those positions. They are deliberately textual: the leak is a property of
the command line, so the command line is what gets asserted.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "deploy" / "intranet"
SHELL_SCRIPTS = ("idp-up.sh", "idp-realm.sh", "reissue-oidc-trust-bundle.sh")

#: Variables whose value must never reach an argv.
SECRET_VARIABLE = re.compile(
    r"\$\{?(?:[A-Z_]*(?:PASSWORD|SECRET|TOKEN)[A-Z_]*)\}?"
)


def script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def code_lines(name: str) -> list[str]:
    """Executable lines only. These scripts describe the leak in their comments."""
    return [
        line
        for line in script(name).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


@pytest.mark.parametrize("name", SHELL_SCRIPTS)
def test_no_docker_environment_flag_carries_a_secret(name):
    """-e NAME=$SECRET puts the value in host argv and then in Config.Env forever."""
    offenders = [
        line.strip()
        for line in code_lines(name)
        if re.search(r"-e\s+[A-Za-z_][A-Za-z0-9_]*=", line) and SECRET_VARIABLE.search(line)
    ]
    assert offenders == [], offenders


@pytest.mark.parametrize("name", SHELL_SCRIPTS)
def test_no_password_option_is_followed_by_a_secret(name):
    """kcadm's --password / --new-password / --secret take the value in argv."""
    pattern = re.compile(r"--(?:password|new-password|secret|storepass|keypass|trustpass)[= ]\S+")
    offenders = []
    for line in code_lines(name):
        for match in pattern.finditer(line):
            if SECRET_VARIABLE.search(match.group(0)):
                offenders.append(line.strip())
    assert offenders == [], offenders


def test_postgres_takes_its_password_from_a_file():
    text = script("idp-up.sh")
    assert "POSTGRES_PASSWORD_FILE=/run/secrets/db-password" in text
    # The plain form must be gone, not merely accompanied by the file form.
    assert not re.search(r"-e\s+POSTGRES_PASSWORD=", text)


def test_keycloak_receives_its_secrets_through_a_launcher_not_the_environment():
    text = script("idp-up.sh")
    assert "--entrypoint /run/secrets/keycloak-entry.sh" in text
    assert ". /run/secrets/keycloak.env" in text
    for name in ("KC_DB_PASSWORD", "KC_BOOTSTRAP_ADMIN_PASSWORD"):
        assert not re.search(rf"-e\s+{name}=", text), name


def test_the_mounted_secret_files_are_not_group_or_world_readable():
    text = script("idp-up.sh")
    assert 'chmod 700 "$SECRETS"' in text
    assert 'chmod 400 "$SECRETS/db-password" "$SECRETS/keycloak.env"' in text


def test_the_admin_login_reads_the_password_inside_the_container():
    """KC_CLI_PASSWORD is set inside the container from the mounted file.

    kcadm's interactive prompt cannot be used: without a TTY it refuses with
    "Console is not active". KC_CLI_PASSWORD is kcadm's documented alternative and
    keeps the value out of every argv and out of Config.Env.
    """
    code = "\n".join(code_lines("idp-realm.sh"))
    assert "config credentials" in code
    assert re.search(r'KC_CLI_PASSWORD="\$KC_BOOTSTRAP_ADMIN_PASSWORD"', code)
    # Sourced from the mounted file, which defaults to the 0400 mount.
    assert '$SECRETS_IN_CONTAINER' in code
    assert "/run/secrets/keycloak.env" in code
    assert not re.search(r"config credentials[^\n]*--password", code)
    # The value must be exported inside the container, never handed to docker.
    assert not re.search(r"docker exec[^\n]*-e\s+KC_CLI_PASSWORD", code)


def test_user_passwords_are_reset_over_stdin():
    code = "\n".join(code_lines("idp-realm.sh"))
    assert "users/$uid/reset-password" in code
    assert '"value": "$password"' in code
    # kcadm set-password would put the value in the container's process list. The
    # word boundary keeps this from matching "reset-password", which is the fix.
    assert not re.search(r"\bset-password", code)


def test_a_container_owned_by_someone_else_is_not_removed():
    """These nodes run other projects; "docker rm -f" by name alone is not enough."""
    text = script("idp-up.sh")
    assert "remove_if_ours" in text
    assert "refusing to remove" in text
    assert re.search(r'--label "\$OWNER_KEY=\$OWNER"', text)
    # Every forced removal goes through the ownership check.
    direct = [
        line.strip()
        for line in code_lines("idp-up.sh")
        if "docker rm -f" in line and "remove_if_ours" not in line
    ]
    assert len(direct) == 1, direct
    assert 'docker rm -f "$name"' in direct[0]
