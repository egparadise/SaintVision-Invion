// @vitest-environment happy-dom
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { EvidenceViewer } from '@/features/evidence/EvidenceViewer';

describe('EvidenceViewer Integrity Contract Guard (허위 PASS 차단 및 정직한 미검증 고지)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
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

  it('sealed이고 sha256 해시가 있어도 verified가 참이 아니면 결코 PASS를 위조하지 않고 UNVERIFIED와 안내 배너를 표출한다', async () => {
    // Mock backend returning sealed run with output hash, but NO verified=true
    const mockResult = {
      runId: 'run_test_unverified_01',
      projectId: 'prj_test_pacs',
      state: 'succeeded',
      sealed: true,
      output: {
        sha256: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        sizeBytes: 1024,
        // verified is deliberately omitted/undefined
      },
      completedAt: '2026-09-22T04:00:00.000Z',
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => mockResult,
      } as any;
    });

    await act(async () => {
      root.render(
        <EvidenceViewer
          runId="run_test_unverified_01"
          projectId="prj_test_pacs"
          onBack={() => {}}
        />
      );
    });

    // Allow promise resolution
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const renderedText = container.textContent || '';

    // 1. Must display UNVERIFIED badge
    expect(renderedText).toContain('⚠️ 출력 무결성 미검증 (UNVERIFIED)');

    // 2. Must NOT display PASS badge
    expect(renderedText).not.toContain('✓ 출력 무결성 검증 통과 (PASS)');

    // 3. Must display honest notice banner explaining that hash exists and sealed, but cryptographic verification is pending
    const noticeEl = container.querySelector('[data-testid="evidence-unverified-notice"]');
    expect(noticeEl).not.toBeNull();
    expect(noticeEl?.textContent).toContain('봉인 및 해시 계산 완료 (SEALED)');
    expect(noticeEl?.textContent).toContain('미검증 (UNVERIFIED)');
  });

  it('res.output.verified === true 일 때만 비로소 PASS 뱃지를 표출한다', async () => {
    // Mock backend returning verified=true
    const mockResult = {
      runId: 'run_test_verified_02',
      projectId: 'prj_test_pacs',
      state: 'succeeded',
      sealed: true,
      output: {
        sha256: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        sizeBytes: 1024,
        verified: true, // Cryptographically verified
      },
      completedAt: '2026-09-22T04:00:00.000Z',
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => mockResult,
      } as any;
    });

    await act(async () => {
      root.render(
        <EvidenceViewer
          runId="run_test_verified_02"
          projectId="prj_test_pacs"
          onBack={() => {}}
        />
      );
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const renderedText = container.textContent || '';

    // 1. Must display PASS badge
    expect(renderedText).toContain('✓ 출력 무결성 검증 통과 (PASS)');

    // 2. Must NOT display UNVERIFIED badge
    expect(renderedText).not.toContain('⚠️ 출력 무결성 미검증 (UNVERIFIED)');

    // 3. Notice banner should not be displayed
    const noticeEl = container.querySelector('[data-testid="evidence-unverified-notice"]');
    expect(noticeEl).toBeNull();
  });

  it('실행이 실패한 경우(state === failed) 무결성 위조로 오도하지 않고 RUN_FAILED 뱃지와 실행 실패 안내 배너를 정직하게 표출한다', async () => {
    const mockResult = {
      runId: 'run_test_failed_03',
      projectId: 'prj_test_pacs',
      state: 'failed',
      sealed: false,
      outputAbsentReason: 'EXECUTION_ERROR',
      completedAt: '2026-09-22T04:00:00.000Z',
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => mockResult,
      } as any;
    });

    await act(async () => {
      root.render(
        <EvidenceViewer
          runId="run_test_failed_03"
          projectId="prj_test_pacs"
          onBack={() => {}}
        />
      );
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const renderedText = container.textContent || '';

    // 1. Must display RUN_FAILED badge (not misleading FAIL)
    expect(renderedText).toContain('✗ 실행 실패 · 출력 부재 (RUN_FAILED)');

    // 2. Must NOT display PASS badge
    expect(renderedText).not.toContain('✓ 출력 무결성 검증 통과 (PASS)');

    // 3. Must display honest execution failure notice distinguishing process failure from output tampering
    const noticeEl = container.querySelector('[data-testid="evidence-run-failed-notice"]');
    expect(noticeEl).not.toBeNull();
    expect(noticeEl?.textContent).toContain('작업 실행 실패 (RUN_FAILED)');
    expect(noticeEl?.textContent).toContain('프로세스 실행 자체의 미완료 또는 실패');
  });

  it('출력이 존재하나 verified === false인 경우 FAIL 뱃지와 다이제스트 불일치 경고 배너를 표출한다 (계약 확장 대비)', async () => {
    const mockResult = {
      runId: 'run_test_tampered_04',
      projectId: 'prj_test_pacs',
      state: 'succeeded',
      sealed: true,
      output: {
        sha256: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        sizeBytes: 1024,
        verified: false, // Cryptographic verification failed
      },
      completedAt: '2026-09-22T04:00:00.000Z',
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => mockResult,
      } as any;
    });

    await act(async () => {
      root.render(
        <EvidenceViewer
          runId="run_test_tampered_04"
          projectId="prj_test_pacs"
          onBack={() => {}}
        />
      );
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const renderedText = container.textContent || '';

    // 1. Must display FAIL badge
    expect(renderedText).toContain('✗ 출력 무결성 검증 실패 (FAIL)');

    // 2. Must display cryptographic failure notice banner
    const failEl = container.querySelector('[data-testid="evidence-failed-notice"]');
    expect(failEl).not.toBeNull();
    expect(failEl?.textContent).toContain('출력 무결성 검증 실패 (FAIL)');
    expect(failEl?.textContent).toContain('암호학적 영수증 또는 체크섬 검증에 실패');
  });
});
