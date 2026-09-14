"""Read-only preflight for migration-owned permission groups.

Published revisions create these groups only when absent. Never silently accept
an unsafe predecessor, and never change live login access as a migration side effect.
"""
from sqlalchemy import text


def assert_permission_groups(connection):
    rows = connection.execute(text("""
        SELECT rolname, rolcanlogin, rolsuper, rolbypassrls,
               rolcreatedb, rolcreaterole, rolreplication
        FROM pg_roles WHERE rolname IN ('inv_app', 'inv_kernel')
        ORDER BY rolname
    """)).mappings()
    violations = []
    for row in rows:
        flags = [name for name in row if name != 'rolname' and row[name]]
        if flags:
            violations.append(row['rolname'] + ': ' + ', '.join(flags))
    if violations:
        raise RuntimeError(
            'Unsafe migration permission group; operator reconciliation required: '
            + '; '.join(violations)
        )
