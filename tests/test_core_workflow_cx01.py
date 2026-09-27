from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "core.yml"


def test_core_workflow_owns_one_explicit_cx01_container_lifecycle():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "services:\n      postgres:" not in text
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
    assert "--memory 512m" in create_step
    assert "-p 127.0.0.1:5432:5432" in create_step
    assert 'echo "CX01_CONTAINER=$cx01_id" >> "$GITHUB_ENV"' in create_step
    assert 'echo "INV_TEST_ADMIN_DSN=' in create_step
    assert 'printf \'%s\\n\' "$cx01_id" > .work/cx01-container-id' in create_step

    cleanup_step = text[cleanup:upload]
    assert "if: always()" in cleanup_step
    assert 'cx01_id="$(cat .work/cx01-container-id)"' in cleanup_step
    assert 'test "$actual_owner" = "$cx01_owner"' in cleanup_step
    assert 'test "$actual_name" = "$expected_name"' in cleanup_step
    assert 'docker rm -f -v "$cx01_id"' in cleanup_step
    assert "if docker inspect \"$cx01_id\"" in cleanup_step


def test_core_skip_ratchet_no_longer_accepts_unset_cx01_identity():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "CX01_CONTAINER is unset; container identity/ownership cannot be verified"
        not in text
    )
