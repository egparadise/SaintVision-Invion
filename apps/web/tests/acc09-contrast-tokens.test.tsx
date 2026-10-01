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

describe('Card 180: S11-FE ACC-09 Design Token Contrast Calculation Suite', () => {
  const rootBlock = indexCss.match(/:root\s*\{([^}]+)\}/)?.[1] || '';
  const darkBlock = indexCss.match(/\[data-theme=['"]dark['"]\]\s*\{([^}]+)\}/)?.[1] || '';

  const lightTokens = extractTokens(rootBlock);
  const darkTokens = extractTokens(darkBlock);

  // 1. Light Theme (:root) - Text Tokens
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

    // Ensure visual hierarchy between subtle and strong borders
    const subtleCr = getContrast(lightTokens['--color-border-subtle'], lightTokens['--color-bg-surface']);
    const strongCr = getContrast(lightTokens['--color-border-strong'], lightTokens['--color-bg-surface']);
    expect(strongCr).toBeGreaterThan(subtleCr);
  });

  // 3. Dark Theme ([data-theme='dark']) - Text Tokens
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

    // Ensure visual hierarchy between subtle and strong borders in dark theme
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

  // 6. Revert-Fail Invariant Assertions
  it('ACC-09 Revert-Fail: Previous legacy low-contrast token values strictly fail WCAG AA criteria', () => {
    // Legacy Dark --color-border-subtle: #374151
    const legacyDarkBorderSubtle = '#374151';
    const darkSurface = darkTokens['--color-bg-surface'];
    const darkSubtle = darkTokens['--color-bg-subtle'];
    expect(getContrast(legacyDarkBorderSubtle, darkSurface)).toBeLessThan(3.0); // 1.72:1 < 3.0
    expect(getContrast(legacyDarkBorderSubtle, darkSubtle)).toBeLessThan(3.0); // 1.42:1 < 3.0

    // Legacy Light --color-border-subtle: #e2e8f0
    const legacyLightBorderSubtle = '#e2e8f0';
    const lightSurface = lightTokens['--color-bg-surface'];
    const lightSubtle = lightTokens['--color-bg-subtle'];
    expect(getContrast(legacyLightBorderSubtle, lightSurface)).toBeLessThan(3.0); // 1.23:1 < 3.0
    expect(getContrast(legacyLightBorderSubtle, lightSubtle)).toBeLessThan(3.0); // 1.13:1 < 3.0

    // Legacy Light --color-text-muted: #64748b on subtle background
    const legacyLightTextMuted = '#64748b';
    expect(getContrast(legacyLightTextMuted, lightSubtle)).toBeLessThan(4.5); // 4.34:1 < 4.5

    // Legacy Light --color-status-online: #16a34a on surface background
    const legacyLightStatusOnline = '#16a34a';
    expect(getContrast(legacyLightStatusOnline, lightSurface)).toBeLessThan(4.5); // 3.30:1 < 4.5

    // Legacy Light --color-status-degraded: #d97706 on surface background
    const legacyLightStatusDegraded = '#d97706';
    expect(getContrast(legacyLightStatusDegraded, lightSurface)).toBeLessThan(4.5); // 3.19:1 < 4.5
  });
});
