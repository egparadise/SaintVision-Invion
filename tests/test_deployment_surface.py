"""What a candidate backend serves before anybody configures it.

Written against synthetic modules rather than the repository's own applications,
because which application a branch holds is exactly the thing under dispute and a
test that changes its mind with the branch decides nothing.

The case that matters is the one where a module-level ``app = FastAPI(...)``
answers data routes with no credentials while reporting itself ready. A check
that could not fail on that would be worthless, so it is driven both ways.
"""

from __future__ import annotations

import sys
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from deployment_surface import inspect, verdict  # noqa: E402

SERVES_UNCONFIGURED = '''
from fastapi import FastAPI
app = FastAPI()
APPROVALS = [{"id": "apr_0001"}]

@app.get("/readyz")
def readyz():
    return {"status": "ready", "scope": "authenticated-control-api"}

@app.get("/v1/approvals")
def approvals():
    return {"items": APPROVALS}

@app.get("/v1/runs")
def runs():
    return {"items": []}
'''

REFUSES_WITHOUT_CONFIGURATION = '''
from fastapi import FastAPI

def create_app(*, engine, settings, verifier):
    return FastAPI()
'''


@pytest.fixture
def module(tmp_path, monkeypatch):
    """Write a module, put it on the path, and hand back its import name."""
    monkeypatch.syspath_prepend(str(tmp_path))

    def write(name: str, source: str) -> str:
        (tmp_path / f"{name}.py").write_text(textwrap.dedent(source), encoding="utf-8")
        return name

    return write


def test_a_module_level_app_is_obtainable_and_answers(module) -> None:
    name = module("surface_serves", SERVES_UNCONFIGURED)
    report = inspect(f"{name}:app", SERVES_UNCONFIGURED)
    assert report["obtainable"] is True
    assert report["how"] == "module-level application object"
    answered = {a["path"] for a in report["answers"] if a["status"] == 200}
    assert {"/v1/approvals", "/v1/runs"} <= answered


def test_that_case_is_refused_with_each_reason_named(module) -> None:
    name = module("surface_serves2", SERVES_UNCONFIGURED)
    problems = verdict(inspect(f"{name}:app", SERVES_UNCONFIGURED))
    joined = " | ".join(problems)
    assert "without credentials" in joined
    assert "readyz reports ready" in joined
    assert "no database" in joined
    assert "no authentication" in joined


def test_a_factory_that_requires_configuration_is_not_obtainable(module) -> None:
    """The shape that cannot be served by accident."""
    name = module("surface_factory", REFUSES_WITHOUT_CONFIGURATION)
    report = inspect(f"{name}:create_app", REFUSES_WITHOUT_CONFIGURATION)
    assert report["obtainable"] is False
    assert "refuses to build without arguments" in report["how"]
    assert "diagnostics suppressed" in report["how"]
    assert verdict(report) == []


def test_a_factory_that_builds_from_nothing_is_still_judged(module) -> None:
    """A factory is not a safeguard by itself; only a refusing one is."""
    name = module(
        "surface_loose",
        SERVES_UNCONFIGURED + "\ndef create_app():\n    return app\n",
    )
    report = inspect(f"{name}:create_app", SERVES_UNCONFIGURED)
    assert report["obtainable"] is True
    assert "with no arguments" in report["how"]
    assert verdict(report), "it serves, so it must be judged like any other"


def test_a_missing_attribute_is_reported_not_crashed(module) -> None:
    name = module("surface_absent", REFUSES_WITHOUT_CONFIGURATION)
    report = inspect(f"{name}:app", REFUSES_WITHOUT_CONFIGURATION)
    assert report["obtainable"] is False
    assert "has no 'app'" in report["how"]


def test_configuration_is_stripped_before_the_import(module, monkeypatch) -> None:
    """The point is what a container gets when the environment is not there.

    Importing with the developer's own INV_* variables present would measure
    this machine rather than the deployment.
    """
    monkeypatch.setenv("INV_DATABASE_URL", "postgresql://should-not-survive/x")
    source = ('import os\nassert "INV_DATABASE_URL" not in os.environ\n'
              'os.environ["INV_CANDIDATE_ADDED"] = "discard-me"\n'
              + SERVES_UNCONFIGURED)
    name = module("surface_env", source)
    assert inspect(f"{name}:app", source)["obtainable"] is True
    import os

    assert os.environ["INV_DATABASE_URL"] == "postgresql://should-not-survive/x"
    assert "INV_CANDIDATE_ADDED" not in os.environ


def test_a_database_reference_is_noticed(module) -> None:
    source = SERVES_UNCONFIGURED + "\nimport sqlalchemy\n"
    name = module("surface_db", source)
    report = inspect(f"{name}:app", source)
    assert report["referencesDatabase"] is True
    assert "no database" not in " ".join(verdict(report))


def test_declared_authentication_is_noticed(module) -> None:
    source = SERVES_UNCONFIGURED + "\nfrom fastapi import Depends\n_ = Depends(lambda: 1)\n"
    name = module("surface_auth", source)
    report = inspect(f"{name}:app", source)
    assert report["declaresAuthentication"] is True
    assert "no authentication" not in " ".join(verdict(report))


ACCEPTS_ANY_TOKEN = '''
from typing import Optional
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
app = FastAPI()

@app.get("/v1/auth/userinfo")
def userinfo(authorization: Optional[str] = Header(None)):
    # Refuses an absent credential, then accepts any present one. This is the
    # shape that reads as protection to everything downstream.
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"sub": "usr_admin", "role": "cluster:admin"}
'''

REALLY_CHECKS = '''
from typing import Optional
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
app = FastAPI()

@app.get("/v1/auth/userinfo")
def userinfo(authorization: Optional[str] = Header(None)):
    if authorization != "Bearer the-one-valid-token":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"sub": "usr_admin"}
'''


def test_a_route_that_accepts_any_bearer_token_is_reported(module) -> None:
    """Refusing an absent credential is not checking a present one.

    This is the sharpest shape, because everything downstream reads the 401 as
    proof that the endpoint authenticates.
    """
    name = module("surface_forged", ACCEPTS_ANY_TOKEN)
    report = inspect(f"{name}:app", ACCEPTS_ANY_TOKEN)
    entry = next(a for a in report["answers"] if a["path"] == "/v1/auth/userinfo")
    assert entry["status"] == 401, "it must genuinely refuse the empty case first"
    assert entry["acceptsAnyBearerToken"] is True
    assert entry["bearerStatus"] == 200
    assert "grants" not in entry
    assert [p for p in verdict(report) if "arbitrary one" in p]


def test_a_route_that_verifies_the_token_is_not_reported(module) -> None:
    """The check must not accuse an endpoint that actually validates."""
    name = module("surface_real", REALLY_CHECKS)
    report = inspect(f"{name}:app", REALLY_CHECKS)
    entry = next(a for a in report["answers"] if a["path"] == "/v1/auth/userinfo")
    assert entry["status"] == 401
    assert not entry.get("acceptsAnyBearerToken")
    assert not [p for p in verdict(report) if "arbitrary one" in p]


def test_an_unimportable_target_is_inconclusive_not_a_pass(module) -> None:
    """The failure mode this tool exists to remove, in the tool itself.

    A checkout that cannot import the target has established nothing. Reporting
    that as "nothing serves without configuration" would be a check that passes
    because it could not run -- which is the shape this whole exercise has been
    about.
    """
    name = module("surface_broken", "import a_module_that_is_not_installed\n")
    report = inspect(f"{name}:app", None)
    assert report["obtainable"] is False
    assert report["how"].startswith("INCONCLUSIVE")
    problems = verdict(report)
    assert problems and "did not run" in problems[0]


@pytest.mark.parametrize("where", ["import", "factory", "typeerror"])
def test_exception_diagnostics_do_not_publish_sensitive_values(module, where):
    secret = "synthetic-private-dsn-sentinel"
    if where == "import":
        source = f'raise RuntimeError("{secret}")'
    else:
        kind = "TypeError" if where == "typeerror" else "RuntimeError"
        source = f'def create_app():\n    raise {kind}("{secret}")'
    name = module("surface_secret_" + where, source)
    report = inspect(f"{name}:create_app", None)
    assert report["obtainable"] is False
    assert secret not in json.dumps({**report, "problems": verdict(report)})
    assert "diagnostics suppressed" in report["how"]


def test_candidate_python_output_and_response_bodies_are_not_evidence(module, capsys):
    secret = "synthetic-response-private-sentinel"
    source = ACCEPTS_ANY_TOKEN.replace(
        '{"sub": "usr_admin", "role": "cluster:admin"}',
        '{"secret": "' + secret + '"}',
    ) + f'''
import sys
print("{secret}")
print("{secret}", file=sys.stderr)
@app.get("/readyz")
def ready():
    print("{secret}")
    return {{"status": "ready", "dsn": "{secret}"}}
'''
    name = module("surface_secret_response", source)
    report = inspect(f"{name}:app", None)
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    assert secret not in json.dumps({**report, "problems": verdict(report)})
    assert report["claims"] == {"status": "ready"}
    problems = verdict(report)
    assert any("readyz reports ready" in p for p in problems)
    assert any("arbitrary one" in p and "HTTP 200" in p for p in problems)


@pytest.mark.parametrize("body", [
    '{"status":"not_ready","detail":"ready"}',
    '{"status":"private-status-sentinel"}',
    '["ready"]',
    '"ready"',
])
def test_only_exact_readiness_status_is_reported(module, body):
    source = f'''
from fastapi import FastAPI
from fastapi.responses import Response
app = FastAPI()
@app.get("/readyz")
def ready():
    return Response({body!r}, media_type="application/json")
'''
    name = module("surface_status_" + str(len(body)), source)
    report = inspect(f"{name}:app", None)
    assert not any("readyz reports ready" in p for p in verdict(report))
    assert "private-status-sentinel" not in json.dumps(report)


def test_dockerfile_json_cli_is_single_redacted_document(tmp_path):
    root = Path(__file__).resolve().parents[1]
    module_path = tmp_path / "surface_cli_secret.py"
    module_path.write_text('print("synthetic-cli-secret")\nraise RuntimeError("synthetic-cli-secret")\n')
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text('CMD ["uvicorn", "surface_cli_secret:app"]\n')
    import os
    result = subprocess.run(
        [sys.executable, str(root / "tools/deployment_surface.py"),
         "--dockerfile", str(dockerfile), "--json"],
        cwd=root, env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "synthetic-cli-secret" not in result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["how"].startswith("INCONCLUSIVE")
    assert report["problems"]


@pytest.mark.parametrize("behavior", [
    'raise RuntimeError("synthetic-probe-secret")',
    'return Response("synthetic-probe-secret", status_code=503)',
])
def test_failed_probe_is_not_a_security_pass(module, behavior):
    source = f'''
from fastapi import FastAPI
from fastapi.responses import Response
app = FastAPI()
@app.get("/v1/projects")
def projects():
    {behavior}
'''
    name = module("surface_probe_error_" + str(len(behavior)), source)
    report = inspect(f"{name}:app", None)
    assert "synthetic-probe-secret" not in json.dumps(report)
    assert any("failing probes" in p for p in verdict(report))
