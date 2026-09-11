"""Let the application project membership without letting it grant permission.

Revision ID: 0025_project_grant_projection
Revises: 0024_initial_recovery_epoch
Create Date: 2026-09-10

``public.project_members`` is authoritative for who may act in a project.
``inv.approval_requests.requester_id`` has a foreign key to
``inv.project_grants``, so an approval cannot exist unless a matching grant row
does — which makes projecting membership across the seam load-bearing rather
than a convenience.

But the execution core deliberately withholds write access to
``inv.project_grants`` from the runtime role. It gets ``UPDATE(lock_sentinel)``
and nothing else: enough to take ``SELECT ... FOR SHARE`` and prove membership
did not change under it, never enough to change membership. That is a good
property — a compromised application cannot grant itself permission — and this
revision does not weaken it. The first attempt at the projection failed with
``permission denied for table project_grants``, and the permission was right.

So the projection becomes a function the application may call but whose effect
it cannot choose. ``inv.project_grants_from_members`` reads
``public.project_members`` and makes the core's row agree with it. The caller
passes a tenant, a project and a user; it cannot pass the permissions. If
``public`` says a user is a viewer, the projection writes a viewer's grant, and
an application that has been taken over can do nothing with this except make
the core agree with a membership table it also cannot write.

Two details that decide whether that holds:

* ``search_path`` is pinned. A SECURITY DEFINER function that resolves names
  through the caller's ``search_path`` can be made to execute the caller's
  objects with the owner's rights, which is the usual way this feature becomes
  a privilege escalation.
* The role mapping lives here, in SQL, rather than being passed in. Passing the
  booleans would put the decision back in the caller's hands and make the
  function a way to write arbitrary grants after all.
"""

from __future__ import annotations

from alembic import op

revision = "0025_project_grant_projection"
down_revision = "0024_initial_recovery_epoch"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "inv.project_grants_from_members"

#: Mirrors ``saintvision.services.handoff.CAN_REQUEST`` and ``CAN_APPROVE``.
#: Duplicated deliberately: the projection must be decidable inside the database
#: from ``public.project_members`` alone, because the point is that the caller
#: does not get to say what the permissions are.
CAN_REQUEST = "('owner','maintainer','operator')"
CAN_APPROVE = "('owner','approver')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(
            p_tenant_id uuid, p_project_id char(30), p_user_id char(30)
        ) RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        -- Pinned: resolving through the caller's search_path is how a
        -- SECURITY DEFINER function becomes a privilege escalation.
        SET search_path = pg_catalog, public, inv
        AS $fn$
        DECLARE
            member_role text;
        BEGIN
            SELECT role_code INTO member_role
            FROM public.project_members
            WHERE tenant_id = p_tenant_id
              AND project_id = p_project_id
              AND user_id = p_user_id;

            IF member_role IS NULL THEN
                -- Not a member. Disable rather than delete: the core's approval
                -- rows point at this table, and removing a grant would either
                -- fail on the foreign key or orphan the history of a decision
                -- that really was authorised when it was made.
                UPDATE inv.project_grants
                   SET enabled = false, can_request = false, can_approve = false
                 WHERE tenant_id = p_tenant_id
                   AND project_id = p_project_id
                   AND subject_id = p_user_id;
                RETURN;
            END IF;

            INSERT INTO inv.project_grants
                (tenant_id, project_id, subject_id, can_request, can_approve, enabled)
            VALUES (
                p_tenant_id, p_project_id, p_user_id,
                member_role IN {CAN_REQUEST},
                member_role IN {CAN_APPROVE},
                true
            )
            ON CONFLICT (tenant_id, project_id, subject_id) DO UPDATE SET
                can_request = excluded.can_request,
                can_approve = excluded.can_approve,
                enabled = true;
        END
        $fn$;
        """
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, char(30), char(30)) FROM PUBLIC"
    )
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, char(30), char(30)) TO {APP_ROLE}"
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, char(30), char(30))")
