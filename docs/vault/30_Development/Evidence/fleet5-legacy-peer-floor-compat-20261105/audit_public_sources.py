"""Read-only allowlisted public Git object hash/function audit; no runtime probe."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).with_name("public-source-index.json")
COMMITS = {
    "source03": "03e17c31cf535008d39534aaa80d3ae274bd75cc",
    "executorB5": "b5b8ca68398517f6227a81caac02654a848c8b1d",
    "accepted2fb": "2fb52bbe5e500354b323eb8e46d5aa5066690d2d",
    "nativeFe7": "fe7ebeff1f695e0744a7f25eace52c7321dcc1d7",
}
FILES = {
    "services/node-agent/runtime/journal.go": ["PinPeerPolicy"],
    "services/node-agent/transport/trust.go": ["NewAuthority", "policy", "Authorize"],
    "services/node-agent/cmd/inv-node/main.go": ["run"],
    "deploy/lan/worker_leaf_rotation.py": ["_policy", "validate_bundle", "install", "finalize", "docker_restart", "main"],
    "deploy/lan/worker_config.py": ["credential_archive", "install_files", "check_running"],
    "tools/lan_pilot.py": ["_write_rotation_public_material", "prepare_leaf_rotation", "prepare_leaf_rotation_batch", "commit_leaf_rotation_batch"],
    "deploy/lan/leaf_rotation_standalone_runtime.py": ["run_worker", "main"],
    "deploy/lan/leaf-rotation-runtime-lock.json": [],
    "deploy/lan/prepare-leaf-rotation-runtime.sh": [],
    "deploy/lan/README.md": [],
    "tools/check_leaf_rotation_standalone_lifecycle.py": ["main"],
}
B5_ONLY = {
    "tools/scheduled_leaf_renewal.py": ["load_plan", "_command", "_run", "execute"],
    "deploy/lan/Invoke-ScheduledLeafRenewal.ps1": [],
    "deploy/lan/Register-LeafRenewalTask.ps1": [],
}


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} exit {result.returncode}: {result.stderr.decode('utf-8', 'replace')}")
    return result.stdout


def row(commit, path, names):
    raw = git("cat-file", "blob", f"{commit}:{path}")
    text = raw.decode("utf-8")
    functions = {}
    if path.endswith(".py"):
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
                segment = ast.get_source_segment(text, node)
                functions[node.name] = dict(start=node.lineno, end=node.end_lineno,
                    sha256=hashlib.sha256(segment.encode()).hexdigest())
    elif path.endswith(".go"):
        matches = list(re.finditer(r"(?m)^func (?:\([^\n]+?\) )?(\w+)\(", text))
        for index, match in enumerate(matches):
            name = match.group(1)
            if name in names:
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                segment = text[match.start():end].rstrip()
                functions[name] = dict(start=text.count("\n", 0, match.start()) + 1,
                    end=text.count("\n", 0, match.start()) + len(segment.splitlines()),
                    sha256=hashlib.sha256(segment.encode()).hexdigest())
    return dict(path=path, gitBlob=git("rev-parse", f"{commit}:{path}").decode().strip(),
        sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), functions=functions,
        observerFlagPresent="observe-peer-policy-floor" in text)


def main():
    result = dict(schemaVersion="fleet5-public-source-compat:1", kind="source-only-no-execution",
        base="9ec6d6bf4697745bfe41602bb720473b1ff9b22f", commits={})
    for label, commit in COMMITS.items():
        paths = {**FILES, **(B5_ONLY if label == "executorB5" else {})}
        result["commits"][label] = dict(sha=commit, files=[row(commit, p, n) for p, n in paths.items()])
    def item(label, path):
        return next(r for r in result["commits"][label]["files"] if r["path"] == path)
    assertions = {}
    for path in list(FILES)[:3]:
        assertions[path + ":all-four-exact-bytes"] = len({item(label, path)["sha256"] for label in COMMITS}) == 1
    for name in ("_write_rotation_public_material", "prepare_leaf_rotation"):
        assertions[name + ":all-four-exact-function"] = len({item(label, "tools/lan_pilot.py")["functions"][name]["sha256"] for label in COMMITS}) == 1
    assertions["source03-B5-exact-worker"] = item("source03", "deploy/lan/worker_leaf_rotation.py")["sha256"] == item("executorB5", "deploy/lan/worker_leaf_rotation.py")["sha256"]
    assertions["all-four-no-observer-flag"] = not any(item(label, "services/node-agent/cmd/inv-node/main.go")["observerFlagPresent"] for label in COMMITS)
    source03_schedule_paths = git("ls-tree", "-r", "--name-only", COMMITS["source03"], "--", *B5_ONLY).decode().splitlines()
    result["source03SchedulePaths"] = source03_schedule_paths
    assertions["source03-lacks-B5-schedule-paths"] = source03_schedule_paths == []
    result["assertions"] = assertions
    if not all(assertions.values()):
        raise ValueError("Source equivalence assertion failed; inspect public objects")
    proof_root = "docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/hosted-native-peer-phase/"
    result["existingNativeProof"] = []
    for name in ("go-events.jsonl", "native-go-result.json", "publication-receipt.json"):
        path = proof_root + name
        raw = git("cat-file", "blob", f"5023ce7d72b7f13431cb6a7182e2677eb6926662:{path}")
        result["existingNativeProof"].append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(),
            gitBlob=git("rev-parse", f"5023ce7d72b7f13431cb6a7182e2677eb6926662:{path}").decode().strip()))
        if name == "native-go-result.json":
            proof = json.loads(raw)
            result["existingNativeProofResult"] = proof
            if proof["completedNormalCycles"] != 0 or proof["sameVersionDifferentHashFinalRejections"] != 2 or proof["runtimeGOOS"] != "linux":
                raise ValueError("Existing native proof result differs")
        elif name == "publication-receipt.json":
            proof = json.loads(raw)
            result["existingNativeProofPublication"] = {k: proof[k] for k in ("sourceSHA", "headSHA", "goTestExit", "classification", "proofValid")}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    for path in list(FILES)[:5]:
        print(path)
        for label, data in result["commits"].items():
            item = next(r for r in data["files"] if r["path"] == path)
            print(label, item["sha256"], json.dumps(item["functions"], sort_keys=True))
    print(f"wrote {OUT.relative_to(ROOT)}; source reads only")


if __name__ == "__main__":
    main()
