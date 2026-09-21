// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import { downloadAndVerifyArtifact } from '../src/shared/api/runArtifactObservation';
import * as client from '../src/shared/api/client';
import type { ProjectItem, RunItem } from '../src/contracts/types';
import { runResultViewFixture, runArtifactListFixture } from './fixtures/run-result';

const sampleProject: ProjectItem = {
  id: 'prj_test_artifact',
  name: 'Artifact Download Integrity Test Project',
};

const sampleRun: RunItem = {
  id: 'run_artifact_01',
  projectId: 'prj_test_artifact',
  status: 'succeeded',
  state: 'succeeded',
  targetNodeId: 'nod_01JABCDEF01',
  createdAt: '2026-09-22T00:00:00Z',
  startedAt: '2026-09-22T00:00:01Z',
  finishedAt: '2026-09-22T00:00:05Z',
};

const sampleResult = {
  ...runResultViewFixture,
  runId: 'run_artifact_01',
};

describe('산출물 바이트 다운로드 X-Content-SHA256 무결성 검증 및 3상태(검증됨·불일치·미검증) 단언', () => {
  const sampleContent = 'Hello SaintVision Raw Bytes';
  // echo -n "Hello SaintVision Raw Bytes" | sha256sum
  const sampleContentSha256 = 'f5c7ed5bc8c946092bcba0514cf15c5e011e12e96d15d7ef958dc136f48d2847';
  const corruptedSha256 = '0000000000000000000000000000000000000000000000000000000000000000';

  describe('1. downloadAndVerifyArtifact API 클라이언트 삼분할 무결성 검증', () => {
    const originalFetch = window.fetch;

    afterEach(() => {
      window.fetch = originalFetch;
      vi.restoreAllMocks();
    });

    it('X-Content-SHA256 헤더가 바이트 해시와 일치하면 integrity="verified"를 반환하고 Content-Disposition 파일명을 채택한다', async () => {
      const headers = new Headers();
      headers.set('x-content-sha256', sampleContentSha256);
      headers.set('content-disposition', 'attachment; filename="inference-output.dcm"');
      headers.set('content-length', String(sampleContent.length));

      window.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers,
        blob: async () => new Blob([sampleContent]),
      } as any);

      const result = await downloadAndVerifyArtifact(
        'prj_test',
        'run_01',
        'output/inference.dcm',
        'fallback.dcm'
      );

      expect(result.integrity).toBe('verified');
      expect(result.fileName).toBe('inference-output.dcm');
      expect(result.calculatedSha256).toBe(sampleContentSha256);
      expect(result.expectedSha256).toBe(sampleContentSha256);
      expect(result.blob.size).toBe(sampleContent.length);
    });

    it('X-Content-SHA256 헤더와 계산된 바이트 해시가 불일치하면 integrity="mismatch"를 반환한다 (전송 변조/손상 포착)', async () => {
      const headers = new Headers();
      headers.set('x-content-sha256', corruptedSha256); // Mismatched checksum
      headers.set('content-length', String(sampleContent.length));

      window.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers,
        blob: async () => new Blob([sampleContent]),
      } as any);

      const result = await downloadAndVerifyArtifact(
        'prj_test',
        'run_01',
        'output/inference.dcm'
      );

      expect(result.integrity).toBe('mismatch');
      expect(result.calculatedSha256).toBe(sampleContentSha256);
      expect(result.expectedSha256).toBe(corruptedSha256);
    });

    it('X-Content-SHA256 헤더가 부재하면 조작이나 단언 없이 integrity="unverified"를 반환한다', async () => {
      const headers = new Headers(); // No x-content-sha256 header

      window.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers,
        blob: async () => new Blob([sampleContent]),
      } as any);

      const result = await downloadAndVerifyArtifact(
        'prj_test',
        'run_01',
        'output/inference.dcm'
      );

      expect(result.integrity).toBe('unverified');
      expect(result.calculatedSha256).toBe(sampleContentSha256);
      expect(result.expectedSha256).toBeNull();
    });
  });

  describe('2. DeveloperStudio 컴포넌트 DOM 레벨 무결성 단언 및 허위 완료 차단', () => {
    let container: HTMLDivElement;
    let root: Root;
    const originalFetch = window.fetch;

    beforeEach(() => {
      (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
      container = document.createElement('div');
      document.body.appendChild(container);
      root = createRoot(container);

      window.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
      window.URL.revokeObjectURL = vi.fn();

      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint.endsWith('/result')) {
          return sampleResult as any;
        }
        if (endpoint.includes('/workspaces')) {
          return { projectId: sampleProject.id, workspaces: [] } as any;
        }
        if (endpoint.includes('/runs/')) {
          return sampleRun as any;
        }
        return {} as any;
      });
    });

    afterEach(() => {
      act(() => {
        root.unmount();
      });
      container.remove();
      window.fetch = originalFetch;
      vi.restoreAllMocks();
    });

    it('서버 X-Content-SHA256 헤더와 일치할 때만 [무결성 검증 완료]를 표출하고 파일을 다운로드한다', async () => {
      const headers = new Headers();
      headers.set('x-content-sha256', sampleContentSha256);
      headers.set('content-disposition', 'attachment; filename="verified-output.dcm"');

      window.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers,
        blob: async () => new Blob([sampleContent]),
      } as any);

      await act(async () => {
        root.render(
          <DeveloperStudio
            project={sampleProject}
            nodes={[]}
            runs={[sampleRun]}
            initialStep={4}
            initialRunId={sampleRun.id}
          />
        );
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      const rawDownloadBtn = container.querySelector('[data-testid="artifact-raw-download-btn"]') as HTMLButtonElement;
      expect(rawDownloadBtn).not.toBeNull();
      expect(rawDownloadBtn.disabled).toBe(false);

      await act(async () => {
        rawDownloadBtn.click();
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      // role="status" 피드백 배너 검증
      const notice = container.querySelector('[data-testid="studio-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('[무결성 검증 완료]');
      expect(notice?.textContent).toContain('verified-output.dcm');
      expect(notice?.textContent).toContain('SHA-256 일치');

      // createObjectURL 호출되어 브라우저 다운로드 트리거됨
      expect(window.URL.createObjectURL).toHaveBeenCalled();
    });

    it('서버 X-Content-SHA256 헤더와 불일치 시 조용히 넘기지 않고 [무결성 검증 실패](role=alert)를 표출하며 다운로드를 차단한다', async () => {
      const headers = new Headers();
      headers.set('x-content-sha256', corruptedSha256); // Tampered / Corrupted checksum
      headers.set('content-disposition', 'attachment; filename="tampered-file.dcm"');

      window.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers,
        blob: async () => new Blob([sampleContent]),
      } as any);

      await act(async () => {
        root.render(
          <DeveloperStudio
            project={sampleProject}
            nodes={[]}
            runs={[sampleRun]}
            initialStep={4}
            initialRunId={sampleRun.id}
          />
        );
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      const rawDownloadBtn = container.querySelector('[data-testid="artifact-raw-download-btn"]') as HTMLButtonElement;
      expect(rawDownloadBtn).not.toBeNull();

      await act(async () => {
        rawDownloadBtn.click();
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      // role="alert" 에러 배너 표출 검증
      const notice = container.querySelector('[data-testid="studio-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('alert');
      expect(notice?.textContent).toContain('[무결성 검증 실패]');
      expect(notice?.textContent).toContain('tampered-file.dcm');
      expect(notice?.textContent).toContain('불일치');
      expect(notice?.textContent).toContain('손상 위험으로 저장이 중단되었습니다');

      // createObjectURL이 호출되지 않아 손상 파일 저장이 차단됨
      expect(window.URL.createObjectURL).not.toHaveBeenCalled();
    });

    it('서버 X-Content-SHA256 헤더가 부재할 경우 [다운로드 완료 · 무결성 미검증]으로 정직하게 고지한다', async () => {
      const headers = new Headers(); // No x-content-sha256 header

      window.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers,
        blob: async () => new Blob([sampleContent]),
      } as any);

      await act(async () => {
        root.render(
          <DeveloperStudio
            project={sampleProject}
            nodes={[]}
            runs={[sampleRun]}
            initialStep={4}
            initialRunId={sampleRun.id}
          />
        );
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      const rawDownloadBtn = container.querySelector('[data-testid="artifact-raw-download-btn"]') as HTMLButtonElement;
      expect(rawDownloadBtn).not.toBeNull();

      await act(async () => {
        rawDownloadBtn.click();
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      // role="status"로 미검증 사실 고지
      const notice = container.querySelector('[data-testid="studio-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('[다운로드 완료 · 무결성 미검증]');
      expect(notice?.textContent).toContain('서버 X-Content-SHA256 헤더 부재');

      // 다운로드는 진행됨
      expect(window.URL.createObjectURL).toHaveBeenCalled();
    });
  });
});
