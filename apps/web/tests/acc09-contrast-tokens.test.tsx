import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const indexCss = fs.readFileSync(path.resolve(__dirname, '../src/index.css'), 'utf-8');

// Helper functions for WCAG 2.1 / 2.2 relative luminance and contrast ratio calculations
function parseHex(hex: string): [number, number, number] {
  let clean = hex.replace('#', '').trim();
  if (clean.length === 3) {
    clean = clean.split('').map((c) => c + c).join('');
  }
  const num = parseInt(clean, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function srgbToLinear(val: number): number {
  const norm = val / 255;
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

function getLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

function getContrast(hex1: string, hex2: string): number {
  const l1 = getLuminance(hex1);
  const l2 = getLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function blendRgba(tintRgb: [number, number, number], alpha: number, underlayHex: string): string {
  const underlayRgb = parseHex(underlayHex);
  const r = Math.round(alpha * tintRgb[0] + (1 - alpha) * underlayRgb[0]);
  const g = Math.round(alpha * tintRgb[1] + (1 - alpha) * underlayRgb[1]);
  const b = Math.round(alpha * tintRgb[2] + (1 - alpha) * underlayRgb[2]);
  const toHex = (n: number) => n.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function extractTokens(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const regex = /(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let match;
  while ((match = regex.exec(block)) !== null) {
    const val = match[2].split('/*')[0].trim();
    if (val.startsWith('#')) {
      tokens[match[1].trim()] = val;
    }
  }
  return tokens;
}

function getAllSourceFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { recursive: true, withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    if (entry.isFile()) {
      const fullPath = path.join(entry.parentPath || dir, entry.name);
      if (/\.(tsx?|jsx?|css)$/.test(entry.name)) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

// Fail-closed baseline of registered files and their exact color literal counts
const COLOR_LITERAL_BASELINE: Record<string, number> = {
  "app/App.tsx": 11,
  "contracts/model-verify-request.ts": 1,
  "contracts/model-version-register-request.ts": 1,
  "features/admin/AdminSecurityConsole.tsx": 186,
  "features/agent/NaturalLanguageRunView.tsx": 79,
  "features/agent/evalRunner.ts": 1,
  "features/approvals/ApprovalCenter.tsx": 17,
  "features/approvals/ApprovalDetail.tsx": 7,
  "features/dashboard/ClusterOverview.tsx": 17,
  "features/deployment/IntranetDeploymentView.tsx": 152,
  "features/desktop/DesktopShell.tsx": 49,
  "features/desktop/DesktopWindow.tsx": 17,
  "features/desktop/InvFileExplorer.tsx": 124,
  "features/desktop/ModelStudioView.tsx": 78,
  "features/desktop/ResourceExplorer.tsx": 390,
  "features/desktop/TerminalSessionView.tsx": 37,
  "features/editor/ConflictResolutionModal.tsx": 16,
  "features/editor/DiffViewer.tsx": 18,
  "features/editor/GitCommitModal.tsx": 26,
  "features/editor/MonacoWorkspaceEditor.tsx": 86,
  "features/evidence/EvidenceViewer.tsx": 16,
  "features/mlops/ModelLineageView.tsx": 458,
  "features/nodes/NodeDetail.tsx": 26,
  "features/nodes/NodeList.tsx": 31,
  "features/placement/PlacementExplainView.tsx": 5,
  "features/placement/PlacementSimulator.tsx": 33,
  "features/placement/ResourceTopologyGraph.tsx": 3,
  "features/recovery/DistributedRecoveryView.tsx": 81,
  "features/release/ReleaseCandidateView.tsx": 84,
  "features/release/releaseEngine.ts": 6,
  "features/runs/RunDetail.tsx": 122,
  "features/runs/RunList.tsx": 45,
  "features/runs/SealRecordPanel.tsx": 135,
  "features/studio/DeveloperStudio.tsx": 176,
  "features/terminal/WebTerminal.tsx": 32,
  "features/workspaces/ExecutionResultView.tsx": 1,
  "features/workspaces/WorkspaceCreateModal.tsx": 1,
  "features/workspaces/WorkspaceList.tsx": 9,
  "shared/api/adapterObservation.ts": 2,
  "shared/ui/Button.tsx": 2,
  "shared/ui/Header.tsx": 11,
  "shared/ui/RiskBadge.tsx": 4,
};

describe('Card 180: S11-FE ACC-09 Design Token & Composite Contrast Calculation Suite', () => {
  const rootBlock = indexCss.match(/:root\s*\{([^}]+)\}/)?.[1] || '';
  const darkBlock = indexCss.match(/\[data-theme=['"]dark['"]\]\s*\{([^}]+)\}/)?.[1] || '';

  const lightTokens = extractTokens(rootBlock);
  const darkTokens = extractTokens(darkBlock);

  // 1. Light Theme (:root) - Text Tokens on Solid Underlays
  it('ACC-09: Light Theme (:root) text tokens achieve >= 4.5:1 on canvas, surface, and subtle backgrounds', () => {
    const bgs = [
      { name: 'bg-surface', val: lightTokens['--color-bg-surface'] },
      { name: 'bg-canvas', val: lightTokens['--color-bg-canvas'] },
      { name: 'bg-subtle', val: lightTokens['--color-bg-subtle'] },
    ];

    const textTokenNames = [
      '--color-text-primary',
      '--color-text-secondary',
      '--color-text-muted',
      '--color-brand-primary',
      '--color-status-online',
      '--color-status-degraded',
      '--color-status-offline',
      '--color-status-neutral',
      '--color-risk-l0',
      '--color-risk-l1',
      '--color-risk-l2',
      '--color-risk-l3',
    ];

    for (const tName of textTokenNames) {
      const fg = lightTokens[tName];
      expect(fg, `Token ${tName} must exist in :root`).toBeDefined();
      for (const bg of bgs) {
        const cr = getContrast(fg, bg.val);
        expect(
          cr,
          `Light token ${tName} (${fg}) on ${bg.name} (${bg.val}) contrast ratio ${cr.toFixed(2)}:1 must be >= 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  // 2. Light Theme (:root) - UI Component and Boundary Tokens
  it('ACC-09 / DEF-S11-10: Light Theme (:root) border tokens achieve >= 3.0:1 on all light backgrounds', () => {
    const bgs = [
      { name: 'bg-surface', val: lightTokens['--color-bg-surface'] },
      { name: 'bg-canvas', val: lightTokens['--color-bg-canvas'] },
      { name: 'bg-subtle', val: lightTokens['--color-bg-subtle'] },
    ];

    const borderTokenNames = [
      '--color-border-subtle',
      '--color-border-strong',
    ];

    for (const tName of borderTokenNames) {
      const fg = lightTokens[tName];
      expect(fg, `Token ${tName} must exist in :root`).toBeDefined();
      for (const bg of bgs) {
        const cr = getContrast(fg, bg.val);
        expect(
          cr,
          `Light border token ${tName} (${fg}) on ${bg.name} (${bg.val}) contrast ratio ${cr.toFixed(2)}:1 must be >= 3.0:1`
        ).toBeGreaterThanOrEqual(3.0);
      }
    }

    const subtleCr = getContrast(lightTokens['--color-border-subtle'], lightTokens['--color-bg-surface']);
    const strongCr = getContrast(lightTokens['--color-border-strong'], lightTokens['--color-bg-surface']);
    expect(strongCr).toBeGreaterThan(subtleCr);
  });

  // 3. Dark Theme ([data-theme='dark']) - Text Tokens on Solid Underlays
  it('ACC-09: Dark Theme ([data-theme="dark"]) text tokens achieve >= 4.5:1 on canvas, surface, and subtle backgrounds', () => {
    const bgs = [
      { name: 'bg-surface', val: darkTokens['--color-bg-surface'] },
      { name: 'bg-canvas', val: darkTokens['--color-bg-canvas'] },
      { name: 'bg-subtle', val: darkTokens['--color-bg-subtle'] },
    ];

    const textTokenNames = [
      '--color-text-primary',
      '--color-text-secondary',
      '--color-text-muted',
      '--color-brand-primary',
      '--color-status-online',
      '--color-status-degraded',
      '--color-status-offline',
      '--color-status-neutral',
      '--color-risk-l0',
      '--color-risk-l1',
      '--color-risk-l2',
      '--color-risk-l3',
    ];

    for (const tName of textTokenNames) {
      const fg = darkTokens[tName];
      expect(fg, `Token ${tName} must exist in dark theme`).toBeDefined();
      for (const bg of bgs) {
        const cr = getContrast(fg, bg.val);
        expect(
          cr,
          `Dark token ${tName} (${fg}) on ${bg.name} (${bg.val}) contrast ratio ${cr.toFixed(2)}:1 must be >= 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  // 4. Dark Theme ([data-theme='dark']) - UI Component and Boundary Tokens
  it('ACC-09 / DEF-S11-10: Dark Theme ([data-theme="dark"]) border tokens achieve >= 3.0:1 on all dark backgrounds', () => {
    const bgs = [
      { name: 'bg-surface', val: darkTokens['--color-bg-surface'] },
      { name: 'bg-canvas', val: darkTokens['--color-bg-canvas'] },
      { name: 'bg-subtle', val: darkTokens['--color-bg-subtle'] },
    ];

    const borderTokenNames = [
      '--color-border-subtle',
      '--color-border-strong',
    ];

    for (const tName of borderTokenNames) {
      const fg = darkTokens[tName];
      expect(fg, `Token ${tName} must exist in dark theme`).toBeDefined();
      for (const bg of bgs) {
        const cr = getContrast(fg, bg.val);
        expect(
          cr,
          `Dark border token ${tName} (${fg}) on ${bg.name} (${bg.val}) contrast ratio ${cr.toFixed(2)}:1 must be >= 3.0:1`
        ).toBeGreaterThanOrEqual(3.0);
      }
    }

    const subtleCr = getContrast(darkTokens['--color-border-subtle'], darkTokens['--color-bg-surface']);
    const strongCr = getContrast(darkTokens['--color-border-strong'], darkTokens['--color-bg-surface']);
    expect(strongCr).toBeGreaterThan(subtleCr);
  });

  // 5. Button Backgrounds on White Text
  it('ACC-09: Button background tokens with white text exceed 4.5:1 in both themes', () => {
    const white = '#ffffff';

    // Light Theme
    const lightPrimaryBg = lightTokens['--color-brand-primary-bg'];
    const lightOfflineBg = lightTokens['--color-status-offline-bg'];
    expect(getContrast(white, lightPrimaryBg)).toBeGreaterThanOrEqual(4.5);
    expect(getContrast(white, lightOfflineBg)).toBeGreaterThanOrEqual(4.5);

    // Dark Theme
    const darkPrimaryBg = darkTokens['--color-brand-primary-bg'];
    const darkOfflineBg = darkTokens['--color-status-offline-bg'];
    expect(getContrast(white, darkPrimaryBg)).toBeGreaterThanOrEqual(4.5);
    expect(getContrast(white, darkOfflineBg)).toBeGreaterThanOrEqual(4.5);
  });

  // 6. [F1.a] RiskBadge Alpha-Composite Contrast Verification across All Themes and Underlays
  it('ACC-09 / RiskBadge F1.a: RiskBadge text on 15% RGBA tint over canvas/surface/subtle achieves >= 4.5:1 in both themes', () => {
    const riskTints: Record<string, [number, number, number]> = {
      '--color-risk-l0': [16, 185, 129], // rgba(16, 185, 129, 0.15)
      '--color-risk-l1': [59, 130, 246], // rgba(59, 130, 246, 0.15)
      '--color-risk-l2': [245, 158, 11], // rgba(245, 158, 11, 0.15)
      '--color-risk-l3': [239, 68, 68],  // rgba(239, 68, 68, 0.15)
    };

    const lightUnderlays = [
      { name: 'canvas', hex: lightTokens['--color-bg-canvas'] },
      { name: 'surface', hex: lightTokens['--color-bg-surface'] },
      { name: 'subtle', hex: lightTokens['--color-bg-subtle'] },
    ];

    const darkUnderlays = [
      { name: 'canvas', hex: darkTokens['--color-bg-canvas'] },
      { name: 'surface', hex: darkTokens['--color-bg-surface'] },
      { name: 'subtle', hex: darkTokens['--color-bg-subtle'] },
    ];

    // Light theme alpha-composite checks
    for (const [tokenName, tint] of Object.entries(riskTints)) {
      const fg = lightTokens[tokenName];
      for (const underlay of lightUnderlays) {
        const compositeBg = blendRgba(tint, 0.15, underlay.hex);
        const cr = getContrast(fg, compositeBg);
        expect(
          cr,
          `Light ${tokenName} (${fg}) on 15% tint over ${underlay.name} (${underlay.hex}) -> composite ${compositeBg} contrast ${cr.toFixed(3)}:1 must be >= 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }

    // Dark theme alpha-composite checks
    for (const [tokenName, tint] of Object.entries(riskTints)) {
      const fg = darkTokens[tokenName];
      for (const underlay of darkUnderlays) {
        const compositeBg = blendRgba(tint, 0.15, underlay.hex);
        const cr = getContrast(fg, compositeBg);
        expect(
          cr,
          `Dark ${tokenName} (${fg}) on 15% tint over ${underlay.name} (${underlay.hex}) -> composite ${compositeBg} contrast ${cr.toFixed(3)}:1 must be >= 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  // 7. [F1.b & F1.c] Real Usage Pairs: Source-Bound Binding Verification for RunDetail, NodeList, and DeveloperStudio
  it('ACC-09 / F1.b & F1.c: Component Source-Bound Verification: RunDetail, NodeList, and DeveloperStudio bind to var(--color-text-inverse)', () => {
    // 1) RunDetail.tsx:1080-1098 Lifecycle Step Indicator (isPassed background)
    const runDetailPath = path.resolve(__dirname, '../src/features/runs/RunDetail.tsx');
    const runDetailSrc = fs.readFileSync(runDetailPath, 'utf-8');

    // Source-bound assertion: isPassed must bind to var(--color-text-inverse) and never hardcoded #ffffff
    expect(runDetailSrc, 'RunDetail.tsx must bind isPassed step text to var(--color-text-inverse)').toMatch(
      /isPassed\s*\?\s*['"]var\(--color-text-inverse\)['"]/
    );
    expect(runDetailSrc, 'RunDetail.tsx must not hardcode white text for isPassed').not.toMatch(
      /color:\s*isPassed\s*\|\|\s*isCurrent\s*\?\s*['"]#ffffff['"]/
    );

    // Verify contrast ratio of the bound token against the bound background (--color-status-online)
    const darkStatusOnline = darkTokens['--color-status-online']; // #22c55e
    const darkTextInverse = darkTokens['--color-text-inverse'];   // #0f172a
    const runDetailDarkCr = getContrast(darkStatusOnline, darkTextInverse);
    expect(runDetailDarkCr, 'RunDetail dark isPassed step with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    const lightStatusOnline = lightTokens['--color-status-online']; // #15803d
    const lightTextInverse = lightTokens['--color-text-inverse'];   // #ffffff
    const runDetailLightCr = getContrast(lightStatusOnline, lightTextInverse);
    expect(runDetailLightCr, 'RunDetail light isPassed step with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // 2) NodeList.tsx:431-432 Observation-only Studio Button
    const nodeListPath = path.resolve(__dirname, '../src/features/nodes/NodeList.tsx');
    const nodeListSrc = fs.readFileSync(nodeListPath, 'utf-8');

    // Source-bound assertion: node.observationOnly must bind text to var(--color-text-inverse)
    expect(nodeListSrc, 'NodeList.tsx must bind observationOnly button text to var(--color-text-inverse)').toMatch(
      /node\.observationOnly\s*\?\s*['"]var\(--color-text-inverse\)['"]/
    );

    // Verify contrast ratio of the bound token against the bound background (--color-border-strong)
    const darkBorderStrong = darkTokens['--color-border-strong']; // #9ca3af
    const nodeListDarkCr = getContrast(darkBorderStrong, darkTextInverse);
    expect(nodeListDarkCr, 'NodeList observationOnly dark button with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    const lightBorderStrong = lightTokens['--color-border-strong']; // #475569
    const nodeListLightCr = getContrast(lightBorderStrong, lightTextInverse);
    expect(nodeListLightCr, 'NodeList observationOnly light button with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // 3) DeveloperStudio.tsx:905-906 Stepper Circle
    const devStudioPath = path.resolve(__dirname, '../src/features/studio/DeveloperStudio.tsx');
    const devStudioSrc = fs.readFileSync(devStudioPath, 'utf-8');

    // Source-bound assertion: stepper text must bind to var(--color-text-inverse) when not active
    expect(devStudioSrc, 'DeveloperStudio.tsx must bind stepper text to var(--color-text-inverse)').toMatch(
      /isActive\s*\?\s*['"]#ffffff['"]\s*:\s*['"]var\(--color-text-inverse\)['"]/
    );

    const devStudioUpcomingDarkCr = getContrast(darkBorderStrong, darkTextInverse);
    expect(devStudioUpcomingDarkCr, 'DeveloperStudio upcoming step dark with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    const devStudioPassedDarkCr = getContrast(darkStatusOnline, darkTextInverse);
    expect(devStudioPassedDarkCr, 'DeveloperStudio passed step dark with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
  });

  // 8. [F1 Revert-Fail Probes] Mutating fixes back to defective combinations strictly fails
  it('ACC-09 Revert-Fail Probes: Defective color combinations strictly fail WCAG AA criteria', () => {
    // Probe 1: RiskBadge light L1 with former #2563eb on 15% tint over light surface
    const defectiveLightL1 = '#2563eb';
    const lightSurfaceCompositeL1 = blendRgba([59, 130, 246], 0.15, lightTokens['--color-bg-surface']);
    const probe1Cr = getContrast(defectiveLightL1, lightSurfaceCompositeL1);
    expect(probe1Cr, 'Defective light L1 on light surface composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe1Cr).toBeCloseTo(4.347, 2);

    // Probe 2: RiskBadge light L2 with former #b45309 on 15% tint over light surface
    const defectiveLightL2 = '#b45309';
    const lightSurfaceCompositeL2 = blendRgba([245, 158, 11], 0.15, lightTokens['--color-bg-surface']);
    const probe2Cr = getContrast(defectiveLightL2, lightSurfaceCompositeL2);
    expect(probe2Cr, 'Defective light L2 on light surface composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe2Cr).toBeCloseTo(4.469, 2);

    // Probe 3: RiskBadge light L0 with former #047857 on 15% tint over light subtle
    const defectiveLightL0 = '#047857';
    const lightSubtleCompositeL0 = blendRgba([16, 185, 129], 0.15, lightTokens['--color-bg-subtle']);
    const probe3Cr = getContrast(defectiveLightL0, lightSubtleCompositeL0);
    expect(probe3Cr, 'Defective light L0 on light subtle composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe3Cr).toBeCloseTo(4.388, 2);

    // Probe 4: RiskBadge dark L0 with former #10b981 on 15% tint over dark subtle
    const defectiveDarkL0 = '#10b981';
    const darkSubtleCompositeL0 = blendRgba([16, 185, 129], 0.15, darkTokens['--color-bg-subtle']);
    const probe4Cr = getContrast(defectiveDarkL0, darkSubtleCompositeL0);
    expect(probe4Cr, 'Defective dark L0 on dark subtle composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe4Cr).toBeCloseTo(4.495, 2);

    // Probe 5: RunDetail dark isPassed with hardcoded white #ffffff on status-online #22c55e
    const probe5Cr = getContrast('#22c55e', '#ffffff');
    expect(probe5Cr, 'RunDetail dark isPassed white text on status-online must fail 4.5:1').toBeLessThan(4.5);
    expect(probe5Cr).toBeCloseTo(2.279, 2);

    // Probe 6: NodeList & DeveloperStudio dark border-strong #9ca3af with hardcoded white #ffffff
    const probe6Cr = getContrast('#9ca3af', '#ffffff');
    expect(probe6Cr, 'border-strong with hardcoded white text must fail 4.5:1').toBeLessThan(4.5);
    expect(probe6Cr).toBeCloseTo(2.539, 2);

    // Legacy Token Reverts:
    // Legacy Dark --color-border-subtle: #374151
    expect(getContrast('#374151', darkTokens['--color-bg-surface'])).toBeLessThan(3.0); // 1.72:1
    expect(getContrast('#374151', darkTokens['--color-bg-subtle'])).toBeLessThan(3.0);  // 1.42:1
    // Legacy Light --color-border-subtle: #e2e8f0
    expect(getContrast('#e2e8f0', lightTokens['--color-bg-surface'])).toBeLessThan(3.0); // 1.23:1
    expect(getContrast('#e2e8f0', lightTokens['--color-bg-subtle'])).toBeLessThan(3.0);  // 1.13:1
    // Legacy Light --color-text-muted: #64748b on subtle
    expect(getContrast('#64748b', lightTokens['--color-bg-subtle'])).toBeLessThan(4.5); // 4.34:1
  });

  // 9. [F2 Fail-Closed Inventory & Ratchet] var(--color-border-subtle) exact 140/21 and all hex/rgb/hsl literals strictly bounded
  it('ACC-09 / F2 Fail-Closed Inventory & Ratchet: var(--color-border-subtle) exact 140/21 and all hex/rgb/hsl literals strictly bounded', () => {
    const srcDir = path.resolve(__dirname, '../src');
    const allFiles = getAllSourceFiles(srcDir);

    let borderSubtleCount = 0;
    const borderSubtleFiles = new Set<string>();

    const legacyCounts: Record<string, number> = {
      '#64748b': 0,
      '#d97706': 0,
      '#e2e8f0': 0,
      '#dc2626': 0,
      '#30363d': 0,
    };
    const legacyFiles: Record<string, Set<string>> = {
      '#64748b': new Set(),
      '#d97706': new Set(),
      '#e2e8f0': new Set(),
      '#dc2626': new Set(),
      '#30363d': new Set(),
    };

    const borderSubtleRegex = /var\(--color-border-subtle/g;
    const hexRegex = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g;
    const rgbRegex = /rgba?\s*\([^)]+\)/gi;
    const hslRegex = /hsla?\s*\([^)]+\)/gi;

    const observedFileCounts: Record<string, number> = {};

    for (const f of allFiles) {
      const content = fs.readFileSync(f, 'utf-8');
      const relPath = path.relative(srcDir, f).replace(/\\/g, '/');
      const isIndexCss = f.endsWith('index.css');

      // 1) Border subtle token usage count
      const matches = content.match(borderSubtleRegex);
      if (matches) {
        borderSubtleCount += matches.length;
        borderSubtleFiles.add(f);
      }

      // 2) Scan all color literals (excluding index.css design token definitions)
      if (!isIndexCss) {
        const hMatches = content.match(hexRegex) || [];
        const rMatches = content.match(rgbRegex) || [];
        const sMatches = content.match(hslRegex) || [];
        const totalLiterals = hMatches.length + rMatches.length + sMatches.length;

        if (totalLiterals > 0) {
          observedFileCounts[relPath] = totalLiterals;

          // Fail-closed check 1: File must be in baseline allowlist
          expect(
            COLOR_LITERAL_BASELINE[relPath],
            `New unregistered file containing color literals detected: "${relPath}". All files with color literals must be registered in COLOR_LITERAL_BASELINE.`
          ).toBeDefined();

          // Fail-closed check 2: File literal count must not exceed baseline
          expect(
            totalLiterals,
            `Color literal count in "${relPath}" (${totalLiterals}) exceeded baseline (${COLOR_LITERAL_BASELINE[relPath]}). New color literals are prohibited.`
          ).toBeLessThanOrEqual(COLOR_LITERAL_BASELINE[relPath]);
        }

        // Count specific legacy tokens
        const lower = content.toLowerCase();
        for (const lit of Object.keys(legacyCounts)) {
          const occurrences = (lower.match(new RegExp(lit, 'g')) || []).length;
          if (occurrences > 0) {
            legacyCounts[lit] += occurrences;
            legacyFiles[lit].add(relPath);
          }
        }
      }
    }

    // Exact count verification for var(--color-border-subtle)
    expect(borderSubtleCount, 'var(--color-border-subtle) exact occurrence count in apps/web/src must be 140').toBe(140);
    expect(borderSubtleFiles.size, 'var(--color-border-subtle) file count in apps/web/src must be 21').toBe(21);

    // Fail-closed check 3: Total files with color literals must not exceed baseline file count
    const baselineFileCount = Object.keys(COLOR_LITERAL_BASELINE).length;
    expect(Object.keys(observedFileCounts).length, 'Total files with color literals must not exceed baseline').toBeLessThanOrEqual(baselineFileCount);

    // Ratchet assertions for specific legacy literals (occurrences & files)
    expect(legacyCounts['#64748b'], 'Legacy #64748b literal count must not exceed 15').toBeLessThanOrEqual(15);
    expect(legacyFiles['#64748b'].size, 'Legacy #64748b file count must not exceed 6').toBeLessThanOrEqual(6);

    expect(legacyCounts['#d97706'], 'Legacy #d97706 literal count must not exceed 14').toBeLessThanOrEqual(14);
    expect(legacyFiles['#d97706'].size, 'Legacy #d97706 file count must not exceed 6').toBeLessThanOrEqual(6);

    expect(legacyCounts['#e2e8f0'], 'Legacy #e2e8f0 literal count must not exceed 3').toBeLessThanOrEqual(3);
    expect(legacyFiles['#e2e8f0'].size, 'Legacy #e2e8f0 file count must not exceed 2').toBeLessThanOrEqual(2);

    expect(legacyCounts['#dc2626'], 'Legacy #dc2626 literal count must not exceed 1').toBeLessThanOrEqual(1);
    expect(legacyFiles['#dc2626'].size, 'Legacy #dc2626 file count must not exceed 1').toBeLessThanOrEqual(1);

    expect(legacyCounts['#30363d'], 'Legacy #30363d literal count must not exceed 161').toBeLessThanOrEqual(161);
    expect(legacyFiles['#30363d'].size, 'Legacy #30363d file count must not exceed 15').toBeLessThanOrEqual(15);
  });
});
