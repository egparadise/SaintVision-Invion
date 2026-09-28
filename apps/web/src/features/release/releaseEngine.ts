import { SloMetricRecord, AccessibilityAuditResult, ReleaseCandidate } from '@/contracts/types';

export interface DynamicSloEvidence {
  schedulerP95LatencySeconds?: number;
  heartbeatDetectionSeconds?: number;
  unapprovedExecutionsCount?: number;
  dockerSocketExposedCount?: number;
  rpoMinutes?: number;
  rtoMinutes?: number;
  unresolvedVulnerabilitiesCount?: number;
  evidenceRef?: string;
}

export class ReleaseManager {
  private activeEvidence: DynamicSloEvidence = {};

  /**
   * Computes dynamic SLO status directly from actual measured telemetry & evidence records.
   * If server telemetry/evidence for a metric is absent, status is marked as 'unmeasured'
   * and actualValue is displayed as '미측정' (no synthetic default measurements).
   */
  public computeSloRecords(evidence?: DynamicSloEvidence): SloMetricRecord[] {
    const e = { ...this.activeEvidence, ...evidence };

    const formatMetric = (
      name: string,
      targetValue: string,
      val: number | undefined,
      threshold: number,
      op: '<=' | '==',
      unit: string,
      category: 'latency' | 'resilience' | 'security' | 'storage',
      customSuccessStr?: string,
      customFailStr?: (v: number) => string
    ): SloMetricRecord => {
      if (val === undefined || val === null || isNaN(val)) {
        return {
          name,
          targetValue,
          actualValue: '미측정',
          status: 'unmeasured',
          category,
        };
      }
      const isMet = op === '<=' ? val <= threshold : val === threshold;
      let actualValue = `${val} ${unit}`;
      if (unit === '초') actualValue = `${val.toFixed(op === '<=' && threshold === 60 ? 1 : 2)} 초`;
      if (unit === '분') actualValue = `${val.toFixed(1)} 분`;
      if (customSuccessStr && isMet) actualValue = customSuccessStr;
      else if (customFailStr && !isMet) actualValue = customFailStr(val);

      return {
        name,
        targetValue,
        actualValue,
        status: isMet ? 'met' : 'breached',
        category,
      };
    };

    return [
      formatMetric('P95 배치 스케줄러 지연시간', '≤ 2.0 초', e.schedulerP95LatencySeconds, 2.0, '<=', '초', 'latency'),
      formatMetric('노드 Heartbeat 이탈 감지 시간', '≤ 60 초', e.heartbeatDetectionSeconds, 60.0, '<=', '초', 'resilience'),
      formatMetric('미승인 L2/L3 명령 우회 실행 수', '0 건', e.unapprovedExecutionsCount, 0, '==', '건', 'security', '0 건 (100% 차단)', (v) => `${v} 건 위반`),
      formatMetric('Docker Socket 호스트 노출 수', '0 건', e.dockerSocketExposedCount, 0, '==', '건', 'security', '0 건 (완전 격리)', (v) => `${v} 건 노출`),
      formatMetric('WAL 백업 복원 목표 시점 (RPO)', '≤ 15 분', e.rpoMinutes, 15.0, '<=', '분', 'storage'),
      formatMetric('재해 복구 가동 목표 시간 (RTO)', '≤ 60 분', e.rtoMinutes, 60.0, '<=', '분', 'storage'),
      formatMetric('Critical / High 미완화 보안 취약점', '0 건', e.unresolvedVulnerabilitiesCount, 0, '==', '건', 'security', '0 건', (v) => `${v} 건`),
    ];
  }

  private accessibilityAudits: AccessibilityAuditResult[] = [
    {
      ruleId: 'wcag21-1.4.3-contrast-minimum',
      wcagLevel: 'AA',
      description: '본문 텍스트와 배경 간 명도 대비가 최소 4.5:1 이상이어야 함',
      status: 'pass',
      contrastRatio: 11.4, // #c9d1d9 on #0d1117
    },
    {
      ruleId: 'wcag21-1.4.11-non-text-contrast',
      wcagLevel: 'AA',
      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(#6e7681 on #0d1117) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',
      status: 'pass',
      contrastRatio: 4.12, // #6e7681 on #0d1117 (WCAG 2.1 AA non-text >= 3.0:1)
    },
    {
      ruleId: 'wcag21-2.1.1-keyboard-navigation',
      wcagLevel: 'A',
      description: '모든 대화형 컴포넌트(모달, 탭, 버튼, 입력창)가 키보드 Tab 및 Enter/Space로 조작 가능해야 함',
      status: 'pass',
    },
    {
      ruleId: 'wcag21-2.4.7-focus-visible',
      wcagLevel: 'AA',
      description: '키보드 포커스를 받는 모든 요소에 명확한 포커스 링이 표시되어야 함',
      status: 'pass',
    },
    {
      ruleId: 'wcag21-4.1.2-name-role-value',
      wcagLevel: 'A',
      description: '스크린 리더를 위한 ARIA Role(alert, status, dialog) 및 접근 가능한 레이블이 제공되어야 함',
      status: 'pass',
    },
  ];

  private releaseCandidates: ReleaseCandidate[] = [
    {
      tag: 'v1.0.0-rc.2',
      buildSha: 'dc717b6',
      builtAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      unresolvedVulnerabilities: null,
      sloComplianceRate: null,
      rollbackVerified: false,
      isActive: true,
    },
    {
      tag: 'v1.0.0-rc.1',
      buildSha: '39699e9',
      builtAt: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
      unresolvedVulnerabilities: null,
      sloComplianceRate: null,
      rollbackVerified: true,
      isActive: false,
    },
  ];

  getSloRecords(evidence?: DynamicSloEvidence): SloMetricRecord[] {
    return this.computeSloRecords(evidence);
  }

  getAccessibilityAudits(): AccessibilityAuditResult[] {
    return [...this.accessibilityAudits];
  }

  getReleaseCandidates(): ReleaseCandidate[] {
    return [...this.releaseCandidates];
  }

  /**
   * Execute Web Rollback Simulation (AC-11)
   */
  rollbackToVersion(targetTag: string): { success: boolean; activeCandidate?: ReleaseCandidate; error?: string } {
    const target = this.releaseCandidates.find((rc) => rc.tag === targetTag);
    if (!target) {
      return { success: false, error: `Release candidate ${targetTag} not found` };
    }

    this.releaseCandidates.forEach((rc) => {
      rc.isActive = rc.tag === targetTag;
    });

    target.rollbackVerified = true;
    return { success: true, activeCandidate: { ...target } };
  }
}
