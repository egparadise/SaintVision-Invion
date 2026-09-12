"""What a candidate backend serves before anybody configures it.

A container image is built from a module name. If importing that module is
enough to produce a serving application, then the application it produces is
what an operator gets on the day something is misconfigured — and an
application that answers anyway will answer with whatever it has, which in a
module with no database is whatever was typed into it.

So this imports a candidate the way a container does, with every ``INV_*``
variable removed, and reports four things:

``obtainable``
    Did importing alone yield an application object? A factory that requires an
    engine, settings and a verifier cannot be served by accident; a module-level
    ``app = FastAPI(...)`` can.
``answers``
    Which routes return a success status with no credentials attached.
``claims``
    What ``/readyz`` says about itself. "ready" from an unconfigured process is
    the sentence that makes every other signal untrustworthy.
``reaches``
    Whether the module refers to a database at all. A control plane that never
    mentions one is not reading the records it appears to be reporting.

**What this cannot see.** It tests the application, not the deployment. If a
reverse proxy in front of it authenticates every request, these routes are not
reachable as shown — but that makes the proxy the only thing standing between
the network and the data, which is a decision somebody should have made on
purpose rather than discovered here.

Usage:
    python tools/deployment_surface.py --app saintvision.server:app
    python tools/deployment_surface.py --app saintvision.api.app:create_app
    python tools/deployment_surface.py --dockerfile deploy/Dockerfile.backend
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Mirror the container's import path, not a narrower one. deploy/Dockerfile.backend
# sets PYTHONPATH=/app/src:/app/services/control-plane/src, and judging the
# entrypoint on less than the container sees reports INCONCLUSIVE about a module
# the container would actually import — which is how this tool spent a day
# unable to say whether the factory entrypoint refuses.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
_KERNEL_SRC = _ROOT / "services" / "control-plane" / "src"
if _KERNEL_SRC.is_dir():
    sys.path.insert(1, str(_KERNEL_SRC))

#: Paths worth asking about without credentials. Health endpoints are here
#: because what they *claim* matters as much as what the data routes return.
PROBES: tuple[str, ...] = (
    "/readyz",
    "/v1/auth/userinfo",
    "/healthz",
    "/v1/approvals",
    "/v1/runs",
    "/v1/projects",
    "/v1/nodes",
    "/v1/admin/audit-logs",
)

#: Evidence that a module talks to a database at all.
_DATABASE = re.compile(r"psycopg|sqlalchemy|create_engine|DATABASE_URL|asyncpg")
#: Evidence that a module declares authentication of its own.
_AUTH = re.compile(r"Depends\(|Security\(|HTTPBearer|oauth2|verify_token|require_\w+\(")


def _strip_configuration() -> None:
    import os

    for name in [k for k in os.environ if k.startswith("INV_")]:
        del os.environ[name]


def obtain(target: str) -> tuple[Any, str]:
    """Import ``module:attr`` the way uvicorn does, with nothing configured."""
    import importlib

    module_name, _, attr = target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except Exception as error:  # noqa: BLE001
        # Reported, not raised. A tool that tracebacks teaches people to
        # distrust the tool; and "could not import" is a real answer that is
        # not the same as "refuses by design" — it usually means this checkout
        # cannot see a dependency the container would have.
        return None, (
            f"INCONCLUSIVE: module could not be imported here: "
            f"{type(error).__name__}: {error}"
        )
    if not attr:
        return None, "no attribute named; nothing to serve"
    candidate = getattr(module, attr, None)
    if candidate is None:
        return None, f"{module_name} has no {attr!r}"
    if callable(candidate) and not hasattr(candidate, "routes"):
        # A factory. Calling it with nothing is exactly what a misconfigured
        # deployment would amount to, so the failure is the finding.
        try:
            return candidate(), "factory returned an application with no arguments"
        except TypeError as error:
            return None, f"factory refuses to build without arguments: {error}"
        except Exception as error:  # noqa: BLE001 - any refusal is the answer
            return None, f"factory refused: {type(error).__name__}: {error}"
    return candidate, "module-level application object"


def inspect(target: str, module_source: str | None) -> dict[str, Any]:
    _strip_configuration()
    app, how = obtain(target)
    report: dict[str, Any] = {
        "target": target,
        "obtainable": app is not None,
        "how": how,
        "answers": [],
        "claims": None,
        "routes": None,
    }
    if module_source is not None:
        report["referencesDatabase"] = bool(_DATABASE.search(module_source))
        report["declaresAuthentication"] = bool(_AUTH.search(module_source))

    if app is None:
        return report

    from fastapi.testclient import TestClient

    report["routes"] = len([r for r in getattr(app, "routes", []) if hasattr(r, "path")])
    client = TestClient(app)
    for path in PROBES:
        try:
            response = client.get(path)
        except Exception as error:  # noqa: BLE001
            report["answers"].append({"path": path, "status": type(error).__name__})
            continue
        entry = {"path": path, "status": response.status_code}
        if path == "/readyz" and response.status_code < 400:
            report["claims"] = response.text[:200]
        if response.status_code < 400:
            entry["bytes"] = len(response.content)
        elif response.status_code in (401, 403):
            # It refused, which is the right answer — but refusing an absent
            # credential is not the same as checking a present one. A route that
            # turns a rejection into a success for *any* string beginning with
            # "Bearer " has authentication in shape only, and that reads as
            # protection to everyone downstream.
            try:
                retried = client.get(
                    path, headers={"Authorization": "Bearer not-a-real-token"}
                )
            except Exception:  # noqa: BLE001
                retried = None
            if retried is not None and retried.status_code < 400:
                entry["acceptsAnyBearerToken"] = True
                entry["grants"] = retried.text[:160]
        report["answers"].append(entry)
    return report


def verdict(report: dict[str, Any]) -> list[str]:
    """Everything wrong with serving this, stated one finding per line."""
    problems: list[str] = []
    if report["how"].startswith("INCONCLUSIVE"):
        # Not a pass. The tool established nothing, and "could not run" must
        # never read as "nothing wrong" — usually it means this checkout cannot
        # see a dependency the container would have, so the question is still
        # open.
        return ["the check did not run: " + report["how"]]
    if not report["obtainable"]:
        return problems
    served = [
        a for a in report["answers"]
        if isinstance(a["status"], int) and a["status"] < 400
        and a["path"].startswith("/v1/")
    ]
    if served:
        problems.append(
            f"{len(served)} data route(s) answer without credentials: "
            + ", ".join(a["path"] for a in served)
        )
    if report.get("claims") and '"ready"' in report["claims"]:
        problems.append(
            "/readyz reports ready with nothing configured, so readiness does "
            "not mean the process can do its job"
        )
    if report.get("referencesDatabase") is False:
        problems.append(
            "the module refers to no database, so whatever it returns is not "
            "the recorded state"
        )
    if report.get("declaresAuthentication") is False:
        problems.append("the module declares no authentication of its own")
    forged = [a for a in report["answers"] if a.get("acceptsAnyBearerToken")]
    for answer in forged:
        problems.append(
            f"{answer['path']} refuses a missing credential and then accepts an "
            f"arbitrary one: 'Bearer not-a-real-token' returns "
            f"{answer.get('grants', '')[:120]}"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app",
        help="module:attr, exactly as a container's CMD names it",
    )
    parser.add_argument(
        "--dockerfile",
        help="read the target out of a Dockerfile's uvicorn CMD instead",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.app and not args.dockerfile:
        parser.error("--app or --dockerfile is required")

    target = args.app
    if args.dockerfile:
        text = Path(args.dockerfile).read_text(encoding="utf-8")
        found = re.search(r'"uvicorn",\s*"([^"]+)"|uvicorn\s+([\w.]+:\w+)', text)
        if not found:
            print(f"no uvicorn target found in {args.dockerfile}")
            return 1
        target = found.group(1) or found.group(2)
        print(f"{args.dockerfile} serves {target}\n")

    source = None
    module_name = target.partition(":")[0]
    candidate = Path("src") / Path(module_name.replace(".", "/") + ".py")
    if candidate.is_file():
        source = candidate.read_text(encoding="utf-8", errors="replace")

    report = inspect(target, source)
    problems = verdict(report)

    if args.json:
        print(json.dumps({**report, "problems": problems}, indent=2))
        return 1 if problems else 0

    print(f"target        {report['target']}")
    print(f"obtainable    {report['obtainable']} — {report['how']}")
    if report["routes"] is not None:
        print(f"routes        {report['routes']}")
    for answer in report["answers"]:
        print(f"  {str(answer['status']):>4}  {answer['path']}")
    if report.get("claims"):
        print(f"readyz says   {report['claims']}")
    if "referencesDatabase" in report:
        print(f"database      {'referenced' if report['referencesDatabase'] else 'NOT referenced'}")
        print(f"authentication{'  declared' if report['declaresAuthentication'] else '  NOT declared'}")

    if report["how"].startswith("INCONCLUSIVE"):
        # Deliberately not phrased as a finding about the target. The tool
        # established nothing, and saying anything stronger would turn "could
        # not run" into evidence.
        print(f"\nNOTHING ESTABLISHED — {report['how']}")
        print(
            "  This checkout could not import the target, which is not evidence "
            "either way. Run it where the container's dependencies are present. "
            "Exiting non-zero because an unanswered question is not a pass."
        )
        return 1
    if problems:
        print("\nnot fit to serve as it stands:")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nThis inspects the application, not the deployment. A proxy in "
            "front may authenticate; if so, that proxy is the only thing between "
            "the network and this, which should be a decision rather than a "
            "discovery."
        )
    else:
        print("\nnothing here serves without configuration")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
