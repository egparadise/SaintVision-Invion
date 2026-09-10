"""Read exact peer commits and reproduce bounded contract findings, without services.

Requires the existing frontend TypeScript installation via --typescript. Does not
edit peer worktrees, contact Nodes, authenticate users, or perform a deployment.
"""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "c323f551068b469e73fb8e84608c2a323c7ee98e": [
        "apps/web/src/features/release/releaseEngine.ts",
        "apps/web/src/features/recovery/recoveryEngine.ts",
        "apps/web/src/features/auth/Login.tsx",
        "apps/web/tests/release-candidate.test.ts",
    ],
    "251b00ab8218a58307270432972e9900bdf3d2a8": [
        "apps/web/src/features/deployment/deploymentEngine.ts",
        "apps/web/tests/intranet-deployment.test.ts",
    ],
    "4fa551da59e05731b2a4b92976d62b1eb6a60e8a": [
        "src/saintvision/api/v1/nodes.py",
        "src/saintvision/services/nodes.py",
        "src/saintvision/services/pilot.py",
        "src/saintvision/api/deps.py",
        "src/saintvision/api/app.py",
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--typescript", required=True, type=Path)
    args = parser.parse_args()
    output = ROOT / ".work/handoff-review"
    output.mkdir(exist_ok=True, parents=True)
    records = []
    for sha, names in SOURCES.items():
        for name in names:
            raw = subprocess.check_output(["git", "show", sha + ":" + name], cwd=ROOT)
            dest = output / name
            dest.parent.mkdir(exist_ok=True, parents=True)
            dest.write_bytes(raw)
            records.append(
                {"sha": sha, "path": name, "sha256": hashlib.sha256(raw).hexdigest()}
            )
    tree = ast.parse((output / "src/saintvision/services/pilot.py").read_text("utf-8"))
    fn = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "verify_backup"
    )
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            fn,
        ],
        type_ignores=[],
    )
    namespace = {
        "BackupRecord": object,
        "InvError": lambda code, message: ValueError(message),
        "VAL_SCHEMA": "VAL",
        "RES_ARTIFACT_NOT_FOUND": "RES",
    }
    exec(
        compile(
            ast.fix_missing_locations(module), "snapshot:pilot.verify_backup", "exec"
        ),
        namespace,
    )
    tenant = uuid4()
    row = SimpleNamespace(tenant_id=tenant, verified=False)
    session = SimpleNamespace(get=lambda *args: row, flush=lambda: None)
    result = namespace["verify_backup"](
        session,
        tenant_id=tenant,
        backup_id="fixture",
        checksum_sha256="g" * 64,
        now=datetime.now(timezone.utc),
    )
    route = ast.parse((output / "src/saintvision/api/v1/nodes.py").read_text("utf-8"))
    heartbeat = next(
        n
        for n in route.body
        if isinstance(n, ast.FunctionDef) and n.name == "post_heartbeat"
    )
    claude = {
        "scope": "Exact verify_backup function with fake Session; route signature inspection. No production HTTP/DB exploit test.",
        "non_hex_checksum_accepted": result.verified,
        "stored_checksum": result.checksum_sha256,
        "heartbeat_default_dependencies": [
            ast.unparse(n)
            for n in heartbeat.args.defaults + heartbeat.args.kw_defaults
            if n is not None
        ],
    }
    subprocess.run(
        [
            "node",
            str(ROOT / "tools/reproduce_handoff_review.mjs"),
            str(output),
            str(args.typescript.resolve()),
        ],
        check=True,
        cwd=ROOT,
    )
    evidence = {
        "reviewer": "Codex",
        "review_result": "request_changes",
        "verified_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(
            timespec="seconds"
        ),
        "sources": records,
        "claude": claude,
        "gemini": json.loads((output / "frontend.json").read_text("utf-8")),
    }
    (output / "provenance.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    print("Reproduced exact-source findings; output:", output / "provenance.json")


if __name__ == "__main__":
    main()
