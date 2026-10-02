import React, { useState } from 'react';
import { Button } from '@/shared/ui/Button';
import { ReleaseManager, DynamicSloEvidence } from './releaseEngine';

export interface ReleaseCandidateViewProps {
  initialEvidence?: DynamicSloEvidence;
}

export type SloRecordStatus = 'met' | 'unmeasured' | 'breached';

export interface SloStatusStyle {
  color: string;
  border: string;
  bg: string;
  label: string;
}

export const SLO_STATUS_CONFIG: Record<SloRecordStatus, SloStatusStyle> = {
  met: {
    color: 'var(--color-status-online)',
    border: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    label: '모의 MET (미측정)',
  },
  unmeasured: {
    color: 'var(--color-text-secondary)',
    border: 'var(--color-border-subtle)',
    bg: 'var(--color-bg-subtle)',
    label: 'UNMEASURED (미측정) · 모의 MET (미측정)',
  },
  breached: {
    color: 'var(--color-status-offline)',
    border: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    label: 'BREACHED',
  },
};

export type AuditStatus = 'pass' | 'fail';

export interface AuditStatusStyle {
  color: string;
  border: string;
  bg: string;
  label: string;
}

export const AUDIT_STATUS_CONFIG: Record<AuditStatus, AuditStatusStyle> = {
  pass: {
    color: 'var(--color-status-online)',
    border: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    label: '모의 PASS',
  },
  fail: {
    color: 'var(--color-status-offline)',
    border: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    label: 'FAIL',
  },
};

export type CandidateActiveStatus = 'active' | 'waiting';

export interface CandidateStatusStyle {
  color: string;
  border: string;
  bg: string;
  label: string;
}

export const CANDIDATE_STATUS_CONFIG: Record<CandidateActiveStatus, CandidateStatusStyle> = {
  active: {
    color: 'var(--color-brand-hover)',
    border: 'var(--color-brand-hover)',
    bg: 'var(--color-bg-subtle)',
    label: '모의 활성 (서버 API 미노출 · 실 인프라 미배포)',
  },
  waiting: {
    color: 'var(--color-text-secondary)',
    border: 'var(--color-border-subtle)',
    bg: 'var(--color-bg-subtle)',
    label: '모의 대기',
  },
};

export function getSloStatusConfig(status?: string | null): SloStatusStyle {
  if (status && status in SLO_STATUS_CONFIG) {
    return SLO_STATUS_CONFIG[status as SloRecordStatus];
  }
  return {
    color: 'var(--color-status-unknown)',
    border: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    label: `UNKNOWN (${status || 'UNKNOWN'})`,
  };
}

export function getAuditStatusConfig(status?: string | null): AuditStatusStyle {
  if (status && status in AUDIT_STATUS_CONFIG) {
    return AUDIT_STATUS_CONFIG[status as AuditStatus];
  }
  return {
    color: 'var(--color-status-unknown)',
    border: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    label: `UNKNOWN (${status || 'UNKNOWN'})`,
  };
}

export function getCandidateStatusConfig(status?: string | null): CandidateStatusStyle {
  if (status && status in CANDIDATE_STATUS_CONFIG) {
    return CANDIDATE_STATUS_CONFIG[status as CandidateActiveStatus];
  }
  return {
    color: 'var(--color-status-unknown)',
    border: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    label: `UNKNOWN (${status || 'UNKNOWN'})`,
  };
}

export const ReleaseCandidateView: React.FC<ReleaseCandidateViewProps> = ({ initialEvidence }) => {
  const [releaseManager] = useState<ReleaseManager>(() => new ReleaseManager());
  const [slos] = useState(() =>
    initialEvidence ? releaseManager.computeSloRecords(initialEvidence) : releaseManager.getSloRecords()
  );
  const [audits] = useState(releaseManager.getAccessibilityAudits());
  const [candidates, setCandidates] = useState(releaseManager.getReleaseCandidates());
  const [activeDevice, setActiveDevice] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const activeCandidate = candidates.find((c) => c.isActive) || candidates[0];

  const metCount = slos.filter((s) => s.status === 'met').length;
  const unmeasuredCount = slos.filter((s) => s.status === 'unmeasured').length;
  const totalSlos = slos.length;
  const totalMeasured = totalSlos - unmeasuredCount;
  const sloRate = totalMeasured > 0 ? Math.round((metCount / totalMeasured) * 100) : 0;

  const passCount = audits.filter((a) => a.status === 'pass').length;
  const totalAudits = audits.length;

  const vulnsSlo = slos.find((s) => s.name.includes('취약점'));
  const isZeroVulns = vulnsSlo?.status === 'met';
  const isVulnsUnmeasured = vulnsSlo?.status === 'unmeasured';
  const vulnsCountStr = vulnsSlo?.actualValue || (isVulnsUnmeasured ? '미측정' : '0 건');

  const handleRollback = (targetTag: string) => {
    const res = releaseManager.rollbackToVersion(targetTag);
    if (!res.success) {
      setActionNotice({
        type: 'error',
        text: `🛑 롤백 실패: ${res.error}`,
      });
    } else {
      setCandidates(releaseManager.getReleaseCandidates());
      setActionNotice({
        type: 'success',
        text: `✔ [모의 시뮬레이션] AC-11 롤백 절차 검증 완료: 로컬 활성 버전이 [${targetTag}] (Build ${res.activeCandidate?.buildSha})로 전환되었습니다. (백엔드 릴리스 제어 API 미노출 상태로 실제 인프라 및 CDN 캐시 미반영)`,
      });
    }
  };

  return (
    <div
      style={{
        padding: '24px',
        maxWidth: activeDevice === 'mobile' ? '375px' : activeDevice === 'tablet' ? '768px' : '1400px',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        transition: 'max-width 0.25s ease-in-out',
        width: '100%',
      }}
    >
      {/* Unexposed Release Notice Banner */}
      <div
        role="status"
        aria-live="polite"
        data-testid="release-unexposed-notice"
        style={{
          padding: '8px 16px',
          backgroundColor: 'var(--color-bg-subtle)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '6px',
          color: 'var(--color-text-secondary)',
          fontSize: '12px',
        }}
      >
        ℹ️ <strong>릴리스 후보(RC) 및 무중단 롤백 제어기 (백엔드 배포 API 미노출)</strong>: 실제 프로덕션 트래픽 스위칭 및 CDN 캐시 무효화는 배포 오케스트레이터에서 수행되며, 본 화면은 AC-11 롤백 수명주기 및 SLO 검증을 위한 클라이언트 인메모리 시뮬레이션입니다.
      </div>

      {/* AC-11 Top Metrics Banner */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
        }}
      >
        <div
          data-testid="kpi-vulns-card"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>Critical / High 미완화 결함 (AC-11)</div>
          <div
            style={{
              fontSize: '24px',
              fontWeight: 700,
              color: isZeroVulns ? 'var(--color-status-online)' : isVulnsUnmeasured ? 'var(--color-text-secondary)' : 'var(--color-status-offline)',
              marginTop: '4px',
            }}
          >
            {isVulnsUnmeasured ? '미측정 (NOT_OBSERVED)' : `${vulnsCountStr} ${isZeroVulns ? '(모의 기준 충족)' : '(조치 필요)'}`}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {isVulnsUnmeasured ? '서버 텔레메트리 연동 대기 (미측정) (모의 기준 충족)' : isZeroVulns ? '[정적 요약] 보안·무결성 지표 예시' : '미완화 결함 조치 필요'}
          </div>
        </div>

        <div
          data-testid="kpi-slo-card"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>주요 SLO 목표치 (모의 규격 시뮬레이션)</div>
          <div
            style={{
              fontSize: '24px',
              fontWeight: 700,
              color: totalMeasured > 0 && metCount === totalMeasured ? 'var(--color-status-online)' : 'var(--color-status-degraded)',
              marginTop: '4px',
            }}
          >
            {totalMeasured > 0 ? `${sloRate}% (${metCount}/${totalMeasured} 모의 규격 충족)` : `0% (0/0 실측)`}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {unmeasuredCount > 0
              ? `${unmeasuredCount}개 지표 서버 관측치 부재 (UNMEASURED)`
              : metCount === totalSlos
              ? '모의 설계 목표 충족 (서버 미측정)'
              : `${totalSlos - metCount}개 지표 미충족 또는 미측정`}
          </div>
        </div>

        <div
          data-testid="kpi-wcag-card"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>WCAG 2.1 AA 접근성 체크리스트 (모의 점검)</div>
          <div
            style={{
              fontSize: '24px',
              fontWeight: 700,
              color: passCount === totalAudits ? 'var(--color-status-online)' : 'var(--color-status-degraded)',
              marginTop: '4px',
            }}
          >
            {passCount}/{totalAudits} 항목 점검 (자동화 검증 미실시)
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {passCount === totalAudits ? '규격 체크리스트 충족 (모의 점검)' : `${totalAudits - passCount}개 규정 점검 필요`}
          </div>
        </div>

        <div
          data-testid="active-candidate-card"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>현재 활성 릴리스 후보 (RC)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-brand-hover)', marginTop: '4px' }}>
            {activeCandidate.tag}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>Build: <code>{activeCandidate.buildSha}</code></div>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div
          role={actionNotice.type === 'error' ? 'alert' : 'status'}
          aria-live={actionNotice.type === 'error' ? 'assertive' : 'polite'}
          data-testid="release-action-notice"
          style={{
            padding: '12px 18px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: 'var(--color-bg-subtle)',
            border: `1px solid ${actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)'}`,
            color: actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)',
          }}
        >
          {actionNotice.text}
        </div>
      )}

      {/* Split: SLO Metrics & WCAG Accessibility Audit */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Left: SLO Metrics Actual vs Target Table */}
        <div
          data-testid="slo-metrics-card"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
              주요 SLO 모의 규격 및 목표 비교 (AC-11)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
              측정 환경: 실측 텔레메트리 연동 대기 (미측정) · [정적 예시] 원격 텔레메트리 미연동 (사전 설계 규격 시뮬레이션)
            </p>
          </div>

          <div style={{ overflowX: 'auto', width: '100%' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
                  <th style={{ padding: '8px' }}>SLO 항목</th>
                  <th style={{ padding: '8px' }}>목표치</th>
                  <th style={{ padding: '8px' }}>모의 예시값 (서버 미측정)</th>
                  <th style={{ padding: '8px' }}>상태</th>
                </tr>
              </thead>
              <tbody>
                {slos.map((slo) => {
                  const statusCfg = getSloStatusConfig(slo.status);
                  return (
                    <tr key={slo.name} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                      <td style={{ padding: '8px', fontWeight: 500, color: 'var(--color-text-primary)' }}>{slo.name}</td>
                      <td style={{ padding: '8px', color: 'var(--color-text-muted)' }}>{slo.targetValue}</td>
                      <td style={{ padding: '8px', color: 'var(--color-brand-hover)', fontWeight: 600 }}>{slo.actualValue}</td>
                      <td style={{ padding: '8px' }}>
                        <span
                          data-testid={`slo-status-badge-${slo.name}`}
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: statusCfg.bg,
                            border: `1px solid ${statusCfg.border}`,
                            color: statusCfg.color,
                            display: 'inline-block',
                          }}
                        >
                          {statusCfg.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: WCAG 2.1 AA Accessibility Audit Matrix */}
        <div
          data-testid="wcag-audit-card"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
              WCAG 2.1 AA 접근성 심층 감사 결과
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
              [모의 지표] WCAG 2.1 AA 규격 체크리스트 (자동화 검증 미실시)
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {audits.map((audit) => {
              const auditCfg = getAuditStatusConfig(audit.status);
              return (
                <div
                  key={audit.ruleId}
                  style={{
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    padding: '10px 14px',
                    fontSize: '12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                      {audit.ruleId} <span style={{ color: 'var(--color-brand-hover)', fontSize: '11px' }}>({audit.wcagLevel})</span>
                    </div>
                    <div style={{ color: 'var(--color-text-secondary)', marginTop: '2px' }}>{audit.description}</div>
                    {audit.contrastRatio && (
                      <div style={{ color: 'var(--color-status-online)', fontSize: '11px', marginTop: '2px' }}>
                        [수동 계산값] 특정 텍스트 쌍 기준 (전체 UI 렌더 실측 아님): <strong>{audit.contrastRatio}:1</strong>
                      </div>
                    )}
                  </div>
                  <span
                    data-testid={`audit-status-badge-${audit.ruleId}`}
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor: auditCfg.bg,
                      border: `1px solid ${auditCfg.border}`,
                      color: auditCfg.color,
                      display: 'inline-block',
                    }}
                  >
                    {auditCfg.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Release Candidate Management & Rollback Verification Panel (AC-11) */}
      <div
        data-testid="rollback-management-card"
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
              릴리스 후보 관리 및 즉시 롤백 검증 (AC-11 Rollback Verification)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
              [모의 안내] 클라이언트 인메모리 롤백 시뮬레이션 (실 인프라 캐시 무효화 미연동)
            </p>
          </div>

          {/* Viewport Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginRight: '6px' }}>뷰포트 시뮬레이션:</span>
            {(['desktop', 'tablet', 'mobile'] as const).map((dev) => (
              <Button
                key={dev}
                size="sm"
                variant={activeDevice === dev ? 'primary' : 'secondary'}
                onClick={() => setActiveDevice(dev)}
              >
                {dev.toUpperCase()}
              </Button>
            ))}
          </div>
        </div>

        <div style={{ overflowX: 'auto', width: '100%' }}>
          <table data-testid="candidates-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
                <th style={{ padding: '8px' }}>Release Tag</th>
                <th style={{ padding: '8px' }}>Build SHA</th>
                <th style={{ padding: '8px' }}>SLO 달성률</th>
                <th style={{ padding: '8px' }}>미완화 취약점</th>
                <th style={{ padding: '8px' }}>롤백 검증</th>
                <th style={{ padding: '8px' }}>활성 상태</th>
                <th style={{ padding: '8px', textAlign: 'right' }}>액션</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((rc) => {
                const rcCfg = getCandidateStatusConfig(rc.isActive ? 'active' : 'waiting');
                return (
                  <tr key={rc.tag} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                    <td style={{ padding: '10px 8px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{rc.tag}</td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)', color: 'var(--color-text-secondary)' }}>
                      <code>{rc.buildSha}</code>
                    </td>
                    <td style={{ padding: '10px 8px', color: rc.sloComplianceRate !== null ? 'var(--color-status-online)' : 'var(--color-text-secondary)' }}>
                      {rc.sloComplianceRate !== null ? `${rc.sloComplianceRate}%` : '미측정 (NOT_OBSERVED)'}
                    </td>
                    <td style={{ padding: '10px 8px', color: rc.unresolvedVulnerabilities !== null ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
                      {rc.unresolvedVulnerabilities !== null ? `${rc.unresolvedVulnerabilities} 건` : '미측정 (NOT_OBSERVED)'}
                    </td>
                    <td style={{ padding: '10px 8px' }}>
                      <span style={{ color: rc.rollbackVerified ? 'var(--color-status-online)' : 'var(--color-text-secondary)' }}>
                        {rc.rollbackVerified ? '✔ 모의 검증 완료' : '미측정 (대기)'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 8px' }}>
                      <span
                        data-testid={`candidate-status-badge-${rc.tag}`}
                        style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: rcCfg.bg,
                          border: `1px solid ${rcCfg.border}`,
                          color: rcCfg.color,
                          display: 'inline-block',
                        }}
                      >
                        {rcCfg.label}
                      </span>
                    </td>
                    <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                      {!rc.isActive && (
                        <Button
                          size="sm"
                          variant="secondary"
                          aria-label={`이 버전(${rc.tag})으로 롤백 실행 (AC-11)`}
                          onClick={() => handleRollback(rc.tag)}
                        >
                          이 버전으로 롤백 실행 (AC-11)
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
