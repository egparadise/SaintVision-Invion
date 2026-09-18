"""Which paths the browser asks for, and which of them anything actually serves.

This exists because I measured it twice by hand and got it wrong twice, in the
same direction. First against a control-plane that turned out to be far behind
the one under review, then with a pattern that matched ``@app.`` and ``@router.``
while the kernel registers its routes on ``@api.`` inside a factory. Both errors
inflated the gap, and an inflated gap argues for building things that already
exist.

So the extraction is a tested function rather than a regex typed at a prompt. The
decorator forms it must handle are the ones it previously missed.

    python tools/route_coverage.py --served . --served ../codex-workspace-bridge \\
        --client apps/web/src

``--served`` may be given more than once: a deployment is normally several trees,
and asking "does anything serve this" is a different question from "does this one
tree serve it".

What it cannot tell you: whether a served path means the same thing to both
sides. Matching ``/v1/runs/{id}/result`` proves a route exists at that shape, not
that its response is what the screen expects.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LIMITATION = (
    "Static path shapes only; dynamic prefixes may be omitted. HTTP methods, "
    "payloads, authentication, live availability and operating acceptance are not verified."
)


def registered_routes(api) -> set[str]:
    """Inspect the constructed application, not every Python file in its tree.

    BusinessDispatch deliberately exposes only a subset of the business app.
    Respect its selection and shadowing instead of unioning both full apps.
    OpenAPI expands FastAPI's included routers, including lazy wrappers.
    """
    from inv.business_surface import BusinessDispatch
    from starlette.routing import WebSocketRoute

    http = {normalise(path) for path in api.openapi()['paths']}
    websocket = set()
    for route in api.routes:
        # Older FastAPI flattens includes; newer versions expose effective
        # contexts. Use the resolved Starlette route so include prefixes survive.
        contexts = getattr(route, 'effective_route_contexts', None)
        candidates = [context.starlette_route for context in contexts()] if callable(contexts) else [route]
        websocket.update(normalise(candidate.path) for candidate in candidates
                         if isinstance(candidate, WebSocketRoute))
    for middleware in api.user_middleware:
        if middleware.cls is BusinessDispatch:
            business = middleware.kwargs['business']
            selected = {normalise(route.path) for route in
                        BusinessDispatch(None, business).routes}
            available = {normalise(path) for path in business.openapi()['paths']}
            http = (http - selected) | (selected & available)
    return {path for path in http | websocket if path.startswith('/v1/')}


def configured_routes() -> set[str]:
    from inv.app import create_configured_app
    return registered_routes(create_configured_app())

#: Route decorators. ``@api.get`` is here because the kernel builds its
#: application inside a factory and names it ``api``; missing that form is what
#: made a 54-route service look like a 10-route one.
_DECORATOR = re.compile(
    r"@(?:\w+)\.(get|post|put|patch|delete|websocket)\(\s*f?[\"']([^\"']+)[\"']"
)
#: A router's prefix applies to every path it declares.
_PREFIX = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)", re.DOTALL)
#: Literal paths in client source, including the head of an interpolated one.
_CLIENT = re.compile(r"""[\"'`](/v1/[A-Za-z0-9_\-/{}$:.]*)[\"'`]""")
_CLIENT_HEAD = re.compile(r"""[\"'`](/v1/[^\"'`]*?)\$\{""")
#: A template hole glued directly onto a path segment, e.g. ``${prj}runs`` where
#: ``prj`` already ends in ``projects/<id>/``. The leftover ``{}runs`` is a tool
#: artefact, not a path the SPA asks for.
_GLUED_HOLE = re.compile(r"\{\}(?=[A-Za-z])")


def normalise(path: str) -> str:
    """Collapse every parameter spelling to one, so paths compare.

    ``/v1/runs/{run_id}``, ``/v1/runs/${runId}`` and ``/v1/runs/{id}`` are the
    same route named three ways by three languages.
    """
    path = re.sub(r"\$\{[^}]*\}", "{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path)
    path = re.sub(r"//+", "/", path)
    return path.rstrip("/") or "/"


def served_routes(text: str) -> set[str]:
    """Routes one Python source file declares, prefix applied."""
    prefix_match = _PREFIX.search(text)
    prefix = prefix_match.group(1) if prefix_match else ""
    return {normalise(prefix + path) for _, path in _DECORATOR.findall(text)}


def client_paths(text: str) -> set[str]:
    """``/v1`` paths a client source file mentions.

    A bare ``/v1`` base-URL constant is not a call and is dropped, and a
    template hole fused to the next segment (``/v1/{}runs`` from ``/v1/${prj}runs``,
    where ``prj`` already ends in ``projects/<id>/``) is a tool artefact rather
    than a request, so it is dropped too rather than reported as unserved.
    """
    found = {normalise(m) for m in _CLIENT.findall(text)}
    found |= {normalise(m) for m in _CLIENT_HEAD.findall(text)}
    return {
        p
        for p in found
        if p.startswith("/v1/") and not _GLUED_HOLE.search(p)
    }


def scan_served(root: Path) -> set[str]:
    routes: set[str] = set()
    for path in root.rglob("*.py"):
        if any(part in {".work", "node_modules", "__pycache__"} for part in path.parts):
            continue
        routes |= served_routes(path.read_text(encoding="utf-8", errors="replace"))
    return routes


def scan_client(root: Path) -> set[str]:
    paths: set[str] = set()
    for pattern in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for path in root.rglob(pattern):
            if "node_modules" in path.parts:
                continue
            paths |= client_paths(path.read_text(encoding="utf-8", errors="replace"))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--served", action="append", type=Path)
    mode.add_argument("--configured-surface", action="store_true",
                      help="Use the validated INV_API_CONFIG factory; never scan demo source")
    parser.add_argument("--client", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.client.is_dir() or any(not root.is_dir() for root in args.served or []):
        parser.error('Client and source inputs must be existing directories')
    if args.configured_surface:
        try:
            per_tree = {'configured-factory': configured_routes()}
        except Exception:
            # Configuration/database failures can contain private file names or
            # credentials. Never print them or fall back to source-tree scans.
            parser.exit(2, 'Configured factory validation failed; no source fallback performed.\n')
    else:
        per_tree = {str(root): scan_served(root) for root in args.served}
    served = set().union(*per_tree.values()) if per_tree else set()
    wanted = scan_client(args.client)
    missing = sorted(wanted - served)
    exit_code = 2 if not wanted else (1 if missing else 0)

    if args.json:
        print(json.dumps(
            {
                "servedByTree": {k: sorted(v) for k, v in per_tree.items()},
                "clientPaths": sorted(wanted),
                "assessment": "inconclusive-no-client-paths" if not wanted else "compared",
                "unserved": missing,
                "measurement": "configured-factory" if args.configured_surface else "source-declarations",
                "operationalAcceptanceAssessed": False,
                "limitations": LIMITATION,
            },
            indent=2,
        ))
        return exit_code

    for root, routes in per_tree.items():
        print(f"  {len(routes):4} routes  {root}")
    print(f"  {len(served):4} distinct once combined")
    print(f"  {len(wanted):4} paths the client asks for")
    print(f"  {len(missing):4} unserved\n")
    for path in missing:
        print(f"    {path}")
    if not wanted:
        print('INCONCLUSIVE: no client paths discovered; coverage was not assessed.')
    print('\n' + LIMITATION)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
