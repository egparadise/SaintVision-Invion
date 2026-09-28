from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "core.yml"


def test_core_workflow_owns_one_explicit_cx01_container_lifecycle():
    text = WORKFLOW.read_text(encoding="utf-8")
    core_job = text[text.index("  core:") : text.index("  s01-storage-roundtrip:")]

    assert "services:\n      postgres:" not in core_job
    create = text.index("name: Create disposable CX01 PostgreSQL")
    migrations = text.index("name: Upgrade each published migration head")
    cleanup = text.index("name: Cleanup disposable CX01 PostgreSQL")
    upload = text.index("uses: actions/upload-artifact@v4")
    assert create < migrations < cleanup < upload

    create_step = text[create:migrations]
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

    cleanup_step = text[cleanup:upload]
    assert "if: always()" in cleanup_step
    assert 'cx01_id="$(cat .work/cx01-container-id)"' in cleanup_step
    assert 'test "$actual_owner" = "$cx01_owner"' in cleanup_step
    assert 'test "$actual_name" = "$expected_name"' in cleanup_step
    assert 'docker rm -f -v "$cx01_id"' in cleanup_step
    assert "if docker inspect \"$cx01_id\"" in cleanup_step


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
    assert "assert passed == 18" in text[gate:full]
    assert "Counter({internal_network_reason: 2})" in text[gate:full]
    assert "--ignore=tests/integration/test_recovery_drill.py" in text[full:]
