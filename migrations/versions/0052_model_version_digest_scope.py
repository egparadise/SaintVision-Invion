"""Scope the model version digest uniqueness to the model, not the tenant.

``uq_model_versions_tenant_id_content_sha256`` has been on ``model_versions``
since ``0004_s10_lineage``, recording a real invariant: the same bytes registered
twice under two names is a mistake worth catching. Scoped to the **tenant**, it
also became an authorisation leak, which is what Codex found reviewing the
registration route (#191 F1).

The leak is not in any message. ``POST /projects/{p}/models/{m}/versions`` is
graded ``canApprove`` **per project**, so a caller who may approve only in project
A can submit a digest and read the answer: 201 means those bytes are not in this
tenant, 409 means they are -- possibly in project B, which that caller cannot see
and has no membership of. Removing identifiers from the response body does not
help, because the existence bit is the status code. A project-scoped grade whose
refusal reports across projects is not project-scoped.

**What replaces it.** ``uq_model_versions_model_id_content_sha256``. A model
belongs to exactly one project (``models.project_id``, with the composite foreign
key to ``projects``), so a conflict on this constraint is always a conflict the
caller already named in the path: they hold the model, and the version they are
duplicating is one of its own. The original invariant survives where it is
meaningful -- two names for identical bytes **within one model** is still refused
-- and the cross-project answer disappears.

**Why this is not a data migration.** The constraint being dropped is strictly
stronger than the one being added: any pair of rows that agree on
``(model_id, content_sha256)`` also agrees on ``(tenant_id, content_sha256)``,
because a model has one tenant. So no existing row can violate the new
constraint, and nothing has to be rewritten. That is an argument, not an
observation, so ``upgrade`` checks the database before it changes it -- an
argument that turns out to be wrong should stop the migration with a sentence
rather than an opaque DDL error halfway through. Offline rendering
(``alembic upgrade --sql``) skips the read: there is no database to ask, and the
output of that mode is SQL for a person to review rather than a run.

**Order: create, then drop.** The new constraint exists before the old one is
removed, so there is no window in which the table has no uniqueness protection at
all. A crash between the two leaves both, which is the safe direction: both hold
simultaneously and a retry converges.

``CONCURRENTLY``, and therefore an autocommit block, for the reason
``0050_dataset_digest_lookup`` states: a plain unique-constraint add holds ACCESS
EXCLUSIVE on ``model_versions`` for the whole index build and blocks every
registration for the duration. Two consequences of the block, as that migration
also had to say:

* inside it this migration does not roll back as a transaction, so the
  ``IF EXISTS``/``IF NOT EXISTS`` pair is what makes a partial failure converge
  rather than wedge;
* a failed ``CREATE UNIQUE INDEX CONCURRENTLY`` leaves an INVALID index holding
  the name, which ``ADD CONSTRAINT ... USING INDEX`` would then refuse, so the
  upgrade drops that name first. That is what makes a retry safe.

Numbered 0052 on ``0051_service_credentials`` by the coordinator's decision of
2026-09-28, which moved the W5 eval-suite migration to 0053. This is its own PR
rather than part of the registration route because the route's branch carries
migration head 0048: a revision there would have nothing to depend on, or would
make a second head.
"""

from alembic import op

revision = "0052_model_version_digest_scope"
down_revision = "0051_service_credentials"
branch_labels = None
depends_on = None

OLD_CONSTRAINT = "uq_model_versions_tenant_id_content_sha256"
NEW_CONSTRAINT = "uq_model_versions_model_id_content_sha256"

#: Rows that would violate the narrower constraint. Empty by the argument above;
#: read rather than assumed, because the migration is what acts on the answer.
VIOLATIONS = f"""
SELECT model_id, content_sha256, count(*) AS rows
FROM model_versions
GROUP BY model_id, content_sha256
HAVING count(*) > 1
"""


def upgrade():
    context = op.get_context()
    # ``alembic upgrade --sql`` renders against a mock connection that cannot run
    # a query, and there is no database to check in that mode anyway: the output
    # is SQL for a person to read. The guard runs when the migration runs.
    offending = (
        [] if context.as_sql else op.get_bind().exec_driver_sql(VIOLATIONS).fetchall()
    )
    if offending:
        # Fail before touching anything. The rows are named by model and digest,
        # which the operator already has access to; no other column is echoed.
        listed = ", ".join(f"{row[0]}/{row[1]} x{row[2]}" for row in offending[:10])
        raise RuntimeError(
            f"{len(offending)} (model_id, content_sha256) group(s) already hold more "
            f"than one model version, so {NEW_CONSTRAINT} cannot be created: {listed}"
            ". Resolve the duplicates with a reviewed data fix and run this again."
        )

    with context.autocommit_block():
        # A previous failed attempt can have left an INVALID index holding this
        # name; ADD CONSTRAINT USING INDEX would refuse it.
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {NEW_CONSTRAINT}")
        op.execute(
            f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {NEW_CONSTRAINT} "
            "ON model_versions (model_id, content_sha256)"
        )

    # Promote the index to a constraint, so the catalogue says what the rule is
    # rather than leaving it as an index that happens to be unique. The name is
    # already the constraint's, so nothing is renamed.
    op.execute(
        f"ALTER TABLE model_versions "
        f"ADD CONSTRAINT {NEW_CONSTRAINT} UNIQUE USING INDEX {NEW_CONSTRAINT}"
    )
    # Only now is the wider one removed: the narrower rule is already enforced.
    op.execute(f"ALTER TABLE model_versions DROP CONSTRAINT {OLD_CONSTRAINT}")


def downgrade():
    raise RuntimeError(
        "0052_model_version_digest_scope is irreversible: once the digest "
        "uniqueness is scoped to the model, two projects of one tenant may "
        "legitimately hold the same bytes, so the tenant-wide constraint can no "
        "longer be restored -- and restoring it would reopen the cross-project "
        "existence oracle it was narrowed to close. Apply a reviewed forward fix."
    )
