"""Short, tenant-scoped transactions. DSN is never included in errors or logs."""

from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import re
from time import perf_counter_ns
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from .errors import DomainError


_statement_phase = ContextVar("inv_statement_phase", default="outside-transaction")
_placement_logger = logging.getLogger("inv.placement")


def mark_statement_phase(
    phase: str, *, attempt: int = 1, track_lock_hold: bool = True
) -> None:
    """Label opt-in SQL diagnostics without changing the transaction contract."""

    marker = {"name": phase, "attempt": attempt}
    if track_lock_hold:
        marker["startedNs"] = perf_counter_ns()
    _statement_phase.set(marker)


def record_placement_metric(database, metric: dict) -> None:
    """Emit identifier-free placement timing to the configured trusted sink."""

    try:
        if getattr(database, "placement_metric_sink", None) is not None:
            database.placement_metric_sink(metric)
        elif getattr(database, "placement_short_commit", False):
            _placement_logger.info(
                "placement_metric %s",
                json.dumps(metric, sort_keys=True, separators=(",", ":")),
            )
    except Exception:
        pass


def _statement_template(query) -> str:
    """Return a parameter-free, bounded SQL template for diagnostics."""

    if not isinstance(query, str):
        return type(query).__name__
    return re.sub(r"\s+", " ", query).strip()[:500]


class _ObservedConnection:
    """Transparent psycopg adapter used only when an observer is supplied."""

    def __init__(self, conn, observer):
        self._conn = conn
        self._observer = observer

    def execute(self, query, params=None, **kwargs):
        started = perf_counter_ns()
        try:
            result = self._conn.execute(query, params, **kwargs)
        except psycopg.Error as error:
            try:
                self._observer(
                    {
                        "phase": (
                            _statement_phase.get().get("name")
                            if isinstance(_statement_phase.get(), dict)
                            else _statement_phase.get()
                        ),
                        "statement": _statement_template(query),
                        "sqlState": error.sqlstate,
                        "errorType": type(error).__name__,
                        "outcome": "error",
                        "elapsedMs": round(
                            (perf_counter_ns() - started) / 1_000_000, 3
                        ),
                    }
                )
            except Exception:
                pass
            raise
        try:
            self._observer(
                {
                    "phase": (
                        _statement_phase.get().get("name")
                        if isinstance(_statement_phase.get(), dict)
                        else _statement_phase.get()
                    ),
                    "statement": _statement_template(query),
                    "sqlState": None,
                    "errorType": None,
                    "outcome": "success",
                    "elapsedMs": round(
                        (perf_counter_ns() - started) / 1_000_000, 3
                    ),
                }
            )
        except Exception:
            pass
        return result

    def __getattr__(self, name):
        return getattr(self._conn, name)


class BoundDatabase:
    """Private adapter: nested service operations share one outer transaction."""

    def __init__(self, db, tenant, conn):
        self.recovery_epoch, self.tenant, self.conn = db.recovery_epoch, tenant, conn
        self.shard_recovery_admission = getattr(db, "shard_recovery_admission", False)
        self.business_handoff = getattr(db, "business_handoff", False)
        self.registry_binding_policy = getattr(db, "registry_binding_policy", None)
        self.placement_short_commit = getattr(db, "placement_short_commit", False)
        self.statement_observer = getattr(db, "statement_observer", None)
        self.placement_metric_sink = getattr(db, "placement_metric_sink", None)

    @contextmanager
    def transaction(self, tenant):
        if tenant != self.tenant:
            raise DomainError("AUTH-0011", "Nested transaction scope differs", 403)
        yield self.conn


class Database:
    def __init__(
        self,
        dsn: str,
        *,
        recovery_epoch: str,
        registry_binding_policy=None,
        placement_short_commit: bool = False,
        statement_observer=None,
        placement_metric_sink=None,
    ):
        if registry_binding_policy is not None:
            from .model_registry_binding import RegistryBindingPolicy
            if not isinstance(registry_binding_policy, RegistryBindingPolicy):
                raise ValueError("Operator registry binding policy required")
        self.registry_binding_policy = registry_binding_policy
        if type(placement_short_commit) is not bool:
            raise ValueError("placement_short_commit must be boolean")
        self.placement_short_commit = placement_short_commit
        self.statement_observer = statement_observer
        self.placement_metric_sink = placement_metric_sink
        self._dsn = dsn
        self.recovery_epoch = str(UUID(recovery_epoch))

    @contextmanager
    def transaction(self, tenant_id: str, *, containment_write=False):
        tenant = str(UUID(tenant_id))
        phase_token = _statement_phase.set("transaction-pre-placement-lock")
        committed = False
        try:
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
                observed_conn = (
                    _ObservedConnection(conn, self.statement_observer)
                    if self.statement_observer is not None
                    else conn
                )
                epoch = observed_conn.execute(
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
                    gate = observed_conn.execute(
                        "SELECT tenant_id FROM inv.tenant_controls WHERE tenant_id=%s FOR "
                        + ("UPDATE" if containment_write else "SHARE"),
                        (tenant,),
                    ).fetchone()
                    if not gate:
                        raise DomainError("AUTH-0060", "Tenant containment control unavailable", 503)
                    yield observed_conn
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
            committed = True
        finally:
            phase = _statement_phase.get()
            _statement_phase.reset(phase_token)
            if isinstance(phase, dict) and phase.get("startedNs") is not None:
                metric = {
                    "mode": phase["name"],
                    "attempt": phase["attempt"],
                    "lockHoldMs": round(
                        (perf_counter_ns() - phase["startedNs"]) / 1_000_000,
                        3,
                    ),
                    "outcome": "commit" if committed else "rollback",
                }
                record_placement_metric(self, metric)
