"""Bind source-only clarification to frozen WIP01 without executing modules."""

import ast
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
ORIGINAL = OUT.parent
BASE = "7033778ad3d2bc284e36f7e29be7597dbb7d9f23"
BRANCH = "agent/codex/fleet5-fresh-cpu-admission-r1-20261107"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    assert result.returncode == 0
    return result.stdout


raw = (ORIGINAL / "wip-manifest.json").read_bytes()
assert sha(raw) == "c584f14d7bd6cc32fa184891ff3cf6bdbbc7032cdd3fc9a41b9f29ea3f9e8921"
original = json.loads(raw)
assert git("rev-parse", "HEAD").decode().strip() == BASE
assert git("branch", "--show-current").decode().strip() == BRANCH
assert not git("diff", "--cached", "--name-only").strip()
original_sources = {}
current = None
for line in (ORIGINAL / "four-file-wip.patch").read_text(encoding="utf-8").splitlines(keepends=True):
    if line.startswith("+++ b/"):
        current = line[len("+++ b/"):].strip()
        original_sources[current] = []
    elif current is not None and line.startswith("+"):
        original_sources[current].append(line[1:])
for name in original_sources:
    original_sources[name] = "".join(original_sources[name]).encode()


def without_module_docstring(raw):
    tree = ast.parse(raw)
    if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        if isinstance(tree.body[0].value.value, str):
            tree.body.pop(0)
    return tree


records, tests, changes = [], [], []
for record in original["files"]:
    name = record["path"]
    old, new = original_sources[name], (ROOT / name).read_bytes()
    assert sha(old) == record["workingSHA256"]
    assert b"\r" not in new and new.endswith(b"\n")
    assert all(line == line.rstrip() for line in new.decode().splitlines())
    before, after = ast.parse(old), ast.parse(new)
    if name == "tests/core/test_fresh_cpu_admission.py":
        assert old == new
        proof = "BYTE_IDENTICAL_TO_FROZEN_WIP01"
    elif name.endswith("test_fresh_cpu_admission_cli.py"):
        assert len(after.body) == len(before.body) + 1
        assert ast.dump(ast.Module(body=after.body[:-1], type_ignores=[])) == ast.dump(before)
        assert isinstance(after.body[-1], ast.FunctionDef)
        assert after.body[-1].name == "test_trusted_operator_driver_profile_is_forwarded_without_rewrite"
        proof = "ONLY_ONE_APPENDED_SYNTHETIC_TRUST_PREMISE_TEST"
    else:
        assert ast.dump(without_module_docstring(old)) == ast.dump(without_module_docstring(new))
        proof = "EXECUTABLE_AST_IDENTICAL_ONLY_MODULE_DOCSTRING_AND_COMMENTS_CHANGED"
    blob = git("hash-object", "--path=" + name, name).decode().strip()
    assert blob == hashlib.sha1(b"blob " + str(len(new)).encode() + b"\0" + new).hexdigest()
    records.append({"path": name, "preimageAt703": "ABSENT", "originalWip01SHA256": sha(old),
                    "workingSHA256": sha(new), "gitCanonicalSHA256": sha(new), "bytes": len(new),
                    "gitBlobSHA1": blob, "changeProof": proof})
    changes.extend(difflib.unified_diff(old.decode().splitlines(keepends=True), new.decode().splitlines(keepends=True),
                                      fromfile="wip01/" + name, tofile="publication-v2/" + name, n=0))
    for node in after.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        count, pg = 1, False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute) and decorator.attr == "postgres":
                pg = True
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == "parametrize":
                    assert isinstance(decorator.args[1], (ast.List, ast.Tuple))
                    count *= len(decorator.args[1].elts)
        tests.append({"path": name, "name": node.name, "staticExpansion": count,
                      "mandatoryPostgres": pg, "execution": "NOT_RUN_ON_MAIN"})
(OUT / "wording-and-trust-test-only.patch").write_text("".join(changes), encoding="utf-8")
for item in original["dependencies"]:
    assert sha(git("show", BASE + ":" + item["path"])) == item["canonicalSHA256"]
    assert sha((ROOT / item["path"]).read_bytes().replace(b"\r\n", b"\n")) == item["canonicalSHA256"]
for item in original["artifacts"]:
    path = ROOT / item["path"]
    if path.name.endswith("_Fresh_CPU_Admission_Code_R1_Codex.md"):
        path = OUT / "wip01-history-original.txt"
    assert sha(path.read_bytes()) == item["sha256"], "original raw WIP evidence changed"
assert not git("diff", "--name-only", "HEAD", "--", "services", "tools", "tests").strip()
status = git("status", "--porcelain=v1", "-uall").decode().splitlines()
files = [item["path"] for item in records]
prefix = ORIGINAL.relative_to(ROOT).as_posix() + "/"
history = "docs/vault/30_Development/History/2026-11-07_FLEET5_Fresh_CPU_Admission_Code_R1_Codex.md"
old = original["preservedExcludedResidue"]
assert sha((ROOT / old["history"]).read_bytes()) == old["historyCurrentSHA256"]
for line in status:
    name = line[3:]
    assert name in files + [history, old["history"]] or name.startswith((prefix, old["postCiPrefix"]))
assert not git("ls-tree", "-r", "--name-only", BASE, "--", *files, prefix, history).strip()
manifest = {
    "kind": "PRECOMMIT_SOURCE_CANDIDATE_V2_NOT_PRODUCT_OR_RUNTIME_ACCEPTANCE",
    "taskId": "task_a95ef3d8ccce", "dispatchId": "ctx_ed23b4a777d0",
    "card": "FLEET5-FRESH-CPU-ADMISSION-CODE-R1-20261107", "owner": "Codex",
    "independentCodeReview": "PENDING_ACTUAL_CLAUDE_THROUGH_ROOT",
    "recordedAtKST": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "rootGrant": "msg_97efddc65fbd", "base": BASE, "branch": BRANCH,
    "originalWip01ManifestSHA256": sha(raw), "originalRawArtifactsVerifiedUnchanged": True,
    "files": records, "existing703SourceTestChanges": [], "preservedExcludedResidue": old,
    "statusBeforeManifestWrite": status,
    "plannedTestFunctions": len(tests), "staticExpansionNotActualCollection": sum(t["staticExpansion"] for t in tests),
    "plannedMandatoryPgExpansionNotActualCollection": sum(t["staticExpansion"] for t in tests if t["mandatoryPostgres"]),
    "tests": tests, "driverTrustPremise": "TRUSTED_OPERATOR_PROFILE_NOT_PUBLIC_REQUEST_NOT_A_DSN_OR_FILESYSTEM_SANDBOX",
    "productExecutionOnMain": "NOT_RUN_PROHIBITED", "candidateCommitAndCi": "PENDING_NORMAL_PUBLICATION",
    "rootJointDependencyReview": "PENDING_NOT_INFERRED_FROM_CORE_SUCCESS",
}
(OUT / "candidate-manifest-v2.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": records, "staticTestsNotExecution": manifest["staticExpansionNotActualCollection"],
                  "plannedPgNotExecution": manifest["plannedMandatoryPgExpansionNotActualCollection"],
                  "manifestSHA256": sha((OUT / "candidate-manifest-v2.json").read_bytes()),
                  "scopeAndOriginalEvidence": "PASS"}, indent=2))
