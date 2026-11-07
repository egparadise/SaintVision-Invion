"""Selected business Workspace metadata and atomic first-Run creation.

No provisioning, placement, grant, vote or execution is performed here. SQL helper
context is a trusted service boundary, never a claim about an end user's SQL access.
"""
from datetime import datetime, timezone
import re

import psycopg
from psycopg.types.json import Jsonb
from .approvals import digest
from .business_auth import permission
from .containment import require_execution
from .contracts import validate_contract
from .control import Control
from .errors import DomainError
from .ids import new_id
from .runs import event
from .sandbox import compile_launch
from .workspace_files import canonical

MAX_SAFE = 9007199254740991
VERSION = r"[1-9][0-9]{0,15}"
WORKSPACE_ETAG = re.compile(r'"workspace-v(' + VERSION + r')"\Z')
INTENT_ETAG = re.compile(r'"workspace-v(' + VERSION + r')-workload-v(' + VERSION + r')-sha256-([a-f0-9]{64})"\Z')


def header_versions(value, *, intent=False):
    match = (INTENT_ETAG if intent else WORKSPACE_ETAG).fullmatch(value or "")
    if not match or any(int(part) > MAX_SAFE for part in match.groups()[:2 if intent else 1]):
        raise DomainError("VAL-0003", "Exact strong If-Match version is required", 422)
    return match.groups()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class WorkspaceIntents:
    def __init__(self, workspace):
        self.workspace, self.db, self.runtime = workspace, workspace.db, workspace.runtime
        self.control = Control(self.db)
        self.ledger = self.control.approvals

    def _authority(self, conn, principal, project):
        if not re.fullmatch(r"oidc:[a-f0-9]{64}", principal.subject_id):
            raise DomainError("AUTH-0030", "Current business identity is required", 403)
        self.control.grant(conn, principal, project, "can_request")
        permission(conn, project, principal.subject_id, "can_request", linked=True)
        # Only called after authenticated route supplied the verified principal.
        conn.execute("SELECT set_config('inv.first_workspace_subject',%s,true)", (principal.subject_id,))
        conn.execute("SELECT set_config('inv.first_workspace_epoch',%s,true)", (self.db.recovery_epoch,))

    def _selected(self, conn, project, workspace):
        validate_contract("WorkspaceId", workspace)
        row = conn.execute(
            "SELECT workspace_id,project_id,status,version,node_id FROM public.workspaces WHERE project_id=%s AND workspace_id=%s FOR SHARE",
            (project, workspace),
        ).fetchone()
        if not row:
            raise DomainError("RES-0004", "Selected Workspace is unavailable", 404)
        if row["status"] != "ready":
            raise DomainError("AUTH-0045", "Selected Workspace is not ready; provisioning prerequisite remains", 403)
        if row["node_id"] is not None and row["node_id"] != self.runtime.node.node_id:
            raise DomainError("AUTH-0045", "Selected Workspace has a different Node binding", 403)
        self.workspace._node_membership(conn, project, lock=True)
        if not 1 <= row["version"] <= MAX_SAFE:
            raise DomainError("VAL-0002", "Workspace version is invalid", 422)
        return row

    def _profile(self):
        p = self.runtime.profile
        if p.max_memory_bytes < 8388608 or len(p.images) > 64 or len(p.executables) > 64:
            raise DomainError("AUTH-0044", "Configured CPU profile prerequisite is unavailable", 503)
        result = dict(nodeId=self.runtime.node.node_id, profileVersion=p.version,
                      images=sorted(p.images), executables=sorted(p.executables),
                      maxCpuMillis=min(p.max_cpu_millis, 500), minMemoryBytes=8388608,
                      maxMemoryBytes=min(p.max_memory_bytes, 67108864),
                      maxTimeoutSeconds=min(p.max_timeout_seconds, 30), terminalAllowed=False)
        validate_contract("WorkspaceFirstProfile", result)
        return result

    def _validate(self, spec, principal, project, workspace, workload_id):
        validate_contract("WorkloadSpec", spec)
        r = spec["resources"]
        if any(spec[k] != v for k, v in dict(tenantId=principal.tenant_id, projectId=project,
                workspaceId=workspace, workloadId=workload_id).items()) or any(
                k in spec for k in ("workspaceStart", "workspaceResume", "terminal", "modelInput")) or (
                spec.get("targetNodeId", self.runtime.node.node_id) != self.runtime.node.node_id
                or r["gpuCount"] != 0 or r["minVramBytes"] != 0 or r["cpuMillis"] > 500
                or not 8388608 <= r["memoryBytes"] <= 67108864 or spec["timeoutSeconds"] > 30
                or len(spec["command"]) > 64):
            raise DomainError("AUTH-0045", "Selected canonical CPU intent scope or bounds differ", 403)
        self._profile()
        compile_launch(spec, self.runtime.profile)

    def _item(self, row, selected, principal, project, at):
        spec = row["spec"]
        self._validate(spec, principal, project, selected["workspace_id"], row["workload_id"])
        if digest(spec) != row["spec_sha256"] or not 1 <= row["version"] <= MAX_SAFE:
            raise DomainError("VERIFY-0023", "Stored intent canonical digest or version differs", 409)
        etag = f'"workspace-v{selected["version"]}-workload-v{row["version"]}-sha256-{row["spec_sha256"]}"'
        result = dict(workspaceId=selected["workspace_id"], workspaceVersion=selected["version"],
                      workloadVersion=row["version"], workloadSha256=row["spec_sha256"],
                      intentEtag=etag, workload=spec, observedAt=at)
        validate_contract("WorkspaceFirstIntent", result)
        return result

    def list(self, principal, project, workspace, *, after=None, limit=20):
        if after is not None:
            validate_contract("WorkloadId", after)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise DomainError("VAL-0003", "Intent page limit must be 1..50", 422)
        with self.db.transaction(principal.tenant_id) as conn:
            self._authority(conn, principal, project)
            selected = self._selected(conn, project, workspace)
            rows = conn.execute("""SELECT workload_id,spec,spec_sha256,version FROM public.workloads
                WHERE project_id=%s AND spec->>'workspaceId'=%s AND (%s::text IS NULL OR workload_id>%s)
                ORDER BY workload_id LIMIT %s FOR SHARE""", (project, workspace, after, after, limit + 1)).fetchall()
            at = timestamp()
            # Invalid rows fail the read; they are never filtered into a misleading empty page.
            items = [self._item(row, selected, principal, project, at) for row in rows]
            result = dict(projectId=project, workspaceId=workspace, workspaceVersion=selected["version"],
                          observedAt=at, profile=self._profile(), items=items[:limit],
                          nextCursor=rows[limit - 1]["workload_id"] if len(rows) > limit else None)
            validate_contract("WorkspaceFirstIntentPage", result)
            return result

    def create_intent(self, principal, project, workspace, data, key, if_match):
        validate_contract("WorkspaceFirstIntentCreateInput", data)
        expected = int(header_versions(if_match)[0])
        with self.db.transaction(principal.tenant_id) as conn:
            self._authority(conn, principal, project)
            payload = dict(workspaceId=workspace, ifMatch=if_match, input=data)
            prior = self.ledger._ledger(conn, principal, project, "workspace.intent.create", key, payload)
            selected = self._selected(conn, project, workspace)
            if selected["version"] != expected:
                raise DomainError("GRAPH-0003", "Workspace version changed", 409)
            require_execution(conn)
            if prior is not None:
                row = conn.execute("SELECT workload_id,spec,spec_sha256,version FROM public.workloads WHERE workload_id=%s FOR SHARE",
                                   (prior["workload"]["workloadId"],)).fetchone()
                if not row or self._item(row, selected, principal, project, prior["observedAt"]) != prior:
                    raise DomainError("GRAPH-0003", "Intent changed after creation", 409)
                return prior
            spec = dict(apiVersion="inv.saintvision.ai/v1alpha1", kind="Workload", workloadId=new_id("wld"),
                        tenantId=principal.tenant_id, projectId=project, workspaceId=workspace,
                        targetNodeId=self.runtime.node.node_id,
                        **{k: data[k] for k in ("imageDigest", "command", "resources", "timeoutSeconds")})
            self._validate(spec, principal, project, workspace, spec["workloadId"])
            try:
                conn.execute("SELECT inv.append_first_workspace_intent(%s,%s,%s,%s,%s,%s,%s)",
                             (project, workspace, Jsonb(spec), digest(spec), canonical(spec).decode(), data["objective"], expected))
            except psycopg.errors.InsufficientPrivilege as error:
                raise DomainError("AUTH-0030", "Business intent writer refused current scope", 403) from error
            row = dict(workload_id=spec["workloadId"], spec=spec, spec_sha256=digest(spec), version=1)
            result = self._item(row, selected, principal, project, timestamp())
            return self.ledger._save(conn, project, "workspace.intent.create", key, result)

    def create_run(self, principal, project, workspace, workload, data, key, if_match):
        validate_contract("EmptyRequest", data)
        validate_contract("WorkloadId", workload)
        header_versions(if_match, intent=True)
        with self.db.transaction(principal.tenant_id) as conn:
            self._authority(conn, principal, project)
            payload = dict(workspaceId=workspace, workloadId=workload, ifMatch=if_match)
            prior = self.ledger._ledger(conn, principal, project, "workspace.intent.run.create", key, payload)
            selected = self._selected(conn, project, workspace)
            row = conn.execute("SELECT workload_id,spec,spec_sha256,version FROM public.workloads WHERE project_id=%s AND workload_id=%s FOR SHARE",
                               (project, workload)).fetchone()
            if not row:
                raise DomainError("RES-0004", "Selected intent is unavailable", 404)
            item = self._item(row, selected, principal, project, timestamp())
            if item["intentEtag"] != if_match:
                raise DomainError("GRAPH-0003", "Selected intent version or digest changed", 409)
            require_execution(conn)
            if prior is not None:
                validate_contract("WorkspaceFirstRunCreateResult", prior)
                return prior
            run_id = new_id("run")
            try:
                conn.execute("SELECT inv.append_first_workspace_run(%s,%s,%s,%s,%s,%s,%s,%s)",
                             (project, workspace, workload, run_id, selected["version"], row["version"], row["spec_sha256"], canonical(row["spec"]).decode()))
            except psycopg.errors.InsufficientPrivilege as error:
                raise DomainError("AUTH-0030", "Business Run writer refused current scope", 403) from error
            run = dict(runId=run_id, tenantId=principal.tenant_id, projectId=project, state="draft", version=1, attempt=0)
            result = dict(run=run, intent=item, requesterId=principal.subject_id, observedAt=item["observedAt"])
            validate_contract("WorkspaceFirstRunCreateResult", result)
            event(conn, principal.tenant_id, run_id, "inv.run.created", run)
            return self.ledger._save(conn, project, "workspace.intent.run.create", key, result)
