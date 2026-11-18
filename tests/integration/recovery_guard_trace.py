"""Test-only guard attribution for the read-only cohort collector.

The collector deliberately answers every operator-visibility refusal with one
public code (OPERATOR_VISIBILITY_UNKNOWN). These helpers recover, from the
outside, which predicate refused an input: the original exception that the
collector suppresses with ``from None`` stays reachable as ``__context__``, and
a cursor proxy records the SQL statements and the rows each one returned. No
collector source is changed, so the public result is exactly what the operator
sees.
"""
import errno
import json
import linecache

# Order matters: the privilege probe also names pg_control_system().
GUARD_SQL = (
    ("has_function_privilege", "control-function-privilege"),
    ("system_identifier", "cluster-identifier"),
    ("pg_database db", "session-role-database-oid"),
    ("operator_grants", "operator-grant"),
)
DESCRIPTOR_LINES = (
    ("st_uid==0", "descriptor-owner-mode"),
    ("S_ISREG", "descriptor-type-links-size"),
    ("len(raw)", "descriptor-read-stability"),
)


class TracingCursor:
    def __init__(self, cursor, trace):
        self._cursor = cursor
        self._trace = trace

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *exc):
        return self._cursor.__exit__(*exc)

    def execute(self, query, params=None):
        self._trace.append({"sql": " ".join(str(query).split()), "rows": None})
        self._cursor.execute(query, params)
        return self

    def fetchall(self):
        rows = self._cursor.fetchall()
        self._trace[-1]["rows"] = rows
        return rows

    def fetchone(self):
        row = self._cursor.fetchone()
        self._trace[-1]["rows"] = [] if row is None else [row]
        return row


class TracingConnection:
    """Only the surface observe() uses: cursor()."""

    def __init__(self, db):
        self._db = db
        self.trace = []

    def cursor(self):
        return TracingCursor(self._db.cursor(), self.trace)


def _origin(exc):
    while exc.__context__ is not None:
        exc = exc.__context__
    return exc


def _raising_frame(exc):
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        frames.append((tb.tb_frame.f_code.co_name, tb.tb_frame.f_code.co_filename, tb.tb_lineno))
        tb = tb.tb_next
    callers = [frame for frame in frames if frame[0] != "require"]
    return callers[-1] if callers else ("", "", 0)


def _sql_guard(trace):
    statement = trace[-1] if trace else {"sql": "", "rows": None}
    for token, label in GUARD_SQL:
        if token in statement["sql"]:
            return label, len(statement["rows"] or [])
    # verify_reader refused before its first query: the pure binding/descriptor equality.
    return "binding-shape-scope", None


def attribute(exc, trace):
    """Return (guard, rows returned by the guarding statement or None)."""
    root = _origin(exc)
    if isinstance(root, OSError):
        return "descriptor-open:" + errno.errorcode.get(root.errno, str(root.errno)), None
    if isinstance(root, json.JSONDecodeError):
        return "descriptor-json-syntax", None
    name, filename, line = _raising_frame(root)
    if name in ("decode", "unique"):
        return "descriptor-json:" + str(root), None
    if name == "provisioned_reader":
        text = linecache.getline(filename, line)
        for token, label in DESCRIPTOR_LINES:
            if token in text:
                return label, None
        return "descriptor-unclassified:" + text.strip(), None
    if name == "verify_reader":
        return _sql_guard(trace)
    if name == "observe":
        return "session-facts", None
    return "unclassified:" + name, None
