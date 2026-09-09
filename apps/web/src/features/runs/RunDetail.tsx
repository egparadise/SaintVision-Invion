import React, { useState } from 'react';
import { RunItem, RunState } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface RunDetailProps {
  run: RunItem;
  onBack: () => void;
  onNavigateEvidence?: (runId: string) => void;
}

const LIFECYCLE_STEPS: RunState[] = [
  'draft',
  'validated',
  'planned',
  'awaiting_approval',
  'scheduled',
  'running',
  'verifying',
  'succeeded',
];

export const RunDetail: React.FC<RunDetailProps> = ({ run, onBack, onNavigateEvidence }) => {
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs' | 'artifacts' | 'explain'>('timeline');

  return (
    <div>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Button variant="ghost" size="sm" onClick={onBack}>
            ← 목록으로
          </Button>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
              Run 상세: <code>{run.id}</code>
            </h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              {run.objective}
            </p>
          </div>
        </div>

        {onNavigateEvidence && (
          <Button variant="secondary" size="md" onClick={() => onNavigateEvidence(run.id)}>
            🔍 불변 증거 (Evidence) 패키지 열람
          </Button>
        )}
      </div>

      {/* 4 Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          borderBottom: '1px solid var(--color-border-subtle)',
          marginBottom: '24px',
        }}
      >
        {[
          { id: 'timeline', label: '1. 상태 전이 타임라인' },
          { id: 'logs', label: '2. 실시간 SSE 로그' },
          { id: 'artifacts', label: '3. 산출물 (Artifacts)' },
          { id: 'explain', label: '4. 자원 배치 Explain' },
        ].map((t) => {
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as typeof activeTab)}
              style={{
                padding: '10px 16px',
                fontSize: '0.875rem',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? 'var(--color-brand-primary)' : 'var(--color-text-secondary)',
                borderBottom: isActive ? '2px solid var(--color-brand-primary)' : '2px solid transparent',
                background: 'none',
                cursor: 'pointer',
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Timeline */}
      {activeTab === 'timeline' && (
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, marginBottom: '20px' }}>
            RunGraph 상태 전이 파이프라인 (불변 전이 계약 준수)
          </h3>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', overflowX: 'auto', padding: '16px 0' }}>
            {LIFECYCLE_STEPS.map((step, idx) => {
              const currentStepIdx = LIFECYCLE_STEPS.indexOf(run.state as RunState);
              const isPassed = currentStepIdx >= idx;
              const isCurrent = run.state === step;

              return (
                <div key={step} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: '90px' }}>
                  <div style={{ textAlign: 'center', width: '100%' }}>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        margin: '0 auto 8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.875rem',
                        fontWeight: 700,
                        backgroundColor: isCurrent
                          ? 'var(--color-brand-primary)'
                          : isPassed
                          ? 'var(--color-status-online)'
                          : 'var(--color-bg-subtle)',
                        color: isPassed || isCurrent ? '#ffffff' : 'var(--color-text-muted)',
                        border: isCurrent ? '3px solid var(--color-brand-subtle)' : 'none',
                      }}
                    >
                      {isPassed && !isCurrent ? '✓' : idx + 1}
                    </div>
                    <div style={{ fontSize: '0.75rem', fontWeight: isCurrent ? 700 : 500 }}>
                      {step}
                    </div>
                  </div>
                  {idx < LIFECYCLE_STEPS.length - 1 && (
                    <div
                      style={{
                        height: '2px',
                        flex: 1,
                        backgroundColor: isPassed ? 'var(--color-status-online)' : 'var(--color-border-subtle)',
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 2: Logs (Streaming) */}
      {activeTab === 'logs' && (
        <div
          style={{
            padding: '20px',
            backgroundColor: '#0d1117',
            color: '#c9d1d9',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid #30363d',
            fontFamily: 'monospace',
            fontSize: '0.8125rem',
            lineHeight: 1.6,
            maxHeight: '450px',
            overflowY: 'auto',
          }}
        >
          <div style={{ color: '#8b949e', borderBottom: '1px solid #21262d', paddingBottom: '8px', marginBottom: '12px' }}>
            [SSE Streaming: /v1/runs/{run.id}/events (Last-Event-ID: evt_01JABC1042, P95 지연 실측: 142ms)]
          </div>
          <div>[17:35:01 KST] [INFO] RunGraph 초기화 완료. TraceID: 4bf92f3577b34da6a3ce929d0e0e4736</div>
          <div>[17:35:02 KST] [INFO] Node-01 자원 Lease 확보 (Allocation: 4 Cores, 8 GiB RAM, 6 GiB VRAM)</div>
          <div>[17:35:05 KST] [INFO] Workspace [wsp-saint-pilot] 파일 시스템 마운트 완료.</div>
          <div>[17:35:10 KST] [INFO] 합성 데이터셋 로드 및 무결성 검증 (SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855)</div>
          <div>[17:35:18 KST] [INFO] 빌드 파이프라인 수행 중... [단위 테스트 48/48 통과]</div>
          <div style={{ color: '#58a6ff' }}>[17:35:22 KST] [STDOUT] All unit tests completed with exit code 0.</div>
          <div>[17:35:25 KST] [INFO] 결과 아티팩트 생성 및 Evidence 패키지 해시 계산 완료.</div>
        </div>
      )}

      {/* Tab 3: Artifacts */}
      {activeTab === 'artifacts' && (
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, marginBottom: '16px' }}>생성된 아티팩트 목록</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              { name: 'test-report-summary.json', size: '24.8 KiB', sha: 'a3f91c...89d1' },
              { name: 'build-output-manifest.tar.gz', size: '4.2 MiB', sha: '7b2210...fe45' },
              { name: 'model-evaluation-metrics.csv', size: '112 KiB', sha: '99e34a...12cc' },
            ].map((art) => (
              <div
                key={art.name}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-bg-canvas)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>📄 {art.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                    크기: {art.size} · SHA-256: {art.sha}
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => alert(`${art.name} 다운로드 요청`)}>
                  다운로드
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Explain */}
      {activeTab === 'explain' && (
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, marginBottom: '16px' }}>자원 배치 결정론적 Explain 분석</h3>
          <div style={{ fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
            <p style={{ marginBottom: '12px' }}>
              <strong>1단계 Hard Filter (필수 요건 검사):</strong>
            </p>
            <ul style={{ paddingLeft: '20px', marginBottom: '16px' }}>
              <li>Node-01-WinMain: 통과 (VRAM 8GiB 이상 요구 충족, VRAM 24GiB 가용)</li>
              <li>Node-02-WinWork: 통과 (VRAM 10GiB 가용)</li>
              <li>Node-03-WinDev: 탈락 (GPU 미탑재)</li>
              <li>Node-04-LinuxBuild: 탈락 (GPU 미탑재)</li>
              <li>Node-05-LinuxTrain: 통과 (VRAM 16GiB 가용)</li>
            </ul>

            <p style={{ marginBottom: '12px' }}>
              <strong>2단계 가중치 채점 (Weighted Scoring):</strong>
            </p>
            <div style={{ padding: '12px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-md)', fontFamily: 'monospace', fontSize: '0.8125rem' }}>
              <div>• Node-01-WinMain: 총점 94.2점 (GPU 여유도 0.82 × 40 + 지역성 1.0 × 30 + CPU 가용도 0.76 × 30) - [선정]</div>
              <div>• Node-05-LinuxTrain: 총점 81.5점</div>
              <div>• Node-02-WinWork: 총점 73.0점</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
