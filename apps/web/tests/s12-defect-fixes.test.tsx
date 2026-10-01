// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { IntranetDeploymentView } from '@/features/deployment/IntranetDeploymentView';
import { DeploymentManager } from '@/features/deployment/deploymentEngine';
import { NodeItem } from '@/contracts/types';

describe('S12-FE Products Defect Fixes (DEF-S12-01 ~ DEF-S12-18)', () => {
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
  });

  // =========================================================================
  // DEF 외 접근성 추가: Accessible Skip Navigation Link & Heading Level 1
  // =========================================================================
  it('DEF 외 접근성 추가: provides skip-link navigation and accessible H1 with tabIndex', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    const skipLink = container.querySelector('a[href="#deployment-main-content"]');
    expect(skipLink).not.toBeNull();
    expect(skipLink?.textContent).toContain('본문으로 바로가기');

    const h1 = container.querySelector('h1#deployment-main-content');
    expect(h1).not.toBeNull();
    expect(h1?.getAttribute('tabIndex')).toBe('-1');
    expect(h1?.textContent).toContain('내부망 HTTPS 배포 및 운영 인수 검증');
  });

  // =========================================================================
  // DEF-S12-01: '프로덕션 가동 승인 완료' false label prevented
  // =========================================================================
  it('DEF-S12-01: prevents false "프로덕션 가동 승인 완료" and shows honest sign-off states', async () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    // Before sign-off: shows pending state without false production approval
    expect(container.textContent).toContain('SIGN-OFF 대기 (로컬 모의)');
    expect(container.textContent).not.toContain('프로덕션 가동 승인 완료');
    expect(container.textContent).not.toContain('SIGNED-OFF ✔');

    const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
    await act(async () => {
      signoffBtn.click();
    });

    // After sign-off: shows local simulation completed, strictly no false production approval
    expect(container.textContent).toContain('모의 서명 완료 ✔');
    expect(container.textContent).not.toContain('프로덕션 가동 승인 완료');
    expect(container.textContent).not.toContain('SIGNED-OFF ✔');
  });

  // =========================================================================
  // DEF-S12-02: '운영자 인수 완료 (docker compose up -d 가능)' false label prevented
  // =========================================================================
  it('DEF-S12-02: prevents false "docker compose up -d" claim and shows "모의 인수 절차 확인됨"', async () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    // Initial state: Pending acceptance
    expect(container.textContent).toContain('현장 운영자 인수 대기 (Pending Acceptance)');
    expect(container.textContent).not.toContain('docker compose up -d');

    const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
    await act(async () => {
      signoffBtn.click();
    });

    // Post-simulation state: simulation verified, no docker compose claim
    expect(container.textContent).toContain('모의 인수 절차 확인됨 (온프레미스 실장비 기동 별도 필요)');
    expect(container.textContent).not.toContain('docker compose up -d');
  });

  // =========================================================================
  // DEF-S12-03: Node table status badge binding & accessibility
  // =========================================================================
  describe('DEF-S12-03: Node table status badge binding & accessibility', () => {
    it('displays unmeasured status and latency when live cluster is not connected or unmatched', () => {
      act(() => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
      });

      const nodeRows = container.querySelectorAll('[data-testid^="node-row-"]');
      expect(nodeRows.length).toBe(5);

      // Without live status match, none of the rows must show PASSED or numerical latency
      expect(container.textContent).not.toContain('PASSED ✔');
      nodeRows.forEach((row) => {
        const badge = row.querySelector('[aria-label="Smoke status: unmeasured"]');
        expect(badge).not.toBeNull();
        expect(badge?.textContent).toContain('미측정');
      });
    });

    it('renders FAILED ✘ with accessible label when matched live node is offline', () => {
      const offlineCluster: NodeItem[] = [
        {
          id: 'nod_01JABCDEF01',
          hostname: 'Node-01-WinMain',
          status: 'offline',
          os: 'windows',
          cpuCores: 8,
          cpuUsagePercent: 0,
          memoryTotalBytes: 32000000000,
          memoryUsedBytes: 0,
          gpuCount: 0,
          storageTotalBytes: 100000000000,
          storageUsedBytes: 0,
          heartbeatAt: '2026-09-28T09:00:00Z',
        },
      ];

      act(() => {
        root.render(
          <IntranetDeploymentView
            clusterNodes={offlineCluster}
            currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }}
          />
        );
      });

      const row1 = container.querySelector('[data-testid="node-row-nod_01JABCDEF01"]');
      expect(row1).not.toBeNull();

      const failedBadge = row1?.querySelector('[aria-label="Smoke status: failed"]');
      expect(failedBadge).not.toBeNull();
      expect(failedBadge?.textContent).toContain('FAILED ✘');
    });

    it('renders PASSED ✔ with accessible label when matched live node is online', () => {
      const onlineCluster: NodeItem[] = [
        {
          id: 'nod_01JABCDEF01',
          hostname: 'Node-01-WinMain',
          status: 'online',
          os: 'windows',
          cpuCores: 8,
          cpuUsagePercent: 12,
          memoryTotalBytes: 32000000000,
          memoryUsedBytes: 12000000000,
          gpuCount: 0,
          storageTotalBytes: 100000000000,
          storageUsedBytes: 20000000000,
          heartbeatAt: '2026-09-28T09:00:00Z',
        },
      ];

      act(() => {
        root.render(
          <IntranetDeploymentView
            clusterNodes={onlineCluster}
            currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }}
          />
        );
      });

      const row1 = container.querySelector('[data-testid="node-row-nod_01JABCDEF01"]');
      expect(row1).not.toBeNull();

      const passedBadge = row1?.querySelector('[aria-label="Smoke status: passed"]');
      expect(passedBadge).not.toBeNull();
      expect(passedBadge?.textContent).toContain('PASSED ✔');
      expect(row1?.textContent).toContain('11 ms');
    });
  });

  // =========================================================================
  // DEF-S12-04 & DEF-S12-13: Preflight checks specification labeling
  // =========================================================================
  it('DEF-S12-04 & DEF-S12-13: clearly marks preflight and gateway probe as specification examples without fake PREFLIGHT PASS', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('미측정 (설계 규격 예시)');
    expect(container.textContent).toContain('[설계 규격 예시 (202개 검증 항목)]');
    expect(container.textContent).toContain('[사전 설계 규격 항목] Nginx TLS 1.2/1.3 협상');
    expect(container.textContent).toContain('(게이트웨이 실시간 프로브 미연결)');
    expect(container.textContent).not.toContain('PREFLIGHT PASS ✔');
  });

  // =========================================================================
  // DEF-S12-05: Dynamic actionNotice accessibility (both error and success paths)
  // =========================================================================
  describe('DEF-S12-05: Dynamic actionNotice accessibility', () => {
    it('actionNotice uses alert role and assertive aria-live on error path', async () => {
      act(() => {
        root.render(
          <IntranetDeploymentView currentUser={{ id: 'usr_viewer_01', name: 'Viewer', role: 'viewer' }} />
        );
      });

      const signoffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
      expect(signoffBtn).not.toBeNull();

      await act(async () => {
        signoffBtn.click();
      });

      const notice = container.querySelector('[data-testid="deployment-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('alert');
      expect(notice?.getAttribute('aria-live')).toBe('assertive');
      expect(notice?.textContent).toContain("서명 실패: 현재 사용자 권한('viewer')은 운영 인수 서명 권한이 없습니다");
    });

    it('actionNotice uses status role and polite aria-live on success path', async () => {
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
      expect(notice?.textContent).toContain('✔ [모의 시뮬레이션]');
    });
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
  it('DEF-S12-08 & DEF-S12-17: binds training step status dynamically and labels autonomous practice', async () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    const step1 = container.querySelector('[data-testid="training-step-1"]');
    expect(step1?.textContent).toContain('PENDING');

    const completeBtn1 = container.querySelector('[data-testid="training-complete-btn-1"]') as HTMLButtonElement;
    await act(async () => {
      completeBtn1.click();
    });

    expect(step1?.textContent).toContain('COMPLETED ✔');
    expect(container.textContent).toContain('✔ [자율 실습 확인] 운영 교육 모듈 Step 1 실습이 확인되었습니다.');
  });

  // =========================================================================
  // DEF-S12-09 & DEF-S12-10: TLS 1.2/1.3 negotiation & dev CA labeling
  // =========================================================================
  it('DEF-S12-09 & DEF-S12-10: labels TLS as negotiation and CA as internal self-signed dev CA', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('TLS 1.2 / TLSv1.3 협상 (개발용 자체서명 CA)');
    expect(container.textContent).toContain('[정적 구성 예시 (실시간 인증서 조회 아님)]');
    expect(container.textContent).toContain('SaintVision Internal Dev Self-Signed CA');

    expect(container.textContent).not.toContain('TLS 1.3 STRICT');
    expect(container.textContent).not.toContain('전용 Enterprise CA');
  });

  // =========================================================================
  // DEF-S12-11: Nginx config matches apps/web/nginx.conf upstream & excerpt label
  // =========================================================================
  it('DEF-S12-11: labels nginx config as excerpt example and verifies upstream and ports', () => {
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('[발췌 예시 — 전문은 apps/web/nginx.conf]');
    expect(container.textContent).not.toContain('실제 apps/web/nginx.conf 정합');

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
  // DEF-S12-12: Dynamic cluster compliance ratio (heartbeat based)
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
        cpuCores: 8,
        cpuUsagePercent: 10,
        memoryTotalBytes: 32000000000,
        memoryUsedBytes: 8000000000,
        gpuCount: 0,
        storageTotalBytes: 100000000000,
        storageUsedBytes: 10000000000,
        heartbeatAt: '2026-09-28T09:00:00Z',
      },
      {
        id: 'nod_01JABCDEF02',
        hostname: 'Node-02-WinWork',
        status: 'offline',
        os: 'windows',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 32000000000,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 100000000000,
        storageUsedBytes: 0,
        heartbeatAt: '2026-09-28T09:00:00Z',
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

    expect(container.textContent).toContain('1/2 online (heartbeat 기준, smoke 미측정)');
  });

  // =========================================================================
  // DEF-S12-14: Observation timestamp / heartbeat labeling
  // =========================================================================
  it('DEF-S12-14: labels observation column with example or live heartbeat', () => {
    // Without live nodes
    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });
    expect(container.textContent).toContain('기준 시각 (예시) / heartbeat');
    expect(container.textContent).toContain('2026-09-28T09:00:00Z [정적 예시]');

    // With live node providing heartbeat
    const liveNodes: NodeItem[] = [
      {
        id: 'nod_01JABCDEF01',
        hostname: 'Node-01-WinMain',
        status: 'online',
        os: 'windows',
        cpuCores: 8,
        cpuUsagePercent: 10,
        memoryTotalBytes: 32000000000,
        memoryUsedBytes: 8000000000,
        gpuCount: 0,
        storageTotalBytes: 100000000000,
        storageUsedBytes: 10000000000,
        heartbeatAt: '2026-09-28T09:42:00Z',
      },
    ];

    act(() => {
      root.render(
        <IntranetDeploymentView
          clusterNodes={liveNodes}
          currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }}
        />
      );
    });
    expect(container.textContent).toContain('2026-09-28T09:42:00Z (heartbeat)');
  });

  // =========================================================================
  // DEF-S12-15: Release identifier lowered to Pilot RC
  // =========================================================================
  it('DEF-S12-15: uses Pilot RC labels instead of misleading final GA production labels', () => {
    const dm = new DeploymentManager();
    const manifest = dm.getReleaseManifest();

    expect(manifest.version).toBe('v1.0.0-pilot-rc');
    expect(manifest.releaseId).toBe('REL-2026-PILOT-RC');

    act(() => {
      root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Op', role: 'operator' }} />);
    });

    expect(container.textContent).toContain('v1.0.0-pilot-rc');
    expect(container.textContent).toContain('REL-2026-PILOT-RC');
    expect(container.textContent).not.toContain('v1.0.0-final-GA');
    expect(container.textContent).not.toContain('REL-2026-R4-GA');
    expect(container.textContent).not.toContain('프로덕션 운영 인수 서명');
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
  // DEF-S12-18: Strict Operator Sign-off Privilege Guard & Canonical Immutability
  // =========================================================================
  describe('DEF-S12-18: Operator Sign-off Privilege Guard & Canonical Immutability', () => {
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
      expect(authNotice?.textContent).toContain('인증 필요');
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

    it('rejects sign-off when caller has operator id prefix but viewer role (regex bypass blocked)', () => {
      const dm = new DeploymentManager();
      const attempt = dm.signOffRelease('usr_operator_lead', { roles: ['viewer'] });
      expect(attempt.success).toBe(false);
      expect(attempt.error).toContain('lacks required cluster authority roles');
    });

    it('rejects sign-off when caller provides operator id prefix without roles argument', () => {
      const dm = new DeploymentManager();
      const attempt = dm.signOffRelease('usr_operator_lead');
      expect(attempt.success).toBe(false);
      expect(attempt.error).toContain('lacks required cluster authority roles');
    });

    it('keeps canonical manifest.operatorSignOff as false even when simulation sign-off succeeds', () => {
      const dm = new DeploymentManager();
      const result = dm.signOffRelease('usr_operator_real', { roles: ['operator'] });
      expect(result.success).toBe(true);
      expect(result.localSimulationCompleted).toBe(true);
      expect(result.manifest.operatorSignOff).toBe(false);
      expect(dm.getReleaseManifest().operatorSignOff).toBe(false);
    });

    it('allows sign-off for operator role and shows honest local simulation message with signed id', async () => {
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
      expect(container.textContent).toContain('모의 서명자: usr_operator_real');

      // Strictly no false SIGNED-OFF or production approval
      expect(container.textContent).not.toContain('SIGNED-OFF ✔');
      expect(container.textContent).not.toContain('프로덕션 가동 승인 완료');
    });
  });
});
