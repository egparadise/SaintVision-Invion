"""Public build prepare/enqueue boundary over server-owned build documents.

Only the four-field prepare input and two-field enqueue input cross HTTP.  Raw
BuildRequest/BuildPlan/PolicyDecision documents remain server-owned.  Product
dispatch is disabled unless ``INV_BUILDKIT_PRODUCT_ENABLED`` is exactly ``1``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import os
from pathlib import Path
from typing import Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from .approvals import ApprovalStore, Principal, digest
from .build_execution import PRODUCT_ENABLE_SETTING, PRODUCT_ENABLE_VALUE
from .build_governance import canonical_build_action
from .contracts import validate_contract
from .db import BoundDatabase
from .errors import DomainError
from .ids import new_id
from .leases import Allocation, LeaseStore, active_total, lock_resources, lock_run
from .policy import action_digest
from .runs import event
from .workspace_files import decode_snapshot

PREPARE_LIMITS = (("subject", "prepare", 5), ("project", "combined", 30),
                  ("tenant-project", "combined", 60))
ENQUEUE_LIMITS = (("subject", "enqueue", 10), ("project", "combined", 30),
                  ("tenant-project", "combined", 60))
TERMINAL_ENQUEUE_CODES = frozenset({"GRAPH-0003", "VERIFY-0002"})


def validate_build_input(contract: str, value: Mapping) -> None:
    """Map strict public build-shape failures to the documented VAL-0003."""

    try:
        validate_contract(contract, value)
    except DomainError as error:
        if error.code == "VAL-0002":
            raise DomainError("VAL-0003", "Invalid build request shape", 422) from None
        raise


def _git_hash(kind: bytes, body: bytes) -> bytes:
    framed = kind + b" " + str(len(body)).encode("ascii") + b"\0" + body
    # Git object identity is defined as SHA-1.  It is not used for a security
    # decision; the capsule's SHA-256 remains the content authority.
    return hashlib.sha1(framed, usedforsecurity=False).digest()


def _git_source_identity(raw: bytes, workspace_id: str, context: str, dockerfile: str):
    """Return real Git object identities for one canonical immutable snapshot."""

    manifest, content = decode_snapshot(raw, workspace_id)
    directories = set(manifest["directories"])
    if context not in directories or dockerfile not in content or not dockerfile.startswith(
        context.rstrip("/") + "/"
    ):
        raise DomainError("VERIFY-0002", "Build context or Dockerfile escapes the snapshot", 422)
    tree: dict[str, dict] = {}
    executable = {item["path"]: item["executable"] for item in manifest["files"]}
    for path, body in content.items():
        node = tree
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = (body, executable[path])

    def tree_oid(node: dict) -> bytes:
        entries = []
        for name in sorted(node, key=lambda value: (value + ("/" if isinstance(node[value], dict) else "")).encode()):
            value = node[name]
            if isinstance(value, dict):
                mode, oid = b"40000", tree_oid(value)
            else:
                body, is_executable = value
                mode, oid = (b"100755" if is_executable else b"100644"), _git_hash(b"blob", body)
            entries.append(mode + b" " + name.encode("utf-8") + b"\0" + oid)
        return _git_hash(b"tree", b"".join(entries))

    tree_digest = tree_oid(tree)
    tree_hex = tree_digest.hex()
    commit = (
        f"tree {tree_hex}\n"
        "author SaintVision Build Authority <build@sv.invalid> 0 +0000\n"
        "committer SaintVision Build Authority <build@sv.invalid> 0 +0000\n\n"
        "SaintVision immutable build capsule\n"
    ).encode("utf-8")
    return _git_hash(b"commit", commit).hex(), tree_hex


def _identity_decision(decision: Mapping) -> dict:
    result = deepcopy(dict(decision))
    result.pop("approvedBy", None)
    return result


class ConfiguredBuildPlanAuthority:
    """Measure the configured builder, then create plan/lease authority in DB.

    The worker configuration is operator-owned.  Only the health read and
    ``buildctl debug workers`` call happen outside the business transaction;
    resource selection, the lease, session and evidence identities are created
    after the approval transaction has locked the Run and preparation.
    """

    def __init__(self, database, build_execution: Mapping, *, environment=None):
        from .buildkit_transport import (
            BuildkitTransportConfiguration,
            RootlessBuildkitTransport,
        )
        from .worker import BUILD_EXECUTION_KEYS

        values = dict(build_execution)
        if set(values) != BUILD_EXECUTION_KEYS:
            raise ValueError("Exact build execution configuration required")
        self.db = database
        self.node_id = values["nodeId"]
        self.transport = RootlessBuildkitTransport(
            BuildkitTransportConfiguration(
                buildctl_path=Path(values["buildctlPath"]),
                address=values["address"],
                source_root=Path(values["sourceRoot"]),
                health_receipt_path=Path(values["referenceHealthReceipt"]),
                builder_instance_id=values["builderInstanceId"],
                builder_profile_id=values["builderProfileId"],
                recovery_epoch=values["providerRecoveryEpoch"],
            ),
            environment=environment,
        )

    def measure_candidate(self, _principal, _preparation, request):
        measured = self.transport.measure()
        if request["targetPlatform"] not in measured.platforms:
            raise DomainError(
                "RES-0006", "Measured builder does not support the target platform", 503, True
            )
        return measured

    def compile_plan(self, conn, principal, preparation, request, decision, candidate):
        from .buildkit_transport import MeasuredBuilder

        if not isinstance(candidate, MeasuredBuilder):
            raise DomainError("RES-0006", "Measured build provider authority unavailable", 503, True)
        run = lock_run(conn, preparation["run_id"], preparation["project_id"])
        limits = conn.execute(
            "SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE",
            (preparation["project_id"],),
        ).fetchone()
        if not limits:
            raise DomainError("RES-0006", "Build resource ceiling unavailable", 503, True)
        candidates = conn.execute(
            """SELECT r.resource_id FROM inv.resources r
            JOIN inv.project_nodes p USING(tenant_id,node_id)
            WHERE p.project_id=%s AND p.enabled AND r.node_id=%s AND r.kind='cpu'
            ORDER BY r.resource_id""",
            (preparation["project_id"], self.node_id),
        ).fetchall()
        resources = lock_resources(conn, [row["resource_id"] for row in candidates])
        selected = next(
            (
                resource_id
                for resource_id in sorted(resources)
                if resources[resource_id]["offered"] - int(active_total(conn, resource_id)) >= 1
            ),
            None,
        )
        if selected is None:
            raise DomainError("RES-0001", "Measured builder capacity is unavailable", 409, True)
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        provider = candidate.provider
        if provider.observed_at.tzinfo is None:
            raise DomainError("RES-0003", "Build provider observation is stale", 409, True)
        age = (now - provider.observed_at).total_seconds()
        if not 0 <= age <= 15:
            raise DomainError("RES-0003", "Build provider observation is stale", 409, True)
        policy_expires = datetime.fromisoformat(decision["expiresAt"].replace("Z", "+00:00"))
        remaining = int((policy_expires - now).total_seconds()) - 1
        if remaining < 1:
            raise DomainError("AUTH-0031", "Build approval has no lease budget", 403)
        ttl_seconds = min(request["timeoutSeconds"], remaining)
        lease = LeaseStore(self.db)._reserve_prepared_locked(
            conn,
            principal.tenant_id,
            preparation["project_id"],
            preparation["run_id"],
            [Allocation(selected, 1)],
            ttl_seconds,
            run=run,
            limits=limits,
            resources={selected: resources[selected]},
        )[0]
        plan = {
            "apiVersion": "inv.saintvision.ai/v1alpha1",
            "kind": "BuildPlan",
            "tenantId": principal.tenant_id,
            "projectId": preparation["project_id"],
            "workspaceId": request["workspaceId"],
            "traceId": uuid4().hex,
            "requestDigest": action_digest(request),
            "actionDigest": decision["actionDigest"],
            "policyDecisionId": decision["decisionId"],
            "policyVersion": "s08-build-pdp-v1",
            "policyExpiresAt": decision["expiresAt"],
            "buildSessionId": str(uuid4()),
            "builderInstanceId": provider.builder_instance_id,
            "builderProfileId": provider.builder_profile_id,
            "builderObservationDigest": provider.observation_digest,
            "recoveryEpoch": provider.recovery_epoch,
            "rootless": True,
            "privileged": False,
            "hostAccess": False,
            "networkMode": "none",
            "networkPolicyId": "none",
            "egressAllowlistDigest": "0" * 64,
            "devices": [],
            "binds": [],
            "budget": {
                "cpuMillis": 1,
                "memoryBytes": 1,
                "storageBytes": 1,
            },
            "lease": {
                "leaseId": lease["leaseId"],
                "resourceId": lease["resourceId"],
                "fencingToken": lease["fencingToken"],
                "expiresAt": lease["expiresAt"],
            },
            "cacheNamespaceDigest": digest(
                {
                    "tenantId": principal.tenant_id,
                    "projectId": preparation["project_id"],
                    "cachePolicyId": request["cachePolicyId"],
                }
            ),
            "secretRefsDigest": digest(request["secretRefIds"]),
            "resolvedBaseImageDigests": ["sha256:" + digest(request)],
        }
        validate_contract("BuildPlan", plan)
        return plan, new_id("evd")


def configured_build_plan_authority(database, worker_config, *, environment=None):
    """Construct the API-side authority from the strict shared worker document."""

    from .worker import validated_worker_configuration

    # ``create_configured_app`` deliberately passes the bytes returned by
    # ``trusted_file``.  Keep that trust boundary intact: the worker validator
    # owns duplicate-key rejection and the exact JSON shape.  Converting here
    # with ``dict(...)`` rejects bytes before the canonical parser can inspect
    # them and made every product-enabled API startup fail closed.
    config = validated_worker_configuration(worker_config)
    build = config.get("buildExecution")
    if build is None:
        raise ValueError("Build execution configuration unavailable")
    return ConfiguredBuildPlanAuthority(database, build, environment=environment)


class BuildPreparationService:
    """Coordinate source capture, approval quorum, and trusted admission creation."""

    def __init__(
        self,
        database,
        capsule_store,
        *,
        plan_factory: Callable | None = None,
        secret_resolver: Callable | None = None,
    ):
        self.db = database
        self.capsule_store = capsule_store
        self.plan_factory = plan_factory
        self.secret_resolver = secret_resolver

    def _reserve(self, principal, project_id, operation, key, payload, limits):
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise DomainError("VAL-0003", "Idempotency key is required", 422)
        request_hash = digest({"subject": principal.subject_id, "epoch": self.db.recovery_epoch,
                               "payload": payload})
        with self.db.transaction(principal.tenant_id) as conn:
            ApprovalStore(BoundDatabase(self.db, principal.tenant_id, conn))._grant(
                conn, project_id, principal.subject_id, "can_request"
            )
            conn.execute(
                """INSERT INTO inv.idempotency(tenant_id,project_id,operation,key,request_hash)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (principal.tenant_id, project_id, operation, key, request_hash),
            )
            ledger = conn.execute(
                """SELECT request_hash,response FROM inv.idempotency
                WHERE project_id=%s AND operation=%s AND key=%s FOR UPDATE""",
                (project_id, operation, key),
            ).fetchone()
            if not ledger or ledger["request_hash"] != request_hash:
                raise DomainError("IDEM-0001", "Idempotency key was already used", 409)
            if ledger["response"] is not None:
                return deepcopy(ledger["response"])
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            window = now.replace(second=0, microsecond=0)
            conn.execute(
                "DELETE FROM inv.build_preparation_rate_windows "
                "WHERE window_started_at < clock_timestamp() - interval '35 days'"
            )
            for scope, rate_operation, maximum in limits:
                subject = principal.subject_id if scope == "subject" else "*"
                count = conn.execute(
                    """INSERT INTO inv.build_preparation_rate_windows(
                    tenant_id,project_id,scope,subject_id,operation,window_started_at,count)
                    VALUES(%s,%s,%s,%s,%s,%s,1)
                    ON CONFLICT(tenant_id,project_id,scope,subject_id,operation,window_started_at)
                    DO UPDATE SET count=inv.build_preparation_rate_windows.count+1,
                                  updated_at=clock_timestamp()
                    RETURNING count""",
                    (principal.tenant_id, project_id, scope, subject, rate_operation, window),
                ).fetchone()["count"]
                if count > maximum:
                    raise DomainError("RES-0007", "Build request rate budget exceeded", 429, True)
            return None

    def _save_replay(self, conn, principal, project_id, operation, key, response):
        updated = conn.execute(
            """UPDATE inv.idempotency SET response=%s
            WHERE project_id=%s AND operation=%s AND key=%s AND response IS NULL""",
            (Jsonb(response), project_id, operation, key),
        ).rowcount
        if updated != 1:
            row = conn.execute(
                "SELECT response FROM inv.idempotency WHERE project_id=%s AND operation=%s AND key=%s",
                (project_id, operation, key),
            ).fetchone()
            if not row or row["response"] != response:
                raise DomainError("IDEM-0001", "Idempotency response differs", 409)

    def prepare(self, principal: Principal, project_id: str, run_id: str, data: Mapping, *, key: str):
        data = dict(data)
        validate_build_input("BuildPreparationInput", data)
        replay = self._reserve(
            principal, project_id, "build.prepare", key,
            {"projectId": project_id, "runId": run_id, **data}, PREPARE_LIMITS,
        )
        if replay is not None:
            validate_contract("BuildPreparationView", replay)
            return replay

        # Short read transaction.  The immutable editor bytes are copied before
        # ObjectStore I/O; no DB lock is held during that I/O.
        with self.db.transaction(principal.tenant_id) as conn:
            approvals = ApprovalStore(BoundDatabase(self.db, principal.tenant_id, conn))
            approvals._grant(conn, project_id, principal.subject_id, "can_request")
            run = conn.execute(
                "SELECT * FROM inv.runs WHERE project_id=%s AND run_id=%s",
                (project_id, run_id),
            ).fetchone()
            checkout = conn.execute(
                """SELECT c.*,e.revision,e.content_hash,e.snapshot,
                r.state AS source_state,r.attempt AS current_source_attempt
                FROM inv.workspace_checkouts c JOIN LATERAL (
                  SELECT revision,content_hash,snapshot FROM inv.workspace_edits
                  WHERE checkout_id=c.checkout_id ORDER BY revision DESC LIMIT 1
                ) e ON true JOIN inv.runs r
                  ON r.project_id=c.project_id AND r.run_id=c.run_id
                WHERE c.project_id=%s AND c.checkout_id=%s""",
                (project_id, UUID(data["checkoutId"])),
            ).fetchone()
            profile = conn.execute(
                """SELECT * FROM inv.build_policy_profiles
                WHERE profile_id=%s AND %s=ANY(project_ids)
                ORDER BY version DESC LIMIT 1""",
                (data["buildPolicyProfileId"], project_id),
            ).fetchone()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if not run or run["state"] != "planned" or run["version"] != data["expectedRunVersion"]:
            raise DomainError("GRAPH-0003", "Build preparation requires the current planned Run")
        if not checkout or not profile:
            raise DomainError("RES-0004", "Build preparation authority was not found", 404)
        if (
            checkout["source_state"] != "recovering"
            or checkout["current_source_attempt"] != checkout["source_attempt"]
            or str(checkout["recovery_epoch"]) != self.db.recovery_epoch
        ):
            raise DomainError("VERIFY-0002", "Build source recovery authority differs", 422)
        raw = bytes(checkout["snapshot"])
        commit_sha, tree_sha = _git_source_identity(
            raw, checkout["workspace_id"], profile["context_path"], profile["dockerfile_path"]
        )
        snapshot_sha = hashlib.sha256(raw).hexdigest()
        if snapshot_sha != checkout["content_hash"]:
            raise DomainError("VERIFY-0002", "Workspace snapshot digest differs", 422)
        capsule_sha = snapshot_sha
        # S3 owns a tenant/project namespace.  The rollout-compatible local
        # provider has a flat locator grammar, so its opaque name is derived from
        # the scope as well as the content digest.  A caller controls neither.
        locator_factory = getattr(self.capsule_store, "locator", None)
        if locator_factory is not None:
            locator = locator_factory(
                principal.tenant_id,
                project_id,
                "objects",
                str(uuid5(NAMESPACE_URL, f"{principal.tenant_id}/{project_id}/{capsule_sha}")),
            )
        else:
            scoped = hashlib.sha256(
                f"{principal.tenant_id}\0{project_id}\0{capsule_sha}".encode("utf-8")
            ).hexdigest()
            locator = "obj-" + scoped[:32]
        self.capsule_store.put(locator, raw, capsule_sha)
        if self.capsule_store.get(locator, capsule_sha, len(raw)) != raw:
            raise DomainError("VERIFY-0010", "Stored build capsule differs", 422)

        secret_aliases = list(profile["secret_aliases"])
        if secret_aliases:
            if self.secret_resolver is None:
                raise DomainError(
                    "RES-0006", "Build secret authority unavailable", 503, True
                )
            resolved = self.secret_resolver(
                principal, project_id, run_id, tuple(secret_aliases)
            )
            if tuple(resolved) != tuple(secret_aliases):
                raise DomainError("VERIFY-0002", "Build secret authority differs", 422)

        request = {
            "apiVersion": "inv.saintvision.ai/v1alpha1", "kind": "BuildRequest",
            "tenantId": principal.tenant_id, "projectId": project_id,
            "workspaceId": checkout["workspace_id"],
            "sourceCommitSha": commit_sha, "sourceTreeSha": tree_sha,
            "contextPath": profile["context_path"],
            "dockerfilePath": profile["dockerfile_path"],
            "targetPlatform": profile["target_platform"],
            "targetStage": profile["target_stage"],
            "networkPolicyId": profile["network_policy_id"],
            "cachePolicyId": profile["cache_policy_id"],
            "secretRefIds": secret_aliases,
            "timeoutSeconds": profile["timeout_seconds"],
        }
        validate_contract("BuildRequest", request)
        action_hash = action_digest(canonical_build_action(request))
        expires = now + timedelta(seconds=600)
        policy = {
            "decisionId": str(uuid4()), "tenantId": principal.tenant_id,
            "projectId": project_id, "subjectId": principal.subject_id,
            "effect": "require_approval", "riskLevel": "L2", "actionDigest": action_hash,
            "expiresAt": expires.isoformat(), "requiredApprovals": 2, "approvedBy": [],
        }
        validate_contract("PolicyDecision", policy)
        request_sha = digest(request)
        decision_sha = digest(policy)
        identity_sha = digest(_identity_decision(policy))
        build_id = new_id("bld")

        with self.db.transaction(principal.tenant_id) as conn:
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            approval = ApprovalStore(bound).request(
                principal, run_id, request, policy, policy_version="s08-build-pdp-v1",
                expected_version=data["expectedRunVersion"], key=f"build:{key}",
            )
            current = conn.execute(
                """SELECT revision,content_hash FROM inv.workspace_edits
                WHERE checkout_id=%s ORDER BY revision DESC LIMIT 1""",
                (UUID(data["checkoutId"]),),
            ).fetchone()
            locked_profile = conn.execute(
                """SELECT * FROM inv.build_policy_profiles
                WHERE profile_id=%s AND version=%s""",
                (profile["profile_id"], profile["version"]),
            ).fetchone()
            if (not current or current["revision"] != checkout["revision"]
                    or current["content_hash"] != snapshot_sha or not locked_profile
                    or project_id not in locked_profile["project_ids"]):
                raise DomainError("VERIFY-0002", "Build source or policy profile drifted", 422)
            conn.execute(
                """INSERT INTO inv.build_preparations(
                tenant_id,project_id,run_id,build_id,source_run_id,checkout_id,source_revision,
                source_attempt,source_recovery_epoch,
                source_snapshot_sha256,source_capsule_sha256,source_capsule_locator,
                source_capsule_retained_until,approval_id,
                requester_id,profile_id,profile_version,expected_run_version,bound_run_version,
                request_sha256,decision_sha256,decision_identity_sha256,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       clock_timestamp()+interval '36 days',
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (principal.tenant_id, project_id, run_id, build_id, checkout["run_id"],
                 checkout["checkout_id"], checkout["revision"], checkout["source_attempt"],
                 checkout["recovery_epoch"], snapshot_sha, capsule_sha,
                 locator, approval["approvalId"],
                 principal.subject_id, profile["profile_id"],
                 profile["version"], data["expectedRunVersion"], approval["runVersion"],
                 request_sha, decision_sha, identity_sha, expires),
            )
            event(conn, principal.tenant_id, run_id, "inv.build.preparation_requested",
                  {"buildId": build_id, "approvalId": approval["approvalId"],
                   "requestDigest": request_sha, "profileVersion": profile["version"]})
            event(conn, principal.tenant_id, run_id, "inv.build.approval_bound",
                  {"buildId": build_id, "approvalId": approval["approvalId"],
                   "decisionIdentityDigest": identity_sha})
            response = {"buildId": build_id, "runId": run_id,
                        "sourceRunId": checkout["run_id"], "approvalId": approval["approvalId"],
                        "requestDigest": request_sha, "decisionIdentityDigest": identity_sha,
                        "status": "awaiting_approval", "expiresAt": expires.isoformat()}
            validate_contract("BuildPreparationView", response)
            self._save_replay(conn, principal, project_id, "build.prepare", key, response)
            return response

    def enqueue(self, principal: Principal, project_id: str, run_id: str, build_id: str,
                data: Mapping, *, key: str):
        data = dict(data)
        validate_build_input("BuildEnqueueInput", data)
        if os.environ.get(PRODUCT_ENABLE_SETTING) != PRODUCT_ENABLE_VALUE:
            raise DomainError("RES-0006", "Product BuildKit dispatch is disabled", 503, True)
        replay = self._reserve(
            principal, project_id, "build.enqueue", key,
            {"projectId": project_id, "runId": run_id, "buildId": build_id, **data},
            ENQUEUE_LIMITS,
        )
        if replay is not None:
            return replay
        if self.plan_factory is None:
            raise DomainError("RES-0006", "Measured build provider authority unavailable", 503, True)

        with self.db.transaction(principal.tenant_id) as conn:
            prep = conn.execute(
                """SELECT * FROM inv.build_preparations
                WHERE project_id=%s AND run_id=%s AND build_id=%s FOR SHARE""",
                (project_id, run_id, build_id),
            ).fetchone()
        if not prep or prep["approval_id"] != data["approvalId"]:
            raise DomainError("RES-0004", "Build preparation was not found", 404)
        if prep["requester_id"] != principal.subject_id:
            raise DomainError("AUTH-0011", "Build preparation actor differs", 403)
        if prep["bound_run_version"] != data["expectedRunVersion"]:
            raise DomainError("GRAPH-0003", "Build approval Run version differs", 409)
        request = self._request_for(prep)
        measure_candidate = getattr(self.plan_factory, "measure_candidate", None)
        compile_plan = getattr(self.plan_factory, "compile_plan", None)
        if measure_candidate is None or compile_plan is None:
            raise DomainError("RES-0006", "Measured build provider authority unavailable", 503, True)
        # Provider health/measurement may perform I/O.  It is deliberately read
        # without a business transaction; compile_plan must rebind this
        # candidate to the locked source/profile and live lease below.
        candidate = measure_candidate(principal, deepcopy(dict(prep)), deepcopy(request))

        def authority_factory(conn, run, approved_decision, request):
            locked = conn.execute(
                """SELECT p.*,e.revision,e.content_hash,r.state AS source_state,
                r.attempt AS current_source_attempt,c.source_attempt AS current_checkout_attempt,
                c.recovery_epoch AS current_source_recovery_epoch
                FROM inv.build_preparations p JOIN inv.workspace_checkouts c
                  ON c.checkout_id=p.checkout_id
                JOIN LATERAL (SELECT revision,content_hash FROM inv.workspace_edits
                  WHERE checkout_id=c.checkout_id ORDER BY revision DESC LIMIT 1) e ON true
                JOIN inv.runs r ON r.project_id=p.project_id AND r.run_id=p.source_run_id
                WHERE p.project_id=%s AND p.run_id=%s AND p.build_id=%s FOR UPDATE OF p""",
                (project_id, run_id, build_id),
            ).fetchone()
            if (not locked or locked["queued_at"] is not None
                    or locked["revision"] != locked["source_revision"]
                    or locked["content_hash"] != locked["source_snapshot_sha256"]
                    or locked["source_state"] != "recovering"
                    or locked["current_source_attempt"] != locked["source_attempt"]
                    or locked["current_checkout_attempt"] != locked["source_attempt"]
                    or locked["current_source_recovery_epoch"] != locked["source_recovery_epoch"]
                    or str(locked["source_recovery_epoch"]) != self.db.recovery_epoch
                    or digest(request) != locked["request_sha256"]
                    or digest(_identity_decision(approved_decision)) != locked["decision_identity_sha256"]):
                raise DomainError("VERIFY-0002", "Build preparation authority drifted", 422)
            plan, evidence_id = compile_plan(
                conn, principal, locked, request, approved_decision, candidate
            )
            conn.execute(
                "UPDATE inv.build_preparations SET queued_at=clock_timestamp() WHERE build_id=%s",
                (build_id,),
            )
            return plan, evidence_id

        try:
            result = ApprovalStore(self.db).dispatch(
                principal, project_id, data["approvalId"], request, key=f"build:{key}",
                build_authority_factory=authority_factory,
            )
        except DomainError as error:
            if error.code in TERMINAL_ENQUEUE_CODES:
                self._terminalize(
                    principal, project_id, run_id, data["approvalId"], error.code
                )
            raise
        with self.db.transaction(principal.tenant_id) as conn:
            self._save_replay(conn, principal, project_id, "build.enqueue", key, result)
        return result

    def _request_for(self, prep):
        with self.db.transaction(str(prep["tenant_id"])) as conn:
            row = conn.execute(
                "SELECT workload FROM inv.approval_review_snapshots WHERE approval_id=%s",
                (prep["approval_id"],),
            ).fetchone()
            if not row:
                raise DomainError("VERIFY-0002", "Build approval snapshot unavailable", 422)
            return deepcopy(row["workload"])

    def _terminalize(self, principal, project_id, run_id, approval_id, code):
        with self.db.transaction(principal.tenant_id) as conn:
            row = conn.execute(
                "SELECT * FROM inv.approval_requests WHERE approval_id=%s FOR UPDATE",
                (approval_id,),
            ).fetchone()
            if row and row["status"] in {"pending", "approved"}:
                phase = "rejected" if row["status"] == "pending" else "expired"
                row = conn.execute(
                    "UPDATE inv.approval_requests SET status=%s "
                    "WHERE approval_id=%s RETURNING *",
                    (phase, approval_id),
                ).fetchone()
                run = conn.execute("SELECT * FROM inv.runs WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
                if run and run["state"] == "awaiting_approval":
                    from .runs import RunStore
                    RunStore(BoundDatabase(self.db, principal.tenant_id, conn))._transition(
                        conn, principal.tenant_id, run, "failed", run["version"]
                    )
                system = Principal(principal.tenant_id, "system:build-preparation-drift")
                ApprovalStore(BoundDatabase(self.db, principal.tenant_id, conn))._audit(
                    conn, system, row, phase
                )
                event(conn, principal.tenant_id, run_id, "inv.build.preparation_terminalized",
                      {"approvalId": approval_id, "approvalStatus": phase, "errorCode": code,
                       "actorId": "system:build-preparation-drift"})
