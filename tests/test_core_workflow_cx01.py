from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "core.yml"

CORE_EVIDENCE_ARTIFACT = "saintvision-core-evidence"
UPLOAD_ACTION = "actions/upload-artifact@v4"


def _core_steps(text):
    workflow = yaml.safe_load(text)
    jobs = workflow["jobs"]
    return jobs, jobs["core"]["steps"]


def _named_step(steps, name):
    matches = [index for index, step in enumerate(steps) if step.get("name") == name]
    assert len(matches) == 1, f"expected exactly one core step named {name!r}: {matches}"
    return matches[0]


def assert_core_cx01_lifecycle(text):
    """Bind the CX01 lifecycle to the parsed core job, not to raw YAML substrings.

    A substring search accepted a commented-out ``name:`` and a suffixed artifact
    name (PR 412 independent review). Parse ``jobs.core.steps`` instead and require
    exactly one upload step whose ``with.name`` equals the core evidence artifact.
    """
    jobs, steps = _core_steps(text)
    core = jobs["core"]
    assert "services" not in core

    # Across every job, exactly one step publishes the exact core evidence name;
    # earlier opt-in diagnostic uploads and later unrelated uploads cannot satisfy it.
    owners = [
        (job_name, index)
        for job_name, job in jobs.items()
        for index, step in enumerate(job.get("steps") or [])
        if isinstance(step.get("with"), dict)
        and step["with"].get("name") == CORE_EVIDENCE_ARTIFACT
    ]
    assert len(owners) == 1, f"core evidence artifact owners: {owners}"
    owner_job, upload = owners[0]
    assert owner_job == "core"

    upload_step = steps[upload]
    assert upload_step.get("uses") == UPLOAD_ACTION
    assert upload_step.get("if") == "always()"
    assert upload_step["with"].get("path") == "dist/"

    create = _named_step(steps, "Create disposable CX01 PostgreSQL")
    migrations = _named_step(steps, "Upgrade each published migration head")
    cleanup = _named_step(steps, "Cleanup disposable CX01 PostgreSQL")
    assert create < migrations < cleanup < upload

    create_step = steps[create]["run"]
    assert 'cx01_owner="${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"' in create_step
    assert '--label "ai.saintvision.kernel-test=$cx01_owner"' in create_step
    assert '--label "ai.saintvision.cx01=$cx01_owner"' in create_step
    assert "--tmpfs /var/lib/postgresql/data:rw,noexec,nosuid" in create_step
    assert "--memory 512m" not in create_step
    assert "--cidfile .work/cx01-container-id" in create_step
    assert "-p 127.0.0.1:5432:5432" in create_step
    assert 'echo "CX01_CONTAINER=$cx01_id" >> "$GITHUB_ENV"' in create_step
    assert 'echo "INV_TEST_ADMIN_DSN=' in create_step
    assert 'cx01_id="$(cat .work/cx01-container-id)"' in create_step

    assert "bridge_gateway=$(docker network inspect bridge" not in text
    assert "cx01_ip=$(docker inspect --format" in text
    assert '"$CX01_CONTAINER")' in text
    assert 'echo "INV_CONTAINER_TEST_DB_HOST=$cx01_ip" >> "$GITHUB_ENV"' in text

    cleanup_step = steps[cleanup]
    assert cleanup_step.get("if") == "always()"
    cleanup_run = cleanup_step["run"]
    assert 'cx01_id="$(cat .work/cx01-container-id)"' in cleanup_run
    assert 'test "$actual_owner" = "$cx01_owner"' in cleanup_run
    assert 'test "$actual_name" = "$expected_name"' in cleanup_run
    assert 'docker rm -f -v "$cx01_id"' in cleanup_run
    assert "if docker inspect \"$cx01_id\"" in cleanup_run


def test_core_workflow_owns_one_explicit_cx01_container_lifecycle():
    assert_core_cx01_lifecycle(WORKFLOW.read_text(encoding="utf-8"))


_NL = chr(10)
_EVIDENCE_UPLOAD_LINES = (
    "      - uses: actions/upload-artifact@v4",
    "        if: always()",
    "        with:",
    "          name: saintvision-core-evidence",
    "          path: dist/",
)
_EVIDENCE_UPLOAD_BLOCK = _NL.join(_EVIDENCE_UPLOAD_LINES) + _NL


def _upload_block(**replace):
    """The published core evidence upload with selected lines replaced or dropped."""
    lines = []
    for index, line in enumerate(_EVIDENCE_UPLOAD_LINES):
        line = replace.get(f"line{index}", line)
        if line is not None:
            lines.append(line)
    return _NL.join(lines) + _NL


def _mutate(text, old, new):
    assert text.count(old) == 1, f"mutation anchor must be unique: {old!r}"
    return text.replace(old, new)


# Each fixture loses the required core evidence identity. The first two were
# accepted by the earlier raw-substring guard (PR 412 independent review of d35f28f5).
_IDENTITY_MUTATIONS = {
    "commented_out_name": _upload_block(line3="          # name: saintvision-core-evidence"),
    "suffixed_name": _upload_block(line3="          name: saintvision-core-evidence-wrong"),
    "renamed": _upload_block(line3="          name: saintvision-core-results"),
    "duplicated": _EVIDENCE_UPLOAD_BLOCK + _EVIDENCE_UPLOAD_BLOCK,
    "other_action": _upload_block(line0="      - uses: actions/upload-artifact@v3"),
    "conditional_dropped": _upload_block(line1=None),
    "other_path": _upload_block(line4="          path: dist/core/"),
}


def test_core_workflow_mutation_anchor_matches_the_published_upload():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(_EVIDENCE_UPLOAD_BLOCK) == 1


@pytest.mark.parametrize("mutation", sorted(_IDENTITY_MUTATIONS))
def test_cx01_guard_rejects_lost_core_evidence_identity(mutation):
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = _mutate(text, _EVIDENCE_UPLOAD_BLOCK, _IDENTITY_MUTATIONS[mutation])
    yaml.safe_load(mutated)  # every fixture stays valid YAML
    with pytest.raises(AssertionError):
        assert_core_cx01_lifecycle(mutated)


def test_cx01_guard_rejects_upload_moved_before_cleanup():
    text = WORKFLOW.read_text(encoding="utf-8")
    cleanup = text.index("      - name: Cleanup disposable CX01 PostgreSQL" + _NL)
    assert cleanup < text.index(_EVIDENCE_UPLOAD_BLOCK)
    removed = _mutate(text, _EVIDENCE_UPLOAD_BLOCK, "")
    mutated = removed[:cleanup] + _EVIDENCE_UPLOAD_BLOCK + removed[cleanup:]
    yaml.safe_load(mutated)
    with pytest.raises(AssertionError):
        assert_core_cx01_lifecycle(mutated)


def test_core_skip_ratchet_no_longer_accepts_unset_cx01_identity():
    text = WORKFLOW.read_text(encoding="utf-8")
    ratchet = text[
        text.index("name: Require executed evidence and declared platform skips") :
        text.index("name: Cleanup disposable CX01 PostgreSQL")
    ]

    assert (
        "CX01_CONTAINER is unset; container identity/ownership cannot be verified"
        not in ratchet
    )


def test_recovery_drill_runs_in_a_fresh_focused_session_before_the_full_suite():
    text = WORKFLOW.read_text(encoding="utf-8")

    focused = text.index("name: Run owned CX01 recovery drill evidence")
    gate = text.index("name: Require executed CX01 recovery evidence")
    full = text.index("python -m pytest --junitxml=dist/core-tests.xml")
    assert focused < gate < full
    assert "tests/integration/test_recovery_drill.py -q" in text[focused:gate]
    assert "assert len(cases) == 20" in text[gate:full]
    # G-02: every one of the 20 focused cases executes; no internal-network skip remains.
    assert "assert passed == 20" in text[gate:full]
    assert "assert skips == Counter()" in text[gate:full]
    assert "internal_network_reason" not in text[gate:full]
    assert "--ignore=tests/integration/test_recovery_drill.py" in text[full:]


def test_build_admission_real_pg_cases_execute_once_in_a_focused_core_step():
    text = WORKFLOW.read_text(encoding="utf-8")

    focused = text.index("name: Verify build admission queue fairness on PostgreSQL")
    gate = text.index("name: Require executed build admission queue evidence")
    full = text.index("python -m pytest --junitxml=dist/core-tests.xml")
    assert focused < gate < full
    assert "tests/integration/test_build_product_runtime_real_pg.py" in text[focused:gate]
    assert "assert len(cases) == 13" in text[gate:full]
    assert "assert not root.findall('.//skipped')" in text[gate:full]
    assert "--ignore=tests/integration/test_build_product_runtime_real_pg.py" in text[full:]


def test_lan_database_real_pg_case_executes_once_in_a_focused_core_step():
    text = WORKFLOW.read_text(encoding="utf-8")
    backend = (ROOT / ".github" / "workflows" / "backend.yml").read_text(encoding="utf-8")

    focused = text.index("name: Verify LAN pilot database scripts with real PostgreSQL")
    gate = text.index("name: Require executed LAN pilot database evidence")
    full = text.index("python -m pytest --junitxml=dist/core-tests.xml")
    assert focused < gate < full
    assert 'INV_TEST_LAN_DATABASE_IMAGE="$image"' in text[focused:gate]
    assert "tests/integration/test_lan_pilot_database_real_pg.py" in text[focused:gate]
    assert "assert len(cases) == 1" in text[gate:full]
    assert "LAN database real-PG case must execute" in text[gate:full]
    ignore = "--ignore=tests/integration/test_lan_pilot_database_real_pg.py"
    assert ignore in text[full:]
    assert ignore in backend
