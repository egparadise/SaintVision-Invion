// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MonacoWorkspaceEditor } from '../src/features/editor/MonacoWorkspaceEditor';
import * as workspaceEditApi from '../src/shared/api/workspaceEditObservation';
import type { WorkspaceEditView } from '../src/contracts/types';

function setTextareaValue(textarea: HTMLTextAreaElement, value: string) {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
  descriptor?.set?.call(textarea, value);
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
  textarea.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('화면 결함 5대 부류 치유 트랙 3차: MonacoWorkspaceEditor 커널 체크아웃 파일 저장 실배선, 인메모리 은폐 차단 및 터미널 모의 고지', () => {
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
  // 1. 커널 체크아웃 파일 저장 실배선 (runId, checkoutId 컨텍스트 제공 시)
  // =========================================================================
  describe('Priority 6-A: 커널 체크아웃 파일 저장 실배선 및 성공 상태 표출', () => {
    it('runId와 checkoutId가 제공되면 커널 POST .../files API를 정합한 payload로 호출하고 성공 배너를 표출한다', async () => {
      const mockResult: WorkspaceEditView = {
        projectId: 'prj_test',
        runId: 'run_test_01',
        checkoutId: 'chk_test_01',
        revision: 4,
        sha256: 'a'.repeat(64),
        files: [{ path: 'src/server.ts', sha256: 'b'.repeat(64), size: 100, executable: false }],
        readOnly: false,
      };

      const saveSpy = vi
        .spyOn(workspaceEditApi, 'saveWorkspaceEditView')
        .mockResolvedValue(mockResult);

      const onSaveSuccessSpy = vi.fn();

      act(() => {
        root.render(
          <MonacoWorkspaceEditor
            workspaceId="wsp_test_100"
            projectId="prj_test"
            runId="run_test_01"
            checkoutId="chk_test_01"
            currentRevision={3}
            currentSha256={'c'.repeat(64)}
            onSaveSuccess={onSaveSuccessSpy}
          />
        );
      });

      // 1. 상단 모드 배너가 '커널 체크아웃 실배선 모드'를 안내해야 함
      const topNotice = container.querySelector('[data-testid="editor-unexposed-notice"]');
      expect(topNotice?.textContent).toContain('커널 체크아웃 실배선 모드');
      expect(topNotice?.textContent).toContain('/v1/projects/prj_test/runs/run_test_01/checkouts/chk_test_01/files');

      // 2. 저장 버튼 라벨이 'Save File (Kernel)'이어야 함
      const saveBtn = container.querySelector('[data-testid="editor-save-btn"]') as HTMLButtonElement;
      expect(saveBtn).not.toBeNull();
      expect(saveBtn.textContent?.trim()).toBe('Save File (Kernel)');

      // 3. 파일 내용 변경 (Dirty 상태 유도)
      const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
      expect(textarea).not.toBeNull();
      await act(async () => {
        setTextareaValue(textarea, '// modified content for kernel test\nconst x = 1;');
      });

      // 4. 저장 버튼 클릭
      await act(async () => {
        saveBtn.click();
      });

      // 5. saveWorkspaceEditView가 정확한 계약으로 호출되었는지 검증
      expect(saveSpy).toHaveBeenCalledTimes(1);
      expect(saveSpy).toHaveBeenCalledWith(
        'prj_test',
        'run_test_01',
        'chk_test_01',
        expect.objectContaining({
          expectedRevision: 3,
          expectedSha256: 'c'.repeat(64),
          changes: expect.arrayContaining([
            expect.objectContaining({
              path: 'src/server.ts',
              executable: false,
            }),
          ]),
        })
      );

      // 6. 성공 배너(editor-save-success-notice, role="status") 및 콜백 검증
      const successNotice = container.querySelector('[data-testid="editor-save-success-notice"]');
      expect(successNotice).not.toBeNull();
      expect(successNotice?.getAttribute('role')).toBe('status');
      expect(successNotice?.textContent).toContain('커널 체크아웃 파일 저장 완료');
      expect(successNotice?.textContent).toContain('Revision: 4');
      expect(onSaveSuccessSpy).toHaveBeenCalledWith(mockResult);

      // 7. 오류 배너나 미연결 경고 배너는 없어야 함
      expect(container.querySelector('[data-testid="editor-save-error-banner"]')).toBeNull();
      expect(container.querySelector('[data-testid="editor-context-notice"]')).toBeNull();
    });
  });

  // =========================================================================
  // 2. 커널 저장 실패 시 에러 은폐 차단 및 조기 성공 위장 금지
  // =========================================================================
  describe('Priority 6-B: 커널 저장 실패 시 에러 은폐 차단 및 조기 성공 위장 금지', () => {
    it('백엔드 저장 API 실패 시 에러 배너(role=alert)를 표시하고 성공을 위장하지 않는다', async () => {
      vi.spyOn(workspaceEditApi, 'saveWorkspaceEditView').mockRejectedValue(
        new Error('409 Conflict: revision mismatch on checkout')
      );

      act(() => {
        root.render(
          <MonacoWorkspaceEditor
            workspaceId="wsp_test_100"
            projectId="prj_test"
            runId="run_test_01"
            checkoutId="chk_test_01"
          />
        );
      });

      // 파일 수정 후 저장
      const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
      await act(async () => {
        setTextareaValue(textarea, '// conflict test');
      });

      const saveBtn = container.querySelector('[data-testid="editor-save-btn"]') as HTMLButtonElement;
      await act(async () => {
        saveBtn.click();
      });

      // 1. 에러 배너(editor-save-error-banner, role="alert") 표출
      const errorBanner = container.querySelector('[data-testid="editor-save-error-banner"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.getAttribute('role')).toBe('alert');
      expect(errorBanner?.textContent).toContain('409 Conflict: revision mismatch on checkout');

      // 2. 성공 배너는 절대 존재하지 않아야 함
      expect(container.querySelector('[data-testid="editor-save-success-notice"]')).toBeNull();
    });
  });

  // =========================================================================
  // 3. 체크아웃 컨텍스트 부재 시 로컬 메모리 전용 경고 및 네트워크 호출 0회 가드
  // =========================================================================
  describe('Priority 6-C: 체크아웃 컨텍스트 미연결 시 로컬 메모리 임시 보존 경고(role=alert) 및 네트워크 0회 차단', () => {
    it('runId나 checkoutId가 없을 때 저장하면 네트워크 호출 없이 로컬 메모리 보존 경고 배너를 표출한다', async () => {
      const saveSpy = vi.spyOn(workspaceEditApi, 'saveWorkspaceEditView');

      act(() => {
        root.render(<MonacoWorkspaceEditor workspaceId="wsp_standalone_01" projectId="prj_alpha" />);
      });

      // 1. 상단 안내 및 버튼 라벨 확인
      const topNotice = container.querySelector('[data-testid="editor-unexposed-notice"]');
      expect(topNotice?.textContent).toContain('인메모리 워크스페이스 에디터 (체크아웃 컨텍스트 미연결)');

      const saveBtn = container.querySelector('[data-testid="editor-save-btn"]') as HTMLButtonElement;
      expect(saveBtn.textContent?.trim()).toBe('Save File (Local Sandbox)');

      // 2. 파일 수정 후 저장
      const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
      await act(async () => {
        setTextareaValue(textarea, '// standalone edit');
      });

      await act(async () => {
        saveBtn.click();
      });

      // 3. 백엔드 네트워크 호출은 0회여야 함
      expect(saveSpy).not.toHaveBeenCalled();

      // 4. 컨텍스트 미연결 경고 배너(editor-context-notice, role="alert")가 표시되어야 함 (사용자 오판 방지)
      const contextNotice = container.querySelector('[data-testid="editor-context-notice"]');
      expect(contextNotice).not.toBeNull();
      expect(contextNotice?.getAttribute('role')).toBe('alert');
      expect(contextNotice?.textContent).toContain('체크아웃 컨텍스트(runId/checkoutId)가 연결되지 않아 서버에 영속 저장되지 않았습니다');
      expect(contextNotice?.textContent).toContain('로컬 브라우저 샌드박스 메모리에만 임시 보존됨');
    });
  });

  // =========================================================================
  // 4. 터미널 PTY 로컬 에뮬레이션 모의 고지
  // =========================================================================
  describe('Priority 6-D: 터미널 PTY 로컬 에뮬레이션 모의 고지', () => {
    it('터미널 헤더에 editor-terminal-mock-notice(role=status)를 표출하여 독립 PTY 미연결임을 정직하게 알린다', () => {
      act(() => {
        root.render(<MonacoWorkspaceEditor workspaceId="wsp_standalone_01" />);
      });

      const terminalNotice = container.querySelector('[data-testid="editor-terminal-mock-notice"]');
      expect(terminalNotice).not.toBeNull();
      expect(terminalNotice?.getAttribute('role')).toBe('status');
      expect(terminalNotice?.textContent).toContain('[로컬 에뮬레이션 · 독립 PTY 미연결]');
    });
  });
});
