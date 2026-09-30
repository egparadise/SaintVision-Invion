"""A password passed on a command line is a password anyone on the host can read.

`docker run -e NAME=$SECRET` leaks twice: into the host process list while the
command runs, and then permanently into `docker inspect`, which anyone who can reach
the daemon can read. `kcadm --password "$SECRET"` and `kcadm set-password
--new-password "$SECRET"` leak into the process list inside the container. None of
that is fixed by tightening file permissions afterwards.

The first version of these tests matched flag spellings with regexes, and an
independent review showed five ways past them: a quoted `-e "NAME=$X"`, `--env K=V`,
`--env=K=V`, `kcadm -s value="$X"`, and a lowercase `$password`. Two more survived on
top of that -- a later `chmod 444` undoing an earlier `chmod 400`, and a secret
smuggled inside `-s credentials=[...]`. Chasing spellings was the wrong shape.

So the rule here is about *shell expansion*, not spelling:

    On any line that invokes `docker run`, `docker exec` or `kcadm`, a secret
    variable that the HOST shell would expand is a leak.

Single quotes are what make the difference. `docker exec c sh -c '... "$SECRET" ...'`
is safe because the host passes those bytes through literally and the expansion
happens inside the container, reading a file only that container can see. The same
text outside single quotes would put the value in the host's argv. Tracking quote
state is therefore the whole check, and it catches every spelling at once --
including ones nobody has thought of yet.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "deploy" / "intranet"
SHELL_SCRIPTS = ("idp-up.sh", "idp-realm.sh", "reissue-oidc-trust-bundle.sh")

#: Commands whose arguments become a process list entry somewhere.
ARGV_COMMANDS = ("docker run", "docker exec", "kcadm")

#: A shell function definition, so wrappers can be followed. These scripts call
#: kcadm through `kc` and `kc_in`; a check that only knew the literal spellings
#: would pass a secret handed to the wrapper, which is exactly what happened to the
#: first version of this file.
FUNCTION = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{(.*)$")

#: A shell variable reference, of any case. The name decides whether it is a secret.
VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
SECRET_NAME = re.compile(r"(?i)pass(word|wd)?|secret|token|credential")
#: Names that match the nouns above but do not hold a secret value. Enumerated one by
#: one, with the reason, so the exemption stays auditable rather than becoming a
#: pattern anything can slip through.
NOT_SECRET_VALUES = {
    "SECRETS": "a directory path",
    "SECRETS_IN_CONTAINER": "a directory path inside the container",
    "TOKEN_LIFESPAN": "a duration in seconds",
}

#: A heredoc introducer. A heredoc body is stdin, not argv -- sending a secret that
#: way is the fix here, not the leak -- so its body is skipped.
HEREDOC = re.compile(r"<<-?\s*'?([A-Za-z_][A-Za-z0-9_]*)'?")

#: One argument: a quoted run, or a bare run of non-space characters.
TOKEN = re.compile(r"""'[^']*'|"[^"]*"|\S+""")


def script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def is_secret(name: str) -> bool:
    return bool(SECRET_NAME.search(name)) and name not in NOT_SECRET_VALUES


def scan(text: str, inside_single: bool) -> tuple[list[str], bool]:
    """Secret variables the HOST shell expands here, and the quote state afterwards.

    Single-quoted regions pass through literally, so a reference inside one is
    expanded by whatever finally interprets the string -- for us, a shell inside the
    container reading a mounted file. Double quotes do NOT stop expansion.
    """
    found: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == "'":
            inside_single = not inside_single
            index += 1
            continue
        if not inside_single and character == "$":
            match = VARIABLE.match(text, index)
            if match and is_secret(match.group(1)):
                found.append(match.group(0))
                index = match.end()
                continue
        index += 1
    return found, inside_single


def host_expanded_secrets(text: str) -> list[str]:
    return scan(text, False)[0]


def commands(name: str) -> list[tuple[str, list[str]]]:
    """Every logical command, with the secrets the host would expand into its argv.

    Continuations are joined, comments dropped, quote state carried ACROSS lines --
    the admin login's `sh -c '...'` body spans several lines, and judging each line
    on its own would read that body as unquoted and call it a leak. Heredoc bodies
    are skipped because they are stdin.
    """
    lines = script(name).splitlines()
    result: list[tuple[str, list[str]]] = []
    inside_single = False
    buffer, buffer_secrets = "", []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not inside_single and not buffer and (not line.strip() or line.lstrip().startswith("#")):
            continue
        found, inside_single = scan(line, inside_single)
        buffer_secrets += found
        piece = line.strip()
        continues = piece.endswith("\\")
        if continues:
            piece = piece[:-1].rstrip()
        buffer = f"{buffer} {piece}".strip() if buffer else piece
        heredoc = HEREDOC.search(line)
        if heredoc and not inside_single:
            delimiter = heredoc.group(1)
            while index < len(lines) and lines[index].strip() != delimiter:
                index += 1
            index += 1
        if continues or inside_single:
            continue
        result.append((buffer, buffer_secrets))
        buffer, buffer_secrets = "", []
    if buffer:
        result.append((buffer, buffer_secrets))
    return result


def logical_lines(name: str) -> list[str]:
    return [text for text, _ in commands(name)]


def argv_invokers(name: str) -> list[str]:
    """The literal commands, plus every wrapper function that reaches one."""
    invokers = list(ARGV_COMMANDS)
    for line in script(name).splitlines():
        match = FUNCTION.match(line)
        if match and any(command in match.group(2) for command in ARGV_COMMANDS):
            invokers.append(match.group(1))
    return invokers


def invokes_argv_command(text: str, invokers: list[str]) -> bool:
    return any(re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text)
               for name in invokers)


def argv_leaks(name: str) -> list[tuple[str, list[str]]]:
    invokers = argv_invokers(name)
    return [
        (text, secrets)
        for text, secrets in commands(name)
        if secrets and invokes_argv_command(text, invokers)
    ]


def tokens(line: str) -> list[str]:
    out = []
    for match in TOKEN.finditer(line):
        token = match.group(0)
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            token = token[1:-1]
        out.append(token)
    return out


@pytest.mark.parametrize("name", SHELL_SCRIPTS)
def test_no_container_or_admin_command_expands_a_secret_on_the_host(name):
    leaks = argv_leaks(name)
    assert leaks == [], leaks


# --- the five variants the regex version let through ------------------------------
#
# Each is injected into a real line of a real script, and the check must catch it.
# These are pinned because they are the mutations that actually got past the first
# implementation, not hypotheticals.

MUTATIONS = {
    "quoted -e form": 'docker run -d --name "$CONTAINER" -e "KC_DB_PASSWORD=$SV_IDP_DB_PASSWORD" image',
    "--env with a space": 'docker run -d --name "$CONTAINER" --env KC_DB_PASSWORD=$SV_IDP_DB_PASSWORD image',
    "--env= form": 'docker run -d --name "$CONTAINER" --env=KC_DB_PASSWORD="$SV_IDP_DB_PASSWORD" image',
    "kcadm -s value=": 'docker exec c /opt/keycloak/bin/kcadm.sh update users/x -s value="$SV_USER1_PASSWORD"',
    "lowercase variable": 'docker exec c /opt/keycloak/bin/kcadm.sh update users/x -s "value=$password"',
    "credentials array": (
        'docker exec c /opt/keycloak/bin/kcadm.sh create users '
        '-s credentials=[{"type":"password","value":"$password"}]'
    ),
    "backslash continuation": 'docker run -d \\\n  -e KC_BOOTSTRAP_ADMIN_PASSWORD="$SV_IDP_ADMIN_PASSWORD" \\\n  image',
    "brace expansion": 'docker run -d -e "KC_DB_PASSWORD=${SV_IDP_DB_PASSWORD}" image',
}


@pytest.mark.parametrize(("label", "line"), sorted(MUTATIONS.items()))
def test_each_known_bypass_is_caught(label, line):
    flattened = re.sub(r"\\\n\s*", " ", line)
    assert host_expanded_secrets(flattened), f"{label} slipped through"


def test_the_safe_in_container_form_is_not_flagged():
    """The real login line: expansion happens inside the container, not on the host.

    This is the test that keeps the check honest. If it started failing, the rule
    would be rejecting the correct construction and would get relaxed.
    """
    line = (
        "docker exec \"$CONTAINER\" sh -c '\n"
        "  . /run/secrets/keycloak.env\n"
        '  KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" kcadm.sh config credentials\n'
        "'"
    )
    assert host_expanded_secrets(line) == []


def test_writing_a_secret_to_a_file_is_not_an_argv_leak():
    """`printf ... > file` is how the secret gets into the mount in the first place."""
    line = 'printf \'%s\' "$SV_IDP_DB_PASSWORD" > "$SECRETS/db-password"'
    assert host_expanded_secrets(line) == ["$SV_IDP_DB_PASSWORD"]
    assert not any(command in line for command in ARGV_COMMANDS)


# --- file modes: the last chmod is the one that counts ----------------------------


SECRET_FILES = ("db-password", "keycloak.env")


def chmod_modes(name: str) -> list[tuple[str, str]]:
    """Every (mode, target) a chmod in this script applies, in order."""
    applied = []
    for line in logical_lines(name):
        for command in re.finditer(r"\bchmod\s+(\S+)((?:\s+(?:'[^']*'|\"[^\"]*\"|[^\s;&|]+))+)", line):
            mode = command.group(1)
            for target in tokens(command.group(2)):
                applied.append((mode, target))
    return applied


def test_no_later_chmod_loosens_a_secret_file():
    """A `chmod 400` followed by `chmod 444` leaves the file world-readable.

    Only the final mode matters, so the test looks at every chmod that touches a
    secret file rather than at the presence of a strict one.
    """
    final: dict[str, str] = {}
    for mode, target in chmod_modes("idp-up.sh"):
        for secret in SECRET_FILES:
            if secret in target or target in {'"$SECRETS"/*', "$SECRETS/*"}:
                final[secret if secret in target else target] = mode
    assert final, "no chmod touches the secret files at all"
    for target, mode in final.items():
        if mode.startswith("u+") or mode.startswith("u-"):
            continue  # a symbolic change to the owner's bits only
        assert re.fullmatch(r"[0-7]{3,4}", mode), (target, mode)
        group_other = int(mode[-2:], 8)
        assert group_other & 0o44 == 0, f"{target} ends up group/other readable: {mode}"


def test_the_secrets_directory_is_owner_only():
    assert ("700", "$SECRETS") in chmod_modes("idp-up.sh")


@pytest.mark.parametrize("name", sorted(NOT_SECRET_VALUES))
def test_an_exempt_name_is_not_treated_as_a_secret(name):
    """$SECRETS is a path and $TOKEN_LIFESPAN is a number; neither is a value to hide.

    The exemptions are pinned here so adding one is a visible change rather than a
    quiet widening of the rule.
    """
    assert not is_secret(name), NOT_SECRET_VALUES[name]


@pytest.mark.parametrize(
    "name",
    ["SV_IDP_DB_PASSWORD", "SV_IDP_ADMIN_PASSWORD", "KC_CLI_PASSWORD",
     "SV_USER1_PASSWORD", "password", "CLIENT_SECRET", "access_token", "MY_CREDENTIAL"],
)
def test_a_secret_name_is_recognised_in_any_case(name):
    assert is_secret(name)


# --- the structural choices those modes depend on ---------------------------------


def test_postgres_takes_its_password_from_a_file():
    text = script("idp-up.sh")
    assert "POSTGRES_PASSWORD_FILE=/run/secrets/db-password" in text
    assert not re.search(r"-e\s+\"?POSTGRES_PASSWORD=", text)


def test_keycloak_receives_its_secrets_through_a_launcher_not_the_environment():
    text = script("idp-up.sh")
    assert "--entrypoint /run/secrets/keycloak-entry.sh" in text
    assert ". /run/secrets/keycloak.env" in text
    for name in ("KC_DB_PASSWORD", "KC_BOOTSTRAP_ADMIN_PASSWORD"):
        assert not re.search(rf"(?:-e|--env)[= ]\"?{name}=", text), name


def test_the_admin_login_reads_the_password_inside_the_container():
    """KC_CLI_PASSWORD is set inside the container from the mounted file.

    kcadm's interactive prompt cannot be used: without a TTY it refuses with
    "Console is not active". KC_CLI_PASSWORD is kcadm's documented alternative and
    keeps the value out of every argv and out of Config.Env.
    """
    code = "\n".join(logical_lines("idp-realm.sh"))
    assert "config credentials" in code
    assert re.search(r'KC_CLI_PASSWORD="\$KC_BOOTSTRAP_ADMIN_PASSWORD"', code)
    assert "$SECRETS_IN_CONTAINER" in code
    assert "/run/secrets/keycloak.env" in code
    assert not re.search(r"config credentials[^\n]*--password", code)
    assert not re.search(r"docker exec[^\n]*(?:-e|--env)[= ]\"?KC_CLI_PASSWORD", code)


def test_user_passwords_are_reset_over_stdin():
    code = "\n".join(logical_lines("idp-realm.sh"))
    assert "users/$uid/reset-password" in code
    # The value lives in a heredoc body, which logical_lines drops on purpose --
    # that body is stdin. Assert against the raw script for it.
    assert '"value": "$password"' in script("idp-realm.sh")
    # kcadm set-password would put the value in the container's process list. The
    # word boundary keeps this from matching "reset-password", which is the fix.
    assert not re.search(r"\bset-password", code)


def test_a_container_owned_by_someone_else_is_not_removed():
    """These nodes run other projects; "docker rm -f" by name alone is not enough."""
    text = script("idp-up.sh")
    assert "remove_if_ours" in text
    assert "refusing to remove" in text
    assert re.search(r'--label "\$OWNER_KEY=\$OWNER"', text)
    direct = [
        line
        for line in logical_lines("idp-up.sh")
        if "docker rm -f" in line and "remove_if_ours" not in line
    ]
    assert len(direct) == 1, direct
    assert 'docker rm -f "$name"' in direct[0]


# --- each container gets only the files it needs ---------------------------------
#
# Mounting the whole secrets directory into both containers hands the database the
# Keycloak bootstrap admin password. The database has no use for it, and a
# credential reachable from a container that does not need it is a credential with
# a larger blast radius than anyone intended.


def docker_run_command(name: str, container_variable: str) -> str:
    for line in logical_lines(name):
        if "docker run -d --name" in line and container_variable in line:
            return line
    raise AssertionError(f"no docker run command for {container_variable}")


def mounts(command: str) -> list[str]:
    argv = tokens(command)
    return [argv[index + 1] for index, token in enumerate(argv[:-1]) if token in {"-v", "--volume"}]


def test_the_database_container_mounts_one_password_file_and_no_directory():
    command = docker_run_command("idp-up.sh", '"$DB_CONTAINER"')
    assert mounts(command) == [
        "$SECRETS/db-password:/run/secrets/db-password:ro",
        "$VOLUME:/var/lib/postgresql/data",
    ], mounts(command)
    # POSTGRES_DB=keycloak is expected. A Keycloak *secret* reaching this container
    # is the thing that must not happen.
    assert not any(
        "keycloak.env" in entry or "keycloak-entry" in entry for entry in mounts(command)
    )


def test_the_keycloak_container_mounts_its_own_files_not_the_directory():
    command = docker_run_command("idp-up.sh", '"$CONTAINER"')
    mounted = mounts(command)
    assert "$SECRETS/keycloak.env:/run/secrets/keycloak.env:ro" in mounted
    assert "$SECRETS/keycloak-entry.sh:/run/secrets/keycloak-entry.sh:ro" in mounted
    assert not any(entry.startswith("$SECRETS:") for entry in mounted), mounted
    # The database's password reaches Keycloak through keycloak.env, not a raw mount.
    assert not any("db-password" in entry for entry in mounted), mounted


def test_no_container_mounts_the_secrets_directory_wholesale():
    for line in logical_lines("idp-up.sh"):
        assert '"$SECRETS:/run/secrets' not in line, line
