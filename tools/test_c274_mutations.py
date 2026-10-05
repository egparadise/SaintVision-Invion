#!/usr/bin/env python3
"""
tools/test_c274_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting Card 274 Node & Placement Detail components:
  - apps/web/src/features/nodes/NodeDetail.tsx (W1-W14)
  - apps/web/src/features/placement/PlacementExplainView.tsx (W15-W28)
  - apps/web/src/features/placement/ResourceTopologyGraph.tsx (W29-W40)

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant and verify byte equality + git diff 0.
- Sequential execution only (under 1GB memory).
- 100% kill rate (40/40) required.
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
APPS_WEB = WORKTREE_ROOT / "apps" / "web"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c274_mutation_results.json"

TARGET_FILES = {
    "NodeDetail": APPS_WEB / "src" / "features" / "nodes" / "NodeDetail.tsx",
    "PlacementExplainView": APPS_WEB / "src" / "features" / "placement" / "PlacementExplainView.tsx",
    "ResourceTopologyGraph": APPS_WEB / "src" / "features" / "placement" / "ResourceTopologyGraph.tsx",
}

MUTANTS = [
    # Batch 1 (W1-W14): NodeDetail styling, status contracts, and literals
    {
        "id": "W1",
        "file": "NodeDetail",
        "desc": "NodeDetail: observation callout bgVar==colorVar collision (backgroundColor: var(--color-status-unknown))",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-lg)',\n            border: '1px solid var(--color-status-unknown)',\n            color: 'var(--color-status-unknown)',",
        "replacement": "            backgroundColor: 'var(--color-status-unknown)',\n            borderRadius: 'var(--radius-lg)',\n            border: '1px solid var(--color-status-unknown)',\n            color: 'var(--color-status-unknown)',",
    },
    {
        "id": "W2",
        "file": "NodeDetail",
        "desc": "NodeDetail: observation callout low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-lg)',\n            border: '1px solid var(--color-status-unknown)',\n            color: 'var(--color-status-unknown)',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-lg)',\n            border: '1px solid var(--color-status-unknown)',\n            color: 'var(--color-text-inverse)',",
    },
    {
        "id": "W3",
        "file": "NodeDetail",
        "desc": "NodeDetail: observation callout border==bgVar collision (border: 1px solid var(--color-bg-subtle))",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-lg)',\n            border: '1px solid var(--color-status-unknown)',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-lg)',\n            border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "W4",
        "file": "NodeDetail",
        "desc": "NodeDetail: resource alert bgVar==colorVar collision (backgroundColor: var(--color-status-lost))",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            border: '1px solid var(--color-status-lost)',\n            color: 'var(--color-status-lost)',",
        "replacement": "            backgroundColor: 'var(--color-status-lost)',\n            borderRadius: 'var(--radius-md)',\n            border: '1px solid var(--color-status-lost)',\n            color: 'var(--color-status-lost)',",
    },
    {
        "id": "W5",
        "file": "NodeDetail",
        "desc": "NodeDetail: resource alert low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            border: '1px solid var(--color-status-lost)',\n            color: 'var(--color-status-lost)',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            border: '1px solid var(--color-status-lost)',\n            color: 'var(--color-text-inverse)',",
    },
    {
        "id": "W6",
        "file": "NodeDetail",
        "desc": "NodeDetail: resource alert border==bgVar collision (border: 1px solid var(--color-bg-subtle))",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            border: '1px solid var(--color-status-lost)',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "W7",
        "file": "NodeDetail",
        "desc": "NodeDetail: schedulable box observationOnly border mutated to subtle",
        "target": "border: `1px solid ${node.observationOnly ? 'var(--color-status-unknown)' : 'var(--color-status-online)'}`,",
        "replacement": "border: `1px solid ${node.observationOnly ? 'var(--color-border-subtle)' : 'var(--color-status-online)'}`,",
    },
    {
        "id": "W8",
        "file": "NodeDetail",
        "desc": "NodeDetail: schedulable box normal border mutated to subtle",
        "target": "border: `1px solid ${node.observationOnly ? 'var(--color-status-unknown)' : 'var(--color-status-online)'}`,",
        "replacement": "border: `1px solid ${node.observationOnly ? 'var(--color-status-unknown)' : 'var(--color-border-subtle)'}`,",
    },
    {
        "id": "W9",
        "file": "NodeDetail",
        "desc": "NodeDetail: schedulable box label color mutated to subtle",
        "target": "data-testid=\"node-detail-schedulable-label\"\n                style={{ color: node.observationOnly ? 'var(--color-status-unknown)' : 'var(--color-status-online)', marginBottom: '2px', fontWeight: 600 }}",
        "replacement": "data-testid=\"node-detail-schedulable-label\"\n                style={{ color: 'var(--color-bg-subtle)', marginBottom: '2px', fontWeight: 600 }}",
    },
    {
        "id": "W10",
        "file": "NodeDetail",
        "desc": "NodeDetail: timeline status color mutated to text-secondary",
        "target": "                  color: nodeStatusConfig.color,\n                  fontWeight: 600,",
        "replacement": "                  color: 'var(--color-text-secondary)',\n                  fontWeight: 600,",
    },
    {
        "id": "W11",
        "file": "NodeDetail",
        "desc": "NodeDetail: timeline corrupt status label fallback bypassed",
        "target": ": `Heartbeat FAILED (${nodeStatusConfig.label})`}",
        "replacement": ": 'Heartbeat FAILED (Offline)'}",
    },
    {
        "id": "W12",
        "file": "NodeDetail",
        "desc": "NodeDetail: observation callout raw literal regression rgba(210, 153, 34, 0.12)",
        "target": "          data-testid=\"node-detail-observation-callout\"\n          style={{\n            marginBottom: '20px',\n            padding: '16px 20px',\n            backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "          data-testid=\"node-detail-observation-callout\"\n          style={{\n            marginBottom: '20px',\n            padding: '16px 20px',\n            backgroundColor: 'rgba(210, 153, 34, 0.12)',",
    },
    {
        "id": "W13",
        "file": "NodeDetail",
        "desc": "NodeDetail: resource alert raw literal regression rgba(248, 81, 73, 0.1)",
        "target": "          data-testid=\"node-resource-usage-error\"\n          role=\"alert\"\n          style={{\n            marginBottom: '20px',\n            padding: '16px 20px',\n            backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "          data-testid=\"node-resource-usage-error\"\n          role=\"alert\"\n          style={{\n            marginBottom: '20px',\n            padding: '16px 20px',\n            backgroundColor: 'rgba(248, 81, 73, 0.1)',",
    },
    {
        "id": "W14",
        "file": "NodeDetail",
        "desc": "NodeDetail: schedulable box raw literal regression rgba(210, 153, 34, 0.15)",
        "target": "              data-testid=\"node-detail-schedulable-box\"\n              style={{\n                padding: '10px',\n                backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "              data-testid=\"node-detail-schedulable-box\"\n              style={{\n                padding: '10px',\n                backgroundColor: node.observationOnly ? 'rgba(210, 153, 34, 0.15)' : 'var(--color-bg-subtle)',",
    },

    # Batch 2 (W15-W28): PlacementExplainView styling and literals
    {
        "id": "W15",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: simulation badge bgVar==colorVar collision",
        "target": "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-status-unknown)',\n                border: '1px solid var(--color-status-unknown)',",
        "replacement": "                backgroundColor: 'var(--color-status-unknown)',\n                color: 'var(--color-status-unknown)',\n                border: '1px solid var(--color-status-unknown)',",
    },
    {
        "id": "W16",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: simulation badge low-contrast text mutation",
        "target": "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-status-unknown)',\n                border: '1px solid var(--color-status-unknown)',",
        "replacement": "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-text-inverse)',\n                border: '1px solid var(--color-status-unknown)',",
    },
    {
        "id": "W17",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: simulation badge border==bg collision",
        "target": "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-status-unknown)',\n                border: '1px solid var(--color-status-unknown)',",
        "replacement": "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-status-unknown)',\n                border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "W18",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: winner banner bgVar==borderColor collision",
        "target": "        data-testid=\"placement-explain-winner-banner\"\n        style={{\n          padding: '16px 20px',\n          borderRadius: 'var(--radius-md)',\n          backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "        data-testid=\"placement-explain-winner-banner\"\n        style={{\n          padding: '16px 20px',\n          borderRadius: 'var(--radius-md)',\n          backgroundColor: 'var(--color-status-online)',",
    },
    {
        "id": "W19",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: winner banner border mutated to border-subtle",
        "target": "border: `1px solid ${selectedNodeId ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
        "replacement": "border: `1px solid ${selectedNodeId ? 'var(--color-border-subtle)' : 'var(--color-status-lost)'}`,",
    },
    {
        "id": "W20",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: winner banner no-winner border mutated to border-subtle",
        "target": "border: `1px solid ${selectedNodeId ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
        "replacement": "border: `1px solid ${selectedNodeId ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,",
    },
    {
        "id": "W21",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: passed candidate badge bgVar==colorVar collision",
        "target": "                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: passed ? 'var(--color-status-online)' : 'var(--color-status-lost)',\n                      border: `1px solid ${passed ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
        "replacement": "                      backgroundColor: passed ? 'var(--color-status-online)' : 'var(--color-bg-subtle)',\n                      color: passed ? 'var(--color-status-online)' : 'var(--color-status-lost)',\n                      border: `1px solid ${passed ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
    },
    {
        "id": "W22",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: rejected candidate badge bgVar==colorVar collision",
        "target": "                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: passed ? 'var(--color-status-online)' : 'var(--color-status-lost)',\n                      border: `1px solid ${passed ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
        "replacement": "                      backgroundColor: !passed ? 'var(--color-status-lost)' : 'var(--color-bg-subtle)',\n                      color: passed ? 'var(--color-status-online)' : 'var(--color-status-lost)',\n                      border: `1px solid ${passed ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
    },
    {
        "id": "W23",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: candidate badge text mutated to text-inverse",
        "target": "color: passed ? 'var(--color-status-online)' : 'var(--color-status-lost)',",
        "replacement": "color: passed ? 'var(--color-text-inverse)' : 'var(--color-status-lost)',",
    },
    {
        "id": "W24",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: candidate badge border mutated to subtle",
        "target": "border: `1px solid ${passed ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
        "replacement": "border: `1px solid ${passed ? 'var(--color-border-subtle)' : 'var(--color-status-lost)'}`,",
    },
    {
        "id": "W25",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: winner score text mutated to text-secondary",
        "target": "color: isWinner ? 'var(--color-status-online)' : 'var(--color-text-primary)',",
        "replacement": "color: isWinner ? 'var(--color-text-secondary)' : 'var(--color-text-primary)',",
    },
    {
        "id": "W26",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: simulation badge raw literal regression (#d97706)",
        "target": "                color: 'var(--color-status-unknown)',\n                border: '1px solid var(--color-status-unknown)',",
        "replacement": "                color: '#d97706',\n                border: '1px solid var(--color-status-unknown)',",
    },
    {
        "id": "W27",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: candidate badge raw literal regression rgba(16, 185, 129, 0.15)",
        "target": "                    data-testid=\"placement-explain-candidate-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 600,\n                      backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                    data-testid=\"placement-explain-candidate-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 600,\n                      backgroundColor: passed ? 'rgba(16, 185, 129, 0.15)' : 'var(--color-bg-subtle)',",
    },
    {
        "id": "W28",
        "file": "PlacementExplainView",
        "desc": "PlacementExplainView: winner banner raw literal regression rgba(16, 185, 129, 0.1)",
        "target": "        data-testid=\"placement-explain-winner-banner\"\n        style={{\n          padding: '16px 20px',\n          borderRadius: 'var(--radius-md)',\n          backgroundColor: 'var(--color-bg-subtle)',\n          border: `1px solid ${selectedNodeId ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
        "replacement": "        data-testid=\"placement-explain-winner-banner\"\n        style={{\n          padding: '16px 20px',\n          borderRadius: 'var(--radius-md)',\n          backgroundColor: selectedNodeId ? 'rgba(16, 185, 129, 0.1)' : 'var(--color-bg-subtle)',\n          border: `1px solid ${selectedNodeId ? 'var(--color-status-online)' : 'var(--color-status-lost)'}`,",
    },

    # Batch 3 (W29-W40): ResourceTopologyGraph styling and literals
    {
        "id": "W29",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: node card background mutated to status-online",
        "target": "                border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,\n                backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,\n                backgroundColor: 'var(--color-status-online)',",
    },
    {
        "id": "W30",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: selected node card border mutated to border-subtle",
        "target": "border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,",
        "replacement": "border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-border-subtle)' : 'var(--color-border-subtle)'}`,",
    },
    {
        "id": "W31",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: fenced node card border mutated to border-subtle",
        "target": "border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,",
        "replacement": "border: `2px solid ${isFenced ? 'var(--color-border-subtle)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,",
    },
    {
        "id": "W32",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: selected badge bgVar==colorVar collision",
        "target": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-online)',\n                      border: '1px solid var(--color-status-online)',\n                    }}",
        "replacement": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-status-online)',\n                      color: 'var(--color-status-online)',\n                      border: '1px solid var(--color-status-online)',\n                    }}",
    },
    {
        "id": "W33",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: selected badge text mutated to text-inverse",
        "target": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-online)',\n                      border: '1px solid var(--color-status-online)',\n                    }}",
        "replacement": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-text-inverse)',\n                      border: '1px solid var(--color-status-online)',\n                    }}",
    },
    {
        "id": "W34",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: selected badge border mutated to border-subtle",
        "target": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-online)',\n                      border: '1px solid var(--color-status-online)',\n                    }}",
        "replacement": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-online)',\n                      border: '1px solid var(--color-border-subtle)',\n                    }}",
    },
    {
        "id": "W35",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: fenced badge bgVar==colorVar collision",
        "target": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-lost)',\n                      border: '1px solid var(--color-status-lost)',\n                    }}",
        "replacement": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-status-lost)',\n                      color: 'var(--color-status-lost)',\n                      border: '1px solid var(--color-status-lost)',\n                    }}",
    },
    {
        "id": "W36",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: fenced badge text mutated to text-inverse",
        "target": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-lost)',\n                      border: '1px solid var(--color-status-lost)',\n                    }}",
        "replacement": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-text-inverse)',\n                      border: '1px solid var(--color-status-lost)',\n                    }}",
    },
    {
        "id": "W37",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: fenced badge border mutated to border-subtle",
        "target": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-lost)',\n                      border: '1px solid var(--color-status-lost)',\n                    }}",
        "replacement": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-lost)',\n                      border: '1px solid var(--color-border-subtle)',\n                    }}",
    },
    {
        "id": "W38",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: selected badge raw literal regression (#ffffff)",
        "target": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-online)',",
        "replacement": "                    data-testid=\"resource-topology-selected-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: '#ffffff',",
    },
    {
        "id": "W39",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: fenced badge raw literal regression (#ffffff)",
        "target": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: 'var(--color-status-lost)',",
        "replacement": "                    data-testid=\"resource-topology-fenced-badge\"\n                    style={{\n                      padding: '2px 6px',\n                      borderRadius: '4px',\n                      fontSize: '0.6875rem',\n                      fontWeight: 700,\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      color: '#ffffff',",
    },
    {
        "id": "W40",
        "file": "ResourceTopologyGraph",
        "desc": "ResourceTopologyGraph: node card raw literal regression rgba(16, 185, 129, 0.08)",
        "target": "                border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,\n                backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                border: `2px solid ${isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,\n                backgroundColor: isSelected ? 'rgba(16, 185, 129, 0.08)' : 'var(--color-bg-subtle)',",
    },
]


def apply_mutation(mutant):
    file_path = TARGET_FILES[mutant["file"]]
    content = file_path.read_text(encoding="utf-8")
    target = mutant["target"]
    replacement = mutant["replacement"]
    if target not in content:
        raise ValueError(f"Target pattern not found in {file_path}:\n{target[:100]}...")
    new_content = content.replace(target, replacement, 1)
    file_path.write_text(new_content, encoding="utf-8", newline="")


def restore_file(file_key: str, original_bytes: bytes):
    file_path = TARGET_FILES[file_key]
    file_path.write_bytes(original_bytes)
    current_bytes = file_path.read_bytes()
    if current_bytes != original_bytes:
        raise RuntimeError(
            f"Byte mismatch after restoration of {file_path}! Expected {len(original_bytes)} bytes, got {len(current_bytes)} bytes"
        )


def run_tsc_check():
    """Run npx tsc -b to ensure the mutant compiles."""
    local_tsc = APPS_WEB / "node_modules" / "typescript" / "bin" / "tsc"
    if local_tsc.exists():
        cmd = ["node", str(local_tsc), "-b"]
    else:
        cmd = [
            "npx.cmd" if os.name == "nt" else "npx",
            "tsc",
            "-b",
        ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return False, str(e)


def run_vitest_acc09(timeout=120):
    """Run vitest on acc09-contrast-tokens.test.tsx."""
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "vitest",
        "run",
        "tests/acc09-contrast-tokens.test.tsx",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or "", False
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -1, stdout, stderr, True


def test_mutant(mutant, original_bytes_map, timeout=120, head_sha=""):
    mutant_id = mutant["id"]
    file_key = mutant["file"]
    desc = mutant["desc"]
    observed_time = datetime.now(timezone.utc).isoformat()

    print(f"\n--- Testing Mutant {mutant_id} [{file_key}]: {desc} ---")
    try:
        apply_mutation(mutant)
    except Exception as e:
        print(f"  [ERROR] Failed to apply mutation: {e}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "ERROR",
            "reason": str(e),
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    # Verify compilation
    compiled_ok, tsc_out = run_tsc_check()
    if not compiled_ok:
        print(f"  [TSC_FAIL] Mutant failed TypeScript compilation:\n{tsc_out[:300]}")
        restore_file(file_key, original_bytes_map[file_key])
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TSC_FAIL",
            "reason": tsc_out,
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    # Run test
    retcode, stdout, stderr, is_timeout = run_vitest_acc09(timeout=timeout)

    # Restore file immediately
    restore_file(file_key, original_bytes_map[file_key])

    if is_timeout:
        print(f"  [TIMEOUT] Vitest timed out after {timeout}s!")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TIMEOUT",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    if retcode != 0:
        failed_test = "acc09-contrast-tokens.test.tsx"
        for line in (stdout + stderr).splitlines():
            if "FAIL" in line or "AssertionError" in line:
                failed_test = line.strip()
                break
        print(f"  [KILLED] Retcode {retcode}, caught by: {failed_test}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "KILLED",
            "killed": True,
            "killer": failed_test,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }
    else:
        print(f"  [SURVIVED] Vitest passed! Mutant was NOT killed!")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "SURVIVED",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }


def main():
    parser = argparse.ArgumentParser(description="Test Card 274 mutations across node & placement detail components")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3], help="Run specific batch (1: NodeDetail, 2: PlacementExplainView, 3: ResourceTopologyGraph)")
    parser.add_argument("--mutant", type=str, help="Run single mutant by ID (e.g. W1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all targets exist in files")
    parser.add_argument("--timeout", type=int, default=120, help="Per-mutant vitest timeout in seconds")
    args = parser.parse_args()

    original_bytes_map = {k: v.read_bytes() for k, v in TARGET_FILES.items()}

    if args.verify_targets:
        print("Verifying all mutation targets exist in target files...")
        missing = 0
        for m in MUTANTS:
            content = original_bytes_map[m["file"]].decode("utf-8")
            if m["target"] not in content:
                print(f"  [MISSING] {m['id']} in {m['file']}: {m['desc']}")
                missing += 1
            else:
                print(f"  [FOUND] {m['id']} in {m['file']}")
        if missing == 0:
            print(f"All {len(MUTANTS)} mutant targets verified!")
            return 0
        else:
            print(f"ERROR: {missing} mutant targets missing!")
            return 1

    try:
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        head_sha = "unknown"

    selected_mutants = []
    if args.mutant:
        selected_mutants = [m for m in MUTANTS if m["id"] == args.mutant]
        if not selected_mutants:
            print(f"Unknown mutant: {args.mutant}")
            return 1
    elif args.batch:
        if args.batch == 1:
            selected_mutants = [m for m in MUTANTS if m["file"] == "NodeDetail"]
        elif args.batch == 2:
            selected_mutants = [m for m in MUTANTS if m["file"] == "PlacementExplainView"]
        elif args.batch == 3:
            selected_mutants = [m for m in MUTANTS if m["file"] == "ResourceTopologyGraph"]
    elif args.all:
        selected_mutants = MUTANTS
    else:
        print("Please specify --mutant, --batch, --all, or --verify-targets")
        return 1

    print(f"Starting mutation testing for {len(selected_mutants)} mutant(s) (head SHA: {head_sha})")

    results = []
    for m in selected_mutants:
        res = test_mutant(m, original_bytes_map, timeout=args.timeout, head_sha=head_sha)
        results.append(res)

    # If updating full results
    if args.all:
        killed_count = sum(1 for r in results if r["killed"])
        summary = {
            "sourceHeadSha": head_sha,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "totalTested": len(results),
            "totalMutants": len(MUTANTS),
            "killed": killed_count,
            "survived": sum(1 for r in results if r.get("status") == "SURVIVED"),
            "timeouts": sum(1 for r in results if r.get("status") == "TIMEOUT"),
            "tsc_fails": sum(1 for r in results if r.get("status") == "TSC_FAIL"),
            "mutations": results,
        }
        RESULTS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nSaved complete mutation results to {RESULTS_FILE}")
        print(f"Kill Rate: {killed_count}/{len(results)} ({killed_count/len(results)*100:.1f}%)")
        return 0 if killed_count == len(results) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
