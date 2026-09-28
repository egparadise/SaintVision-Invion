import React, { useState } from 'react';
import { Button } from '@/shared/ui/Button';
import { ReleaseManager } from './releaseEngine';

export const ReleaseCandidateView: React.FC = () => {
  const [releaseManager] = useState<ReleaseManager>(() => new ReleaseManager());
  const [slos] = useState(releaseManager.getSloRecords());
  const [audits] = useState(releaseManager.getAccessibilityAudits());
  const [candidates, setCandidates] = useState(releaseManager.getReleaseCandidates());
  const [activeDevice, setActiveDevice] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const activeCandidate = candidates.find((c) => c.isActive) || candidates[0];

  const metCount = slos.filter((s) => s.status === 'met').length;
  const totalSlos = slos.length;
  const sloRate = totalSlos > 0 ? Math.round((metCount / totalSlos) * 100) : 0;

  const passCount = audits.filter((a) => a.status === 'pass').length;
  const totalAudits = audits.length;

  const vulnsSlo = slos.find((s) => s.name.includes('취약점'));
  const vulnsCountStr = vulnsSlo?.actualValue || '0 건';
  const isZeroVulns = vulnsSlo?.status === 'met';

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
          backgroundColor: 'rgba(56, 139, 253, 0.12)',
          borderBottom: '1px solid #30363d',
          borderRadius: '6px',
          color: '#58a6ff',
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
        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>Critical / High 미완화 결함 (AC-11)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: isZeroVulns ? '#3fb950' : '#f85149', marginTop: '4px' }}>
            {vulnsCountStr} {isZeroVulns ? '(모의 기준 충족)' : '(조치 필요)'}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {isZeroVulns ? '[정적 요약] 보안·무결성 지표 예시' : '미완화 결함 조치 필요'}
          </div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>주요 SLO 목표치 (모의 규격 시뮬레이션)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: metCount === totalSlos ? '#3fb950' : '#d29922', marginTop: '4px' }}>
            {sloRate}% ({metCount}/{totalSlos} 모의 규격 충족)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {metCount === totalSlos ? '모의 설계 목표 충족 (서버 미측정)' : `${totalSlos - metCount}개 지표 미충족 또는 미측정`}
          </div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>WCAG 2.1 AA 접근성 체크리스트 (모의 점검)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: passCount === totalAudits ? '#3fb950' : '#d29922', marginTop: '4px' }}>
            {passCount}/{totalAudits} 항목 점검 (자동화 검증 미실시)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {passCount === totalAudits ? '규격 체크리스트 충족 (모의 점검)' : `${totalAudits - passCount}개 규정 점검 필요`}
          </div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>현재 활성 릴리스 후보 (RC)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#58a6ff', marginTop: '4px' }}>
            {activeCandidate.tag}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>Build: <code>{activeCandidate.buildSha}</code></div>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div
          role={actionNotice.type === 'error' ? 'alert' : 'status'}
          aria-live={actionNotice.type === 'error' ? 'assertive' : 'polite'}
          style={{
            padding: '12px 18px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: actionNotice.type === 'error' ? 'rgba(248, 81, 73, 0.15)' : 'rgba(46, 160, 67, 0.15)',
            border: `1px solid ${actionNotice.type === 'error' ? '#f85149' : '#3fb950'}`,
            color: actionNotice.type === 'error' ? '#f85149' : '#3fb950',
          }}
        >
          {actionNotice.text}
        </div>
      )}

      {/* Split: SLO Metrics & WCAG Accessibility Audit */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Left: SLO Metrics Actual vs Target Table */}
        <div
          style={{
            backgroundColor: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              주요 SLO 모의 규격 및 목표 비교 (AC-11)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              [정적 예시] 원격 텔레메트리 미연동 (사전 설계 규격 시뮬레이션)
            </p>
          </div>

          <div style={{ overflowX: 'auto', width: '100%' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                  <th style={{ padding: '8px' }}>SLO 항목</th>
                  <th style={{ padding: '8px' }}>목표치</th>
                  <th style={{ padding: '8px' }}>모의 예시값 (서버 미측정)</th>
                  <th style={{ padding: '8px' }}>상태</th>
                </tr>
              </thead>
              <tbody>
                {slos.map((slo) => (
                  <tr key={slo.name} style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '8px', fontWeight: 500, color: '#f0f6fc' }}>{slo.name}</td>
                    <td style={{ padding: '8px', color: '#8b949e' }}>{slo.targetValue}</td>
                    <td style={{ padding: '8px', color: '#58a6ff', fontWeight: 600 }}>{slo.actualValue}</td>
                    <td style={{ padding: '8px' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: slo.status === 'met' ? 'rgba(46, 160, 67, 0.2)' : 'rgba(248, 81, 73, 0.2)',
                          color: slo.status === 'met' ? '#3fb950' : '#f85149',
                        }}
                      >
                        {slo.status === 'met' ? '모의 MET (미측정)' : 'BREACHED'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: WCAG 2.1 AA Accessibility Audit Matrix */}
        <div
          style={{
            backgroundColor: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              WCAG 2.1 AA 접근성 심층 감사 결과
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              [모의 지표] WCAG 2.1 AA 규격 체크리스트 (자동화 검증 미실시)
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {audits.map((audit) => (
              <div
                key={audit.ruleId}
                style={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  fontSize: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: '#f0f6fc' }}>
                    {audit.ruleId} <span style={{ color: '#58a6ff', fontSize: '11px' }}>({audit.wcagLevel})</span>
                  </div>
                  <div style={{ color: '#8b949e', marginTop: '2px' }}>{audit.description}</div>
                  {audit.contrastRatio && (
                    <div style={{ color: '#3fb950', fontSize: '11px', marginTop: '2px' }}>
                      [수동 계산값] 특정 텍스트 쌍 기준 (전체 UI 렌더 실측 아님): <strong>{audit.contrastRatio}:1</strong>
                    </div>
                  )}
                </div>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: audit.status === 'pass' ? 'rgba(46, 160, 67, 0.2)' : 'rgba(248, 81, 73, 0.2)',
                    color: audit.status === 'pass' ? '#3fb950' : '#f85149',
                  }}
                >
                  {audit.status === 'pass' ? '모의 PASS' : 'FAIL'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Release Candidate Management & Rollback Verification Panel (AC-11) */}
      <div
        style={{
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              릴리스 후보 관리 및 즉시 롤백 검증 (AC-11 Rollback Verification)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              [모의 안내] 클라이언트 인메모리 롤백 시뮬레이션 (실 인프라 캐시 무효화 미연동)
            </p>
          </div>

          {/* Viewport Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '12px', color: '#8b949e', marginRight: '6px' }}>뷰포트 시뮬레이션:</span>
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
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
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
              {candidates.map((rc) => (
                <tr key={rc.tag} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={{ padding: '10px 8px', fontWeight: 600, color: '#f0f6fc' }}>{rc.tag}</td>
                  <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)' }}>
                    <code>{rc.buildSha}</code>
                  </td>
                  <td style={{ padding: '10px 8px', color: '#3fb950' }}>{rc.sloComplianceRate}%</td>
                  <td style={{ padding: '10px 8px' }}>{rc.unresolvedVulnerabilities} 건</td>
                  <td style={{ padding: '10px 8px' }}>
                    <span style={{ color: rc.rollbackVerified ? '#3fb950' : '#8b949e' }}>
                      {rc.rollbackVerified ? '✔ 모의 검증 완료' : '미측정 (대기)'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 8px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: rc.isActive ? 'rgba(56, 139, 253, 0.2)' : 'rgba(139, 148, 158, 0.1)',
                        color: rc.isActive ? '#58a6ff' : '#8b949e',
                      }}
                    >
                      {rc.isActive ? '모의 활성 (서버 API 미노출 · 실 인프라 미배포)' : '모의 대기'}
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
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
