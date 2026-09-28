// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { IntranetDeploymentView } from '../src/features/deployment/IntranetDeploymentView';
import { DeploymentManager } from '../src/features/deployment/deploymentEngine';
import { NodeItem } from '../src/contracts/types';

describe('S12-FE: Comprehensive Defect Fix Verification (DEF-S12-01 ~ DEF-S12-18)', () => {
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
  // DEF-S12-01 & DEF-S12-02: Accessibility (Skip link & Heading hierarchy)
  // =========================================================================
  it('DEF-S12-01 & DEF-S12-02: renders accessible skip link and main h1 heading', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    const skipLink = container.querySelector('a[href="#deployment-main-content"]');
    expect(skipLink).not.toBeNull();
    expect(skipLink?.textContent).toContain('본문으로 바로가기');

    const h1 = container.querySelector('h1#deployment-main-content');
    expect(h1).not.toBeNull();
    expect(h1?.textContent).toContain('내부망 HTTPS 배포 및 운영 인수 검증');
  });

  // =========================================================================
  // DEF-S12-03: Node table status badge binding & accessibility
  // =========================================================================
  it('DEF-S12-03: binds node smoke status correctly with accessible aria-label and colors', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    const nodeRows = container.querySelectorAll('[data-testid^="node-row-"]');
    expect(nodeRows.length).toBe(5);

    // Initial architectural nodes all have smokeStatus: passed
    nodeRows.forEach((row) => {
      const badge = row.querySelector('[aria-label="Smoke status: passed"]');
      expect(badge).not.toBeNull();
      expect(badge?.textContent).toContain('PASSED');
    });
  });

  // =========================================================================
  // DEF-S12-04 & DEF-S12-13: Preflight checks specification labeling
  // =========================================================================
  it('DEF-S12-04 & DEF-S12-13: clearly marks preflight and gateway probe as specification examples', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('[설계 규격 예시 (202개 검증 항목)]');
    expect(container.textContent).toContain('[사전 설계 규격 항목] Nginx TLS 1.2/1.3 협상');
    expect(container.textContent).toContain('(게이트웨이 실시간 프로브 미연결)');
  });

  // =========================================================================
  // DEF-S12-05: Dynamic actionNotice accessibility
  // =========================================================================
  it('DEF-S12-05: actionNotice uses status or alert role and assertive/polite aria-live', async () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
    expect(signoffBtn).not.toBeNull();

    await act(async () => {
      signoffBtn.click();
    });

    const notice = container.querySelector('[data-testid="deployment-action-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.getAttribute('role')).toBe('status');
    expect(notice?.getAttribute('aria-live')).toBe('polite');
    expect(container.textContent).toContain('✔ [모의 시뮬레이션]');
  });

  // =========================================================================
  // DEF-S12-06 & DEF-S12-07: Manifest REST disconnection & Mock warning
  // =========================================================================
  it('DEF-S12-06 & DEF-S12-07: marks release manifest as static fixture with unexposed REST API notice', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('[정적 픽스처 / 백엔드 릴리스 매니페스트 REST API 미연결]');
    expect(container.textContent).toContain('내부망 HTTPS 배포 및 운영 인수 시뮬레이터 (백엔드 배포 API 미노출)');
  });

  // =========================================================================
  // DEF-S12-08 & DEF-S12-17: Training step status binding & Autonomous practice notice
  // =========================================================================
  it('DEF-S12-08 & DEF-S12-17: binds training step badges correctly from PENDING to COMPLETED with practice notice', async () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    // Initial state: all pending
    const stepCards = container.querySelectorAll('[data-testid^="training-step-"]');
    expect(stepCards.length).toBe(4);
    stepCards.forEach((card) => {
      expect(card.textContent).toContain('PENDING');
    });

    // Complete Step 1
    const completeBtn = container.querySelector('[data-testid="training-complete-btn-1"]') as HTMLButtonElement;
    expect(completeBtn).not.toBeNull();

    await act(async () => {
      completeBtn.click();
    });

    // Step 1 card now has COMPLETED ✔
    const step1Card = container.querySelector('[data-testid="training-step-1"]');
    expect(step1Card?.textContent).toContain('COMPLETED ✔');

    // Notice contains [자율 실습 확인]
    expect(container.textContent).toContain('✔ [자율 실습 확인] 운영 교육 모듈 Step 1 실습이 확인되었습니다.');
  });

  // =========================================================================
  // DEF-S12-09 & DEF-S12-10: TLS 1.2/1.3 negotiation and Dev Self-Signed CA
  // =========================================================================
  it('DEF-S12-09 & DEF-S12-10: displays TLS 1.2/1.3 negotiation and static cert notice', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('TLS 1.2 / TLSv1.3 협상 (개발용 자체서명 CA)');
    expect(container.textContent).toContain('[정적 구성 예시 (실시간 인증서 조회 아님)]');
    expect(container.textContent).not.toContain('TLS 1.3 (STRICT)');
    expect(container.textContent).not.toContain('전용 Enterprise CA');
  });

  // =========================================================================
  // DEF-S12-11: Nginx config matches apps/web/nginx.conf
  // =========================================================================
  it('DEF-S12-11: verifies generateNginxConfig matches apps/web/nginx.conf upstream and ports', () => {
    const dm = new DeploymentManager();
    const conf = dm.generateNginxConfig();

    expect(conf).toContain('listen 443 ssl http2;');
    expect(conf).toContain('server_name saintvision.local saintvision.internal localhost 127.0.0.1;');
    expect(conf).toContain('ssl_protocols TLSv1.2 TLSv1.3;');
    expect(conf).toContain('ssl_ciphers HIGH:!aNULL:!MD5;');
    expect(conf).toContain('http://control-plane:8080');
    expect(conf).not.toContain('pacs-backend');
    expect(conf).not.toContain('listen 8443');
  });

  // =========================================================================
  // DEF-S12-12: Dynamic cluster compliance ratio
  // =========================================================================
  it('DEF-S12-12: shows unmeasured label when clusterNodes is null, and calculates dynamic ratio when passed', () => {
    // 1. Without clusterNodes
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });
    expect(container.textContent).toContain('미측정 (라이브 클러스터 미연결)');

    // 2. With clusterNodes
    const mockNodes: NodeItem[] = [
      {
        id: 'nod_01JABCDEF01',
        hostname: 'Node-01-WinMain',
        status: 'online',
        os: 'windows',
        cpuCores: 16,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32000,
        memoryUsedBytes: 16000,
        gpuCount: 1,
        storageTotalBytes: 1000,
        storageUsedBytes: 500,
        heartbeatAt: '2026-09-28T09:00:00Z',
        schedulable: true,
        isDraining: false,
      },
      {
        id: 'nod_01JABCDEF02',
        hostname: 'Node-02-WinWork',
        status: 'offline',
        os: 'windows',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16000,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 1000,
        storageUsedBytes: 0,
        heartbeatAt: '2026-09-28T09:00:00Z',
        schedulable: false,
        isDraining: false,
      },
    ];

    act(() => {
      root.render(
        <IntranetDeploymentView
          clusterNodes={mockNodes}
          currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }}
        />
      );
    });

    // 1 out of 2 passed -> 50%
    expect(container.textContent).toContain('1/2 Nodes PASSED (50%)');
  });

  // =========================================================================
  // DEF-S12-14: Fixed baseline observation timestamp
  // =========================================================================
  it('DEF-S12-14: uses fixed historical baseline timestamp instead of dynamic Date.now()', () => {
    const dm = new DeploymentManager();
    const nodes = dm.getNodeVerifications();

    nodes.forEach((n) => {
      expect(n.lastVerifiedAt).toBe('2026-09-28T09:00:00Z');
    });

    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });
    expect(container.textContent).toContain('2026-09-28T09:00:00Z (기준 시각)');
  });

  // =========================================================================
  // DEF-S12-15: Release identifier lowered to Pilot RC
  // =========================================================================
  it('DEF-S12-15: uses Pilot RC labels instead of misleading final GA production labels', () => {
    const dm = new DeploymentManager();
    const manifest = dm.getReleaseManifest();

    expect(manifest.releaseId).toBe('REL-2026-PILOT-RC');
    expect(manifest.version).toBe('v1.0.0-pilot-rc');

    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('파일럿 후보 릴리스 (Pilot RC)');
    expect(container.textContent).not.toContain('최종 프로덕션 릴리스 (R4)');
    expect(container.textContent).not.toContain('SIGNED-OFF ✔');
    expect(container.textContent).not.toContain('프로덕션 가동 승인 완료');
  });

  // =========================================================================
  // DEF-S12-16: Physical hardware acceptance separated from software sign-off
  // =========================================================================
  it('DEF-S12-16: physicalHardwareAcceptance remains pending after software release sign-off', () => {
    const dm = new DeploymentManager();
    expect(dm.getPreflightStatus().physicalHardwareAcceptance).toBe('pending');

    const result = dm.signOffRelease('usr_operator_lead', { roles: ['operator'] });
    expect(result.success).toBe(true);

    // Still pending because on-site physical hardware inspection is external
    expect(dm.getPreflightStatus().physicalHardwareAcceptance).toBe('pending');
  });

  // =========================================================================
  // DEF-S12-18: Strict Operator Sign-off Privilege Guard
  // =========================================================================
  describe('DEF-S12-18: Operator Sign-off Privilege Guard', () => {
    it('locks operatorId input to readOnly currentUser.id and rejects unauthenticated sessions', () => {
      act(() => {
        root.render(<IntranetDeploymentView currentUser={null} />);
      });

      const opInput = container.querySelector('[data-testid="deployment-operator-id-input"]') as HTMLInputElement;
      expect(opInput).not.toBeNull();
      expect(opInput.readOnly).toBe(true);
      expect(opInput.value).toBe('');

      const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
      expect(signoffBtn.disabled).toBe(true);
      expect(signoffBtn.getAttribute('aria-disabled')).toBe('true');

      const authNotice = container.querySelector('[data-testid="deployment-auth-required-notice"]');
      expect(authNotice).not.toBeNull();
      expect(authNotice?.getAttribute('role')).toBe('alert');
    });

    it('rejects sign-off for viewer role with clear privilege error message', async () => {
      act(() => {
        root.render(
          <IntranetDeploymentView
            currentUser={{ id: 'usr_viewer_01', name: 'Regular Viewer', role: 'viewer' }}
          />
        );
      });

      const opInput = container.querySelector('[data-testid="deployment-operator-id-input"]') as HTMLInputElement;
      expect(opInput.readOnly).toBe(true);
      expect(opInput.value).toBe('usr_viewer_01');

      const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
      expect(signoffBtn.disabled).toBe(false);

      await act(async () => {
        signoffBtn.click();
      });

      expect(container.textContent).toContain("서명 실패: 현재 사용자 권한('viewer')은 운영 인수 서명 권한이 없습니다");
    });

    it('allows sign-off for operator role and shows honest local simulation message', async () => {
      act(() => {
        root.render(
          <IntranetDeploymentView
            currentUser={{ id: 'usr_operator_real', name: 'Ops Staff', role: 'operator' }}
          />
        );
      });

      const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;

      await act(async () => {
        signoffBtn.click();
      });

      expect(container.textContent).toContain('✔ [모의 시뮬레이션] 파일럿 후보 릴리스 [v1.0.0-pilot-rc]');
      expect(container.textContent).toContain('운영자 [usr_operator_real]의 인수가 로컬 시뮬레이션 서명되었습니다');
      expect(container.textContent).toContain('(백엔드 배포 API 미연결 · 실 환경 미배포)');
      // Strictly no false SIGNED-OFF or production approval
      expect(container.textContent).not.toContain('SIGNED-OFF ✔');
      expect(container.textContent).not.toContain('프로덕션 가동 승인 완료');
    });
  });
});
