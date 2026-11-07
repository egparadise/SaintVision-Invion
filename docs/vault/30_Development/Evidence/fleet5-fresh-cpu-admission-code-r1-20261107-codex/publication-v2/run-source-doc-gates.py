"""Serial source/docs-only gates; actual exits and byte-exact UTF-8 logs."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent / "gates"
OUT.mkdir(exist_ok=True)
STATE = Path("D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json")
PYTHON = "D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe"
BASE = "7033778ad3d2bc284e36f7e29be7597dbb7d9f23"


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def capture_state(label):
    raw = STATE.read_bytes()
    stat = STATE.stat()
    json.loads(raw)
    (OUT / (label + ".json")).write_bytes(raw)
    return {"path": str(STATE), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "mtimeNs": stat.st_mtime_ns, "capturedAtKST": now(),
            "copy": (OUT / (label + ".json")).relative_to(ROOT).as_posix()}


commands = [
    ("docs", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_docs.py"]),
    ("ontology", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_ontology.py"]),
    ("ontology-generation", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_ontology_generation.py"]),
    ("contract-bindings", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_contract_bindings.py"]),
    ("frontend-integrity", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_frontend_integrity.py"]),
    ("path-ratchet", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_doc_path_citations.py",
                      "--ratchet", "--base-ref", BASE]),
    ("single-source-ratchet", [PYTHON, "-I", "-B", "-X", "utf8", "tools/check_doc_single_source.py", "--ratchet"]),
    ("canonical-sync-check", [PYTHON, "-I", "-B", "-X", "utf8", "tools/sync_obsidian.py", "--check",
                              "--state", str(STATE), "--conflicts-out", str(OUT / "sync-conflicts.json")]),
    ("diff-check", ["git", "diff", "--check"]),
]
results = []
for name, command in commands:
    record = {"name": name, "command": command, "startedAtKST": now()}
    if name == "canonical-sync-check":
        record["canonicalFullStateBefore"] = capture_state("canonical-state-before-check")
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    record["exitCode"] = result.returncode
    record["endedAtKST"] = now()
    for stream, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
        raw.decode("utf-8")  # byte IO, never a locale-dependent PowerShell redirect
        path = OUT / (name + "." + stream + ".txt")
        path.write_bytes(raw)
        record[stream] = {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest()}
    if name == "canonical-sync-check":
        record["canonicalFullStateAfter"] = capture_state("canonical-state-after-check")
        record["stateHashesEqual"] = (record["canonicalFullStateBefore"]["sha256"]
                                       == record["canonicalFullStateAfter"]["sha256"])
        record["stateProvenance"] = "Exact Root-specified canonical state; CHECK only; Root may write concurrently"
    results.append(record)
    (OUT / "results.json").write_text(json.dumps({"kind": "ACTUAL_SOURCE_DOC_GATE_EXITS_NOT_PRODUCT_TESTS",
        "base": BASE, "results": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": name, "exitCode": result.returncode,
                      "rawStdout": record["stdout"]["path"], "rawStderr": record["stderr"]["path"]}), flush=True)
    if result.returncode:
        print("STOP: failed gate preserved; no stage/push/CI permitted", flush=True)
        sys.exit(result.returncode)
