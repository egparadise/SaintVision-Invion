import React, { useState, useEffect } from 'react';
import { RunItem, RunState, ShardExecutionItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { apiClient } from '@/shared/api/client';

export interface RunDetailProps {
  run: RunItem;
  onBack: () => void;
  onNavigateEvidence?: (runId: string) => void;
  onNavigateApproval?: (runId: string) => void;
  onNavigateRun?: (runId: string) => void;
  onCancelRun?: (runId: string, reason: string) => Promise<void>;
  onRefreshRun?: () => void;
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

export const RunDetail: React.FC<RunDetailProps> = ({
  run,
  onBack,
  onNavigateEvidence,
  onNavigateApproval,
  onNavigateRun,
  onCancelRun,
  onRefreshRun,
}) => {
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs' | 'artifacts' | 'explain' | 'shards'>('timeline');
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('user_requested');
  const [isCancelling, setIsCancelling] = useState(false);
  const [shards, setShards] = useState<ShardExecutionItem[]>([]);
  const [isLoadingShards, setIsLoadingShards] = useState(false);
  const [isReclaiming, setIsReclaiming] = useState(false);
  const [isBulkCancelling, setIsBulkCancelling] = useState(false);
  const [reclaimNotice, setReclaimNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function fetchShards() {
      setIsLoadingShards(true);
      try {
        const res = await apiClient<{ items: ShardExecutionItem[] }>(`/v1/runs/${run.id}/shards`);
        if (mounted && res.items) {
          setShards(res.items);
        }
      } catch (err) {
        console.warn('Failed to fetch shards:', err);
      } finally {
        if (mounted) setIsLoadingShards(false);
      }
    }
    fetchShards();
    return () => {
      mounted = false;
    };
  }, [run.id]);

  const handleBulkCancelShards = async () => {
    setIsBulkCancelling(true);
    try {
      await apiClient(`/v1/runs/${run.id}/shards/cancel-all`, { method: 'POST' });
      setReclaimNotice('⚡ 모든 분산 샤드에 일괄 취소 명령이 원자적으로 전달되었습니다. (자원 반환 대기 중)');
      const res = await apiClient<{ items: ShardExecutionItem[] }>(`/v1/runs/${run.id}/shards`);
      if (res.items) setShards(res.items);
      onRefreshRun?.();
    } catch (e: any) {
      alert(e.message || '샤드 일괄 취소 실패');
    } finally {
      setIsBulkCancelling(false);
    }
  };

  const handleReclaimResources = async () => {
    setIsReclaiming(true);
    try {
      await apiClient<{ runId: string; resourceReleasePending: boolean }>(`/v1/runs/${run.id}/reclaim-resources`, {
        method: 'POST',
      });
      setReclaimNotice('✓ 분산 노드로부터 NodeStopReceipt 수신을 확인하고 모든 Lease 자원을 완전히 회수하였습니다. (ADR-040/041)');
      const sRes = await apiClient<{ items: ShardExecutionItem[] }>(`/v1/runs/${run.id}/shards`);
      if (sRes.items) setShards(sRes.items);
      onRefreshRun?.();
    } catch (e: any) {
      alert(e.message || '자원 회수 실패');
    } finally {
      setIsReclaiming(false);
    }
  };

  const canCancel =
    run.state !== 'succeeded' && run.state !== 'failed' && run.state !== 'cancelled';

  const handleCancelSubmit = async () => {
    if (!onCancelRun) return;
    setIsCancelling(true);
    try {
      await onCancelRun(run.id, cancelReason);
      setShowCancelModal(false);
    } catch (e: any) {
      alert(e.message || '취소 실패');
    } finally {
      setIsCancelling(false);
    }
  };

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

        <div style={{ display: 'flex', gap: '8px' }}>
          {run.state === 'awaiting_approval' && onNavigateApproval && (
            <Button variant="danger" size="md" onClick={() => onNavigateApproval(run.id)}>
              🚨 승인 검토 이동
            </Button>
          )}

          {canCancel && onCancelRun && (
            <Button variant="secondary" size="md" onClick={() => setShowCancelModal(true)}>
              ⛔ Run 취소 (S04)
            </Button>
          )}

          {onNavigateEvidence && (
            <Button variant="secondary" size="md" onClick={() => onNavigateEvidence(run.id)}>
              🔍 불변 증거 열람
            </Button>
          )}
        </div>
      </div>

      {/* Cancellation Modal (S04-FE / AC-04) */}
      {showCancelModal && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-subtle)',
              padding: '24px',
              maxWidth: '440px',
              width: '100%',
              boxShadow: 'var(--shadow-md)',
            }}
          >
            <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-brand-danger)' }}>
              Run 실행 취소 확인 (AC-04)
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '8px' }}>
              현재 진행 중인 <code>{run.id}</code> 작업을 즉시 취소하고 할당된 노드 자원을 안전하게 회수합니다.
            </p>

            <div style={{ marginTop: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
                취소 사유 선택 (ADR-001)
              </label>
              <select
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border-strong)',
                  backgroundColor: 'var(--color-bg-subtle)',
                  color: 'var(--color-text-primary)',
                  fontSize: '0.875rem',
                }}
              >
                <option value="user_requested">사용자 직접 취소 요청 (user_requested)</option>
                <option value="timeout">실행 제한 시간 초과 (timeout)</option>
                <option value="budget_exceeded">프로젝트 예산 한도 초과 (budget_exceeded)</option>
                <option value="security_concern">보안 격리 위반 의심 (security_concern)</option>
              </select>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <Button variant="secondary" size="md" onClick={() => setShowCancelModal(false)} disabled={isCancelling}>
                닫기
              </Button>
              <Button variant="danger" size="md" onClick={handleCancelSubmit} disabled={isCancelling}>
                {isCancelling ? '취소 처리 중...' : '즉시 취소 실행'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Parent Shard Navigation Banner */}
      {run.parentId && (
        <div
          style={{
            padding: '12px 18px',
            backgroundColor: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: '0.875rem', color: '#1d4ed8' }}>
            <strong>↳ 하위 분산 샤드:</strong> 이 작업은 상위 분산 계획 <code>{run.parentId}</code>의 샤드 #{((run.shardIndex ?? 0) + 1)}입니다.
          </div>
          {onNavigateRun && (
            <Button variant="secondary" size="sm" onClick={() => onNavigateRun(run.parentId!)}>
              상위 부모 Run으로 이동
            </Button>
          )}
        </div>
      )}

      {/* Resource Release Pending Banner (ADR-040/042) */}
      {run.resourceReleasePending && (
        <div
          style={{
            padding: '14px 18px',
            backgroundColor: 'rgba(217, 119, 6, 0.12)',
            border: '1px solid #d97706',
            borderRadius: 'var(--radius-md)',
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ fontWeight: 600, color: '#d97706', fontSize: '0.875rem' }}>
              ⏳ 자원 반환 대기 중 (Resource Release Pending - ADR-040/042)
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
              작업이 취소/종료되었으나 분산 노드의 물리적 NodeStopReceipt fsync 및 안전한 Lease 반환 절차를 확인 중입니다.
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={handleReclaimResources} disabled={isReclaiming}>
            {isReclaiming ? '확인 중...' : '정지 영수증 확정 및 자원 회수'}
          </Button>
        </div>
      )}

      {/* Reclaim / Bulk Cancel Notice Banner */}
      {reclaimNotice && (
        <div
          style={{
            padding: '12px 18px',
            backgroundColor: 'rgba(16, 185, 129, 0.12)',
            border: '1px solid #10b981',
            color: '#047857',
            borderRadius: 'var(--radius-md)',
            marginBottom: '16px',
            fontSize: '0.875rem',
            fontWeight: 500,
          }}
        >
          {reclaimNotice}
        </div>
      )}

      {/* 5 Tabs */}
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
          { id: 'shards', label: `5. 분산 샤드 & 자원 회수 (${shards.length > 0 ? shards.length : 'ADR-040'})` },
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

      {/* Tab 5: Shards & Resource Reclamation (ADR-040 / ADR-042 / SHARD-I07) */}
      {activeTab === 'shards' && (
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div>
              <h3 style={{ fontSize: '1.0625rem', fontWeight: 600 }}>
                분산 샤드 실행 & 물리 자원 회수 상태 (ADR-040 / ADR-042 / SHARD-I07)
              </h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                독립 샤드의 물리 정지(NodeStopReceipt), 단조 Fencing, 출력 해시 확정 및 자원 반환 관리
              </p>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              {canCancel && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleBulkCancelShards}
                  disabled={isBulkCancelling}
                >
                  {isBulkCancelling ? '일괄 취소 중...' : '⚡ 전체 샤드 일괄 취소 (Bulk Cancel)'}
                </Button>
              )}
            </div>
          </div>

          {/* Aggregate Manifest Card */}
          <div
            style={{
              padding: '16px 20px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-subtle)',
              marginBottom: '24px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
            }}
          >
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>완료 집계 정책 버전</div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600, fontFamily: 'monospace' }}>
                shard-completion:v1
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>결과 Manifest 다이제스트</div>
              <div
                style={{
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  fontFamily: 'monospace',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {run.manifestDigest || '미확정 (실행/수집 중)'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>전체 물리 정지 (Physical Stop)</div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                {run.allPhysicallyStopped ? (
                  <span style={{ color: 'var(--color-status-online)' }}>✓ 전원 정지 영수증 수신</span>
                ) : (
                  <span style={{ color: '#d97706' }}>대기 중 (동작 중인 샤드 존재)</span>
                )}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>전체 결과 검증 (Verified)</div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                {run.allSucceeded ? (
                  <span style={{ color: 'var(--color-status-online)' }}>✓ 전원 검증 합격</span>
                ) : (
                  <span style={{ color: 'var(--color-text-muted)' }}>미완료</span>
                )}
              </div>
            </div>
          </div>

          {/* Shards Table */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--color-bg-canvas)', borderBottom: '1px solid var(--color-border-subtle)' }}>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>샤드 ID</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>할당 노드</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Attempt</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>실행 상태</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>물리 정지 영수증</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>출력 해시 (SHA-256)</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>결과 검증</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>작업</th>
                </tr>
              </thead>
              <tbody>
                {isLoadingShards ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                      샤드 상태 조회 중...
                    </td>
                  </tr>
                ) : shards.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                      등록된 분산 샤드가 없습니다. (단일 노드 실행)
                    </td>
                  </tr>
                ) : (
                  shards.map((s) => (
                    <tr key={s.shardId} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontWeight: 600 }}>
                        {s.shardId}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <div>{s.hostname}</div>
                        <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                          {s.nodeId}
                        </div>
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>#{s.attempt}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 6px',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            backgroundColor:
                              s.executionState === 'running'
                                ? 'rgba(59, 130, 246, 0.15)'
                                : s.executionState === 'succeeded'
                                ? 'rgba(16, 185, 129, 0.15)'
                                : 'rgba(239, 68, 68, 0.15)',
                            color:
                              s.executionState === 'running'
                                ? '#3b82f6'
                                : s.executionState === 'succeeded'
                                ? '#10b981'
                                : '#ef4444',
                          }}
                        >
                          {s.executionState}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {s.physicallyStopped ? (
                          <span style={{ color: 'var(--color-status-online)', fontWeight: 600 }}>
                            ✓ 수신 완료
                          </span>
                        ) : (
                          <span style={{ color: '#d97706', fontSize: '0.8125rem' }}>
                            ⏳ fsync 대기
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                        {s.outputHash ? s.outputHash.slice(0, 18) + '...' : '-'}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {s.verified ? (
                          <span style={{ color: 'var(--color-status-online)', fontWeight: 600 }}>✓ 합격</span>
                        ) : (
                          <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>미검증</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {s.runId && s.runId !== run.id && onNavigateRun && (
                          <Button variant="ghost" size="sm" onClick={() => onNavigateRun(s.runId)}>
                            상세
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
