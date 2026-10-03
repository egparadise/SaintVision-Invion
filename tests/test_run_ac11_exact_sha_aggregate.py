from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from tools import run_ac11_exact_sha_aggregate as subject


SHA = "a" * 40
TREE = "b" * 40
REF = "coord/exact-sha-fixture"
REPOSITORY = "egparadise/SaintVision-Invion"
NOW = dt.datetime(2026, 10, 3, 0, 0, tzinfo=dt.timezone.utc)
RESULT = {
    "schemaVersion": "1.0.0",
    "verdict": "INVALID_RUN",
    "done": False,
    "axes": [],
}


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def zip_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return output.getvalue()


class FakeGh:
    def __init__(self, *, seeded: bool = True) -> None:
        self.remote_sha = SHA
        self.next_run = 200
        self.next_artifact = 1200
        self.runs: dict[str, list[dict[str, object]]] = {
            workflow: [] for workflow in (*subject.EXPECTED_WORKFLOWS, subject.AGGREGATE_WORKFLOW)
        }
        self.views: dict[int, dict[str, object]] = {}
        self.artifacts: dict[int, list[dict[str, object]]] = {}
        self.artifact_details: dict[int, dict[str, object]] = {}
        self.archives: dict[int, bytes] = {}
        self.dispatched: list[str] = []
        self.duplicate_aggregate = False
        if seeded:
            for producer in subject.load_producers():
                self.add_success(producer.workflow, producer.artifact_prefix + SHA)

    @staticmethod
    def _workflow_from_filename(filename: str) -> str:
        matches = [
            workflow
            for workflow in (*subject.EXPECTED_WORKFLOWS, subject.AGGREGATE_WORKFLOW)
            if Path(workflow).name == filename
        ]
        assert len(matches) == 1
        return matches[0]

    @staticmethod
    def _run(workflow: str, identifier: int, title: str | None = None) -> dict[str, object]:
        return {
            "attempt": 1,
            "databaseId": identifier,
            "displayTitle": title or Path(workflow).stem,
            "event": "workflow_dispatch",
            "headBranch": REF,
            "headSha": SHA,
            "status": "completed",
            "conclusion": "success",
            "workflowName": workflow,
            "url": f"https://example.invalid/actions/runs/{identifier}",
            "createdAt": "2026-10-03T00:00:00Z",
        }

    def add_success(
        self,
        workflow: str,
        artifact_name: str,
        *,
        title: str | None = None,
        archive: bytes | None = None,
    ) -> dict[str, object]:
        identifier = self.next_run
        self.next_run += 1
        row = self._run(workflow, identifier, title)
        self.runs[workflow].append(row)
        self.views[identifier] = deepcopy(row)
        artifact_id = self.next_artifact
        self.next_artifact += 1
        body = archive if archive is not None else f"artifact-{artifact_id}".encode()
        detail: dict[str, object] = {
            "id": artifact_id,
            "name": artifact_name,
            "expired": False,
            "expires_at": "2026-12-01T00:00:00Z",
            "digest": "sha256:" + hashlib.sha256(body).hexdigest(),
            "workflow_run": {"id": identifier, "head_sha": SHA, "head_branch": REF},
        }
        self.artifacts[identifier] = [{"id": artifact_id, "name": artifact_name}]
        self.artifact_details[artifact_id] = detail
        self.archives[artifact_id] = body
        return row

    def __call__(self, args: list[str] | tuple[str, ...], *, timeout: float = 300.0):
        del timeout
        command = list(args)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return 0, (SHA + "\n").encode()
        if command[:3] == ["git", "status", "--porcelain"]:
            return 0, b""
        if command[:2] == ["git", "rev-parse"] and command[2].endswith("^{tree}"):
            return 0, (TREE + "\n").encode()
        if command[:2] == ["gh", "api"]:
            endpoint = command[2]
            if "/git/ref/heads/" in endpoint:
                return 0, json_bytes({"object": {"sha": self.remote_sha}})
            if "/actions/runs/" in endpoint and endpoint.endswith("/artifacts?per_page=100"):
                run_id = int(endpoint.split("/actions/runs/")[1].split("/")[0])
                rows = self.artifacts.get(run_id, [])
                return 0, json_bytes({"total_count": len(rows), "artifacts": rows})
            if "/actions/artifacts/" in endpoint and endpoint.endswith("/zip"):
                artifact_id = int(endpoint.split("/actions/artifacts/")[1].split("/")[0])
                return 0, self.archives[artifact_id]
            if "/actions/artifacts/" in endpoint:
                artifact_id = int(endpoint.rsplit("/", 1)[1])
                return 0, json_bytes(self.artifact_details[artifact_id])
        if command[:3] == ["gh", "run", "list"]:
            filename = command[command.index("--workflow") + 1]
            workflow = self._workflow_from_filename(filename)
            return 0, json_bytes(self.runs[workflow])
        if command[:3] == ["gh", "run", "view"]:
            return 0, json_bytes(self.views[int(command[3])])
        if command[:3] == ["gh", "workflow", "run"]:
            workflow = self._workflow_from_filename(command[3])
            values = [command[index + 1] for index, item in enumerate(command[:-1]) if item == "-f"]
            fields = dict(value.split("=", 1) for value in values)
            title = fields.get("correlation_id")
            archive = None
            if workflow == subject.AGGREGATE_WORKFLOW:
                archive = zip_bytes(
                    {
                        "ac11-checkout.json": b"{}",
                        "ac11-aggregate-manifest.json": b"{}",
                        "ac11-aggregate-result.json": b"{}",
                    }
                )
            self.add_success(
                workflow,
                (
                    subject.AGGREGATE_ARTIFACT_PREFIX + SHA
                    if workflow == subject.AGGREGATE_WORKFLOW
                    else next(
                        producer.artifact_prefix + SHA
                        for producer in subject.load_producers()
                        if producer.workflow == workflow
                    )
                ),
                title=title,
                archive=archive,
            )
            if self.duplicate_aggregate and workflow == subject.AGGREGATE_WORKFLOW:
                self.add_success(
                    workflow,
                    subject.AGGREGATE_ARTIFACT_PREFIX + SHA,
                    title=title,
                    archive=archive,
                )
            self.dispatched.append(workflow)
            return 0, b""
        raise AssertionError(f"unexpected command: {command}")


def fixed_correlation(workflow: str) -> str:
    return "ac11-exact-sha/" + Path(workflow).stem


def run(fake: FakeGh, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    monkeypatch.setattr(subject, "recompute", lambda *args, **kwargs: deepcopy(RESULT))
    return subject.orchestrate(
        source=SHA,
        ref=REF,
        repository=REPOSITORY,
        runner=fake,
        poll_seconds=0,
        deadline_seconds=30,
        sleep=lambda _: None,
        monotonic=lambda: 1,
        now_utc=lambda: NOW,
        correlation_factory=fixed_correlation,
    )


def test_source_map_is_exactly_the_three_reviewed_producers_and_four_axes() -> None:
    producers = subject.load_producers()
    assert {producer.workflow for producer in producers} == set(subject.EXPECTED_WORKFLOWS)
    assert {axis for producer in producers for axis in producer.axes} == {
        "security-critical-high-zero",
        "accessibility-e2e",
        "migration-reversible-segment",
        "irreversible-restore-forward",
    }


def test_documented_direct_cli_invocation_loads_the_tools_package() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/run_ac11_exact_sha_aggregate.py", "--help"],
        cwd=subject.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--source-sha" in completed.stdout


def test_reuses_exact_producers_and_dispatches_only_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    receipt = run(fake, monkeypatch)
    assert fake.dispatched == [subject.AGGREGATE_WORKFLOW]
    assert all(row["reused"] is True for row in receipt["producerRuns"])
    assert receipt["canonicalResult"] == RESULT
    assert receipt["promotesScore"] is False
    assert receipt["secretsRequired"] is False


def test_dispatches_only_the_missing_producer_then_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    missing = ".github/workflows/ac11-security-scan.yml"
    run_id = int(fake.runs[missing][0]["databaseId"])
    artifact_id = int(fake.artifacts[run_id][0]["id"])
    fake.runs[missing].clear()
    fake.views.pop(run_id)
    fake.artifacts.pop(run_id)
    fake.artifact_details.pop(artifact_id)
    fake.archives.pop(artifact_id)
    receipt = run(fake, monkeypatch)
    assert fake.dispatched == [missing, subject.AGGREGATE_WORKFLOW]
    security = next(row for row in receipt["producerRuns"] if row["workflow"] == missing)
    assert security["reused"] is False


def test_remote_ref_must_still_equal_the_exact_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    fake.remote_sha = "f" * 40
    with pytest.raises(subject.Refused, match="remote ref"):
        run(fake, monkeypatch)
    assert fake.dispatched == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("headSha", "f" * 40, "headSha differs"),
        ("headBranch", "other/ref", "headBranch differs"),
        ("event", "push", "event differs"),
        ("workflowName", ".github/workflows/backend.yml", "workflowName differs"),
        ("attempt", 2, "attempt differs"),
    ],
)
def test_run_view_identity_mismatch_is_refused(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    fake = FakeGh()
    row = fake.runs[".github/workflows/ac11-security-scan.yml"][0]
    fake.views[int(row["databaseId"])][field] = value
    with pytest.raises(subject.Refused, match=message):
        run(fake, monkeypatch)


def test_rerun_attempt_is_refused_before_adoption(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    fake.runs[".github/workflows/ac11-security-scan.yml"][0]["attempt"] = 2
    with pytest.raises(subject.Refused, match="reused run attempt"):
        run(fake, monkeypatch)


def test_duplicate_usable_producer_run_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    producer = subject.load_producers()[0]
    fake.add_success(producer.workflow, producer.artifact_prefix + SHA)
    with pytest.raises(subject.Refused, match="duplicate usable runs"):
        run(fake, monkeypatch)


def test_saturated_run_listing_is_refused_instead_of_silently_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeGh()
    workflow = ".github/workflows/ac11-security-scan.yml"
    template = fake.runs[workflow][0]
    fake.runs[workflow] = [
        {**template, "databaseId": 5000 + index, "headSha": "f" * 40}
        for index in range(subject.RUN_LIST_LIMIT)
    ]
    with pytest.raises(subject.Refused, match="listing reached its limit"):
        run(fake, monkeypatch)


@pytest.mark.parametrize(
    "damage", ["missing", "duplicate", "expired", "wrong-run", "wrong-sha", "wrong-ref", "digest"]
)
def test_artifact_boundary_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    fake = FakeGh()
    workflow = ".github/workflows/ac11-security-scan.yml"
    run_id = int(fake.runs[workflow][0]["databaseId"])
    artifact_id = int(fake.artifacts[run_id][0]["id"])
    if damage == "missing":
        fake.artifacts[run_id] = []
    elif damage == "duplicate":
        fake.artifacts[run_id].append(deepcopy(fake.artifacts[run_id][0]))
    elif damage == "expired":
        fake.artifact_details[artifact_id]["expired"] = True
    elif damage == "wrong-run":
        fake.artifact_details[artifact_id]["workflow_run"] = {
            "id": 999, "head_sha": SHA, "head_branch": REF
        }
    elif damage == "wrong-sha":
        fake.artifact_details[artifact_id]["workflow_run"] = {
            "id": run_id, "head_sha": "f" * 40, "head_branch": REF
        }
    elif damage == "wrong-ref":
        fake.artifact_details[artifact_id]["workflow_run"] = {
            "id": run_id, "head_sha": SHA, "head_branch": "other/ref"
        }
    else:
        fake.archives[artifact_id] += b"tampered"
    with pytest.raises(subject.Refused):
        run(fake, monkeypatch)


def test_truncated_artifact_listing_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    original = fake.__call__

    def truncated(args, *, timeout=300.0):
        command = list(args)
        if command[:2] == ["gh", "api"] and command[2].endswith("/artifacts?per_page=100"):
            code, body = original(args, timeout=timeout)
            doc = json.loads(body)
            doc["total_count"] += 1
            return code, json_bytes(doc)
        return original(args, timeout=timeout)

    with pytest.raises(subject.Refused, match="listing is truncated"):
        subject.orchestrate(
            source=SHA,
            ref=REF,
            repository=REPOSITORY,
            runner=truncated,
            poll_seconds=0,
            deadline_seconds=30,
            sleep=lambda _: None,
            monotonic=lambda: 1,
            now_utc=lambda: NOW,
            correlation_factory=fixed_correlation,
        )


def test_duplicate_aggregate_correlation_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    fake.duplicate_aggregate = True
    with pytest.raises(subject.Refused, match="duplicate aggregate runs"):
        run(fake, monkeypatch)


def test_one_run_id_cannot_be_reused_by_two_producers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh()
    workflows = list(subject.EXPECTED_WORKFLOWS)
    artifact_ids = {
        producer.artifact_prefix + SHA: 1000 + index
        for index, producer in enumerate(subject.load_producers())
    }
    first = fake.runs[workflows[0]][0]
    second = fake.runs[workflows[1]][0]
    second["databaseId"] = first["databaseId"]
    monkeypatch.setattr(subject, "wait_existing", lambda *args, **kwargs: args[2])
    monkeypatch.setattr(
        subject,
        "artifact_for_run",
        lambda *args, **kwargs: subject.Artifact(
            artifact_ids[args[3]],
            args[3],
            "sha256:" + f"{artifact_ids[args[3]]:064x}",
            "2026-12-01T00:00:00Z",
            b"unused",
        ),
    )
    with pytest.raises(subject.Refused, match="run or artifact was reused"):
        run(fake, monkeypatch)


def test_recompute_rejects_uploaded_result_not_equal_to_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {"schemaVersion": "1.0.0", "runPurpose": "ac11-release-gate", "releaseSha": SHA, "axes": []}
    checkout = {
        "schemaVersion": "ac11-aggregate-checkout:1",
        "sourceSha": SHA,
        "checkoutSha": SHA,
        "event": "workflow_dispatch",
        "runId": "99",
        "correlationId": "fixture-correlation",
    }
    archive = zip_bytes(
        {
            "ac11-checkout.json": json_bytes(checkout),
            "ac11-aggregate-manifest.json": json_bytes(manifest),
            "ac11-aggregate-result.json": json_bytes({"verdict": "MEASURED_PASS"}),
        }
    )
    monkeypatch.setattr(subject.canonical, "aggregate", lambda *args, **kwargs: deepcopy(RESULT))
    run_row = FakeGh._run(subject.AGGREGATE_WORKFLOW, 99, "fixture-correlation")
    with pytest.raises(subject.Refused, match="differs from canonical recomputation"):
        subject.recompute(
            archive,
            SHA,
            run_row,
            "fixture-correlation",
            (),
            now_utc=lambda: NOW,
        )


def test_recompute_binds_every_emitted_axis_to_selected_run_and_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer = subject.load_producers()[0]
    producer_row = FakeGh._run(producer.workflow, 41)
    artifact = subject.Artifact(51, producer.artifact_prefix + SHA, "sha256:" + "c" * 64,
                                "2026-12-01T00:00:00Z", b"unused")
    bound = subject.BoundRun(producer, producer_row, artifact, True)
    rows = [
        {
            "axis": axis,
            "sourceHeadSha": SHA,
            "sourceRunId": "41",
            "artifactSha256": "c" * 64,
            "artifactObservedSha256": "c" * 64,
        }
        for axis in producer.axes
    ]
    manifest = {"releaseSha": SHA, "axes": rows}
    checkout = {
        "schemaVersion": "ac11-aggregate-checkout:1",
        "sourceSha": SHA,
        "checkoutSha": SHA,
        "event": "workflow_dispatch",
        "runId": "99",
        "correlationId": "fixture-correlation",
    }
    archive = zip_bytes(
        {
            "ac11-checkout.json": json_bytes(checkout),
            "ac11-aggregate-manifest.json": json_bytes(manifest),
            "ac11-aggregate-result.json": json_bytes(RESULT),
        }
    )
    monkeypatch.setattr(subject.canonical, "aggregate", lambda *args, **kwargs: deepcopy(RESULT))
    run_row = FakeGh._run(subject.AGGREGATE_WORKFLOW, 99, "fixture-correlation")
    assert subject.recompute(
        archive,
        SHA,
        run_row,
        "fixture-correlation",
        (bound,),
        now_utc=lambda: NOW,
    ) == RESULT
    rows[0]["sourceRunId"] = "42"
    tampered = zip_bytes(
        {
            "ac11-checkout.json": json_bytes(checkout),
            "ac11-aggregate-manifest.json": json_bytes(manifest),
            "ac11-aggregate-result.json": json_bytes(RESULT),
        }
    )
    with pytest.raises(subject.Refused, match="another producer run"):
        subject.recompute(
            tampered,
            SHA,
            run_row,
            "fixture-correlation",
            (bound,),
            now_utc=lambda: NOW,
        )
