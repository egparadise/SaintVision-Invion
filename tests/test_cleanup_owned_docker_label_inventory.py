"""Keep temporary Docker resource labels aligned with the cleanup backstop."""

from __future__ import annotations

import re
from pathlib import Path
import subprocess

from tools.cleanup_owned_docker import OWNERSHIP_LABELS


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ps1", ".sh", ".mjs", ".js", ".yml", ".yaml"}
LABEL_LITERAL = re.compile(r"ai\.saintvision\.[A-Za-z0-9_.-]+")

# These labels identify runtime/workspace state or metadata and must never make
# a resource eligible for age-based test cleanup. Any new source label must be
# explicitly classified here or added to cleanup_owned_docker.OWNERSHIP_LABELS.
NON_CLEANUP_LABELS = {
    "ai.saintvision.command",
    "ai.saintvision.config",
    "ai.saintvision.created-by",
    "ai.saintvision.node",
    "ai.saintvision.output",
    "ai.saintvision.pilot",
    "ai.saintvision.storage-replace",
    "ai.saintvision.supervisor",
    "ai.saintvision.upgrade",
}


def test_all_repository_docker_labels_have_an_explicit_cleanup_policy():
    source_labels = set()
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    for filename in tracked:
        if not filename:
            continue
        path = ROOT / filename
        if path.suffix in SOURCE_SUFFIXES:
            source_labels.update(LABEL_LITERAL.findall(path.read_text(encoding="utf-8")))

    classified = set(OWNERSHIP_LABELS) | NON_CLEANUP_LABELS
    assert source_labels == classified, (
        "Docker ownership label inventory and cleanup policy differ; "
        f"unclassified={sorted(source_labels - classified)}, "
        f"stale={sorted(classified - source_labels)}"
    )

    # The recovery archive resources were the reported gap. Keep both the
    # container and network labels eligible for the age-gated cleanup backstop.
    assert {"ai.saintvision.rpo-test", "ai.saintvision.rpo-network"} <= set(OWNERSHIP_LABELS)
