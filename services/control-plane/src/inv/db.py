"""Short, tenant-scoped transactions. DSN is never included in errors or logs."""

from asyncio import CancelledError
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import re
from threading import Lock
from time import perf_counter_ns
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from .errors import DomainError

_statement_phase = ContextVar("inv_statement_phase", default="outside-transaction")
_placement_logger = logging.getLogger("inv.placement")
DEFAULT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS = 500
MAX_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS = 1900
DEFAULT_PLACEMENT_PROJECT_SEMAPHORE_LIMIT = 4
MAX_PLACEMENT_PROJECT_SEMAPHORE_LIMIT = 20


class _PlacementSemaphoreLimit(Exception):
    """Identifier-free internal cause for the existing RES-0007 surface."""


class _ProjectPermitRegistry:
    """One non-blocking tenant+project permit registry for this CP process."""

    def __init__(self):
        self._lock = Lock()
        self._counts = {}

    def try_acquire(self, key, limit: int) -> dict:
        started = perf_counter_ns()
        with self._lock:
            in_use_before = self._counts.get(key, 0)
            acquired = in_use_before < limit
            if acquired:
                self._counts[key] = in_use_before + 1
            registry_entries = len(self._counts)
        return {
            "acquired": acquired,
            "inUseBefore": in_use_before,
            "registryEntries": registry_entries,
            "admissionElapsedMs": round((perf_counter_ns() - started) / 1_000_000, 3),
        }

    def release(self, key) -> dict:
        with self._lock:
            in_use_before = self._counts.get(key, 0)
            if in_use_before <= 0:
                return {
                    "released": False,
                    "inUseBefore": in_use_before,
                    "registryEntries": len(self._counts),
                }
            if in_use_before == 1:
                self._counts.pop(key, None)
            else:
                self._counts[key] = in_use_before - 1
            return {
                "released": True,
                "inUseBefore": in_use_before,
                "registryEntries": len(self._counts),
            }

    def inspect(self) -> dict:
        with self._lock:
            return dict(self._counts)


class _RootTransactionState:
    """Callbacks that run only after the owning DB transaction settles."""

    def __init__(self, database):
        self.database = database
        self.finalizers = []
        self.finalizer_keys = set()
        self.placement_permit_keys = set()

    def register(self, key, callback) -> bool:
        if key in self.finalizer_keys:
            return False
        self.finalizer_keys.add(key)
        self.finalizers.append(callback)
        return True

    def finalize(self, release_cause: str) -> None:
        for callback in reversed(self.finalizers):
            try:
                callback(release_cause)
            except Exception:
                _placement_logger.exception(
                    "root transaction finalizer failed without identifier context"
                )


_root_transaction_state = ContextVar("inv_root_transaction_state", default=None)
_process_placement_permits = _ProjectPermitRegistry()


def mark_statement_phase(phase: str, *, attempt: int = 1, track_lock_hold: bool = True) -> None:
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
                        "elapsedMs": round((perf_counter_ns() - started) / 1_000_000, 3),
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
                    "elapsedMs": round((perf_counter_ns() - started) / 1_000_000, 3),
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
        self._root_database = getattr(db, "_root_database", db)
        self.shard_recovery_admission = getattr(db, "shard_recovery_admission", False)
        self.business_handoff = getattr(db, "business_handoff", False)
        self.registry_binding_policy = getattr(db, "registry_binding_policy", None)
        self.placement_short_commit = getattr(db, "placement_short_commit", False)
        self.placement_candidate_limit_lock_timeout_ms = getattr(
            db,
            "placement_candidate_limit_lock_timeout_ms",
            DEFAULT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS,
        )
        self.placement_project_semaphore_enabled = getattr(
            db, "placement_project_semaphore_enabled", False
        )
        self.placement_project_semaphore_limit = getattr(
            db,
            "placement_project_semaphore_limit",
            DEFAULT_PLACEMENT_PROJECT_SEMAPHORE_LIMIT,
        )
        self.statement_observer = getattr(db, "statement_observer", None)
        self.placement_metric_sink = getattr(db, "placement_metric_sink", None)

    def acquire_placement_project_permit(self, tenant_id: str, project_id: str) -> bool:
        return self._root_database.acquire_placement_project_permit(tenant_id, project_id)

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
        placement_candidate_limit_lock_timeout_ms: int = DEFAULT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS,
        placement_project_semaphore_enabled: bool = False,
        placement_project_semaphore_limit: int = DEFAULT_PLACEMENT_PROJECT_SEMAPHORE_LIMIT,
        statement_observer=None,
        placement_metric_sink=None,
        _placement_permit_registry=None,
    ):
        if registry_binding_policy is not None:
            from .model_registry_binding import RegistryBindingPolicy

            if not isinstance(registry_binding_policy, RegistryBindingPolicy):
                raise ValueError("Operator registry binding policy required")
        self.registry_binding_policy = registry_binding_policy
        if type(placement_short_commit) is not bool:
            raise ValueError("placement_short_commit must be boolean")
        self.placement_short_commit = placement_short_commit
        if (
            type(placement_candidate_limit_lock_timeout_ms) is not int
            or not 1
            <= placement_candidate_limit_lock_timeout_ms
            <= MAX_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS
        ):
            raise ValueError(
                "placement_candidate_limit_lock_timeout_ms must be an integer "
                f"between 1 and {MAX_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS}"
            )
        self.placement_candidate_limit_lock_timeout_ms = placement_candidate_limit_lock_timeout_ms
        if type(placement_project_semaphore_enabled) is not bool:
            raise ValueError("placement_project_semaphore_enabled must be boolean")
        if (
            type(placement_project_semaphore_limit) is not int
            or not 1 <= placement_project_semaphore_limit <= MAX_PLACEMENT_PROJECT_SEMAPHORE_LIMIT
        ):
            raise ValueError(
                "placement_project_semaphore_limit must be an integer "
                f"between 1 and {MAX_PLACEMENT_PROJECT_SEMAPHORE_LIMIT}"
            )
        self.placement_project_semaphore_enabled = placement_project_semaphore_enabled
        self.placement_project_semaphore_limit = placement_project_semaphore_limit
        self._placement_permit_registry = _placement_permit_registry or _process_placement_permits
        self.statement_observer = statement_observer
        self.placement_metric_sink = placement_metric_sink
        self._dsn = dsn
        self.recovery_epoch = str(UUID(recovery_epoch))

    @contextmanager
    def _root_transaction_lifecycle(self):
        """Install finalizers whose lifetime exactly matches one root transaction."""

        state = _RootTransactionState(self)
        token = _root_transaction_state.set(state)
        release_cause = "rollback"
        try:
            yield state
        except CancelledError:
            release_cause = "cancel"
            raise
        except DomainError:
            release_cause = "rollback"
            raise
        except BaseException:
            release_cause = "exception"
            raise
        else:
            release_cause = "commit"
        finally:
            state.finalize(release_cause)
            _root_transaction_state.reset(token)

    def acquire_placement_project_permit(self, tenant_id: str, project_id: str) -> bool:
        """Acquire immediately or raise the existing retryable contention error."""

        if not (self.placement_short_commit and self.placement_project_semaphore_enabled):
            return False
        tenant = str(UUID(tenant_id))
        project = str(project_id)
        state = _root_transaction_state.get()
        if state is None or state.database is not self:
            raise RuntimeError("placement project permit requires the owning root transaction")
        key = (tenant, project)
        if key in state.placement_permit_keys:
            snapshot = self._placement_permit_registry.inspect()
            record_placement_metric(
                self,
                {
                    "mode": "placement-project-semaphore",
                    "limit": self.placement_project_semaphore_limit,
                    "inUseBefore": snapshot.get(key, 0),
                    "outcome": "acquired",
                    "reentrant": True,
                    "registryEntries": len(snapshot),
                    "admissionElapsedMs": 0.0,
                },
            )
            return True

        admission = self._placement_permit_registry.try_acquire(
            key, self.placement_project_semaphore_limit
        )
        metric = {
            "mode": "placement-project-semaphore",
            "limit": self.placement_project_semaphore_limit,
            "inUseBefore": admission["inUseBefore"],
            "outcome": "acquired" if admission["acquired"] else "rejected",
            "reentrant": False,
            "registryEntries": admission["registryEntries"],
            "admissionElapsedMs": admission["admissionElapsedMs"],
        }
        if not admission["acquired"]:
            metric["reason"] = "project-semaphore-limit"
            record_placement_metric(self, metric)
            raise DomainError(
                "RES-0007",
                "Transaction contention; retry with the same key",
                503,
                retryable=True,
            ) from _PlacementSemaphoreLimit("project-semaphore-limit")

        state.placement_permit_keys.add(key)
        acquired_ns = perf_counter_ns()

        def release(release_cause: str) -> None:
            result = self._placement_permit_registry.release(key)
            record_placement_metric(
                self,
                {
                    "mode": "placement-project-semaphore",
                    "limit": self.placement_project_semaphore_limit,
                    "inUseBefore": result["inUseBefore"],
                    "outcome": "released",
                    "holdMs": round((perf_counter_ns() - acquired_ns) / 1_000_000, 3),
                    "releaseCause": release_cause,
                    "reentrant": False,
                    "registryEntries": result["registryEntries"],
                },
            )

        if not state.register(("placement-project-semaphore", key), release):
            self._placement_permit_registry.release(key)
            state.placement_permit_keys.discard(key)
            raise RuntimeError("duplicate placement project permit finalizer")
        record_placement_metric(self, metric)
        return True

    def _placement_project_permit_snapshot(self) -> dict:
        """PG-free invariant probe; never emit the returned keys to logs."""

        return self._placement_permit_registry.inspect()

    @contextmanager
    def transaction(self, tenant_id: str, *, containment_write=False):
        with self._root_transaction_lifecycle():
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
                            "LEASE-0004",
                            "Recovery epoch requires operator reconciliation",
                            503,
                        )
                    try:
                        # Tenant barrier precedes every Run/Node/grant lock. Containment
                        # writers acquire exclusive access directly, never upgrade SHARE.
                        # No network I/O may run inside this transaction.
                        gate = observed_conn.execute(
                            "SELECT tenant_id FROM inv.tenant_controls "
                            "WHERE tenant_id=%s FOR "
                            + ("UPDATE" if containment_write else "SHARE"),
                            (tenant,),
                        ).fetchone()
                        if not gate:
                            raise DomainError(
                                "AUTH-0060",
                                "Tenant containment control unavailable",
                                503,
                            )
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
