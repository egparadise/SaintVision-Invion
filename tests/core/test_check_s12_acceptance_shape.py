"""The gate must refuse each way a bundle can be wrong, and accept a FAIL verdict.

A gate that only ran on a good bundle would be removed the first time the real verdict was
FAIL -- which it is, and honestly so, until the external waits clear. So the first test here
is that a FAIL bundle is *accepted*: the checker judges shape, not the answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_s12_acceptance_shape import (  # noqa: E402
    CI_DERIVED_CLAIM,
    EXPECTED_ITEMS,
    SCHEMA,
    ShapeRefused,
    check,
)


def bundle(**overrides):
    items = {
        name: {
            "status": "BLOCKED_EXTERNAL" if "pitr" not in name else "FAIL",
            "title": name,
            "source": "operational_readiness.probe",
            "group": "restore",
        }
        for name in EXPECTED_ITEMS
    }
    document = {
        "schemaVersion": SCHEMA,
        "codeSha": "a" * 40,
        # The honest verdict today. The gate must accept it.
        "verdict": "FAIL",
        "acceptanceClaim": False,
        "items": items,
    }
    document.update(overrides)
    return document


def accepted(document):
    return check(document, json.dumps(document, ensure_ascii=False))


def test_a_failing_verdict_is_accepted_because_the_verdict_is_the_measurement():
    summary = accepted(bundle())
    assert summary["verdict"] == "FAIL"
    assert summary["items"] == len(EXPECTED_ITEMS)
    assert set(summary["ciDerived"]) == set(CI_DERIVED_CLAIM)


@pytest.mark.parametrize("verdict", ["PASS_MEASURED_PARTIAL", "NOT_OBSERVED", "FAIL"])
def test_every_verdict_the_collector_can_produce_is_accepted(verdict):
    assert accepted(bundle(verdict=verdict))["verdict"] == verdict


def test_a_dropped_item_is_refused_because_it_reads_as_progress():
    """The failure mode the gate exists for.

    Removing a FAIL item takes it out of the scope lists, so the verdict improves because
    the question disappeared. Nothing in the bundle says so.
    """
    document = bundle()
    del document["items"]["verified-off-site-backup"]
    with pytest.raises(ShapeRefused, match="reads"):
        accepted(document)


def test_every_single_item_removal_is_refused():
    """All seventeen, not a sample: a gate that covered most of them would be a lottery."""
    for name in EXPECTED_ITEMS:
        document = bundle()
        del document["items"][name]
        with pytest.raises(ShapeRefused):
            accepted(document)


def test_an_unrecognised_status_is_refused():
    document = bundle()
    document["items"]["offer-agreement"]["status"] = "OK"
    with pytest.raises(ShapeRefused, match="recognised status"):
        accepted(document)


def test_an_item_that_is_not_an_object_is_refused():
    document = bundle()
    document["items"]["offer-agreement"] = "PASS"
    with pytest.raises(ShapeRefused, match="recognised status"):
        accepted(document)


def test_an_extra_item_is_refused_so_completeness_stays_decidable():
    document = bundle()
    document["items"]["invented-item"] = {"status": "PASS", "source": "x"}
    with pytest.raises(ShapeRefused, match="not in the expected set"):
        accepted(document)


@pytest.mark.parametrize("claim", [True, None, "false", 0, 1])
def test_anything_but_exactly_false_for_acceptanceClaim_is_refused(claim):
    """``0 == False`` in Python, so the comparison is by identity, not equality."""
    with pytest.raises(ShapeRefused, match="acceptanceClaim"):
        accepted(bundle(acceptanceClaim=claim))


def test_a_different_schema_is_refused():
    with pytest.raises(ShapeRefused, match="schemaVersion"):
        accepted(bundle(schemaVersion="s12-db-acceptance-evidence:2"))


def test_items_that_are_not_an_object_are_refused():
    with pytest.raises(ShapeRefused, match="keyed by item id"):
        accepted(bundle(items=[{"id": "offer-agreement", "status": "PASS"}]))


@pytest.mark.parametrize("name", CI_DERIVED_CLAIM)
def test_a_named_observation_without_a_source_is_refused(name):
    """The registry's claim is that CI derives these two, not that they merely appear.

    An item with no ``source`` could have been written by hand, which is the state the
    ``ciVerified`` note described. The gate refuses it.
    """
    document = bundle()
    document["items"][name]["source"] = ""
    with pytest.raises(ShapeRefused, match="names no source tool"):
        accepted(document)


@pytest.mark.parametrize(
    "leak",
    [
        "postgresql://invowner:ci_local_only@localhost:5432/postgres",
        "postgres://u:p@h/db",
        "password=hunter2",
        "PASSWORD=Hunter2",
    ],
)
def test_a_connection_string_in_the_file_is_refused(leak):
    """Re-read independently of the collector's own redaction.

    The collector redacts before serialising and re-checks its own text. This is the second
    pair of eyes on the file that actually shipped -- the artifact is uploaded, so a leak
    here is a leak into a downloadable place.
    """
    document = bundle()
    document["items"]["offer-agreement"]["note"] = leak
    with pytest.raises(ShapeRefused, match="connection string"):
        accepted(document)


def test_a_leak_escaped_by_json_is_still_refused():
    """A value with quotes or backslashes must not hide the pattern from the re-read."""
    document = bundle()
    document["items"]["offer-agreement"]["note"] = 'x" postgresql://u:p@h/db "y'
    with pytest.raises(ShapeRefused, match="connection string"):
        accepted(document)


def test_the_summary_groups_every_item_by_status():
    summary = accepted(bundle())
    grouped = sum(len(names) for names in summary["byStatus"].values())
    assert grouped == len(EXPECTED_ITEMS)
    assert summary["status"].startswith("shape accepted")
