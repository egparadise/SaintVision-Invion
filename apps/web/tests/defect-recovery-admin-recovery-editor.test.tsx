// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import { DistributedRecoveryView } from '../src/features/recovery/DistributedRecoveryView';
import { MonacoWorkspaceEditor } from '../src/features/editor/MonacoWorkspaceEditor';
import * as client from '../src/shared/api/client';
import type { NodeItem } from '../src/contracts/types';

const MOCK_NODES: NodeItem[] = [
  {
    id: 'nod_test_01',
    hostname: 'node-win-01',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 20,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsagePercent: 30,
    gpuName: 'NVIDIA RTX 4090',
    gpuCount: 1,
    status: 'healthy',
    labels: { tier: 'gpu' },
  },
];

describe('화면 결함 5대 부류 치유 트랙 2차 (Priority 4: 관리자 콘솔 행위자 실배선, Priority 5: 분산 복구 모의 고지, Priority 6: 에디터 저장 샌드박스 고지)', () => {
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
    vi.restoreAllMocks();
  });

  // =========================================================================
  // Priority 4: AdminSecurityConsole usr_admin_01 하드코딩 제거 및 세션 실배선
  // =========================================================================
  describe('Priority 4: AdminSecurityConsole 행위자(actor) 실배선 및 세션 부재 0-call 가드', () => {
    it('인증된 currentUser가 주어졌을 때 노드 Drain 요청에 실제 actor 식별자를 전송한다', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockResolvedValue({});

      act(() => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_actual_admin_77', name: 'Actual Admin', role: 'admin' }}
          />
        );
      });

      // 1. 인증 부재 경고 배너가 없어야 함
      const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]');
      expect(authNotice).toBeNull();

      // 2. Drain 탭으로 이동
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      expect(drainTabBtn).toBeDefined();
      act(() => {
        drainTabBtn?.click();
      });

      // 3. Drain 액션 버튼 클릭
      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      );
      expect(drainBtn).toBeDefined();

      await act(async () => {
        drainBtn?.click();
      });

      // 4. apiClient에 하드코딩 'usr_admin_01'이 아니라 실제 로그인 사용자 'usr_actual_admin_77'이 전달되어야 함
      expect(apiClientSpy).toHaveBeenCalledWith(
        '/v1/nodes/nod_test_01/drain',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            actor: 'usr_actual_admin_77',
            reason: 'Admin manual maintenance and isolation protocol',
          }),
        })
      );
    });

    it('currentUser가 null일 때 경고 배너(role=alert)를 렌더링하고 Drain 네트워크 호출을 0회로 원천 차단한다', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockResolvedValue({});

      act(() => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={null}
          />
        );
      });

      // 1. 인증 세션 부재 경고 배너 검증
      const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]');
      expect(authNotice).not.toBeNull();
      expect(authNotice?.getAttribute('role')).toBe('alert');
      expect(authNotice?.textContent).toContain('인증된 관리자 세션 부재');

      // 2. Drain 탭으로 이동 후 클릭 시도
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      expect(drainTabBtn).toBeDefined();
      act(() => {
        drainTabBtn?.click();
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      );
      expect(drainBtn).toBeDefined();

      await act(async () => {
        drainBtn?.click();
      });

      // 3. 네트워크 0회 호출 가드 검증 (0 network calls)
      expect(apiClientSpy).not.toHaveBeenCalled();

      // 4. 에러 배너 표출 검증
      const drainError = container.querySelector('[data-testid="admin-drain-error-banner"]');
      expect(drainError).not.toBeNull();
      expect(drainError?.textContent).toContain('인증된 관리자 세션이 없습니다');
    });
  });

  // =========================================================================
  // Priority 5: DistributedRecoveryView 체크아웃 시뮬레이션 및 unexposed notice
  // =========================================================================
  describe('Priority 5: DistributedRecoveryView 체크아웃 시뮬레이션 및 unexposed notice', () => {
    it('상단에 recovery-unexposed-notice(role=status)를 렌더링하고 백엔드 API 부재를 고지한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      const notice = container.querySelector('[data-testid="recovery-unexposed-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출)');
      expect(notice?.textContent).toContain('클라이언트 인메모리 시뮬레이션입니다');
    });

    it('체크아웃 생성 시 실제 파일시스템에 기록된 양 속이지 않고 모의 시뮬레이션 고지를 표시한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      const checkoutBtn = container.querySelector('[data-testid="create-checkout-btn"]') as HTMLButtonElement;
      expect(checkoutBtn).not.toBeNull();

      act(() => {
        checkoutBtn.click();
      });

      // 이전의 "✓ ADR-043 Writable Generation 생성 완료" 허위 완료 배너가 아니어야 함
      expect(container.textContent).toContain('ℹ️ [모의 시뮬레이션] ADR-043 Writable Generation 생성');
      expect(container.textContent).toContain('백엔드 파일시스템에는 기록되지 않습니다');
      expect(container.textContent).toContain('sim_chk_1');
    });
  });

  // =========================================================================
  // Priority 6: MonacoWorkspaceEditor 인메모리 샌드박스 고지
  // =========================================================================
  describe('Priority 6: MonacoWorkspaceEditor 인메모리 샌드박스 고지', () => {
    it('상단에 editor-unexposed-notice(role=status)를 렌더링하고 저장 버튼에 로컬 샌드박스 명칭을 적용한다', () => {
      act(() => {
        root.render(<MonacoWorkspaceEditor workspaceId="wsp_test_01" projectId="prj_alpha" />);
      });

      const notice = container.querySelector('[data-testid="editor-unexposed-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('인메모리 워크스페이스 에디터 (체크아웃 컨텍스트 미연결)');
      expect(notice?.textContent).toContain('WorkspaceEditView 계약');

      const saveBtn = container.querySelector('[data-testid="editor-save-btn"]');
      expect(saveBtn).not.toBeNull();
      expect(saveBtn?.textContent).toContain('Save File (Local Sandbox)');
      expect(saveBtn?.getAttribute('title')).toContain('체크아웃 컨텍스트 미연결');
    });
  });
});
