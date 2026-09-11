"""Optional business routes behind the same HTTP boundary and token verifier.

The kernel keeps authority for runs, approval, enqueue and containment. Business
CRUD uses its own inv_app connection; the web role never inherits inv_kernel.
"""
from starlette.routing import Match


class BusinessDispatch:
    def __init__(self, app, business):
        self.app, self.business = app, business
        from saintvision.api.v1 import projects, settings, adapters, results
        # Read the three declared routers, not FastAPI's lazily included wrapper
        # routes. Keep all deeper execution routes on the kernel application.
        self.routes = [r for module in (projects, settings, adapters) for r in module.router.routes]
        # Run result paths belong to the execution kernel, including first Runs
        # which have no public.runs row. Only workspace readiness is business CRUD.
        self.routes += [r for r in results.router.routes if r.path.startswith("/v1/workspaces/")]

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and any(r.matches(scope)[0] != Match.NONE for r in self.routes):
            # FastAPI installs its own app reference for dependencies. Restore it
            # when returning so middleware does not retain the other role's app.
            original = scope.get("app")
            try:
                return await self.business(scope, receive, send)
            finally:
                scope["app"] = original
        return await self.app(scope, receive, send)


def configured_business(database, tokens):
    import os
    from sqlalchemy import create_engine, text
    from psycopg.conninfo import conninfo_to_dict
    from saintvision.api.app import create_app
    from saintvision.config import Settings
    from saintvision.db.session import make_session_factory
    from saintvision.identity.oidc import OidcPrincipalVerifier

    business_dsn = os.environ["INV_BUSINESS_DSN"]
    def target(dsn):
        values = conninfo_to_dict(dsn.replace("postgresql+psycopg://", "postgresql://", 1))
        for name in ("user", "password"):
            values.pop(name, None)
        values.setdefault("port", "5432")
        if not values.get("host") or not values.get("dbname"):
            raise ValueError("Explicit database host and name required")
        return values
    if target(business_dsn) != target(database._dsn):
        raise ValueError("Business and execution database targets differ")
    engine = create_engine(business_dsn, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""SELECT current_database(),
              NOT rolsuper AND NOT rolbypassrls AND pg_has_role(current_user,'inv_app','MEMBER')
              AND NOT pg_has_role(current_user,'inv_kernel','MEMBER')
              AND NOT EXISTS(SELECT 1 FROM pg_namespace n WHERE n.nspowner=r.oid
                             AND n.nspname IN ('public','inv'))
              AND NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                             WHERE c.relowner=r.oid AND n.nspname IN ('public','inv')) AS restricted
              FROM pg_roles r WHERE rolname=current_user""")).one()
            if not row.restricted:
                raise ValueError("Separate restricted business role required")
        with database.transaction(tokens.tenant_id) as conn:
            if conn.execute("SELECT current_database() AS name").fetchone()["name"] != row[0]:
                raise ValueError("Business and execution must use the same database")
        business = create_app(engine=engine, settings=Settings(database_url="configured"),
            verifier=OidcPrincipalVerifier(tokens, make_session_factory(engine)))
        business.router.add_event_handler("shutdown", engine.dispose)
        return business
    except Exception:
        engine.dispose()
        raise
