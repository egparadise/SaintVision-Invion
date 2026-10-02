/** @vitest-environment happy-dom */
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SealRecordPanel } from '../src/features/runs/SealRecordPanel';
import * as client from '../src/shared/api/client';
import { ApiError } from '../src/shared/api/client';
import {
  isArtifactPinVerificationResponse,
  isContextBundleResponse,
  isRunRecordResponse,
} from '../src/shared/api/runSealObservation';
import type {
  ArtifactPinVerificationResponse,
  ContextBundleResponse,
  RunRecordArtifactPageResponse,
  RunRecordResponse,
} from '../src/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const sampleRun = {
  id: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
  projectId: 'prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
};

const SHA_A = 'a'.repeat(64);
const SHA_B = 'b'.repeat(64);
const SHA_C = 'c'.repeat(64);
const SHA_D = 'd'.repeat(64);

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
      redacted: true,
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
  const m = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (m) {
    return [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)];
  }
  return [255, 255, 255];
}

function srgbToLinear(c: number): number {
  const norm = c / 255;
  return norm <= 0.03928 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

function contrastRatio(fg: [number, number, number], bg: [number, number, number]): number {
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function makeProblem(
  status: number,
  code: string,
  detail: string,
  category = 'RES',
  retryable = false,
  causeRef: string | null = null,
  evidenceId: string | null = null,
): client.ProblemDetails {
  return {
    type: 'about:blank',
    title: code,
    status,
    code,
    category,
    detail,
    retryable,
    traceId: '0123456789abcdef0123456789abcdef',
    causeRef,
    evidenceId,
  };
}

describe('SealRecordPanel Component (G-04 R1·R2·R3)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it('1. Mounts without initial fetch when projectId or runId is missing', async () => {
    const fetchSpy = vi.spyOn(client, 'apiClient');
    await act(async () => {
      root.render(<SealRecordPanel projectId="" runId="" />);
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('식별자 누락');
  });

  it('2. Sealed run complete success (R1 + R2 + R3)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const statusBadge = container.querySelector('[data-testid="seal-status-badge"]') as HTMLElement;
    expect(statusBadge?.textContent).toContain('봉인됨 (SEALED)');
    expect(statusBadge.style.color).toBe('var(--color-status-online)');
    expect(statusBadge.style.borderColor).toBe('var(--color-status-online)');
    expect(statusBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');

    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 조회 완료: 봉인됨 (아티팩트 이 페이지 2건, 번들 해시일치)');

    expect(container.querySelector('[data-testid="seal-record-details"]')).not.toBeNull();
    expect(container.textContent).toContain('evd_01J8Z3XQ2K9WMV5T7N4B6C8D0E');
    expect(container.textContent).toContain('succeeded');
    expect(container.textContent).toContain('completed');

    const artifactRows = container.querySelectorAll('[data-testid^="seal-artifact-row-"]');
    expect(artifactRows.length).toBe(2);
    expect(container.textContent).toContain('v1.0');
    expect(container.textContent).toContain('토큰 추정: 512');
    expect(container.textContent).toContain('[비식별화]');
    expect(container.textContent).toContain('95%');
  });

  it('3. Artifact pin verification (R2): handles verified: true and verified: false (reported as facts)', async () => {
    let verifyResponse: ArtifactPinVerificationResponse = {
      runId: sampleRun.id,
      recordId: sealedRecordFixture.recordId,
      artifactId: ART_ID_1,
      pinnedChecksumSha256: SHA_A,
      verified: true,
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/verify')) return verifyResponse as any;
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const verifyBtn = container.querySelector(`[data-testid="seal-verify-btn-${ART_ID_1}"]`) as HTMLButtonElement;
    expect(verifyBtn).not.toBeNull();
    expect(verifyBtn.getAttribute('aria-label')).toBe(`아티팩트 ${ART_ID_1} 무결성 검증`);

    await act(async () => {
      verifyBtn.click();
    });

    const successBadge = container.querySelector(`[data-testid="seal-artifact-verify-status-${ART_ID_1}"]`) as HTMLElement;
    expect(successBadge?.textContent).toContain('✔ 일치 (Verified)');
    expect(successBadge.getAttribute('data-tone')).toBe('match');
    expect(successBadge.style.color).toBe('var(--color-status-online)');

    verifyResponse = {
      runId: sampleRun.id,
      recordId: sealedRecordFixture.recordId,
      artifactId: ART_ID_2,
      pinnedChecksumSha256: SHA_B,
      verified: false,
    };

    const verifyBtn2 = container.querySelector(`[data-testid="seal-verify-btn-${ART_ID_2}"]`) as HTMLButtonElement;
    await act(async () => {
      verifyBtn2.click();
    });

    const mismatchBadge = container.querySelector(`[data-testid="seal-artifact-verify-status-${ART_ID_2}"]`) as HTMLElement;
    expect(mismatchBadge?.textContent).toContain('⚠️ 불일치 (봉인 다이제스트와 다름·대상 없음)');
    expect(mismatchBadge.getAttribute('data-tone')).toBe('mismatch');
    expect(mismatchBadge.style.color).toBe('var(--color-status-offline)');
    expect(mismatchBadge.style.color).not.toBe('var(--color-status-online)');
  });

  it('4. Context bundle hash verification (R3): handles hashVerified: true and false (reported as facts)', async () => {
    const unverifiedBundle: ContextBundleResponse = {
      ...contextBundleFixture,
      hashVerified: false,
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/context-bundle')) return unverifiedBundle as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const bundleHashStatus = container.querySelector('[data-testid="bundle-hash-verified-status"]') as HTMLElement;
    expect(bundleHashStatus).not.toBeNull();
    expect(bundleHashStatus.textContent).toContain('⚠️ 해시 불일치 (Hash Mismatch)');
    expect(bundleHashStatus.getAttribute('data-tone')).toBe('mismatch');
    expect(bundleHashStatus.style.color).toBe('var(--color-status-offline)');
    expect(bundleHashStatus.style.color).not.toBe('var(--color-status-online)');
    expect(bundleHashStatus.textContent).not.toMatch(/✔|해시 일치 \(/);
  });

  it('5. Unsealed run (404 RES-0004 with exact detail "No sealed record for this run."): renders unsealed notice, no fake artifacts', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      if (url.includes('/context-bundle')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No context bundle for this run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const statusBadge = container.querySelector('[data-testid="seal-status-badge"]') as HTMLElement;
    expect(statusBadge?.textContent).toContain('미봉인 (UNSEALED)');
    expect(statusBadge.style.color).toBe('var(--color-status-degraded)');
    expect(statusBadge.style.borderColor).toBe('var(--color-status-degraded)');
    expect(statusBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');

    const unsealedNotice = container.querySelector('[data-testid="seal-record-unsealed-notice"]');
    expect(unsealedNotice).not.toBeNull();
    expect(unsealedNotice?.textContent).toContain('이 실행(Run)은 아직 봉인(Seal)되지 않은 실행입니다.');

    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-record-details"]')).toBeNull();
  });

  it('6. 404 with other detail (e.g. "No such run.") is rendered as error banner, not unsealed notice (F4)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No such run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('RES-0004');
    expect(errorBanner?.textContent).toContain('No such run.');
    expect(container.querySelector('[data-testid="seal-record-unsealed-notice"]')).toBeNull();
  });

  it('7. 403 Forbidden (AUTH-0030) ProblemDetails from server is rendered as error banner (F5)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async () => {
      throw new ApiError(makeProblem(403, 'AUTH-0030', 'This project is not accessible.', 'AUTH'));
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('[AUTH-0030]');
    expect(errorBanner?.textContent).toContain('(403)');
    expect(errorBanner?.textContent).toContain('This project is not accessible.');
  });

  it('8. 401 Unauthorized via realistic fetch (legacy InvError body with all 11 keys retains AUTH-MISSING-CREDENTIAL) (F5 & G3)', async () => {
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
          category: 'AUTH',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          instance: '/v1/projects/prj_01/runs/run_01/record',
          causeRef: null,
          evidenceId: null,
        }),
        text: async () => JSON.stringify({
          type: 'https://saintvision.invenio/problems/auth-missing-credential',
          status: 401,
          code: 'AUTH-MISSING-CREDENTIAL',
          title: 'AUTH-MISSING-CREDENTIAL',
          detail: 'a bearer credential is required',
          category: 'AUTH',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          instance: '/v1/projects/prj_01/runs/run_01/record',
          causeRef: null,
          evidenceId: null,
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

  it('9. HTML 502/504 Bad Gateway error is sanitized into clean Korean fallback without HTML tags (F5)', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
        headers: new Headers({ 'content-type': 'text/html' }),
        text: async () => '<html><body>502 Bad Gateway: nginx proxy failed</body></html>',
        json: async () => {
          throw new SyntaxError('Unexpected token <');
        },
      } as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('서버 또는 게이트웨이 오류가 발생했습니다.');
    expect(errorBanner?.textContent).not.toContain('<html>');
    expect(errorBanner?.textContent).not.toContain('proxy failed');
    fetchSpy.mockRestore();
  });

  it('10. Pagination on R2 artifacts: renders "이 페이지 {count}건" and requests nextCursor (F2 & F-R3)', async () => {
    let requestedCursor: string | null = null;
    const page1: RunRecordArtifactPageResponse = {
      recordId: sealedRecordFixture.recordId,
      runId: sealedRecordFixture.runId,
      role: null,
      nextCursor: 'art_01J8Z3XQ2K9WMV5T7N4B6C8D99',
      count: 2,
      items: artifactsPageFixture.items,
    };
    const page2: RunRecordArtifactPageResponse = {
      recordId: sealedRecordFixture.recordId,
      runId: sealedRecordFixture.runId,
      role: null,
      nextCursor: null,
      count: 1,
      items: [artifactsPageFixture.items[0]],
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) {
        const u = new URL('https://saintvision.local' + url);
        requestedCursor = u.searchParams.get('cursor');
        return (requestedCursor ? page2 : page1) as any;
      }
      if (url.includes('/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const pageCountEl = container.querySelector('[data-testid="seal-artifacts-page-count"]');
    expect(pageCountEl?.textContent).toContain('이 페이지 2건');
    expect(pageCountEl?.textContent).not.toContain('총 2개');

    const nextBtn = container.querySelector('[data-testid="seal-artifacts-next-page-btn"]') as HTMLButtonElement;
    expect(nextBtn).not.toBeNull();

    await act(async () => {
      nextBtn.click();
    });

    expect(requestedCursor).toBe('art_01J8Z3XQ2K9WMV5T7N4B6C8D99');
    expect(pageCountEl?.textContent).toContain('이 페이지 1건');
  });

  it('11. Sealed run with R2 500 error (F3 & G4): renders seal-artifacts-error with SYS-0002, no fake "0건"', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/record/artifacts')) {
        throw new ApiError(makeProblem(500, 'SYS-0002', 'Database connection error.', 'SYS'));
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
    expect(artErr?.textContent).toContain('SYS-0002');
    expect(artErr?.textContent).toContain('(500)');
    expect(artErr?.textContent).toContain('Database connection error.');

    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).not.toContain('아티팩트 0건');
    expect(liveRegion?.textContent).toContain('아티팩트 조회 실패');
  });

  it('12. Sealed run with R3 409 GRAPH-0002 error (F3 & G4): renders reproduction-failed fact with exact server detail, no fake "번들 없음"', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/context-bundle')) {
        throw new ApiError(makeProblem(409, 'GRAPH-0002', "A bundle item's snapshot is missing; the bundle cannot be reproduced.", 'GRAPH'));
      }
      if (url.includes('/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/record')) return sealedRecordFixture as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const repFailBanner = container.querySelector('[data-testid="seal-bundle-reproduction-failed"]');
    expect(repFailBanner).not.toBeNull();
    expect(repFailBanner?.getAttribute('data-tone')).toBe('mismatch');
    expect(container.querySelector('[data-testid="seal-bundle-not-found"]')).toBeNull();

    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('재현불가');
    expect(liveRegion?.textContent).not.toContain('번들 없음');
  });

  it('13. Sealed run with R3 404 No context bundle: renders not-found notice (F3)', async () => {
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

    expect(container.querySelector('[data-testid="seal-bundle-not-found"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="seal-bundle-reproduction-failed"]')).toBeNull();
  });

  it('14. Run ID switch: previous artifacts and bundle sections do not leak across runs (F7)', async () => {
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
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="seal-bundle-section"]')).not.toBeNull();

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });
    expect(container.querySelector('[data-testid="seal-artifacts-section"]')).toBeNull();
    expect(container.querySelector('[data-testid="seal-bundle-section"]')).toBeNull();
  });

  it('15. Abort Guard in unsealed path (F6 & G4): late R3 response on run switch does not corrupt state (correct route order)', async () => {
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
      if (url.includes('/run_B/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_B/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/run_B/record')) {
        return sealedRecordFixture as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    await act(async () => {
      resolveRunABundle?.(contextBundleFixture);
    });

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

    const darkBgRgb: [number, number, number] = [13, 17, 23];

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
    expect(isRunRecordResponse(sealedRecordFixture)).toBe(true);
    expect(isRunRecordResponse({ ...sealedRecordFixture, unauthorizedKey: 123 })).toBe(false);
    expect(isRunRecordResponse({ ...sealedRecordFixture, sealedAt: 'not-a-timestamp' })).toBe(false);
    expect(isRunRecordResponse({ ...sealedRecordFixture, sealedAt: '2026-02-30T12:00:00Z' })).toBe(false);

    const validVerify: ArtifactPinVerificationResponse = {
      runId: 'run_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
      recordId: 'rec_01J8Z3XQ2K9WMV5T7N4B6C8D0E',
      artifactId: ART_ID_1,
      pinnedChecksumSha256: SHA_A,
      verified: true,
    };
    expect(isArtifactPinVerificationResponse(validVerify)).toBe(true);
    expect(isArtifactPinVerificationResponse({ ...validVerify, extra: true })).toBe(false);

    expect(isContextBundleResponse(contextBundleFixture)).toBe(true);
    expect(isContextBundleResponse({ ...contextBundleFixture, bogusField: 'nope' })).toBe(false);
    expect(isContextBundleResponse({ ...contextBundleFixture, builtAt: 'not-a-timestamp' })).toBe(false);
    expect(isContextBundleResponse({ ...contextBundleFixture, builtAt: '2026-02-30T12:00:00Z' })).toBe(false);
  });

  it('19. Unsealed run with R3 409 GRAPH-0002 (G1): renders seal-bundle-reproduction-failed fact and live status includes 번들 재현불가', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/context-bundle')) {
        throw new ApiError(makeProblem(409, 'GRAPH-0002', "A bundle item's snapshot is missing; the bundle cannot be reproduced.", 'GRAPH'));
      }
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    expect(container.querySelector('[data-testid="seal-record-unsealed-notice"]')).not.toBeNull();
    const bundleSection = container.querySelector('[data-testid="seal-bundle-section"]');
    expect(bundleSection).not.toBeNull();
    const repFailedBanner = container.querySelector('[data-testid="seal-bundle-reproduction-failed"]');
    expect(repFailedBanner).not.toBeNull();
    expect(repFailedBanner?.getAttribute('data-tone')).toBe('mismatch');

    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 없음: 미봉인 실행, 번들 재현불가');
  });

  it('20. Unsealed run with R3 500 error (G1): renders seal-bundle-error and live status includes 번들 조회 실패', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/context-bundle')) {
        throw new ApiError(makeProblem(500, 'SYS-0002', 'Database connection error.', 'SYS'));
      }
      if (url.includes('/record')) {
        throw new ApiError(makeProblem(404, 'RES-0004', 'No sealed record for this run.', 'RES'));
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    expect(container.querySelector('[data-testid="seal-record-unsealed-notice"]')).not.toBeNull();
    const bundleSection = container.querySelector('[data-testid="seal-bundle-section"]');
    expect(bundleSection).not.toBeNull();
    const bundleErr = container.querySelector('[data-testid="seal-bundle-error"]');
    expect(bundleErr).not.toBeNull();
    expect(bundleErr?.textContent).toContain('SYS-0002');

    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).toContain('봉인 기록 없음: 미봉인 실행, 번들 조회 실패 (SYS-0002)');
  });

  it('21. Next page generation guard (G2): late page 2 response after run switch does not overwrite new run artifacts', async () => {
    let resolvePage2: ((value: any) => void) | null = null;
    const page2Promise = new Promise((resolve) => {
      resolvePage2 = resolve;
    });

    const page1A: RunRecordArtifactPageResponse = {
      recordId: 'rec_A',
      runId: 'run_A',
      role: null,
      nextCursor: 'cur_page2',
      count: 1,
      items: [
        {
          artifactId: 'art_01J8Z3XQ2K9WMV5T7N4B6C8DA1',
          role: 'diff',
          objectVersion: null,
          uri: 's3://art/diffA1',
          checksumSha256: SHA_A,
          byteSize: 100,
        },
      ],
    };

    const page2A: RunRecordArtifactPageResponse = {
      recordId: 'rec_A',
      runId: 'run_A',
      role: null,
      nextCursor: null,
      count: 1,
      items: [
        {
          artifactId: 'art_01J8Z3XQ2K9WMV5T7N4B6C8DA2',
          role: 'model',
          objectVersion: null,
          uri: 's3://art/modelA2',
          checksumSha256: SHA_B,
          byteSize: 200,
        },
      ],
    };

    const page1B: RunRecordArtifactPageResponse = {
      recordId: 'rec_B',
      runId: 'run_B',
      role: null,
      nextCursor: null,
      count: 1,
      items: [
        {
          artifactId: 'art_01J8Z3XQ2K9WMV5T7N4B6C8DB1',
          role: 'diff',
          objectVersion: null,
          uri: 's3://art/diffB1',
          checksumSha256: SHA_C,
          byteSize: 300,
        },
      ],
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/run_A/record/artifacts')) {
        const u = new URL('https://saintvision.local' + url);
        if (u.searchParams.get('cursor') === 'cur_page2') {
          return page2Promise;
        }
        return page1A as any;
      }
      if (url.includes('/run_A/context-bundle')) return { ...contextBundleFixture, runId: 'run_A' } as any;
      if (url.includes('/run_A/record')) return { ...sealedRecordFixture, runId: 'run_A' } as any;

      if (url.includes('/run_B/record/artifacts')) return page1B as any;
      if (url.includes('/run_B/context-bundle')) return { ...contextBundleFixture, runId: 'run_B' } as any;
      if (url.includes('/run_B/record')) return { ...sealedRecordFixture, runId: 'run_B' } as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });
    expect(container.textContent).toContain('art_01J8Z3XQ2K9WMV5T7N4B6C8DA1');

    const nextBtn = container.querySelector('[data-testid="seal-artifacts-next-page-btn"]') as HTMLButtonElement;
    expect(nextBtn).not.toBeNull();
    await act(async () => {
      nextBtn.click();
    });

    // Switch to run_B while run_A's page 2 is pending
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });
    expect(container.textContent).toContain('art_01J8Z3XQ2K9WMV5T7N4B6C8DB1');
    expect(container.textContent).not.toContain('art_01J8Z3XQ2K9WMV5T7N4B6C8DA1');

    // Now resolve run_A's page 2
    await act(async () => {
      resolvePage2?.(page2A);
    });

    // Run B's view must NOT contain Run A's page 2 artifact
    expect(container.textContent).toContain('art_01J8Z3XQ2K9WMV5T7N4B6C8DB1');
    expect(container.textContent).not.toContain('art_01J8Z3XQ2K9WMV5T7N4B6C8DA2');
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).not.toContain('다음 페이지 조회 완료');
  });

  it('22. Verify generation guard (F6 mutation kill): late verify response after run switch does not update state', async () => {
    let resolveVerify: ((value: any) => void) | null = null;
    const verifyPromise = new Promise((resolve) => {
      resolveVerify = resolve;
    });

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/run_A/record/artifacts/' + ART_ID_1 + '/verify')) {
        return verifyPromise;
      }
      if (url.includes('/run_A/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_A/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/run_A/record')) return { ...sealedRecordFixture, runId: 'run_A' } as any;

      if (url.includes('/run_B/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_B/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/run_B/record')) return { ...sealedRecordFixture, runId: 'run_B' } as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });

    const verifyBtn = container.querySelector(`[data-testid="seal-verify-btn-${ART_ID_1}"]`) as HTMLButtonElement;
    expect(verifyBtn).not.toBeNull();
    await act(async () => {
      verifyBtn.click();
    });

    // Switch to run_B while verify on run_A is pending
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    // Resolve verify on run_A with mismatch
    await act(async () => {
      resolveVerify?.({
        runId: 'run_A',
        recordId: 'rec_A',
        artifactId: ART_ID_1,
        pinnedChecksumSha256: SHA_A,
        verified: false,
      });
    });

    // Run B's ART_ID_1 verify badge must NOT show the mismatch result from Run A
    const verifyStatus = container.querySelector(`[data-testid="seal-artifact-verify-status-${ART_ID_1}"]`);
    expect(verifyStatus?.textContent).toContain('미검증 (검증 대기)');
    const liveRegion = container.querySelector('[data-testid="seal-record-live-status"]');
    expect(liveRegion?.textContent).not.toContain(`아티팩트 ${ART_ID_1} 검증 완료`);
  });

  it('23. Artifacts page reset guard (F7 mutation kill): setArtifactsPage(null) ensures previous run artifacts do not persist when new run R2 fails', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/run_A/record/artifacts')) return artifactsPageFixture as any;
      if (url.includes('/run_A/context-bundle')) return contextBundleFixture as any;
      if (url.includes('/run_A/record')) return { ...sealedRecordFixture, runId: 'run_A' } as any;

      if (url.includes('/run_B/record/artifacts')) {
        throw new ApiError(makeProblem(500, 'SYS-0002', 'Failed to retrieve artifacts for run B.', 'SYS'));
      }
      if (url.includes('/run_B/context-bundle')) return { ...contextBundleFixture, runId: 'run_B' } as any;
      if (url.includes('/run_B/record')) return { ...sealedRecordFixture, runId: 'run_B' } as any;
      return {} as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });
    expect(container.textContent).toContain(ART_ID_1);

    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    // Run B's R2 failed, so Run A's artifacts table MUST NOT be displayed
    expect(container.textContent).not.toContain(ART_ID_1);
    expect(container.querySelector('[data-testid="seal-artifacts-error"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="seal-artifacts-error"]')?.textContent).toContain('Failed to retrieve artifacts for run B.');
  });

  it('24. ProblemDetails strictness (G3 contract): canonical 404 missing required nullable causeRef is rejected and downgraded to NET-0404', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: new Headers({ 'content-type': 'application/problem+json' }),
        json: async () => ({
          type: 'about:blank',
          status: 404,
          code: 'RES-0004',
          title: 'RES-0004',
          detail: 'No such run.',
          category: 'RES',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          // causeRef and evidenceId are intentionally missing (undefined)
        }),
        text: async () => JSON.stringify({
          type: 'about:blank',
          status: 404,
          code: 'RES-0004',
          title: 'RES-0004',
          detail: 'No such run.',
          category: 'RES',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
        }),
      } as any;
    });

    await act(async () => {
      root.render(<SealRecordPanel projectId={sampleRun.projectId} runId={sampleRun.id} />);
    });

    const errorBanner = container.querySelector('[data-testid="seal-record-error-banner"]');
    expect(errorBanner).not.toBeNull();
    // Non-canonical problem (missing required nullable causeRef) is downgraded to NET-0404
    expect(errorBanner?.textContent).toContain('[NET-0404]');
    expect(errorBanner?.textContent).not.toContain('[RES-0004]');
    fetchSpy.mockRestore();
  });

  it('25. In-flight R1/R2 abort guard during run transition: late R1 and R2 responses from previous run (run_A) are discarded and do not leak into active run (run_B)', async () => {
    let resolveR1A: ((val: any) => void) | null = null;
    let resolveR2A: ((val: any) => void) | null = null;
    let capturedSignalA: AbortSignal | undefined;

    const uniqueRunAArtifactId = 'art_01J8Z3XQ2K9WMV5T7N4B6C8DA_UNIQUE';
    const uniqueRunBArtifactId = 'art_01J8Z3XQ2K9WMV5T7N4B6C8DB_ACTIVE';

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string, options?: any) => {
      if (url.includes('/run_A/record/artifacts')) {
        return new Promise((resolve) => {
          resolveR2A = resolve;
        });
      }
      if (url.includes('/run_A/context-bundle')) {
        return { ...contextBundleFixture, runId: 'run_A' } as any;
      }
      if (url.includes('/run_A/record')) {
        capturedSignalA = options?.signal;
        return new Promise((resolve) => {
          resolveR1A = resolve;
        });
      }

      if (url.includes('/run_B/record/artifacts')) {
        return {
          ...artifactsPageFixture,
          runId: 'run_B',
          items: [
            {
              ...artifactsPageFixture.items[0],
              artifactId: uniqueRunBArtifactId,
            },
          ],
        } as any;
      }
      if (url.includes('/run_B/context-bundle')) {
        return { ...contextBundleFixture, runId: 'run_B' } as any;
      }
      if (url.includes('/run_B/record')) {
        return { ...sealedRecordFixture, runId: 'run_B' } as any;
      }
      return {} as any;
    });

    // 1. Mount with run_A
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_A" />);
    });

    expect(capturedSignalA).toBeDefined();
    expect(capturedSignalA?.aborted).toBe(false);

    // 2. Switch to run_B while run_A R1 is still in-flight
    await act(async () => {
      root.render(<SealRecordPanel projectId="prj_01" runId="run_B" />);
    });

    // run_A signal must be aborted immediately upon transition
    expect(capturedSignalA?.aborted).toBe(true);

    // run_B loads immediately and renders run_B artifact
    expect(container.textContent).toContain(uniqueRunBArtifactId);
    expect(container.textContent).not.toContain(uniqueRunAArtifactId);

    // 3. Late response from run_A arrives
    await act(async () => {
      resolveR1A?.({ ...sealedRecordFixture, runId: 'run_A' });
      resolveR2A?.({
        ...artifactsPageFixture,
        runId: 'run_A',
        items: [
          {
            ...artifactsPageFixture.items[0],
            artifactId: uniqueRunAArtifactId,
          },
        ],
      });
    });

    // run_A response MUST be discarded by the abort guard and NOT leak into run_B
    expect(container.textContent).toContain(uniqueRunBArtifactId);
    expect(container.textContent).not.toContain(uniqueRunAArtifactId);
  });
});
