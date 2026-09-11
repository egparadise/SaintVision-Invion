"""Read-only current credential scope lookup; provisioning is operator-only.

Credential permission is not an execution/approval permit. The trusted caller
must still use the current ToolGateway/approval path for external side effects.
"""

from saintvision.credentials.linux_file import CredentialBinding
from .containment import require_execution
from .runs import event


class PostgresCredentialRegistry:
    def __init__(self, database):
        self.database = database

    def lookup(self, credential_id, version_id, context, purpose, destination):
        with self.database.transaction(context.tenant_id) as conn:
            require_execution(conn)
            row = conn.execute(
                """SELECT v.file_name,v.device,v.inode,v.content_sha256
                FROM inv.credential_versions v
                JOIN inv.credential_grants g USING(tenant_id,project_id,credential_id,version_id)
                JOIN inv.project_grants p USING(tenant_id,project_id,subject_id)
                JOIN inv.runs r ON r.tenant_id=g.tenant_id AND r.project_id=g.project_id AND r.run_id=g.run_id
                WHERE v.credential_id=%s AND v.version_id=%s AND v.project_id=%s
                  AND g.subject_id=%s AND g.run_id=%s AND v.purpose=%s AND v.destination=%s
                  AND g.enabled AND g.revoked_at IS NULL AND g.expires_at>clock_timestamp()
                  AND p.enabled AND p.can_request AND g.recovery_epoch=%s
                  AND r.state NOT IN ('succeeded','failed','cancelled')""",
                (
                    credential_id,
                    version_id,
                    context.project_id,
                    context.subject_id,
                    context.run_id,
                    purpose,
                    destination,
                    self.database.recovery_epoch,
                ),
            ).fetchone()
            if row:
                event(
                    conn,
                    context.tenant_id,
                    context.run_id,
                    "inv.credential.authorized",
                    {
                        "credentialId": credential_id,
                        "versionId": version_id,
                        "subjectId": context.subject_id,
                        "purpose": purpose,
                        "destinationAlias": destination,
                    },
                )
            return CredentialBinding(**row) if row else None
