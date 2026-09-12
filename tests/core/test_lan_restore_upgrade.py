from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from rehearse_lan_upgrade import assert_preserved


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
