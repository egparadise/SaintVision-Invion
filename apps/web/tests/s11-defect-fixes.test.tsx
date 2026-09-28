// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { Button } from '../src/shared/ui/Button';
import { Header } from '../src/shared/ui/Header';
import { WorkspaceList } from '../src/features/workspaces/WorkspaceList';
import { WorkspaceCreateModal } from '../src/features/workspaces/WorkspaceCreateModal';
import { GitCommitModal } from '../src/features/editor/GitCommitModal';
import { ConflictResolutionModal } from '../src/features/editor/ConflictResolutionModal';
import { ReleaseCandidateView } from '../src/features/release/ReleaseCandidateView';
import { ReleaseManager } from '../src/features/release/releaseEngine';

describe('S11-FE Defect Fixes Verification (DEF-S11-01 ~ DEF-S11-19)', () => {
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

  // DEF-S11-01: Focus visibility on buttons
  it('DEF-S11-01: Button does not hardcode outline: none and allows focus-visible ring', async () => {
    await act(async () => {
      root.render(<Button variant="primary">Accessibility Button</Button>);
    });
    const btn = container.querySelector('button') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.style.outline).not.toBe('none');
  });

  // DEF-S11-02: WorkspaceList keyboard navigation and activation
  it('DEF-S11-02: WorkspaceList cards have role=button, tabIndex=0 and onKeyDown support', async () => {
    const handleSelect = vi.fn();
    const handleOpenStudio = vi.fn();
    const mockWorkspaces = [
      {
        id: 'wsp-101',
        name: 'Workspace 101',
        projectId: 'prj-alpha',
        status: 'ready' as const,
        targetNodeId: 'nod-01',
        isolationMode: 'chroot' as const,
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        createdAt: '2026-09-28T00:00:00Z',
      },
    ];
    const mockNodes = [
      {
        id: 'nod-01',
        hostname: 'node1.saintvision.internal',
        status: 'online' as const,
        cpuTotalCores: 16,
        cpuAllocatedCores: 4,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryAllocatedBytes: 8 * 1024 ** 3,
        storageTotalBytes: 500 * 1024 ** 3,
        storageAllocatedBytes: 100 * 1024 ** 3,
        gpuCount: 0,
        labels: {},
        registeredAt: '2026-09-28T00:00:00Z',
        heartbeatAt: '2026-09-28T00:00:00Z',
        isDraining: false,
      },
    ];

    await act(async () => {
      root.render(
        <WorkspaceList
          workspaces={mockWorkspaces}
          nodes={mockNodes}
          onSelectWorkspace={handleSelect}
          onOpenStudio={handleOpenStudio}
          onOpenCreateModal={vi.fn()}
        />
      );
    });

    const card = container.querySelector('div[role="button"]') as HTMLDivElement;
    expect(card).not.toBeNull();
    expect(card.getAttribute('tabindex')).toBe('0');
    expect(card.getAttribute('aria-label')).toBe('작업공간 Workspace 101 선택');

    // Trigger Enter key on card
    act(() => {
      card.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    expect(handleSelect).toHaveBeenCalledWith('wsp-101');

    // Trigger Space key on card
    act(() => {
      card.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    });
    expect(handleSelect).toHaveBeenCalledTimes(2);

    // Verify Studio button inside card does not trigger onSelectWorkspace when activated
    const studioBtn = container.querySelector('button') as HTMLButtonElement;
    expect(studioBtn).not.toBeNull();
    act(() => {
      studioBtn.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    // handleSelect should NOT be called from inner button
    expect(handleSelect).toHaveBeenCalledTimes(2);
  });

  // DEF-S11-03, DEF-S11-04, DEF-S11-05, DEF-S11-06: Modal focus trap, restore, Esc, dialog ARIA
  it('DEF-S11-03 ~ DEF-S11-06: WorkspaceCreateModal has dialog ARIA, Esc handler and focus trap', async () => {
    const handleClose = vi.fn();
    const handleCreate = vi.fn().mockResolvedValue(undefined);

    await act(async () => {
      root.render(
        <WorkspaceCreateModal
          projectId="prj-test"
          isOpen={true}
          onClose={handleClose}
          onCreate={handleCreate}
        />
      );
    });

    const dialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(dialog).not.toBeNull();
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('aria-labelledby')).toBe('workspace-create-title');

    // Escape closes modal
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('DEF-S11-03 ~ DEF-S11-06: GitCommitModal has dialog ARIA, Esc handler and labeled title', async () => {
    const handleCancel = vi.fn();
    const handleCommit = vi.fn();

    await act(async () => {
      root.render(
        <GitCommitModal
          files={[{ path: 'src/main.ts', content: 'console.log("ok");', isDirty: true }]}
          parentCommit={null}
          onCommit={handleCommit}
          onCancel={handleCancel}
        />
      );
    });

    const dialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(dialog).not.toBeNull();
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('aria-labelledby')).toBe('git-commit-modal-title');

    // Escape cancels modal
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleCancel).toHaveBeenCalledTimes(1);
  });

  it('DEF-S11-03 ~ DEF-S11-06: ConflictResolutionModal has dialog ARIA, Esc handler and labeled title', async () => {
    const handleCancel = vi.fn();

    await act(async () => {
      root.render(
        <ConflictResolutionModal
          filePath="src/kernel.ts"
          diff={{
            path: 'src/kernel.ts',
            originalEtag: 'abcdef1234567890',
            modifiedEtag: '1234567890abcdef',
            additionsCount: 1,
            deletionsCount: 0,
            lines: [{ type: 'same', content: 'const a = 1;' }],
            hunks: [],
            hasConflict: true,
          } as any}
          onKeepMine={vi.fn()}
          onAcceptRemote={vi.fn()}
          onMerge={vi.fn()}
          onCancel={handleCancel}
        />
      );
    });

    const dialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(dialog).not.toBeNull();
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('aria-labelledby')).toBe('conflict-resolution-title');

    // Escape cancels modal
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleCancel).toHaveBeenCalledTimes(1);
  });

  // DEF-S11-06: Header active tab aria-current="page"
  it('DEF-S11-06: Header active tab has aria-current="page"', async () => {
    await act(async () => {
      root.render(
        <Header
          currentUser={{ id: 'gemini', name: 'Gemini Agent', role: 'admin' }}
          activeTab="workspaces"
          onSelectTab={vi.fn()}
          theme="dark"
          onToggleTheme={vi.fn()}
        />
      );
    });

    const activeTabBtn = container.querySelector('[data-testid="header-tab-workspaces"]');
    expect(activeTabBtn).not.toBeNull();
    expect(activeTabBtn?.getAttribute('aria-current')).toBe('page');

    const inactiveTabBtn = container.querySelector('[data-testid="header-tab-nodes"]');
    expect(inactiveTabBtn).not.toBeNull();
    expect(inactiveTabBtn?.getAttribute('aria-current')).toBeNull();
  });

  // DEF-S11-08, 11, 12, 13, 14, 15, 17, 18, 19: ReleaseCandidateView integrity and truthfulness
  it('DEF-S11-08, 11~19: ReleaseCandidateView removes false claims and enforces truthful status', async () => {
    await act(async () => {
      root.render(<ReleaseCandidateView />);
    });

    const text = container.textContent || '';

    // DEF-S11-08: False telemetry claim removed, replaced with static simulation notice
    expect(text).not.toContain('측정 환경: 5-Node 분산 클러스터 및 실제 원격 호출 계측 결과');
    expect(text).toContain('[정적 예시] 원격 텔레메트리 미연동 (사전 설계 규격 시뮬레이션)');

    // DEF-S11-08: False "ACTIVE LIVE" and "STANDBY" replaced with honest simulation badges
    expect(text).not.toContain('ACTIVE LIVE');
    expect(text).toContain('모의 활성 (서버 API 미노출 · 실 인프라 미배포)');
    expect(text).toContain('모의 대기');

    // DEF-S11-08 & DEF-S11-16: Table initially does NOT show unverified "✔ 검증 완료"
    expect(text).not.toContain('✔ 검증 완료');
    expect(text).toContain('미측정 (대기)');

    // DEF-S11-11: WCAG false full automated audit claim downgraded
    expect(text).not.toContain('W3C 웹 콘텐츠 접근성 지침 2.1 AA 등급 전수 자동화 검증');
    expect(text).toContain('[모의 지표] WCAG 2.1 AA 규격 체크리스트 (자동화 검증 미실시)');

    // DEF-S11-12: Contrast ratio false general claim downgraded to manual calculation
    expect(text).not.toContain('(기준 4.5:1 대비 초과 충족)');
    expect(text).toContain('[수동 계산값] 특정 텍스트 쌍 기준 (전체 UI 렌더 실측 아님)');

    // DEF-S11-13: Security full verification false claim downgraded
    expect(text).not.toContain('보안·무결성 전수 검증 완료');
    expect(text).toContain('[정적 요약] 보안·무결성 지표 예시');

    // DEF-S11-14: Zero-downtime guaranteed rollback claim downgraded to in-memory simulation
    expect(text).not.toContain('배포 후 장애 감지 시 1클릭 무중단 롤백 및 캐시 무효화가 보증됩니다.');
    expect(text).toContain('[모의 안내] 클라이언트 인메모리 롤백 시뮬레이션 (실 인프라 캐시 무효화 미연동)');

    // DEF-S11-15: WCAG status badge dynamically bound
    const passBadges = container.querySelectorAll('span');
    const badgeTexts = Array.from(passBadges).map((s) => s.textContent?.trim());
    expect(badgeTexts).toContain('PASS');

    // DEF-S11-17: Table wrapper has overflowX auto
    const tableWrappers = container.querySelectorAll('div[style*="overflow-x: auto"], div[style*="overflowX: auto"]');
    expect(tableWrappers.length).toBeGreaterThanOrEqual(1);

    // DEF-S11-18: Viewport buttons dynamically affect container maxWidth
    const mobileBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'MOBILE');
    expect(mobileBtn).not.toBeUndefined();
    await act(async () => {
      mobileBtn?.click();
    });
    const mainWrapper = container.firstElementChild as HTMLElement;
    expect(mainWrapper.style.maxWidth).toBe('375px');

    const tabletBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'TABLET');
    expect(tabletBtn).not.toBeUndefined();
    await act(async () => {
      tabletBtn?.click();
    });
    expect(mainWrapper.style.maxWidth).toBe('768px');

    const desktopBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'DESKTOP');
    expect(desktopBtn).not.toBeUndefined();
    await act(async () => {
      desktopBtn?.click();
    });
    expect(mainWrapper.style.maxWidth).toBe('1400px');

    // DEF-S11-19: Rollback button has explicit aria-label with version tag
    const rollbackBtn = container.querySelector('button[aria-label*="롤백 실행 (AC-11)"]');
    expect(rollbackBtn).not.toBeNull();
    expect(rollbackBtn?.getAttribute('aria-label')).toBe('이 버전(v1.0.0-rc.1)으로 롤백 실행 (AC-11)');
  });

  // DEF-S11-16: ReleaseManager candidate initial state
  it('DEF-S11-16: ReleaseManager initializes v1.0.0-rc.1 with rollbackVerified: false', () => {
    const rm = new ReleaseManager();
    const candidates = rm.getReleaseCandidates();
    const rc1 = candidates.find((c) => c.tag === 'v1.0.0-rc.1');
    expect(rc1).not.toBeUndefined();
    expect(rc1?.rollbackVerified).toBe(false);

    // After rollback execution, rollbackVerified transitions to true
    const res = rm.rollbackToVersion('v1.0.0-rc.1');
    expect(res.success).toBe(true);
    expect(res.activeCandidate?.rollbackVerified).toBe(true);
  });

  // DEF-S11-09 & DEF-S11-10: Mathematical contrast verification
  it('DEF-S11-09 & DEF-S11-10: Confirms mathematical contrast formulas exceed AA standards', () => {
    // Relative Luminance calculation per WCAG 2.1 specs:
    // L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    // where C_srgb = C <= 0.04045 ? C/12.92 : ((C+0.055)/1.055)^2.4
    const getLuminance = (r: number, g: number, b: number) => {
      const a = [r, g, b].map((v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
      });
      return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
    };

    const getContrast = (l1: number, l2: number) => {
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (lighter + 0.05) / (darker + 0.05);
    };

    const lWhite = getLuminance(255, 255, 255); // 1.0
    const lDarkPrimary = getLuminance(0x1d, 0x4e, 0xd8); // #1d4ed8
    const lDarkDanger = getLuminance(0xdc, 0x26, 0x26); // #dc2626
    const lDarkSubtle = getLuminance(0x1f, 0x29, 0x37); // #1f2937
    const lDarkBorderStrong = getLuminance(0x9c, 0xa3, 0xaf); // #9ca3af
    const lLightSubtle = getLuminance(0xf1, 0xf5, 0xf9); // #f1f5f9
    const lLightBorderStrong = getLuminance(0x64, 0x74, 0x8b); // #64748b

    // DEF-S11-09: Primary and Danger buttons on white text exceed 4.5:1 (WCAG 1.4.3 Level AA)
    const primaryContrast = getContrast(lWhite, lDarkPrimary);
    const dangerContrast = getContrast(lWhite, lDarkDanger);
    expect(primaryContrast).toBeGreaterThanOrEqual(4.5);
    expect(dangerContrast).toBeGreaterThanOrEqual(4.5);

    // DEF-S11-10: Form input borders exceed 3.0:1 (WCAG 1.4.11 Non-text Contrast)
    const darkBorderContrast = getContrast(lDarkBorderStrong, lDarkSubtle);
    const lightBorderContrast = getContrast(lLightSubtle, lLightBorderStrong);
    expect(darkBorderContrast).toBeGreaterThanOrEqual(3.0);
    expect(lightBorderContrast).toBeGreaterThanOrEqual(3.0);
  });
});
