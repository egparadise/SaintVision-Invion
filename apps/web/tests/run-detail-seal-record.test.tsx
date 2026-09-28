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

// Strictly conforming RunItem (F9: no status, targetNodeId, startedAt)
const sampleRun: RunItem = {
  id: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  projectId: 'prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  state: 'succeeded',
  createdAt: '2026-09-28T04:00:00Z',
  completedAt: '2026-09-28T05:00:00Z',
};

// Fixtures with valid ULID IDs and bnd_ prefix (F9)
const ART_ID_1 = 'art_01J8Z3XQ2K9WMV5T7N4B6C8D01';
const ART_ID_2 = 'art_01J8Z3XQ2K9WMV5T7N4B6C8D02';
const BUNDLE_ID = 'bnd_01J8Z3XQ2K9WMV5T7N4B6C8D0E';

const sealedRecordFixture: RunRecordResponse = {
  recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  finalState: 'succeeded',
  terminationReason: 'completed',
  evidenceId: 'evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  bundleId: BUNDLE_ID,
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
      artifactId: ART_ID_1,
      role: 'diff',
      objectVersion: 'v1.0',
      uri: 's3://saintvision-artifacts/diff.patch',
      checksumSha256: SHA_A,
      byteSize: 1024,
    },
    {
      artifactId: ART_ID_2,
      role: 'model',
      objectVersion: null,
      uri: 's3://saintvision-artifacts/model.bin',
      checksumSha256: SHA_B,
      byteSize: 2048,
    },
  ],
};

const contextBundleFixture: ContextBundleResponse = {
  bundleId: BUNDLE_ID,
  runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  bundleHash: SHA_A,
  hashVerified: true,
  sealed: true,
  itemCount: 2,
  totalBytes: 2048,
  tokenEstimate: 512,
  retrievalStrategy: 'explicit',
  componentVersions: { adapter: 'reference', kernel: '1.2.0' },
  builtAt: '2026-09-28T04:00:10Z',
  items: [
    {
      itemId: 'itm_01J8Z3XQ2K9WMV5T7N4B6C8D01',
      itemVersion: 1,
      kind: 'document',
      ordinal: 0,
      contentHash: SHA_C,
      byteSize: 1024,
      redacted: false,
    },
    {
      itemId: 'itm_01J8Z3XQ2K9WMV5T7N4B6C8D02',
      itemVersion: 1,
      kind: 'code',
      ordinal: 1,
      contentHash: SHA_D,
      byteSize: 1024,
      redacted: false,
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

  it('2. R1 Sealed RunRecord Happy Path: renders sealed record, workload spec, attempts, evidenceId', async () => {
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
    expect(badge?.textContent).toContain('✔ 봉인됨 (SEALED)');

    const recordId = container.querySelector('[data-testid="seal-record-id"]');
    expect(recordId?.textContent).toBe('rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E');

    const finalState = container.querySelector('[data-testid="seal-final-state"]');
    expect(finalState?.textContent).toBe('succeeded');

    const terminationReason = container.querySelector('[data-testid="seal-termination-reason"]');
    expect(terminationReason?.textContent).toBe('completed');

    const attemptCount = container.querySelector('[data-testid="seal-attempt-count"]');
    expect(attemptCount?.textContent).toContain('1회');

    const evidenceId = container.querySelector('[data-testid="seal-evidence-id"]');
    expect(evidenceId?.textContent).toBe('evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E');

    const specSha = container.querySelector('[data-testid="seal-workload-spec-sha"]');
    expect(specSha?.textContent).toBe(SHA_B);

    // Live region announcement contains page count
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 조회 완료: 봉인됨 (아티팩트 이 페이지 2건, 번들 해시일치)');
  });

  it('3. R2 Pinned Artifacts Table & Verification: verified:true vs verified:false 200 fact report (F7/F8)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes(`/record/artifacts/${ART_ID_1}/verify`)) {
        return {
          runId: sampleRun.id,
          recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
          artifactId: ART_ID_1,
          pinnedChecksumSha256: SHA_A,
          verified: true,
        } as ArtifactPinVerificationResponse as any;
      }
      if (url.includes(`/record/artifacts/${ART_ID_2}/verify`)) {
        return {
          runId: sampleRun.id,
          recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
          artifactId: ART_ID_2,
          pinnedChecksumSha256: SHA_B,
          verified: false,
        } as ArtifactPinVerificationResponse as any;
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    // Object version rendered (F8)
    const ver1 = container.querySelector(`[data-testid="seal-artifact-version-${ART_ID_1}"]`);
    expect(ver1?.textContent).toBe('v1.0');
    const ver2 = container.querySelector(`[data-testid="seal-artifact-version-${ART_ID_2}"]`);
    expect(ver2?.textContent).toBe('-');

    // Verify button has descriptive aria-label (O3)
    const verifyDiffBtn = container.querySelector(`[data-testid="seal-verify-btn-${ART_ID_1}"]`) as HTMLButtonElement;
    expect(verifyDiffBtn.getAttribute('aria-label')).toBe(`아티팩트 ${ART_ID_1} 무결성 검증`);

    // Verify ART_ID_1 -> verified: true
    await act(async () => {
      verifyDiffBtn.click();
    });
    const diffStatusAfter = container.querySelector(`[data-testid="seal-artifact-verify-status-${ART_ID_1}"]`) as HTMLElement;
    expect(diffStatusAfter?.textContent).toContain('✔ 일치 (Verified)');
    expect(diffStatusAfter?.getAttribute('data-tone')).toBe('match');

    // Verify ART_ID_2 -> verified: false (reported fact with 200, F7/F8)
    const verifyModelBtn = container.querySelector(`[data-testid="seal-verify-btn-${ART_ID_2}"]`) as HTMLButtonElement;
    await act(async () => {
      verifyModelBtn.click();
    });
    const modelStatusAfter = container.querySelector(`[data-testid="seal-artifact-verify-status-${ART_ID_2}"]`) as HTMLElement;
    expect(modelStatusAfter?.textContent).toContain('⚠️ 불일치 (봉인 다이제스트와 다름·대상 없음)');
    expect(modelStatusAfter?.getAttribute('data-tone')).toBe('mismatch');
    // Color mutation kill: must NOT be green (#3fb950)
    expect(modelStatusAfter?.style.color).not.toBe('#3fb950');
    expect(modelStatusAfter?.style.color).not.toBe('rgb(63, 185, 80)');
    expect(['#ff7b72', 'rgb(255, 123, 114)']).toContain(modelStatusAfter?.style.color);

    // CRITICAL INVARIANT: verified: false must NEVER contain PASS or 합격 or 녹색
    expect(modelStatusAfter?.textContent).not.toMatch(/pass|합격|성공|verified /i);

    // Error alert banner is NOT shown for verified: false (it is a valid 200 fact report)
    expect(container.querySelector('[data-testid="seal-record-error-banner"]')).toBeNull();
  });

  it('4. R3 Context Bundle: renders hashVerified:true vs hashVerified:false without error, tokenEstimate (F7/F8)', async () => {
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

    // tokenEstimate rendered
    const tokenSummary = container.querySelector('[data-testid="bundle-item-token-summary"]');
    expect(tokenSummary?.textContent).toContain('토큰 추정: 512');

    const hashStatusTrue = container.querySelector('[data-testid="bundle-hash-verified-status"]') as HTMLElement;
    expect(hashStatusTrue?.textContent).toContain('✔ 해시 일치 (Hash Verified)');
    expect(hashStatusTrue?.getAttribute('data-tone')).toBe('match');

    // Re-render with hashVerified: false (200 fact report)
    returnMismatch = true;
    const refreshBtn = container.querySelector('[data-testid="seal-record-refresh-btn"]') as HTMLButtonElement;
    await act(async () => {
      refreshBtn.click();
    });

    const hashStatusFalse = container.querySelector('[data-testid="bundle-hash-verified-status"]') as HTMLElement;
    expect(hashStatusFalse?.textContent).toContain('⚠️ 해시 불일치 (Hash Mismatch)');
    expect(hashStatusFalse?.getAttribute('data-tone')).toBe('mismatch');
    expect(hashStatusFalse?.style.color).not.toBe('#3fb950');
    expect(hashStatusFalse?.style.color).not.toBe('rgb(63, 185, 80)');
    expect(['#ff7b72', 'rgb(255, 123, 114)']).toContain(hashStatusFalse?.style.color);
    // F7 regex fix: test against /✔|해시 일치 \(/
    expect(hashStatusFalse?.textContent).not.toMatch(/✔|해시 일치 \(/);
  });

  it('5. Unsealed Run (404 RES-0004 with exact detail): displays honest "미봉인" notice with zero fake PASS/numbers', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      if (url.includes('/context-bundle')) {
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

    // Context bundle reflects unsealed state (sealed: false)
    const bundleSealedStatus = container.querySelector('[data-testid="bundle-sealed-status"]');
    expect(bundleSealedStatus?.textContent).toContain('최신 빌드 (Latest Build)');

    // Live region
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 없음: 미봉인 실행');
  });

  it('6. 404 RES-0004 with "No such run.": renders error banner, NOT unsealed notice (F4)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No such run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    // Unsealed badge and notice must NOT be rendered
    expect(container.querySelector('[data-testid="seal-record-unsealed-notice"]')).toBeNull();
    const badge = container.querySelector('[data-testid="seal-status-badge"]');
    expect(badge).toBeNull();

    // Error banner MUST be rendered
    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('[RES-0004]');
    expect(errorBanner?.textContent).toContain('(404)');
    expect(errorBanner?.textContent).toContain('No such run.');
  });

  it('7. 403 Forbidden Canonical ProblemDetails (AUTH-0030): renders alert banner and isolates containers', async () => {
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

  it('8. 401 Unauthorized via realistic fetch (legacy InvError body produces NET-0401) (F5)', async () => {
    // Realistic fetch mock returning legacy InvError body
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/problem+json' }),
        json: async () => ({
          type: 'https://saintvision.invenio/problems/auth-missing-credential',
          status: 401,
          code: 'AUTH-MISSING-CREDENTIAL',
          title: 'AUTH-MISSING-CREDENTIAL',
          detail: 'a bearer credential is required',
          instance: '/v1/projects/prj_01/runs/run_01/record',
        }),
        text: async () => JSON.stringify({
          type: 'https://saintvision.invenio/problems/auth-missing-credential',
          status: 401,
          code: 'AUTH-MISSING-CREDENTIAL',
          title: 'AUTH-MISSING-CREDENTIAL',
          detail: 'a bearer credential is required',
          instance: '/v1/projects/prj_01/runs/run_01/record',
        }),
      } as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('[AUTH-MISSING-CREDENTIAL]');
    expect(errorBanner?.textContent).toContain('(401)');
    expect(errorBanner?.textContent).toContain('a bearer credential is required');
    fetchSpy.mockRestore();
  });

  it('9. 502 HTML proxy error via realistic fetch: sanitizes HTML in problem.detail into Korean fallback (F5)', async () => {
    // Realistic fetch mock returning HTML 502 Bad Gateway
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
        headers: new Headers({ 'content-type': 'text/html' }),
        text: async () => '<html><body><h1>502 Bad Gateway</h1><p>proxy failed</p></body></html>',
      } as any;
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
    expect(container.textContent).not.toContain('proxy failed');
    fetchSpy.mockRestore();
  });

  it('10. R2 Pagination (F2): "이 페이지 N건" label, nextCursor and pagination button', async () => {
    let requestedCursor: string | null = null;
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) {
        const u = new URL('http://localhost' + url);
        requestedCursor = u.searchParams.get('cursor');
        if (requestedCursor) {
          return {
            ...artifactsPageFixture,
            nextCursor: null,
            count: 1,
            items: [artifactsPageFixture.items[0]],
          } as any;
        }
        return {
          ...artifactsPageFixture,
          nextCursor: 'art_01J8Z3XQ2K9WMV5T7N4B6C8D99',
        } as any;
      }
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const pageCountEl = container.querySelector('[data-testid="seal-artifacts-page-count"]');
    expect(pageCountEl?.textContent).toContain('이 페이지 2건 (추가 항목 있음)');
    expect(pageCountEl?.textContent).not.toContain('총 2개');

    const nextBtn = container.querySelector('[data-testid="seal-artifacts-next-page-btn"]') as HTMLButtonElement;
    expect(nextBtn).not.toBeNull();
    expect(nextBtn.textContent).toContain('다음 페이지 (더보기)');

    // Click next page
    await act(async () => {
      nextBtn.click();
    });

    expect(requestedCursor).toBe('art_01J8Z3XQ2K9WMV5T7N4B6C8D99');
    expect(pageCountEl?.textContent).toContain('이 페이지 1건');
  });

  it('11. Sealed run with R2 500 error (F3): renders seal-artifacts-error, no fake "0건"', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) {
        throw new ApiError(makeProblem(500, 'SYS-0001', 'Database connection error.', 'SYS'));
      }
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const artErr = container.querySelector('[data-testid="seal-artifacts-error"]');
    expect(artErr).not.toBeNull();
    expect(artErr?.textContent).toContain('SYS-0001');
    expect(artErr?.textContent).toContain('(500)');
    expect(artErr?.textContent).toContain('Database connection error.');

    // Assert live region announces "조회 실패", NOT "아티팩트 0건"
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).not.toContain('아티팩트 0건');
    expect(liveRegion?.textContent).toContain('아티팩트 조회 실패');
  });

  it('12. Sealed run with R3 409 GRAPH-0002 error (F3): renders reproduction-failed fact, no fake "번들 없음"', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/context-bundle')) {
        throw new ApiError(makeProblem(409, 'GRAPH-0002', 'Missing snapshot, cannot reproduce bundle.', 'GRAPH'));
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const reproFail = container.querySelector('[data-testid="seal-bundle-reproduction-failed"]') as HTMLElement;
    expect(reproFail).not.toBeNull();
    expect(reproFail.getAttribute('data-tone')).toBe('mismatch');
    expect(reproFail.textContent).toContain('번들 재현 불가 (Snapshot Missing / GRAPH-0002)');

    // Live region announces '재현불가', NOT '번들 없음'
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).not.toContain('번들 없음');
    expect(liveRegion?.textContent).toContain('번들 재현불가');
  });

  it('13. Sealed run with R3 404 error (F3): renders seal-bundle-not-found notice', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/context-bundle')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No context bundle for this run.', 'RES'));
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const bundleNotFound = container.querySelector('[data-testid="seal-bundle-not-found"]');
    expect(bundleNotFound).not.toBeNull();
    expect(bundleNotFound?.textContent).toContain('컨텍스트 번들 없음');
  });

  it('14. Stale Data Clearing upon Run ID switch (revert-fail: kills stale state leak, clears bundle) (F7)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/run_A/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_A/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/run_A/record')) return sealedRecordFixture as any;

      if (url.includes('/run_B/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      if (url.includes('/run_B/context-bundle')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No context bundle for this run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });

    expect(container.querySelector('[data-testid="seal-record-details"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="seal-bundle-section"]')).not.toBeNull();

    // Switch to run_B
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    // run_A artifacts, details, and bundle must be completely gone
    expect(container.querySelector('[data-testid="seal-record-details"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).toBeNull();
    // F7: assert bundle section is not retained from run_A
    expect(container.querySelector('[data-testid="seal-bundle-section"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-record-unsealed-notice"]')).not.toBeNull();
  });

  it('15. Abort Guard in unsealed path (F6): late R3 response on run switch does not corrupt state', async () => {
    let resolveRunABundle: ((value: any) => void) | null = null;
    const bundlePromise = new Promise((resolve) => {
      resolveRunABundle = resolve;
    });

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/run_A/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      if (url.includes('/run_A/context-bundle')) {
        return bundlePromise;
      }
      if (url.includes('/run_B/record')) {
        return sealedRecordFixture as any;
      }
      if (url.includes('/run_B/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_B/context-bundle')) return contextBundleFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });

    // Switch to run_B while run_A's bundle fetch is still pending
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    // Resolve run_A's bundle now
    await act(async () => {
      resolveRunABundle?.(contextBundleFixture);
    });

    // Live region must announce run_B's completed state, NOT run_A's unsealed state
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 조회 완료: 봉인됨');
    expect(liveRegion?.textContent).not.toContain('미봉인 실행');
  });

  it('16. Live region node identity is maintained across all state transitions', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_01" />);
    });

    const liveNodeBefore = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveNodeBefore).not.toBeNull();

    const refreshBtn = container.querySelector('[data-testid="seal-record-refresh-btn"]') as HTMLButtonElement;
    await act(async () => {
      refreshBtn.click();
    });

    const liveNodeAfter = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveNodeAfter).toBe(liveNodeBefore);
  });

  it('17. Dark theme WCAG AA contrast (>= 4.5:1) verified from actual DOM styles (including bundle badges) (F7)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const darkBgRgb: [number, number, number] = [13, 17, 23]; // #0d1117

    const checkElementContrast = (el: HTMLElement) => {
      const fgColor = el.style.color;
      if (fgColor) {
        const fgRgb = parseRgb(fgColor);
        const ratio = contrastRatio(fgRgb, darkBgRgb);
        expect(ratio).toBeGreaterThanOrEqual(4.5);
      }
    };

    const sealedBadge = container.querySelector('[data-testid="seal-status-badge"]') as HTMLElement;
    if (sealedBadge) checkElementContrast(sealedBadge);

    const bundleSealedBadge = container.querySelector('[data-testid="bundle-sealed-status"]') as HTMLElement;
    if (bundleSealedBadge) checkElementContrast(bundleSealedBadge);

    const bundleHashBadge = container.querySelector('[data-testid="bundle-hash-verified-status"]') as HTMLElement;
    if (bundleHashBadge) checkElementContrast(bundleHashBadge);

    const roleBadges = container.querySelectorAll('[data-testid^="seal-artifact-role-"]');
    roleBadges.forEach((badge) => checkElementContrast(badge as HTMLElement));
  });

  it('18. Strict Runtime Guards: reject non-conforming responses, invalid sealedAt format, extra keys (F8)', () => {
    // Valid RunRecordResponse
    expect(isRunRecordResponse(sealedRecordFixture)).toBe(true);

    // Extra key rejected
    expect(isRunRecordResponse({ ...sealedRecordFixture, unauthorizedKey: 123 })).toBe(false);

    // Invalid sealedAt format (F8 & F-R4: must be valid RFC 3339 calendar date-time)
    expect(isRunRecordResponse({ ...sealedRecordFixture, sealedAt: 'not-a-timestamp' })).toBe(false);
    expect(isRunRecordResponse({ ...sealedRecordFixture, sealedAt: '2026-02-30T12:00:00Z' })).toBe(false);

    // Valid ArtifactPinVerificationResponse
    const validVerify: ArtifactPinVerificationResponse = {
      runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
      recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
      artifactId: ART_ID_1,
      pinnedChecksumSha256: SHA_A,
      verified: true,
    };
    expect(isArtifactPinVerificationResponse(validVerify)).toBe(true);
    expect(isArtifactPinVerificationResponse({ ...validVerify, extra: true })).toBe(false);

    // Valid ContextBundleResponse
    expect(isContextBundleResponse(contextBundleFixture)).toBe(true);
    expect(isContextBundleResponse({ ...contextBundleFixture, bogusField: 'nope' })).toBe(false);
    // Invalid builtAt calendar date-time rejected (F-R4)
    expect(isContextBundleResponse({ ...contextBundleFixture, builtAt: 'not-a-timestamp' })).toBe(false);
    expect(isContextBundleResponse({ ...contextBundleFixture, builtAt: '2026-02-30T12:00:00Z' })).toBe(false);
  });
});
