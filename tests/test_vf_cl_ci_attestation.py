from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from tools import create_vf_cl_ci_attestation_receipt as creator
from tools import verify_vf_cl_ci_attestation as verifier


HEAD = "a" * 40
RUN_ID = "36930000000"
ARTIFACT_ID = "11190000000"
ARTIFACT_NAME = f"s12-acceptance-{HEAD}"
REF = "refs/heads/agent/codex/c211-vfcl-ci-attestation"
STEPS = [
    "Derive the AC-12 acceptance items",
    "Hold the bundle to its shape and to this head",
    "Record that the two named observations were derived here",
    "Upload the acceptance evidence",
]


def artifact_metadata(**changes):
    artifact = {
        "id": int(ARTIFACT_ID),
        "name": ARTIFACT_NAME,
        "expired": False,
        "digest": "sha256:" + "b" * 64,
        "created_at": "2026-10-02T00:00:00Z",
        "expires_at": "2026-12-31T00:00:00Z",
        "workflow_run": {"id": int(RUN_ID), "head_sha": HEAD},
    }
    artifact.update(changes)
    return {"total_count": 1, "artifacts": [artifact]}


def receipt_document(**changes):
    value = creator.build_receipt(
        metadata=artifact_metadata(),
        artifact_id=ARTIFACT_ID,
        artifact_name=ARTIFACT_NAME,
        repository=creator.REPOSITORY,
        run_id=RUN_ID,
        run_attempt="1",
        event="workflow_dispatch",
        head_sha=HEAD,
        head_ref=REF,
        producer_conclusion="success",
        required_steps=STEPS,
        now=dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc),
    )
    value.update(changes)
    value["receiptSha256"] = creator.canonical_digest(value)
    return value


def write_receipt(path: Path, value=None):
    path.write_text(json.dumps(value or receipt_document(), indent=2) + "\n", encoding="utf-8")


def verification_for(path: Path, *, digest=None, name=None):
    return [{
        "attestation": {"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json"},
        "verificationResult": {
            "signature": {"certificate": {}},
            "verifiedTimestamps": [{}],
            "statement": {
                "predicateType": "https://slsa.dev/provenance/v1",
                "predicate": {},
                "subject": [{
                    "name": name or path.name,
                    "digest": {"sha256": digest or hashlib.sha256(path.read_bytes()).hexdigest()},
                }],
            },
        },
    }]


def test_creator_binds_current_run_head_and_artifact():
    value = receipt_document()
    assert set(value) == creator.RECEIPT_KEYS
    assert set(value["producerJob"]) == creator.PRODUCER_KEYS
    assert set(value["evidenceArtifact"]) == creator.ARTIFACT_KEYS
    assert value["evidenceArtifact"]["id"] == ARTIFACT_ID
    assert value["receiptSha256"] == creator.canonical_digest(value)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"workflow_run": {"id": 1, "head_sha": HEAD}}, "current run"),
        ({"workflow_run": {"id": int(RUN_ID), "head_sha": "c" * 40}}, "current head"),
        ({"expired": True}, "expired"),
        ({"digest": "sha256:nope"}, "digest"),
    ],
)
def test_creator_rejects_unbound_artifact_metadata(change, message):
    with pytest.raises(creator.ReceiptError, match=message):
        creator.build_receipt(
            metadata=artifact_metadata(**change), artifact_id=ARTIFACT_ID,
            artifact_name=ARTIFACT_NAME, repository=creator.REPOSITORY,
            run_id=RUN_ID, run_attempt="1", event="workflow_dispatch",
            head_sha=HEAD, head_ref=REF, producer_conclusion="success",
            required_steps=STEPS,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repository", "attacker/repo", "repository must"),
        ("event", "pull_request", "workflow_dispatch-only"),
        ("head_sha", "a" * 39, "full lowercase"),
        ("head_ref", "refs/pull/1/merge", "branch ref"),
        ("producer_conclusion", "failure", "did not succeed"),
    ],
)
def test_creator_rejects_untrusted_context(field, value, message):
    kwargs = dict(
        metadata=artifact_metadata(), artifact_id=ARTIFACT_ID, artifact_name=ARTIFACT_NAME,
        repository=creator.REPOSITORY, run_id=RUN_ID, run_attempt="1",
        event="workflow_dispatch", head_sha=HEAD, head_ref=REF,
        producer_conclusion="success", required_steps=STEPS,
    )
    kwargs[field] = value
    with pytest.raises(creator.ReceiptError, match=message):
        creator.build_receipt(**kwargs)


def test_verifier_enforces_github_identity_and_exact_subject(tmp_path):
    receipt = tmp_path / "VF-CL-04.json"
    bundle = tmp_path / "bundle.json"
    write_receipt(receipt)
    bundle.write_text("{}", encoding="utf-8")
    seen = []

    def run(command, **kwargs):
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(verification_for(receipt)), "")

    verified = verifier.verify(
        receipt, bundle, expected_repository=creator.REPOSITORY,
        expected_workflow=creator.WORKFLOW_PATH, expected_head=HEAD,
        expected_ref=REF, runner=run,
    )
    assert verified["runId"] == RUN_ID
    command = seen[0][0]
    assert command[command.index("--repo") + 1] == creator.REPOSITORY
    assert command[command.index("--signer-workflow") + 1] == (
        f"{creator.REPOSITORY}/{creator.WORKFLOW_PATH}"
    )
    assert command[command.index("--source-digest") + 1] == HEAD
    assert command[command.index("--source-ref") + 1] == REF
    assert "--deny-self-hosted-runners" in command


@pytest.mark.parametrize(
    ("field", "expected", "message"),
    [
        ("repository", "attacker/repo", "receipt repository"),
        ("workflowPath", ".github/workflows/other.yml", "receipt workflowPath"),
        ("headSha", "c" * 40, "receipt headSha"),
        ("headRef", "refs/heads/other", "receipt headRef"),
    ],
)
def test_wrong_repository_workflow_sha_or_ref_never_reaches_gh(tmp_path, field, expected, message):
    receipt = tmp_path / "VF-CL-04.json"
    bundle = tmp_path / "bundle.json"
    write_receipt(receipt)
    bundle.write_text("{}", encoding="utf-8")
    kwargs = dict(
        expected_repository=creator.REPOSITORY, expected_workflow=creator.WORKFLOW_PATH,
        expected_head=HEAD, expected_ref=REF,
    )
    mapping = {
        "repository": "expected_repository", "workflowPath": "expected_workflow",
        "headSha": "expected_head", "headRef": "expected_ref",
    }
    kwargs[mapping[field]] = expected
    called = False

    def run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("gh must not run")

    with pytest.raises(verifier.AttestationError, match=message):
        verifier.verify(receipt, bundle, runner=run, **kwargs)
    assert called is False


def test_forged_receipt_cannot_reuse_the_original_attestation(tmp_path):
    receipt = tmp_path / "VF-CL-04.json"
    bundle = tmp_path / "bundle.json"
    write_receipt(receipt)
    original_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    forged = receipt_document(runId="99999999999")
    write_receipt(receipt, forged)
    bundle.write_text("{}", encoding="utf-8")

    def run(command, **_kwargs):
        return subprocess.CompletedProcess(
            command, 0, json.dumps(verification_for(receipt, digest=original_digest)), ""
        )

    with pytest.raises(verifier.AttestationError, match="exact receipt bytes"):
        verifier.verify(
            receipt, bundle, expected_repository=creator.REPOSITORY,
            expected_workflow=creator.WORKFLOW_PATH, expected_head=HEAD,
            expected_ref=REF, runner=run,
        )


def test_missing_bundle_and_failed_signature_are_fail_closed(tmp_path):
    receipt = tmp_path / "VF-CL-04.json"
    bundle = tmp_path / "bundle.json"
    write_receipt(receipt)
    with pytest.raises(verifier.AttestationError, match="bundle is missing"):
        verifier.verify(
            receipt, bundle, expected_repository=creator.REPOSITORY,
            expected_workflow=creator.WORKFLOW_PATH, expected_head=HEAD, expected_ref=REF,
        )
    bundle.write_text("{}", encoding="utf-8")

    def run(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1, "", "verification failed")

    with pytest.raises(verifier.AttestationError, match="signature or identity"):
        verifier.verify(
            receipt, bundle, expected_repository=creator.REPOSITORY,
            expected_workflow=creator.WORKFLOW_PATH, expected_head=HEAD,
            expected_ref=REF, runner=run,
        )


def test_workflow_grants_signing_permissions_only_to_manual_attestation_job():
    workflow = yaml.safe_load(Path(".github/workflows/s12-acceptance-evidence.yml").read_text(
        encoding="utf-8"
    ))
    jobs = workflow["jobs"]
    producer = jobs["s12-acceptance-evidence"]
    attestation = jobs["attest-vf-cl-ci-receipt"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in producer
    assert attestation["permissions"] == {
        "contents": "read",
        "actions": "read",
        "id-token": "write",
        "attestations": "write",
        "artifact-metadata": "write",
    }
    assert attestation["if"] == (
        "github.event_name == 'workflow_dispatch' && "
        "needs.s12-acceptance-evidence.result == 'success'"
    )
    uses = [step.get("uses") for step in attestation["steps"]]
    assert uses.count("actions/attest@v4") == 1
    assert "pull_request" not in attestation["if"]
    producer_upload = next(
        step for step in producer["steps"] if step.get("uses") == "actions/upload-artifact@v4"
    )
    attestation_upload = next(
        step for step in attestation["steps"]
        if step.get("uses") == "actions/upload-artifact@v4"
    )
    assert producer_upload["with"]["retention-days"] == 30
    assert attestation_upload["with"]["retention-days"] == 30
