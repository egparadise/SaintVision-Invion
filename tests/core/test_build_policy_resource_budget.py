"""Card 255 activation-budget migration and fail-closed source guards."""

from pathlib import Path

from tools.migration_graph import chain


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0063_build_policy_resource_budgets.py"


def test_0063_is_the_single_head_and_preserves_old_profiles_as_unusable_authority():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0063_build_policy_budgets"' in source
    assert len(chain()[-1].revision) <= 32
    assert 'down_revision = "0062_data_location_project_scope"' in source
    assert chain()[-1].revision == "0063_build_policy_budgets"
    assert "nullable=True" in source
    assert "budget_cpu_millis IS NULL AND budget_memory_bytes IS NULL" in source
    assert "budget_storage_bytes IS NULL" in source
    assert "base_image_digests IS NULL" in source
    assert "cardinality(base_image_digests) BETWEEN 1 AND 64" in source
    assert "BETWEEN 1 AND 9007199254740991" in source
    assert "cannot discard active profile budgets" in source
    assert "SECURITY DEFINER" not in source
    assert "GRANT" not in source


def test_plan_budget_and_base_image_are_not_synthetic_literals_anymore():
    source = (
        ROOT / "services/control-plane/src/inv/build_preparations.py"
    ).read_text(encoding="utf-8")
    assert '"cpuMillis": 1' not in source
    assert '"memoryBytes": 1' not in source
    assert '"storageBytes": 1' not in source
    assert '["sha256:" + digest(request)]' not in source
    assert 'profile["budget_cpu_millis"]' in source
    assert 'profile["budget_memory_bytes"]' in source
    assert 'profile["budget_storage_bytes"]' in source
    assert "_pinned_base_image_digests(" in source
