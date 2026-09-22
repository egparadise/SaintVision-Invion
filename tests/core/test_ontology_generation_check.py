from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools" / "check_ontology_generation.py"


class OntologyGenerationCheckTests(unittest.TestCase):
    def make_checkout(self) -> Path:
        temp = Path(tempfile.mkdtemp(prefix="ontology-generation-test-"))
        shutil.copytree(ROOT / "tools", temp / "tools")
        shutil.copytree(ROOT / "docs" / "sources", temp / "docs" / "sources")
        shutil.copy2(ROOT / "docs" / "task-registry.json", temp / "docs" / "task-registry.json")
        shutil.copytree(ROOT / "ontology", temp / "ontology")
        shutil.copytree(ROOT / "docs" / "vault" / "50_Ontology", temp / "docs" / "vault" / "50_Ontology")
        return temp

    def run_checker(self, checkout: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--root", str(checkout)],
            text=True,
            capture_output=True,
        )

    def test_registry_status_change_without_regeneration_is_detected(self) -> None:
        checkout = self.make_checkout()
        try:
            registry_path = checkout / "docs" / "task-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            task = next(item for item in registry["tasks"] if item["task_id"] == "S01-DB")
            task["status"] = "review"
            registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = self.run_checker(checkout)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("S01-DB", result.stdout)
            self.assertIn("missing", result.stdout)
        finally:
            shutil.rmtree(checkout)

    def test_jsonld_serialization_order_only_passes(self) -> None:
        checkout = self.make_checkout()
        try:
            path = checkout / "ontology" / "example.jsonld"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["@graph"] = list(reversed(payload["@graph"]))
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = self.run_checker(checkout)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(checkout)


if __name__ == "__main__":
    unittest.main()
