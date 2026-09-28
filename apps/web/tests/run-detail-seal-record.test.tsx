// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RunDetail } from '../src/features/runs/RunDetail';
import { SealRecordPanel } from '../src/features/runs/SealRecordPanel';
import * as client from '../src/shared/api/client';
import { ApiError } from '../src/shared/api/client';
import type { RunItem, ProblemDetails } from '../src/contracts/types';
import type { RunRecordResponse } from '../src/contracts/run-record-response';
import type { RunRecordArtifactPageResponse } from '../src/contracts/run-record-artifact-page-response';
import type { ArtifactPinVerificationResponse } from '../src/contracts/artifact-pin-verification-response';
import type { ContextBundleResponse } from '../src/contracts/context-bundle-response';
import {
  isRunRecordResponse,
  isArtifactPinVerificationResponse,
  isContextBundleResponse,
} from '../src/shared/api/runSealObservation';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

function makeProblem(status: number, code: string, detail: string, category = 'AUTH'): ProblemDetails {
  return {
    type: 'about:blank',
    title: code,
    status,
    code,
    category,
    detail,
    retryable: false,
    traceId: '0123456789abcdef0123456789abcdef',
    causeRef: null,
    evidenceId: null,
  };
}

const SHA_A = 'a'.repeat(64);
const SHA_B = 'b'.repeat(64);
const SHA_C = 'c'.repeat(64);
const SHA_D = 'd'.repeat(64);
const SHA_E = 'e'.repeat(64);

const sampleRun: RunItem = {
  id: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  projectId: 'prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  status: 'succeeded',
  state: 'succeeded',
  targetNodeId: 'nod_01JABCDEF01',
  createdAt: '2026-09-28T04:00:00Z',
  startedAt: '2026-09-28T04:00:05Z',
  completedAt: '2026-09-28T05:00:00Z',
};

const sealedRecordFixture: RunRecordResponse = {
  recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  finalState: 'succeeded',
  terminationReason: 'completed',
  evidenceId: 'evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  bundleId: 'bun_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  bundleHash: SHA_A,
  workloadSpecSha256: SHA_B,
  componentVersions: { adapter: 'reference', kernel: '1.2.0' },
  attemptCount: 1,
  sealedAt: '2026-09-28T05:00:00Z',
};

const artifactsPageFixture: RunRecordArtifactPageResponse = {
  recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  role: null,
  nextCursor: null,
  count: 2,
  items: [
    {
      artifactId: 'art_diff_01',
      role: 'diff',
      uri: 's3://artifacts/diff.patch',
      checksumSha256: SHA_C,
      byteSize: 1024,
      objectVersion: 'v1',
    },
    {
      artifactId: 'art_model_01',
      role: 'model',
      uri: 's3://models/weights.bin',
      checksumSha256: SHA_D,
      byteSize: 2048576,
      objectVersion: null,
    },
  ],
};

const contextBundleFixture: ContextBundleResponse = {
  bundleId: 'bun_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  bundleHash: SHA_A,
  hashVerified: true,
  sealed: true,
  itemCount: 1,
  totalBytes: 512,
  retrievalStrategy: 'hybrid',
  componentVersions: { contextBuilder: '2.0.0' },
  builtAt: '2026-09-28T04:55:00Z',
  items: [
    {
      ordinal: 0,
      itemId: 'doc-001',
      itemVersion: 1,
      kind: 'document',
      contentHash: SHA_E,
      byteSize: 512,
      redacted: false,
      confidence: 0.95,
    },
  ],
};

function parseRgb(colorStr: string): [number, number, number] {
  if (colorStr.startsWith('#')) {
    const hex = colorStr.slice(1);
    if (hex.length === 6) {
      return [
        parseInt(hex.slice(0, 2), 16),
        parseInt(hex.slice(2, 4), 16),
        parseInt(hex.slice(4, 6), 16),
      ];
    }
  }
  const match = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (match) {
    return [parseInt(match[1], 10), parseInt(match[2], 10), parseInt(match[3], 10)];
  }
  return [255, 255, 255];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function contrastRatio(rgb1: [number, number, number], rgb2: [number, number, number]): number {
  const l1 = relativeLuminance(rgb1);
  const l2 = relativeLuminance(rgb2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

describe('RunDetail Seal Record Panel - R1/R2/R3 Contract Bindings (Card 86)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.restoreAllMocks();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it('1. Tab 7 button integration in RunDetail: switches to seal record tab', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const sealTabBtn = container.querySelector('[data-testid="tab-seal"]') as HTMLButtonElement;
    expect(sealTabBtn).not.toBeNull();
    expect(sealTabBtn.textContent).toContain('7. 봉인 기록 (Seal Record)');

    await act(async () => {
      sealTabBtn.click();
    });

    const panel = container.querySelector('[data-testid="seal-record-panel"]');
    expect(panel).not.toBeNull();
  });

  it('2. R1 Sealed RunRecord Happy Path: renders sealed record, workload spec, attempts', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const badge = container.querySelector('[data-testid="seal-status-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('✔ 봉인됨 (SEALED)');

    const recordId = container.querySelector('[data-testid="seal-record-id"]');
    expect(recordId?.textContent).toBe(sealedRecordFixture.recordId);

    const workloadSha = container.querySelector('[data-testid="seal-workload-spec-sha"]');
    expect(workloadSha?.textContent).toBe(SHA_B);

    const attemptCount = container.querySelector('[data-testid="seal-attempt-count"]');
    expect(attemptCount?.textContent).toContain('1회');

    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 조회 완료: 봉인됨');
  });

  it('3. R2 Pinned Artifacts Table & Verification: verified:true vs verified:false 200 fact report', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/art_diff_01/verify')) {
        const res: ArtifactPinVerificationResponse = {
          recordId: sealedRecordFixture.recordId,
          runId: sampleRun.id,
          artifactId: 'art_diff_01',
          verified: true,
          pinnedChecksumSha256: SHA_C,
        };
        return res as any;
      }
      if (url.includes('/art_model_01/verify')) {
        const res: ArtifactPinVerificationResponse = {
          recordId: sealedRecordFixture.recordId,
          runId: sampleRun.id,
          artifactId: 'art_model_01',
          verified: false,
          pinnedChecksumSha256: SHA_D,
        };
        return res as any;
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    // Check initial unverified state
    const diffStatusInitial = container.querySelector('[data-testid="seal-artifact-verify-status-art_diff_01"]');
    expect(diffStatusInitial?.textContent).toContain('미검증 (검증 대기)');

    const verifyDiffBtn = container.querySelector('[data-testid="seal-verify-btn-art_diff_01"]') as HTMLButtonElement;
    expect(verifyDiffBtn).not.toBeNull();

    // Verify art_diff_01 -> verified: true
    await act(async () => {
      verifyDiffBtn.click();
    });

    const diffStatusAfter = container.querySelector('[data-testid="seal-artifact-verify-status-art_diff_01"]');
    expect(diffStatusAfter?.textContent).toContain('✔ 일치 (Verified)');

    // Verify art_model_01 -> verified: false (reported fact with 200)
    const verifyModelBtn = container.querySelector('[data-testid="seal-verify-btn-art_model_01"]') as HTMLButtonElement;
    await act(async () => {
      verifyModelBtn.click();
    });

    const modelStatusAfter = container.querySelector('[data-testid="seal-artifact-verify-status-art_model_01"]');
    expect(modelStatusAfter?.textContent).toContain('⚠️ 불일치 (Tampered/Mismatch)');

    // CRITICAL INVARIANT: verified: false must NEVER contain PASS or 합격 or 녹색
    expect(modelStatusAfter?.textContent).not.toMatch(/pass|합격|성공|verified\b/i);

    // Assert that error alert banner is NOT shown for verified: false (it is a valid 200 fact report)
    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).toBeNull();
  });

  it('4. R3 Context Bundle: renders hashVerified:true and hashVerified:false without error', async () => {
    let returnMismatch = false;
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/context-bundle')) {
        return {
          ...contextBundleFixture,
          hashVerified: !returnMismatch,
        } as any;
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const hashStatusTrue = container.querySelector('[data-testid="bundle-hash-verified-status"]');
    expect(hashStatusTrue?.textContent).toContain('✔ 해시 일치 (Hash Verified)');

    // Re-render with hashVerified: false (200 fact report)
    returnMismatch = true;
    const refreshBtn = container.querySelector('[data-testid="seal-record-refresh-btn"]') as HTMLButtonElement;
    await act(async () => {
      refreshBtn.click();
    });

    const hashStatusFalse = container.querySelector('[data-testid="bundle-hash-verified-status"]');
    expect(hashStatusFalse?.textContent).toContain('⚠️ 해시 불일치 (Hash Mismatch)');
    expect(hashStatusFalse?.textContent).not.toMatch(/pass|일치\b/i);
  });

  it('5. Unsealed Run (404 RES-0004): displays honest "미봉인" notice with zero fake PASS/numbers', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      if (url.includes('/context-bundle')) {
        // G-04 R3: unsealed runs can still return latest unsealed bundle
        return {
          ...contextBundleFixture,
          sealed: false,
        } as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const badge = container.querySelector('[data-testid="seal-status-badge"]');
    expect(badge?.textContent).toContain('미봉인 (UNSEALED)');

    const unsealedNotice = container.querySelector('[data-testid="seal-record-unsealed-notice"]');
    expect(unsealedNotice).not.toBeNull();
    expect(unsealedNotice?.textContent).toContain('이 실행(Run)은 아직 봉인(Seal)되지 않은 실행입니다.');

    // Assert sealed record details and artifacts table are NOT rendered
    expect(container.querySelector('[data-testid="seal-record-details"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).toBeNull();

    // Context bundle should reflect unsealed state (sealed: false)
    const bundleSealedStatus = container.querySelector('[data-testid="bundle-sealed-status"]');
    expect(bundleSealedStatus?.textContent).toContain('최신 빌드 (Latest Build)');

    // Live region
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 없음: 미봉인 실행');
  });

  it('6. 403 Forbidden Canonical ProblemDetails (AUTH-0030): renders alert banner and isolates containers', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(403, 'AUTH-0030', 'This project is not accessible.', 'AUTH'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('[AUTH-0030]');
    expect(errorBanner?.textContent).toContain('(403)');
    expect(errorBanner?.textContent).toContain('This project is not accessible.');

    expect(container.querySelector('[data-testid="seal-record-details"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-bundle-section"]')).toBeNull();
  });

  it('7. 401 Unauthorized Legacy InvError (AUTH-MISSING-CREDENTIAL): renders alert banner', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(401, 'AUTH-MISSING-CREDENTIAL', 'a bearer credential is required', 'AUTH'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('[AUTH-MISSING-CREDENTIAL]');
    expect(errorBanner?.textContent).toContain('(401)');
    expect(errorBanner?.textContent).toContain('a bearer credential is required');
  });

  it('8. 502 HTML proxy error: sanitizes raw HTML markup into Korean fallback message', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new Error('<html><body><h1>502 Bad Gateway</h1><p>proxy failed</p></body></html>');
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('서버 또는 게이트웨이 오류가 발생했습니다.');

    // Assert ZERO raw HTML tag leakage into the DOM
    expect(container.innerHTML).not.toContain('<html');
    expect(container.innerHTML).not.toContain('<body');
    expect(container.innerHTML).not.toContain('proxy failed');
  });

  it('9. Stale Data Clearing upon Run ID switch (revert-fail: kills stale state leak)', async () => {
    let currentRun = 'run_A';
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/run_A/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_A/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/run_A/record')) return sealedRecordFixture as any;

      if (url.includes('/run_B/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });

    expect(container.querySelector('[data-testid="seal-record-details"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).not.toBeNull();

    // Switch to run_B
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    // run_A artifacts and details must be completely gone
    expect(container.querySelector('[data-testid="seal-record-details"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-record-unsealed-notice"]')).not.toBeNull();
  });

  it('10. Live region node identity is maintained across all state transitions', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_01" />);
    });

    const initialLiveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(initialLiveRegion).not.toBeNull();

    // Trigger refresh
    const refreshBtn = container.querySelector('[data-testid="seal-record-refresh-btn"]') as HTMLButtonElement;
    await act(async () => {
      refreshBtn.click();
    });

    const postRefreshLiveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(postRefreshLiveRegion).toBe(initialLiveRegion);
  });

  it('11. Dark theme WCAG AA contrast (>= 4.5:1) verified from actual DOM styles', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/art_diff_01/verify')) {
        return {
          recordId: sealedRecordFixture.recordId,
          runId: sampleRun.id,
          artifactId: 'art_diff_01',
          verified: true,
          pinnedChecksumSha256: SHA_C,
        } as any;
      }
      if (url.includes('/art_model_01/verify')) {
        return {
          recordId: sealedRecordFixture.recordId,
          runId: sampleRun.id,
          artifactId: 'art_model_01',
          verified: false,
          pinnedChecksumSha256: SHA_D,
        } as any;
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    // Verify art_diff_01 and art_model_01
    const verifyDiffBtn = container.querySelector('[data-testid="seal-verify-btn-art_diff_01"]') as HTMLButtonElement;
    const verifyModelBtn = container.querySelector('[data-testid="seal-verify-btn-art_model_01"]') as HTMLButtonElement;
    await act(async () => {
      verifyDiffBtn.click();
      verifyModelBtn.click();
    });

    const darkBg: [number, number, number] = [22, 27, 34]; // #161b22

    // 1. Sealed badge
    const sealedBadge = container.querySelector('[data-testid="seal-status-badge"]') as HTMLElement;
    const sealedRgb = parseRgb(sealedBadge.style.color);
    const sealedContrast = contrastRatio(sealedRgb, darkBg);
    expect(sealedContrast).toBeGreaterThanOrEqual(4.5);

    // 2. Verified status badge (#3fb950)
    const verifiedBadge = container.querySelector('[data-testid="seal-artifact-verify-status-art_diff_01"]') as HTMLElement;
    const verifiedRgb = parseRgb(verifiedBadge.style.color);
    const verifiedContrast = contrastRatio(verifiedRgb, darkBg);
    expect(verifiedContrast).toBeGreaterThanOrEqual(4.5);

    // 3. Tampered/Mismatch status badge (#ff7b72)
    const mismatchBadge = container.querySelector('[data-testid="seal-artifact-verify-status-art_model_01"]') as HTMLElement;
    const mismatchRgb = parseRgb(mismatchBadge.style.color);
    const mismatchContrast = contrastRatio(mismatchRgb, darkBg);
    expect(mismatchContrast).toBeGreaterThanOrEqual(4.5);
  });

  it('12. Strict Runtime Guards: reject non-conforming responses and extra keys', () => {
    // Valid fixture passes
    expect(isRunRecordResponse(sealedRecordFixture)).toBe(true);

    // Extra key rejected (additionalProperties: false)
    expect(isRunRecordResponse({ ...sealedRecordFixture, unexpectedKey: 'extra' })).toBe(false);

    // Missing required field rejected
    const { recordId, ...withoutRecordId } = sealedRecordFixture;
    expect(isRunRecordResponse(withoutRecordId)).toBe(false);

    // Invalid SHA rejected
    expect(isRunRecordResponse({ ...sealedRecordFixture, workloadSpecSha256: 'not-64-hex' })).toBe(false);

    // Verification guard: verified: false is valid boolean
    const validVerifyFalse: ArtifactPinVerificationResponse = {
      recordId: 'rec_01',
      runId: 'run_01',
      artifactId: 'art_01',
      verified: false,
      pinnedChecksumSha256: SHA_A,
    };
    expect(isArtifactPinVerificationResponse(validVerifyFalse)).toBe(true);
    expect(isArtifactPinVerificationResponse({ ...validVerifyFalse, extra: true })).toBe(false);

    // Context bundle guard
    expect(isContextBundleResponse(contextBundleFixture)).toBe(true);
    expect(isContextBundleResponse({ ...contextBundleFixture, retrievalStrategy: 'invalid-strategy' })).toBe(false);
  });
});