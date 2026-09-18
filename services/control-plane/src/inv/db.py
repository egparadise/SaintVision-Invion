"""Short, tenant-scoped transactions. DSN is never included in errors or logs."""

from contextlib import contextmanager
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from .errors import DomainError


class BoundDatabase:
    """Private adapter: nested service operations share one outer transaction."""

    def __init__(self, db, tenant, conn):
        self.recovery_epoch, self.tenant, self.conn = db.recovery_epoch, tenant, conn
        self.shard_recovery_admission = getattr(db, "shard_recovery_admission", False)
        self.business_handoff = getattr(db, "business_handoff", False)
        self.registry_binding_policy = getattr(db, "registry_binding_policy", None)

    @contextmanager
    def transaction(self, tenant):
        if tenant != self.tenant:
            raise DomainError("AUTH-0011", "Nested transaction scope differs", 403)
        yield self.conn


class Database:
    def __init__(self, dsn: str, *, recovery_epoch: str, registry_binding_policy=None):
        if registry_binding_policy is not None:
            from .model_registry_binding import RegistryBindingPolicy
            if not isinstance(registry_binding_policy, RegistryBindingPolicy):
                raise ValueError("Operator registry binding policy required")
        self.registry_binding_policy = registry_binding_policy
        self._dsn = dsn
        self.recovery_epoch = str(UUID(recovery_epoch))

    @contextmanager
    def transaction(self, tenant_id: str, *, containment_write=False):
        tenant = str(UUID(tenant_id))
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            # READ COMMITTED is essential: each post-lock statement sees fresh sums.
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            role = conn.execute("""SELECT r.rolsuper, r.rolbypassrls,
                r.oid = n.nspowner AS owns_schema
                FROM pg_roles r JOIN pg_namespace n ON n.nspname='inv'
                WHERE r.rolname = current_user""").fetchone()
            if not role or any(role.values()):
                raise DomainError(
                    "AUTH-0020",
                    "Runtime must use a non-owner role without RLS bypass",
                    500,
                )
            conn.execute("SELECT set_config('inv.tenant_id', %s, true)", (tenant,))
            conn.execute("SET LOCAL lock_timeout = '500ms'")
            conn.execute("SET LOCAL statement_timeout = '2s'")
            epoch = conn.execute(
                "SELECT epoch FROM inv.control_epoch WHERE singleton FOR SHARE"
            ).fetchone()
            if not epoch or str(epoch["epoch"]) != self.recovery_epoch:
                raise DomainError(
                    "LEASE-0004", "Recovery epoch requires operator reconciliation", 503
                )
            try:
                # Tenant barrier precedes every Run/Node/grant lock. Containment
                # writers acquire exclusive access directly, never upgrade SHARE.
                # No network I/O may run inside this transaction.
                gate = conn.execute(
                    "SELECT tenant_id FROM inv.tenant_controls WHERE tenant_id=%s FOR "
                    + ("UPDATE" if containment_write else "SHARE"),
                    (tenant,),
                ).fetchone()
                if not gate:
                    raise DomainError("AUTH-0060", "Tenant containment control unavailable", 503)
                yield conn
            except (
                psycopg.errors.LockNotAvailable,
                psycopg.errors.QueryCanceled,
                psycopg.errors.DeadlockDetected,
            ) as error:
                raise DomainError(
                    "RES-0007",
                    "Transaction contention; retry with the same key",
                    503,
                    retryable=True,
                ) from error
