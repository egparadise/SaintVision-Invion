// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { IntranetDeploymentView } from '../src/features/deployment/IntranetDeploymentView';
import { ReleaseCandidateView } from '../src/features/release/ReleaseCandidateView';

describe('화면 결함 5대 부류 치유 트랙 4차: IntranetDeploymentView 운영자 행위자 실배선/미인증 차단 및 ReleaseCandidateView 롤백 모의 고지', () => {
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
  // 1. IntranetDeploymentView: 운영자 행위자 실배선 & 미인증 서명 차단
  // =========================================================================
  describe('Priority 7-A: IntranetDeploymentView 운영자 행위자 실배선 및 미인증 차단 가드', () => {
    it('currentUser가 주어졌을 때 operatorId에 실제 사용자 ID가 바인딩되고 서명 시 모의 시뮬레이션 배너가 표출된다', async () => {
      act(() => {
        root.render(
          <IntranetDeploymentView
            currentUser={{ id: 'usr_operator_lead_99', name: 'Ops Leader', role: 'operator' }}
          />
        );
      });

      // 1. 백엔드 배포 API 미노출 안내 배너 확인 (role="status")
      const unexposedNotice = container.querySelector('[data-testid="deployment-unexposed-notice"]');
      expect(unexposedNotice).not.toBeNull();
      expect(unexposedNotice?.getAttribute('role')).toBe('status');
      expect(unexposedNotice?.textContent).toContain('내부망 HTTPS 배포 및 운영 인수 시뮬레이터 (백엔드 배포 API 미노출)');

      // 2. 인증 필요 알림 배너가 없어야 함
      expect(container.querySelector('[data-testid="deployment-auth-required-notice"]')).toBeNull();

      // 3. operatorId 입력창에 실제 로그인 사용자 ID가 채워져 있어야 함 (usr_operator_lead 하드코딩 아님)
      const opInput = container.querySelector('[data-testid="deployment-operator-id-input"]') as HTMLInputElement;
      expect(opInput).not.toBeNull();
      expect(opInput.value).toBe('usr_operator_lead_99');

      // 4. 서명 버튼 클릭
      const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
      expect(signoffBtn).not.toBeNull();
      expect(signoffBtn.disabled).toBe(false);

      await act(async () => {
        signoffBtn.click();
      });

      // 5. 서명 결과 알림에 [모의 시뮬레이션] 및 백엔드 배포 API 미노출이 정직하게 표출되어야 함
      expect(container.textContent).toContain('✔ [모의 시뮬레이션] 최종 프로덕션 릴리스');
      expect(container.textContent).toContain('usr_operator_lead_99');
      expect(container.textContent).toContain('(백엔드 배포 API 미노출)');
    });

    it('currentUser가 null일 때 deployment-auth-required-notice(role=alert)를 렌더링하고 서명 버튼을 비활성화한다', async () => {
      act(() => {
        root.render(<IntranetDeploymentView currentUser={null} />);
      });

      // 1. 인증 필요 알림 배너 표출 검증 (role="alert", assertive)
      const authNotice = container.querySelector('[data-testid="deployment-auth-required-notice"]');
      expect(authNotice).not.toBeNull();
      expect(authNotice?.getAttribute('role')).toBe('alert');
      expect(authNotice?.textContent).toContain('인증 필요: 로그인된 운영자 세션이 없습니다');

      // 2. operatorId 입력창이 빈 문자열이어야 함
      const opInput = container.querySelector('[data-testid="deployment-operator-id-input"]') as HTMLInputElement;
      expect(opInput.value).toBe('');

      // 3. 서명 버튼이 비활성화(disabled) 상태여야 함
      const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
      expect(signoffBtn.disabled).toBe(true);
      expect(signoffBtn.getAttribute('aria-disabled')).toBe('true');
      expect(signoffBtn.getAttribute('title')).toContain('운영자 계정 로그인이 필요합니다');
    });
  });

  // =========================================================================
  // 2. ReleaseCandidateView: 롤백 모의 고지 & unexposed notice
  // =========================================================================
  describe('Priority 7-B: ReleaseCandidateView 롤백 모의 고지 및 허위 축하 배너 차단', () => {
    it('상단에 release-unexposed-notice(role=status)를 렌더링하고 롤백 시 모의 고지를 표출한다', async () => {
      act(() => {
        root.render(<ReleaseCandidateView />);
      });

      // 1. 백엔드 배포 API 미노출 안내 배너 확인 (role="status")
      const unexposedNotice = container.querySelector('[data-testid="release-unexposed-notice"]');
      expect(unexposedNotice).not.toBeNull();
      expect(unexposedNotice?.getAttribute('role')).toBe('status');
      expect(unexposedNotice?.textContent).toContain('릴리스 후보(RC) 및 무중단 롤백 제어기 (백엔드 배포 API 미노출)');

      // 2. 롤백 버튼 탐색 및 클릭
      const rollbackBtns = Array.from(container.querySelectorAll('button')).filter((b) =>
        b.textContent?.includes('이 버전으로 롤백')
      );
      expect(rollbackBtns.length).toBeGreaterThan(0);

      await act(async () => {
        rollbackBtns[0].click();
      });

      // 3. 과거의 "캐시 무효화 및 무중단 상태가 확인되었습니다" 허위 축하 배너가 아니어야 함
      expect(container.textContent).not.toContain('캐시 무효화 및 무중단 상태가 확인되었습니다');

      // 4. 정직한 [모의 시뮬레이션] 롤백 고지 확인
      expect(container.textContent).toContain('✔ [모의 시뮬레이션] AC-11 롤백 절차 검증 완료');
      expect(container.textContent).toContain('백엔드 릴리스 제어 API 미노출 상태로 실제 인프라 및 CDN 캐시 미반영');
    });
  });
});
