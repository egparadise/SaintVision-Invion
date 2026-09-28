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
(``alembic upgrade --sql``) skips every read: there is no database to ask, and the
output of that mode is SQL for a person to review rather than a run.

**Resuming after an interruption.** The first version of this migration claimed a
crash between the promotion and the drop was safe because both constraints would
hold. Codex found the claim false in the only way that matters: the revision is
still ``0051``, the new constraint already exists, and the re-run began with
``DROP INDEX CONCURRENTLY IF EXISTS`` on an index the new constraint now **owns**,
which PostgreSQL refuses -- ``cannot drop index ... because constraint ...
requires it``. The migration wedged at exactly the point described as safe.

So the upgrade reads the catalogue first and takes one of three paths:

* the new constraint is **absent** -- clear any standalone or INVALID index
  holding its name (a failed concurrent build leaves one, and
  ``ADD CONSTRAINT ... USING INDEX`` would refuse it), build the index
  concurrently, promote it;
* the new constraint is **present with exactly the right shape** -- unique, on
  ``model_versions``, over ``(model_id, content_sha256)`` -- leave it completely
  alone. Nothing is dropped and nothing is rebuilt;
* a constraint of that **name exists with a different shape** -- refuse. Something
  other than this migration owns the name, and guessing is worse than stopping.

Both paths then drop the old constraint ``IF EXISTS``, which is what makes the
other crash point -- after the drop, before the revision is recorded -- converge
as well.

``CONCURRENTLY``, and therefore an autocommit block, for the reason
``0050_dataset_digest_lookup`` states: a plain unique-constraint add holds ACCESS
EXCLUSIVE on ``model_versions`` for the whole index build and blocks every
registration for the duration. Inside the block this migration does not roll back
as a transaction, which is why that path is only taken when there is no constraint
to protect.

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
TABLE = "model_versions"
COLUMNS = ("model_id", "content_sha256")

#: The shape of a constraint already holding the new name, or no rows. Read before
#: anything is changed, because what the catalogue holds decides which path
#: converges -- and because a name collision is a reason to stop, not to overwrite.
CONSTRAINT_SHAPE = f"""
SELECT c.contype::text AS contype,
       (
         SELECT array_agg(a.attname::text ORDER BY k.ord)
         FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
         JOIN pg_attribute a
           ON a.attrelid = c.conrelid AND a.attnum = k.attnum
       ) AS columns
FROM pg_constraint c
WHERE c.conname = '{NEW_CONSTRAINT}'
  AND c.conrelid = '{TABLE}'::regclass
"""

#: Rows that would violate the narrower constraint. Empty by the argument above;
#: read rather than assumed, because the migration is what acts on the answer.
VIOLATIONS = f"""
SELECT model_id, content_sha256, count(*) AS rows
FROM {TABLE}
GROUP BY model_id, content_sha256
HAVING count(*) > 1
"""

_COLUMN_LIST = ", ".join(COLUMNS)


def _build_and_promote(context) -> None:
    """Create the unique index concurrently and promote it to the constraint.

    Only reached when no constraint holds the name, so the unconditional
    ``DROP INDEX`` here can only meet a standalone index -- the leftover of a
    failed concurrent build, which is exactly what has to go before
    ``ADD CONSTRAINT ... USING INDEX`` will accept the name.
    """
    with context.autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {NEW_CONSTRAINT}")
        op.execute(
            f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {NEW_CONSTRAINT} "
            f"ON {TABLE} ({_COLUMN_LIST})"
        )
    # The catalogue should say what the rule is rather than leaving it as an index
    # that happens to be unique. The name is already the constraint's, so nothing
    # is renamed.
    op.execute(
        f"ALTER TABLE {TABLE} "
        f"ADD CONSTRAINT {NEW_CONSTRAINT} UNIQUE USING INDEX {NEW_CONSTRAINT}"
    )


def _drop_old() -> None:
    """Remove the wide constraint.

    ``IF EXISTS`` so a resume after this statement but before the revision was
    recorded finishes instead of failing.
    """
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {OLD_CONSTRAINT}")


def upgrade():
    context = op.get_context()

    if context.as_sql:
        # Offline: render every statement for a reviewer, ask nothing.
        _build_and_promote(context)
        _drop_old()
        return

    bind = op.get_bind()
    existing = bind.exec_driver_sql(CONSTRAINT_SHAPE).fetchall()

    if existing:
        contype = existing[0][0]
        columns = list(existing[0][1] or [])
        if contype != "u" or columns != list(COLUMNS):
            raise RuntimeError(
                f"{NEW_CONSTRAINT} already exists on {TABLE} with a different "
                f"definition (contype={contype!r}, columns={columns!r}; expected "
                f"'u' over {list(COLUMNS)!r}). Something other than this migration "
                "owns that name; resolve it with a reviewed fix before running again."
            )
        # A previous run was interrupted between the promotion and the drop. The
        # constraint is already exactly right, so it is left untouched -- dropping
        # the index it owns is what wedged the first version of this migration.
    else:
        offending = bind.exec_driver_sql(VIOLATIONS).fetchall()
        if offending:
            # Fail before touching anything. The rows are named by model and
            # digest, which the operator already has access to; no other column is
            # echoed.
            listed = ", ".join(f"{row[0]}/{row[1]} x{row[2]}" for row in offending[:10])
            raise RuntimeError(
                f"{len(offending)} (model_id, content_sha256) group(s) already hold "
                f"more than one model version, so {NEW_CONSTRAINT} cannot be "
                f"created: {listed}. Resolve the duplicates with a reviewed data fix "
                "and run this again."
            )
        _build_and_promote(context)

    # Only now is the wider one removed: the narrower rule is already enforced.
    _drop_old()


def downgrade():
    raise RuntimeError(
        "0052_model_version_digest_scope is irreversible: once the digest "
        "uniqueness is scoped to the model, two projects of one tenant may "
        "legitimately hold the same bytes, so the tenant-wide constraint can no "
        "longer be restored -- and restoring it would reopen the cross-project "
        "existence oracle it was narrowed to close. Apply a reviewed forward fix."
    )
