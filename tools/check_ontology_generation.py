"""Compare generated ontology artifacts by RDF graph meaning, not serialization order."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from rdflib import Graph

ARTIFACTS = (
    Path("ontology/example.ttl"),
    Path("ontology/example.jsonld"),
    Path("docs/vault/50_Ontology/Release-0.2.0/example.ttl"),
    Path("docs/vault/50_Ontology/Release-0.2.0/example.jsonld"),
)


def graph(path: Path) -> Graph:
    fmt = "json-ld" if path.suffix == ".jsonld" else "turtle"
    return Graph().parse(path, format=fmt)


def compact(term: object) -> str:
    return str(term.n3()) if hasattr(term, "n3") else str(term)


def report_differences(expected: Graph, actual: Graph, label: str) -> int:
    missing = set(expected) - set(actual)
    unexpected = set(actual) - set(expected)
    if not missing and not unexpected:
        return 0
    print(f"FAIL: {label} graph differs (missing={len(missing)}, unexpected={len(unexpected)})")
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for subject, predicate, obj in sorted(missing, key=lambda triple: tuple(map(str, triple))):
        grouped["missing"].append((f"{compact(subject)} {compact(predicate)}", compact(obj)))
    for subject, predicate, obj in sorted(unexpected, key=lambda triple: tuple(map(str, triple))):
        grouped["unexpected"].append((f"{compact(subject)} {compact(predicate)}", compact(obj)))
    for kind in ("missing", "unexpected"):
        for key, obj in grouped[kind]:
            print(f"  {kind}: {key} -> {obj}")
    return 1


def generated_root(repo: Path, temp: Path) -> None:
    (temp / "tools").mkdir(parents=True)
    (temp / "docs" / "sources").mkdir(parents=True)
    shutil.copy2(repo / "tools" / "generate_ontology.py", temp / "tools" / "generate_ontology.py")
    shutil.copytree(repo / "docs" / "sources" / "50_Ontology", temp / "docs" / "sources" / "50_Ontology")
    shutil.copy2(repo / "docs" / "task-registry.json", temp / "docs" / "task-registry.json")
    result = subprocess.run(
        [sys.executable, str(temp / "tools" / "generate_ontology.py")],
        cwd=temp,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="repository root; defaults to this checkout")
    args = parser.parse_args()
    repo = (args.root or Path(__file__).resolve().parents[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="ontology-generation-") as directory:
        expected_root = Path(directory)
        generated_root(repo, expected_root)
        failures = 0
        for relative in ARTIFACTS:
            expected = expected_root / relative
            actual = repo / relative
            if not actual.is_file():
                print(f"FAIL: missing tracked artifact {relative}")
                failures += 1
                continue
            failures += report_differences(graph(expected), graph(actual), str(relative))
    if failures:
        return 1
    print(f"PASS: {len(ARTIFACTS)} ontology artifacts are graph-equivalent to a fresh generation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
