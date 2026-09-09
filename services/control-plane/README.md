# INV reliability foundation

This is an internal Python library and a non-ready FastAPI shell. It has no public mutation APIs or Node executor. OIDC/project authorization, mTLS, one-use approval consumption, real Node stopping, object retention and operational restore are integration gates. Do not expose the database or trusted policy/stop-receipt inputs to end users.

From the repository root, install `requirements-test.txt`, then run `python -m pytest`. PostgreSQL tests require `INV_TEST_ADMIN_DSN` pointing to a disposable PostgreSQL 16+ server with database/role creation rights. They create a random database and role, run Alembic, and remove only those resources. CI requires DB tests rather than silently skipping them. `python -m build services/control-plane --outdir dist` builds the package.

Migration: set `INV_MIGRATION_DSN` to a schema-owner SQLAlchemy `postgresql+psycopg://` URL and run `python -m alembic upgrade head`. Never commit DSNs. The migration refuses destructive downgrade. Use an independently tested restore/forward-fix plan before operational adoption.

Runtime uses a separate non-owner, non-superuser, non-BYPASSRLS role with USAGE on schema/sequences; SELECT/INSERT/UPDATE on required mutable tables; SELECT/INSERT only on Evidence/checkpoints; SELECT and UPDATE(singleton) only on control_epoch. The singleton CHECK prevents changes to that sentinel, while the epoch itself is read-only. Operators provision the epoch outside DB backup and initialize `inv.control_epoch`. Pass the expected epoch to `Database(dsn, recovery_epoch=...)`. Nodes without matching enrollment epoch or measured skew within 5 seconds are excluded.

All capacity writers must follow Run -> sorted Node IDs -> sorted Resource IDs locks and READ COMMITTED post-lock sums. Lease expiry and terminal Run states do not release capacity. Only a trusted authenticated Node adapter can provide the physical stop receipt to release it. Restore requires a new epoch, durable Node re-enrollment and verified cleanup before scheduling; those Node-side adapters are not implemented here.

JSON Schema v1alpha1 is authoritative. Run `python tools/generate_contracts.py` and commit all generated types. Generated types alone do not validate untrusted inputs. See `docs/vault/30_Development/Codex 핵심 기반 계약과 검토 회신.md` for CR decisions, evidence gates and deferred integrations.
