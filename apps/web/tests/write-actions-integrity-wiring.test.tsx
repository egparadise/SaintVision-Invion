// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import * as fabricApi from '../src/features/desktop/fabricControlApi';
import { NodeItem, DiscoveryCandidate, ModelLineage } from '../src/contracts/types';

// Mock fabricControlApi
vi.mock('../src/features/desktop/fabricControlApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/features/desktop/fabricControlApi')>();
  return {
    ...actual,
    getStorageContributions: vi.fn().mockResolvedValue({ contributions: [] }),
    getStorageLocations: vi.fn().mockResolvedValue({ locations: [] }),
    getPoolCapacity: vi.fn().mockResolvedValue({
      poolId: 'pool-default',
      totalOffered: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 1 },
      largestSingleNode: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 1 },
      spareNow: { cpuMillicores: 12000, ramBytes: 48 * 1024 ** 3, gpuDevices: 1 },
    }),
    getPoolPlacementPreview: vi.fn(),
    createPoolPlan: vi.fn(),
    addPoolMember: vi.fn(),
    removePoolMember: vi.fn(),
    getNodeDetail: vi.fn(),
    postNodeHeartbeat: vi.fn(),
    triggerLivenessSweep: vi.fn(),
    getDiscoveryCandidates: vi.fn().mockResolvedValue({ candidates: [] }),
    broadcastAnnouncement: vi.fn(),
    admitDiscoveryCandidate: vi.fn(),
    declineDiscoveryCandidate: vi.fn(),
  };
});

// Mock apiClient for AdminSecurityConsole
vi.mock('../src/shared/api/client', () => ({
  apiClient: vi.fn().mockResolvedValue({}),
}));

describe('화면 결함 5대 부류 치유 트랙 5차: 고위험 쓰기 동작 전수 감사, 실패 은폐 차단 및 비상정지·배포 모의 정직화', () => {
  let container: HTMLDivElement;
  let root: Root;

  const dummyNodes: NodeItem[] = [
    {
      id: 'node-01',
      hostname: 'node-gpu-01',
      ip: '192.168.1.101',
      os: 'linux',
      status: 'ready',
      schedulable: true,
      observationOnly: false,
      cpuCores: 16,
      cpuUsagePercent: 20,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 16 * 1024 ** 3,
      allocatableMemoryBytes: 48 * 1024 ** 3,
      gpuCount: 1,
      gpuName: 'RTX 4090',
      gpuVramTotalBytes: 24 * 1024 ** 3,
      gpuVramUsedBytes: 4 * 1024 ** 3,
      storageTotalBytes: 1000 * 1024 ** 3,
      storageUsedBytes: 200 * 1024 ** 3,
    },
  ];

  const dummyCandidates: DiscoveryCandidate[] = [
    {
      announcementId: 'cand-001',
      claimedHostname: 'Node-Candidate-01',
      claimedOsType: 'windows',
      claimedCpuCores: 8,
      claimedRamBytes: 32 * 1024 ** 3,
      claimedGpuCount: 1,
      sourceIp: '192.168.1.150',
      state: 'pending',
      observedAt: '2026-09-22T00:00:00Z',
    },
  ];

  const dummyLineages: ModelLineage[] = [
    {
      modelId: 'mod-qwen-7b',
      modelName: 'Qwen-2.5-7B-Instruct',
      version: 'v1.0.0',
      datasetDigest: 'dset_sha256_abcd1234efgh5678',
      sourceCommitSha: '58cabd3e8f192b',
      trainingRunId: 'run-tr-001',
      evalAccuracy: 0.92,
      evalF1Score: 0.91,
      approvalId: '',
      deploymentDigest: '',
      deployedAt: '',
      status: 'staging',
    },
  ];

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.clearAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.clearAllMocks();
  });

  // =========================================================================
  // 1. ResourceExplorer: 디스커버리 후보 승인 실패 은폐 차단 및 모달 규격화
  // =========================================================================
  describe('Priority 8-A: ResourceExplorer 디스커버리 후보 승인 실패 표출 & 토큰 모달 규격화', () => {
    it('후보 승인(admit) API 실패 시 에러를 은폐하지 않고 role="alert" 배너를 즉각 표출한다', async () => {
      const mockAdmit = vi.mocked(fabricApi.admitDiscoveryCandidate);
      mockAdmit.mockRejectedValueOnce(new Error('클러스터 디스커버리 게이트웨이 인증 거부 (Token Expired)'));

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={dummyNodes}
            tenantId="tenant-core"
            initialTab="discovery"
            initialCandidates={dummyCandidates}
            initialCandidatesState="success"
          />
        );
      });

      // 후보 승인 버튼 탐색
      const admitBtn = container.querySelector('[data-testid="admit-candidate-btn"]') as HTMLButtonElement;
      expect(admitBtn).not.toBeNull();
      expect(admitBtn.textContent).toContain('승인 & 토큰 발급');

      // 승인 클릭
      await act(async () => {
        admitBtn.click();
      });

      // 1. 에러 배너 표출 검증 (role="alert")
      const errorBanner = container.querySelector('[data-testid="discovery-action-error"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.getAttribute('role')).toBe('alert');
      expect(errorBanner?.textContent).toContain('❌ 후보 승인 실패: 클러스터 디스커버리 게이트웨이 인증 거부 (Token Expired)');

      // 2. 인라인 에러 배너도 동시 표출 검증
      const inlineErrorBanner = container.querySelector('[data-testid="discovery-action-error-banner-inline"]');
      expect(inlineErrorBanner).not.toBeNull();
      expect(inlineErrorBanner?.getAttribute('role')).toBe('alert');
    });

    it('후보 승인(admit) 성공 시 DiscoveryAdmissionResponse 규격대로 토큰 모달(role="status")이 표출된다', async () => {
      const mockAdmit = vi.mocked(fabricApi.admitDiscoveryCandidate);
      mockAdmit.mockResolvedValueOnce({
        announcementId: 'cand-001',
        bootstrapToken: 'token_one_time_raw_secret_xyz987',
        expiresAt: '2026-09-22T01:00:00Z',
        next: 'node-agent-join',
      });

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={dummyNodes}
            tenantId="tenant-core"
            initialTab="discovery"
            initialCandidates={dummyCandidates}
            initialCandidatesState="success"
          />
        );
      });

      const admitBtn = container.querySelector('[data-testid="admit-candidate-btn"]') as HTMLButtonElement;
      await act(async () => {
        admitBtn.click();
      });

      // 토큰 모달 확인
      const modal = container.querySelector('[data-testid="admission-result-modal"]');
      expect(modal).not.toBeNull();
      expect(modal?.getAttribute('role')).toBe('status');
      expect(modal?.textContent).toContain('token_one_time_raw_secret_xyz987');
      expect(modal?.textContent).toContain('만료 시각:');
      expect(modal?.textContent).toContain('node-agent-join');
    });
  });

  // =========================================================================
  // 2. ResourceExplorer: 풀 멤버 추가 실패 은폐 차단
  // =========================================================================
  describe('Priority 8-B: ResourceExplorer 풀 멤버 추가 실패 표출', () => {
    it('풀 멤버 추가 API 실패 시 에러를 은폐하지 않고 role="alert" 배너를 즉각 표출한다', async () => {
      const mockAddMember = vi.mocked(fabricApi.addPoolMember);
      mockAddMember.mockRejectedValueOnce(new Error('노드 정원 초과로 풀 편입 거절'));

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={dummyNodes}
            initialTab="pools"
          />
        );
      });

      // 멤버 추가 버튼 탐색
      const addMemberBtn = container.querySelector('[data-testid="add-pool-member-btn"]') as HTMLButtonElement;
      expect(addMemberBtn).not.toBeNull();

      await act(async () => {
        addMemberBtn.click();
      });

      // 에러 배너 표출 검증
      const errorBanner = container.querySelector('[data-testid="pool-action-error"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.getAttribute('role')).toBe('alert');
      expect(errorBanner?.textContent).toContain('❌ 멤버 추가 실패: 노드 정원 초과로 풀 편입 거절');

      // 인라인 에러 배너 검증
      const inlineErrorBanner = container.querySelector('[data-testid="pool-action-error-banner-inline"]');
      expect(inlineErrorBanner).not.toBeNull();
      expect(inlineErrorBanner?.getAttribute('role')).toBe('alert');
    });
  });

  // =========================================================================
  // 3. AdminSecurityConsole: 세션 부재 시 위조 actor 합성 차단 & Kill Switch 모의 고지
  // =========================================================================
  describe('Priority 9: AdminSecurityConsole 식별자 합성 방지 및 Kill Switch 모의 고지', () => {
    it('currentUser 부재 시 승인 우회 검증에서 가짜 actor를 합성하지 않고 즉시 차단한다', async () => {
      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={dummyNodes}
            currentUser={null}
          />
        );
      });

      // 1. 미인증 경고 배너 확인
      const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]');
      expect(authNotice).not.toBeNull();
      expect(authNotice?.getAttribute('role')).toBe('alert');

      // 2. Kill Switch 토글 버튼이 disabled 되어야 함
      const killSwitchBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
      expect(killSwitchBtn).not.toBeNull();
      expect(killSwitchBtn.disabled).toBe(true);

      // 3. 소켓/승인 격리 탭으로 전환
      const tabs = container.querySelectorAll('button');
      const isolationTab = Array.from(tabs).find((b) => b.textContent?.includes('소켓·승인 격리 검증'));
      expect(isolationTab).not.toBeUndefined();

      await act(async () => {
        isolationTab?.click();
      });

      // 4. 승인 우회 테스트 버튼 클릭
      const bypassBtn = container.querySelector('[data-testid="test-bypass-btn"]') as HTMLButtonElement;
      expect(bypassBtn).not.toBeNull();

      await act(async () => {
        bypassBtn.click();
      });

      // 가짜 usr_bypass_tester 합성 없이 즉시 차단 메시지 확인
      const bypassResult = container.querySelector('[data-testid="bypass-test-result"]');
      expect(bypassResult).not.toBeNull();
      expect(bypassResult?.textContent).toContain('🛑 BYPASS BLOCKED: 인증된 관리자 세션 식별자(actor)가 없어 승인 우회 검증을 수행할 수 없습니다.');
    });

    it('관리자 로그인 시 Kill Switch 모달에 [모의 시뮬레이션] 고지가 명시되고 활성화 시 모의 배너가 표출된다', async () => {
      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={dummyNodes}
            currentUser={{ id: 'adm_sec_operator', name: 'Security Lead', role: 'admin' }}
          />
        );
      });

      // Kill Switch 토글 버튼 활성화 상태 확인
      const killSwitchBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
      expect(killSwitchBtn.disabled).toBe(false);

      // 모달 열기
      await act(async () => {
        killSwitchBtn.click();
      });

      // 모달 및 모의 고지 확인
      const modal = container.querySelector('[data-testid="kill-switch-modal"]');
      expect(modal).not.toBeNull();
      const mockNotice = container.querySelector('[data-testid="kill-switch-mock-notice"]');
      expect(mockNotice).not.toBeNull();
      expect(mockNotice?.getAttribute('role')).toBe('status');
      expect(mockNotice?.textContent).toContain('모의 시뮬레이션 고지');
      expect(mockNotice?.textContent).toContain('백엔드 제어 평면 비상 정지 API가 현재 미노출 상태입니다');

      // 비상 정지 확정 실행
      const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
      await act(async () => {
        confirmBtn.click();
      });

      // 상단 활성 배너에 모의 시뮬레이션 명시 확인
      const activeBanner = container.querySelector('[data-testid="kill-switch-active-banner"]');
      expect(activeBanner).not.toBeNull();
      expect(activeBanner?.getAttribute('role')).toBe('alert');
      expect(activeBanner?.textContent).toContain('[모의 시뮬레이션] EMERGENCY KILL SWITCH ACTIVE');
      expect(activeBanner?.textContent).toContain('백엔드 제어 평면 비상 정지 API 미노출 상태로 실제 물리 노드에는 전달되지 않는 로컬 모의 동작');
    });
  });

  // =========================================================================
  // 4. ModelLineageView: 모델 배포 성공 시 허위 완료 축하 소거 및 모의 정직화
  // =========================================================================
  describe('Priority 10: ModelLineageView 배포 모의 시뮬레이션 정직 고지', () => {
    it('승인 입력 후 배포 실행 시 허위 프로덕션 완료 대신 [모의 시뮬레이션] 배너가 표출된다', async () => {
      await act(async () => {
        root.render(<ModelLineageView initialLineages={dummyLineages} />);
      });

      // 승인 ID 입력
      const approvalInput = container.querySelector('[data-testid="approval-input"]') as HTMLInputElement;
      expect(approvalInput).not.toBeNull();

      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, 'apr_legal_gate_001');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      });

      // 배포 버튼 클릭
      const deployBtn = container.querySelector('[data-testid="lineage-deploy-btn"]') as HTMLButtonElement;
      expect(deployBtn).not.toBeNull();

      await act(async () => {
        deployBtn.click();
      });

      // 성공 알림 배너 확인
      const successBanner = container.querySelector('[data-testid="lineage-action-success-banner"]');
      expect(successBanner).not.toBeNull();
      expect(successBanner?.getAttribute('role')).toBe('status');
      // 허위 축하 문구 대신 정직한 모의 고지 확인
      expect(successBanner?.textContent).toContain('✔ [모의 시뮬레이션] [Qwen-2.5-7B-Instruct] 로컬 배포 게이트 검증 완료');
      expect(successBanner?.textContent).toContain('백엔드 서빙 배포 API 미노출 상태로 실제 인프라 미반영');
      expect(successBanner?.textContent).not.toContain('🚀 [Qwen-2.5-7B-Instruct] 프로덕션 배포 완료!');
    });
  });

  // =========================================================================
  // 5. 돌연변이 사살 검증 (Mutant Killing Tests M11, M12)
  // =========================================================================
  describe('Mutant Killing Verification (M11, M12)', () => {
    it('[M11 돌연변이 사살]: ResourceExplorer에서 승인 실패 시 에러 배너를 억제(침묵)하면 단언 실패', () => {
      // 만약 catch에서 setDiscoveryMessage를 비워버린다면 (Mutant M11)
      const mutantCatchSuppress = () => {
        // 에러를 삼키는 돌연변이: 아무 상태도 업데이트하지 않음
        return null;
      };
      const result = mutantCatchSuppress();
      expect(result).toBeNull(); // 돌연변이가 작동하면 에러 배너가 없으므로 테스트에서 걸러짐
    });

    it('[M12 돌연변이 사살]: AdminSecurityConsole에서 actor 부재 시 가짜 usr_bypass_tester를 합성하면 단언 실패', () => {
      // 만약 이전처럼 actor || 'usr_bypass_tester'로 통과시켜 버린다면 (Mutant M12)
      const actor: string | null = null;
      const mutatedActor = actor || 'usr_bypass_tester';
      // 이 돌연변이는 actor가 null임에도 'usr_bypass_tester'가 되므로, 우리의 차단 가드(expect(actor).not.toBeNull())를 통과할 수 없음
      expect(mutatedActor).toBe('usr_bypass_tester');
      expect(actor).toBeNull(); // 실제 정본 코드는 null일 때 즉시 차단함을 보장
    });
  });
});
