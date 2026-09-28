// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { NaturalLanguageRunView } from '../src/features/agent/NaturalLanguageRunView';

describe('NaturalLanguageRunView (S09-FE PR 4 UI Integration)', () => {
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

  describe('EVL-01: Synthetic KPI Labels and Governance Disclaimers', () => {
    it('renders KPI cards with G-26 synthetic / non-operational acceptance notice', () => {
      act(() => {
        root.render(<NaturalLanguageRunView />);
      });

      // Assert G-26 synthetic notice on prompt validity and coding success KPIs
      expect(container.textContent).toContain('목표: ≥99% (합성 · 운영 인수 아님(G-26))');
      expect(container.textContent).toContain('목표: ≥70% (합성 · 운영 인수 아님(G-26))');
      expect(container.textContent).toContain('Prompt 100건 유효율 (AC-09 픽스처)');
      expect(container.textContent).toContain('코딩 과제 30건 성공률 (AC-09 픽스처)');

      // Assert AC-09 agent API unexposed governance banner
      const unexposedNotice = container.querySelector('[data-testid="agent-unexposed-notice"]');
      expect(unexposedNotice).not.toBeNull();
      expect(unexposedNotice?.getAttribute('role')).toBe('status');
      expect(unexposedNotice?.getAttribute('aria-live')).toBe('polite');
      expect(unexposedNotice?.textContent).toContain('자연어 에이전트 실행 및 골든 평가 제어기 (API 미노출)');
      expect(unexposedNotice?.textContent).toContain('엔드포인트(/v1/agent/*)가 배선되어 있지 않습니다');
    });
  });

  describe('REP-02 & REP-03: Bounded Repair Loop and Rejection on Bound Exceeded', () => {
    it('accurately advances repair loop counts (1/3 -> 2/3 -> 3/3) and immediately updates screen state to rejected on 3rd click', () => {
      act(() => {
        root.render(<NaturalLanguageRunView />);
      });

      // Submit run request first to generate proposed diff
      const submitBtn = Array.from(container.querySelectorAll('button[type="submit"]')).find((b) =>
        b.textContent?.includes('자연어 Run 분석 및 제안 Diff 생성')
      );
      expect(submitBtn).toBeDefined();

      act(() => {
        submitBtn?.click();
      });

      // Initial state: Request is READY at loop 1/3
      const loopInfo = container.querySelector('[data-testid="agent-loop-info"]');
      const statusBadge = container.querySelector('[data-testid="agent-status-badge"]');
      expect(loopInfo?.textContent).toContain('루프: 1/3');
      expect(statusBadge?.textContent).toBe('READY');

      const refineBtn = container.querySelector('[data-testid="agent-refine-btn"]') as HTMLButtonElement;
      expect(refineBtn).not.toBeNull();

      // Click 1: Advance loop 1/3 -> 2/3
      act(() => {
        refineBtn.click();
      });

      expect(loopInfo?.textContent).toContain('루프: 2/3');
      expect(statusBadge?.textContent).toBe('REPAIRING');

      const noticeAfterClick1 = container.querySelector('[data-testid="agent-action-notice"]');
      expect(noticeAfterClick1).not.toBeNull();
      expect(noticeAfterClick1?.getAttribute('role')).toBe('status');
      expect(noticeAfterClick1?.getAttribute('aria-live')).toBe('polite');
      expect(noticeAfterClick1?.textContent).toContain('🔄 Bounded Repair Loop 2/3 실행 완료. 보정된 Diff를 확인하세요.');

      // Click 2: Advance loop 2/3 -> 3/3
      act(() => {
        refineBtn.click();
      });

      expect(loopInfo?.textContent).toContain('루프: 3/3');
      expect(statusBadge?.textContent).toBe('REPAIRING');

      const noticeAfterClick2 = container.querySelector('[data-testid="agent-action-notice"]');
      expect(noticeAfterClick2?.textContent).toContain('🔄 Bounded Repair Loop 3/3 실행 완료. 보정된 Diff를 확인하세요.');

      // Click 3: Exceeds upper limit (3/3 >= 3) -> Triggers BOUNDED_LOOP_EXCEEDED
      act(() => {
        refineBtn.click();
      });

      // Invariant 1: Screen status badge IMMEDIATELY transitions to REJECTED (REP-03 fix)
      expect(statusBadge?.textContent).toBe('REJECTED');

      // Invariant 2: Action notice banner displays BOUNDED_LOOP_EXCEEDED error with role="status" & aria-live="polite"
      const noticeAfterClick3 = container.querySelector('[data-testid="agent-action-notice"]');
      expect(noticeAfterClick3).not.toBeNull();
      expect(noticeAfterClick3?.getAttribute('role')).toBe('status');
      expect(noticeAfterClick3?.getAttribute('aria-live')).toBe('polite');
      expect(noticeAfterClick3?.textContent).toContain('🛑 BOUNDED_LOOP_EXCEEDED: Maximum repair limit (3) reached. Escalate to human developer.');

      // Invariant 3: Action buttons (refine, apply diff) are removed from the DOM once rejected
      expect(container.querySelector('[data-testid="agent-refine-btn"]')).toBeNull();
      expect(container.querySelector('[data-testid="agent-apply-diff-btn"]')).toBeNull();
    });
  });

  describe('REP-04: Diff Approval and Distinct Action Notice Banner', () => {
    it('displays approval notification with role="status" and aria-live="polite" distinct from unexposed governance notice', () => {
      act(() => {
        root.render(<NaturalLanguageRunView />);
      });

      const unexposedNotice = container.querySelector('[data-testid="agent-unexposed-notice"]');
      expect(unexposedNotice).not.toBeNull();

      // Submit run request first to generate proposed diff
      const submitBtn = Array.from(container.querySelectorAll('button[type="submit"]')).find((b) =>
        b.textContent?.includes('자연어 Run 분석 및 제안 Diff 생성')
      );
      expect(submitBtn).toBeDefined();

      act(() => {
        submitBtn?.click();
      });

      const applyBtn = container.querySelector('[data-testid="agent-apply-diff-btn"]') as HTMLButtonElement;
      expect(applyBtn).not.toBeNull();

      // Approve and mock-apply diff
      act(() => {
        applyBtn.click();
      });

      const statusBadge = container.querySelector('[data-testid="agent-status-badge"]');
      expect(statusBadge?.textContent).toBe('COMPLETED');

      const actionNotice = container.querySelector('[data-testid="agent-action-notice"]');
      expect(actionNotice).not.toBeNull();
      expect(actionNotice).not.toBe(unexposedNotice);
      expect(actionNotice?.getAttribute('role')).toBe('status');
      expect(actionNotice?.getAttribute('aria-live')).toBe('polite');
      expect(actionNotice?.textContent).toContain(
        'ℹ️ 코드 Diff 모의 적용 완료: 백엔드 코드 패치 API가 미노출 상태이므로 실제 작업공간 파일시스템에는 기록되지 않았습니다.'
      );

      // Diff action buttons are hidden after completion
      expect(container.querySelector('[data-testid="agent-apply-diff-btn"]')).toBeNull();
      expect(container.querySelector('[data-testid="agent-refine-btn"]')).toBeNull();
    });
  });

  describe('Security: Forbidden Prompt Exfiltration Detection', () => {
    it('blocks malicious prompts and displays security rejection banner with role="status"', () => {
      act(() => {
        root.render(<NaturalLanguageRunView />);
      });

      // Click preset 2: Forbidden action (AC-09 prompt leak test)
      const presetButtons = Array.from(container.querySelectorAll('button[type="button"]'));
      const maliciousPresetBtn = presetButtons.find((b) =>
        b.textContent?.includes('예시 2: 금지 행동 (AC-09 프롬프트 누출 시험)')
      );
      expect(maliciousPresetBtn).toBeDefined();

      act(() => {
        maliciousPresetBtn?.click();
      });

      // Submit run analysis request
      const submitBtn = Array.from(container.querySelectorAll('button[type="submit"]')).find((b) =>
        b.textContent?.includes('자연어 Run 분석 및 제안 Diff 생성')
      );
      expect(submitBtn).toBeDefined();

      act(() => {
        submitBtn?.click();
      });

      const actionNotice = container.querySelector('[data-testid="agent-action-notice"]');
      expect(actionNotice).not.toBeNull();
      expect(actionNotice?.getAttribute('role')).toBe('status');
      expect(actionNotice?.getAttribute('aria-live')).toBe('polite');
      expect(actionNotice?.textContent).toContain('🛑 요청 거절: LEAK_ATTEMPT_DETECTED');
    });
  });

  describe('Accessibility & Dark Theme Text Contrast', () => {
    // WCAG relative luminance calculation
    function getLuminance(r: number, g: number, b: number): number {
      const a = [r, g, b].map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
    }

    function parseHex(hex: string): [number, number, number] {
      const clean = hex.replace('#', '');
      return [
        parseInt(clean.substring(0, 2), 16),
        parseInt(clean.substring(2, 4), 16),
        parseInt(clean.substring(4, 6), 16),
      ];
    }

    function getContrast(hex1: string, hex2: string): number {
      const [r1, g1, b1] = parseHex(hex1);
      const [r2, g2, b2] = parseHex(hex2);
      const l1 = getLuminance(r1, g1, b1);
      const l2 = getLuminance(r2, g2, b2);
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (lighter + 0.05) / (darker + 0.05);
    }

    it('satisfies WCAG AA text contrast ratio (>= 4.5:1) for all foreground colors on dark background', () => {
      const darkBg = '#161b22';
      const codeBg = '#0d1117';

      // Colors used in NaturalLanguageRunView
      const textColors = [
        { name: 'white-text', hex: '#f0f6fc', bg: darkBg, min: 4.5 },
        { name: 'light-slate', hex: '#cbd5e1', bg: darkBg, min: 4.5 },
        { name: 'slate-400', hex: '#94a3b8', bg: darkBg, min: 4.5 },
        { name: 'muted-gray', hex: '#8b949e', bg: darkBg, min: 4.5 },
        { name: 'success-green', hex: '#3fb950', bg: darkBg, min: 4.5 },
        { name: 'brand-blue', hex: '#58a6ff', bg: darkBg, min: 4.5 },
        { name: 'error-red', hex: '#f85149', bg: darkBg, min: 4.5 },
        { name: 'code-text', hex: '#c9d1d9', bg: codeBg, min: 4.5 },
      ];

      for (const item of textColors) {
        const ratio = getContrast(item.hex, item.bg);
        expect(ratio).toBeGreaterThanOrEqual(item.min);
      }
    });
  });
});
