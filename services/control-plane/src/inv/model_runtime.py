"""Bounded CPU file adapter using the existing approval, signed plan and Node inbox.

This is not PyTorch/vLLM/GPU or collective support. No host mount or execution
approval is granted by prepare(). The same verified bytes are frozen and then
carried in the existing initialized-workspace permit. Current grants, Node and
Lease fences are rechecked at ToolGateway admission. Explicit remote readers
also freeze channel provenance and recheck it at delivery and admission.
"""

import base64
from copy import deepcopy
import hashlib
import json
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from .approvals import ApprovalStore, Principal
from .business_auth import permission
from .containment import require_execution
from .contracts import validate_contract
from .errors import DomainError
from .leases import assert_fences, lock_resources, lock_run
from .model_locality import _capture
from .model_manifest import ConfiguredModelVerifier, canonical, manifest_copy, rejected
from .model_remote import ConfiguredRemoteModelReader
from .model_source import SOURCE_FILE, capture_channels, frozen_sources, source_content, source_records
from .node_channels import assert_channel
from .runs import event
from .workspace_files import FORMAT, canonical as workspace_canonical
from .workspace_resume import bounded_snapshot

OPERATION = "model.runtime.prepare"


def bound_input(conn, project, run_id):
    row = conn.execute(
        "SELECT * FROM inv.model_run_inputs WHERE project_id=%s AND run_id=%s", (project, run_id)
    ).fetchone()
    if not row:
        raise DomainError("MODEL-0004", "Reserved model input not found", 404)
    return row


def manifest(conn, binding):
    row = conn.execute(
        "SELECT manifest,manifest_sha256 FROM inv.model_manifests WHERE project_id=%s AND model_id=%s AND version=%s",
        (binding["project_id"], binding["model_id"], binding["model_version"]),
    ).fetchone()
    if not row or row["manifest_sha256"] != binding["manifest_sha256"]:
        rejected()
    body = manifest_copy(row["manifest"])
    if hashlib.sha256(canonical(body)).hexdigest() != binding["manifest_sha256"]:
        rejected()
    body["replicas"] = [r for r in body["replicas"] if r["nodeId"] == binding["node_id"]]
    return manifest_copy(body)


def require_model_reference(conn, run, workload):
    binding = conn.execute(
        "SELECT 1 FROM inv.model_run_inputs WHERE run_id=%s", (run["run_id"],)
    ).fetchone()
    if bool(binding) != ("modelInput" in workload):
        raise DomainError("MODEL-0006", "Current frozen model execution input required", 422)


def approved_model(
    conn, run, workload, epoch, *, node_id=None, proofs=None, database=None, requester=None
):
    require_model_reference(conn, run, workload)
    ref = workload["modelInput"]
    row = conn.execute(
        "SELECT * FROM inv.model_runtime_inputs WHERE project_id=%s AND run_id=%s",
        (workload["projectId"], run["run_id"]),
    ).fetchone()
    binding = bound_input(conn, workload["projectId"], run["run_id"])
    if (
        not row
        or str(row["recovery_epoch"]) != epoch
        or row["workload"] != workload
        or ref["runId"] != run["run_id"]
        or str(row["input_id"]) != ref["inputId"]
        or ref["nodeId"] != binding["node_id"]
        or ref["manifestHash"] != binding["manifest_sha256"]
        or (requester is not None and row["requester_id"] != requester)
    ):
        raise DomainError("MODEL-0006", "Frozen model action, Node or epoch differs", 403)
    principal = Principal(str(row["tenant_id"]), row["requester_id"])
    raw = bytes(row["snapshot"])
    bounded_snapshot(raw, workload["workspaceId"])
    if len(raw) != ref["inputSizeBytes"] or hashlib.sha256(raw).hexdigest() != ref["inputSha256"]:
        rejected()
    saved_locations, saved_channels = frozen_sources(
        raw, workload["workspaceId"], row["locations"], principal.tenant_id, epoch
    )
    if saved_channels and node_id is None:
        # Approval creation holds Run/grants, not the allocation's Node locks.
        # Check business permission and only channels here; delivery/claim below
        # rechecks the complete current Node/Location scope after Node locking.
        permission(conn, workload["projectId"], principal.subject_id, "can_request", linked=True)
        for channel in saved_channels:
            assert_channel(conn, channel)
    if node_id is not None:
        if node_id != binding["node_id"] or proofs != {
            l["leaseId"]: l["fencingToken"] for l in binding["input"]["leases"]
        }:
            raise DomainError("LEASE-0002", "Frozen model allocation differs", 403)
        # Called only after ToolGateway has locked current Node/resources.
        current = _capture(
            conn, database, principal, workload["projectId"], manifest(conn, binding)
        )
        if current != saved_locations:
            rejected()
        if saved_channels and capture_channels(conn, principal.tenant_id, epoch, current) != saved_channels:
            rejected()
        assert_fences(conn, run["run_id"], proofs)
    return {
        "startId": ref["inputId"],
        "stepId": ref["inputId"],
        "sha256": ref["inputSha256"],
        "sizeBytes": len(raw),
        "dataBase64": base64.b64encode(raw).decode(),
    }


class ModelRuntimeStore:
    def __init__(self, database, verifier):
        if not isinstance(verifier, (ConfiguredModelVerifier, ConfiguredRemoteModelReader)):
            raise ValueError("Operator-configured model byte verifier required")
        self.db, self.verifier = database, verifier
        self.auth = ApprovalStore(database)

    def _scope(self, conn, principal, project, run_id, workload, proofs):
        run = lock_run(conn, run_id, project)
        require_execution(conn)
        if run["state"] != "planned" or run["attempt"] != 0:
            raise DomainError("MODEL-0006", "Fresh planned model Run required", 409)
        binding = bound_input(conn, project, run_id)
        expected = {l["leaseId"]: l["fencingToken"] for l in binding["input"]["leases"]}
        if (
            proofs != expected
            or workload.get("targetNodeId", binding["node_id"]) != binding["node_id"]
        ):
            raise DomainError("LEASE-0002", "Reserved model allocation differs", 403)
        rows = conn.execute(
            "SELECT resource_id FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (run_id,),
        ).fetchall()
        resources = lock_resources(conn, [r["resource_id"] for r in rows])
        assert_fences(conn, run_id, proofs)
        if {r["node_id"] for r in resources.values()} != {binding["node_id"]}:
            rejected()
        body = manifest(conn, binding)
        locations = _capture(conn, self.db, principal, project, body)
        self.auth._grant(conn, project, principal.subject_id, "can_request")
        permission(conn, project, principal.subject_id, "can_request", linked=True)
        channels = (
            capture_channels(conn, principal.tenant_id, self.db.recovery_epoch, locations)
            if isinstance(self.verifier, ConfiguredRemoteModelReader) else ()
        )
        return (run["version"], binding, body, locations, channels)

    def prepare(self, principal, project, run_id, workload, proofs, *, key):
        workload = deepcopy(workload)
        validate_contract("WorkloadSpec", workload)
        proofs = json.loads(canonical(proofs))
        if (
            workload["tenantId"] != principal.tenant_id
            or workload["projectId"] != project
            or any(
                k in workload
                for k in ("modelInput", "workspaceStart", "workspaceResume", "terminal")
            )
            or workload["resources"]["gpuCount"]
            or workload["resources"]["minVramBytes"]
        ):
            raise DomainError("MODEL-0002", "Independent CPU model file workload required", 422)
        payload = {"runId": run_id, "workload": workload, "fences": proofs}
        if isinstance(self.verifier, ConfiguredRemoteModelReader):
            # A local commitment cannot be replayed as remote verification merely
            # by changing the configured provider while retaining the same key.
            payload["sourceMode"] = "node-mtls-v1"
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
            self.auth._grant(conn, project, principal.subject_id, "can_request")
            if prior is not None:
                permission(conn, project, principal.subject_id, "can_request", linked=True)
                return prior
            if conn.execute(
                "SELECT 1 FROM inv.model_runtime_inputs WHERE run_id=%s", (run_id,)
            ).fetchone():
                raise DomainError("MODEL-0003", "Model runtime input already frozen", 409)
            captured = self._scope(conn, principal, project, run_id, workload, proofs)
        _, binding, body, locations, channels = captured
        if isinstance(self.verifier, ConfiguredRemoteModelReader):
            remote = self.verifier.read(body, locations, channels,
                tenant_id=principal.tenant_id, recovery_epoch=self.db.recovery_epoch)
            if remote.locations != locations or remote.channels != channels:
                rejected()
            verified, chunks = remote.manifest_hash, dict(enumerate(remote.shards))
        else:
            verified, chunks = self.verifier.freeze(body, locations)
        if (
            verified != hashlib.sha256(canonical(body)).hexdigest()
            or set(chunks) != set(range(len(body["shards"])))
            or any(
                not isinstance(chunks[s["index"]], bytes)
                or len(chunks[s["index"]]) != s["byteLength"]
                or hashlib.sha256(chunks[s["index"]]).hexdigest() != s["sha256"]
                for s in body["shards"]
            )
            or hashlib.sha256(b"".join(chunks[i] for i in range(len(chunks)))).hexdigest()
            != body["contentHash"]
        ):
            rejected()
        # Paths are fixed by this adapter, never copied from Catalog/UI filenames.
        contents = {"model/%04d.bin" % i: value for i, value in chunks.items()}
        records = source_records(locations, channels)
        if channels:
            contents[SOURCE_FILE] = source_content(records)
        contents["model/manifest.json"] = canonical(
            {
                "modelId": body["modelId"],
                "version": body["version"],
                "manifestHash": binding["manifest_sha256"],
                "contentHash": body["contentHash"],
                "shards": body["shards"],
            }
        )
        raw = workspace_canonical(
            {
                "format": FORMAT,
                "workspaceId": workload["workspaceId"],
                "directories": ["model"],
                "files": [
                    {
                        "path": name,
                        "executable": False,
                        "sha256": hashlib.sha256(value).hexdigest(),
                        "sizeBytes": len(value),
                        "dataBase64": base64.b64encode(value).decode(),
                    }
                    for name, value in sorted(contents.items())
                ],
            }
        )
        bounded_snapshot(raw, workload["workspaceId"])
        frozen = {
            **workload,
            "targetNodeId": binding["node_id"],
            "modelInput": {
                "inputId": str(uuid4()),
                "runId": run_id,
                "modelId": body["modelId"],
                "version": body["version"],
                "manifestHash": binding["manifest_sha256"],
                "inputSha256": hashlib.sha256(raw).hexdigest(),
                "inputSizeBytes": len(raw),
                "nodeId": binding["node_id"],
                "adapter": "python-files",
                "adapterVersion": "1",
                "mode": "single-node",
            },
        }
        validate_contract("WorkloadSpec", frozen)
        try:
            with self.db.transaction(principal.tenant_id) as conn:
                prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
                self.auth._grant(conn, project, principal.subject_id, "can_request")
                if prior is not None:
                    permission(conn, project, principal.subject_id, "can_request", linked=True)
                    return prior
                if self._scope(conn, principal, project, run_id, workload, proofs) != captured:
                    rejected()
                conn.execute(
                    """INSERT INTO inv.model_runtime_inputs
                    (tenant_id,project_id,run_id,input_id,recovery_epoch,requester_id,workload,snapshot,locations)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        principal.tenant_id,
                        project,
                        run_id,
                        frozen["modelInput"]["inputId"],
                        self.db.recovery_epoch,
                        principal.subject_id,
                        Jsonb(frozen),
                        raw,
                        Jsonb(records),
                    ),
                )
                result = {"runId": run_id, "workload": frozen, "requiresApproval": True}
                event(
                    conn,
                    principal.tenant_id,
                    run_id,
                    "inv.model.runtime_input_frozen",
                    frozen["modelInput"],
                )
                assert_fences(conn, run_id, proofs)
                return self.auth._save(conn, project, OPERATION, key, result)
        except psycopg.errors.UniqueViolation:
            raise DomainError("MODEL-0003", "Model runtime input already frozen", 409) from None
