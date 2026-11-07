"""Source/data/Git-only WIP inspection: no application import or test execution."""

import ast
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
BASE = "7033778ad3d2bc284e36f7e29be7597dbb7d9f23"
BRANCH = "agent/codex/fleet5-fresh-cpu-admission-r1-20261107"
FILES = [
    "services/control-plane/src/inv/fresh_cpu_admission.py",
    "tools/fresh_cpu_admission.py",
    "tests/core/test_fresh_cpu_admission.py",
    "tests/core/test_fresh_cpu_admission_cli.py",
]
PREFIX = OUT.relative_to(ROOT).as_posix() + "/"
HISTORY = "docs/vault/30_Development/History/2026-11-07_FLEET5_Fresh_CPU_Admission_Code_R1_Codex.md"
OLD_HISTORY = "docs/vault/30_Development/History/2026-11-07_FLEET5_K2_H12_Signature_Code_Publication_Codex.md"
OLD_PREFIX = "docs/vault/30_Development/Evidence/fleet5-k2-h12-signature-code-r1-20261107-codex/publication/post-ci/"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    assert result.returncode == 0, "public Git source inspection failed"
    return result.stdout


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


assert git("rev-parse", "HEAD").decode().strip() == BASE
assert git("branch", "--show-current").decode().strip() == BRANCH
assert not git("diff", "--cached", "--name-only").strip(), "no staging is authorized"
assert not git("diff", "--name-only", "HEAD", "--", "services", "tools", "tests").strip()
assert not git("ls-tree", "-r", "--name-only", BASE, "--", *FILES).strip()
tracked_changes = git("diff", "--name-only", "HEAD").decode().splitlines()
assert tracked_changes == [OLD_HISTORY], "unexpected tracked residue or existing-file edit"
git("diff", "--check")

attributes = git("check-attr", "filter", "eol", "--", *FILES).decode()
assert all(line.endswith(("filter: unspecified", "eol: lf")) for line in attributes.splitlines())
records, tests, patch = [], [], []
for name in FILES:
    raw = (ROOT / name).read_bytes()
    text = raw.decode("utf-8")
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert all(line == line.rstrip() for line in text.splitlines())
    tree = ast.parse(text, filename=name)
    canonical = raw.replace(b"\r\n", b"\n")
    git_blob = git("hash-object", "--path=" + name, name).decode().strip()
    assert git_blob == hashlib.sha1(b"blob " + str(len(canonical)).encode() + b"\0" + canonical).hexdigest()
    records.append({"path": name, "preimageAt703": "ABSENT", "bytes": len(raw),
                    "workingSHA256": digest(raw), "gitCanonicalSHA256": digest(canonical),
                    "gitBlobSHA1": git_blob, "lineCount": len(text.splitlines()),
                    "ast": "PASS_PARSE_ONLY_NO_IMPORT_OR_EXECUTION"})
    patch.extend(difflib.unified_diff([], text.splitlines(keepends=True),
                                    fromfile="/dev/null", tofile="b/" + name))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        count, postgres = 1, False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute) and decorator.attr == "postgres":
                postgres = True
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == "parametrize":
                    # Count source entries without evaluating strings/expressions.
                    assert isinstance(decorator.args[1], (ast.List, ast.Tuple))
                    count *= len(decorator.args[1].elts)
        tests.append({"path": name, "function": node.name, "staticParameterExpansion": count,
                      "mandatoryPostgresFixture": postgres, "execution": "NOT_RUN"})
(OUT / "four-file-wip.patch").write_text("".join(patch), encoding="utf-8")

dependencies = [
    "services/control-plane/src/inv/dispatch.py",
    "tests/core/test_delivery_operation_origin.py",
    "services/control-plane/src/inv/errors.py",
    "services/control-plane/src/inv/tooling.py",
    "services/control-plane/src/inv/node_channels.py",
    "services/control-plane/src/inv/capacity.py",
    "services/control-plane/src/inv/migrations/0001_core.sql",
    "services/control-plane/src/inv/migrations/0005_node_channels.sql",
    "services/control-plane/src/inv/migrations/0006_control_api.sql",
    "services/control-plane/src/inv/migrations/0019_runtime_role.sql",
    "services/control-plane/src/inv/migrations/0021_business_kernel.sql",
    "services/control-plane/src/inv/migrations/0022_node_containment.sql",
    "src/saintvision/db/models/identity.py", "tests/conftest.py", "pyproject.toml", ".gitattributes",
]
dependency_records = []
for name in dependencies:
    canonical = git("show", BASE + ":" + name)
    working = (ROOT / name).read_bytes()
    assert working.replace(b"\r\n", b"\n") == canonical
    dependency_records.append({"path": name, "sha": BASE, "canonicalSHA256": digest(canonical),
                               "workingSHA256": digest(working), "unchanged": True})
assert dependency_records[0]["canonicalSHA256"] == "82f029614537eb5bab56934e4b6736fe3dd52ece54b9b9a3996815b131e41de4"
assert dependency_records[1]["canonicalSHA256"] == "3dacdb63f83ab1d8075ddcbe422d82daad20bd56f643adee0fc7ae97715925d2"

status = git("status", "--porcelain=v1", "-uall").decode().splitlines()
for line in status:
    path = line[3:]
    assert path in FILES + [HISTORY, OLD_HISTORY] or path.startswith((PREFIX, OLD_PREFIX)), "unexpected scope"
verification = {
    "kind": "STATIC_SOURCE_CHECK_ONLY_NOT_PRODUCT_TEST_EVIDENCE",
    "recordedAtKST": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "exitCode": 0, "astParsedFiles": len(records), "utf8LfNewlineWhitespace": "PASS",
    "trackedDiffCheckExit": 0, "scope": "PASS", "indexEmpty": True,
    "allFourPreimages": "ABSENT_AT_EXACT_703", "dependencyFilesUnchanged": len(dependency_records),
    "plannedTestFunctions": len(tests), "staticParameterExpansionNotPytestCollection": sum(t["staticParameterExpansion"] for t in tests),
    "plannedPostgresParameterExpansionNotExecution": sum(t["staticParameterExpansion"] for t in tests if t["mandatoryPostgresFixture"]),
    "tests": tests,
    "notRun": ["app imports", "crypto", "pytest", "PostgreSQL", "CLI", "Go", "network/runtime",
               "required delivery gates", "stage", "commit", "push", "CI", "independent review"],
}
(OUT / "wip-static-verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")

manifest = {
    "kind": "FOUR_NEW_FILES_UNCOMMITTED_WIP_HOLD_NOT_PUBLICATION_OR_RUNTIME_ACCEPTANCE",
    "card": "FLEET5-FRESH-CPU-ADMISSION-CODE-R1-20261107",
    "taskId": "task_a95ef3d8ccce", "dispatchId": "ctx_ed23b4a777d0",
    "base": BASE, "branch": BRANCH, "files": records, "dependencies": dependency_records,
    "statusBeforeManifestWrite": status,
    "preservedExcludedResidue": {"history": OLD_HISTORY, "historyCurrentSHA256": digest((ROOT / OLD_HISTORY).read_bytes()),
                                  "postCiPrefix": OLD_PREFIX,
                                  "frozenPriorReportSHA256": "b944af8919538b295dd162e1f0680580931dfc01589073ddefec693c911a718c",
                                  "notStagedNotRecopied": True},
    "holds": ["Root dependency703 Core/Backend and integration-review disposition pending at grant",
              "libpq credential/certificate data-file boundary requires Root interpretation",
              "all product tests/required gates/CI/review NOT_RUN or PENDING",
              "no publication or live admission grant"],
    "artifacts": [],
}
for path in sorted(OUT.iterdir()):
    if path.name == "wip-manifest.json" or not path.is_file():
        continue
    raw = path.read_bytes()
    if path.suffix == ".json":
        json.loads(raw)
    manifest["artifacts"].append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": digest(raw)})
raw = (ROOT / HISTORY).read_bytes()
manifest["artifacts"].append({"path": HISTORY, "bytes": len(raw), "sha256": digest(raw)})
(OUT / "wip-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verification": verification | {"tests": "SEE_ARTIFACT"},
                  "files": records, "manifestSHA256": digest((OUT / "wip-manifest.json").read_bytes())}, indent=2))
