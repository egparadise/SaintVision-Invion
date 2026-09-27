import React, { useState, useEffect } from 'react';
import { NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { DistributedRecoveryManager, ResilientNodeState } from './recoveryEngine';

interface DistributedRecoveryViewProps {
  nodes: NodeItem[];
}

export const DistributedRecoveryView: React.FC<DistributedRecoveryViewProps> = ({ nodes }) => {
  const [recoveryManager] = useState<DistributedRecoveryManager>(() => {
    return new DistributedRecoveryManager(
      nodes.map((n, i) => ({
        nodeId: n.id,
        hostname: n.hostname,
        activeWorkspaces: i + 1,
        status: n.status,
        heartbeatAt: (n as any).heartbeatAt ?? null,
      }))
    );
  });

  const [resilientNodes, setResilientNodes] = useState<ResilientNodeState[]>(() => recoveryManager.getNodes());
  const [selectedNodeId, setSelectedNodeId] = useState<string>(() => nodes[0]?.id || '');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [checkouts, setCheckouts] = useState<
    Array<{
      checkoutId: string;
      nodeId: string;
      inode: string;
      permissions: string;
      checkpointSha: string;
      epoch: number;
      status: 'active' | 'reclaimed';
      createdAt: string;
    }>
  >([]);

  // Sync incoming nodes prop with recoveryManager
  useEffect(() => {
    recoveryManager.syncNodes(
      nodes.map((n, i) => ({
        nodeId: n.id,
        hostname: n.hostname,
        activeWorkspaces: i + 1,
        status: n.status,
        heartbeatAt: (n as any).heartbeatAt ?? null,
      }))
    );
    setResilientNodes(recoveryManager.getNodes());
  }, [nodes, recoveryManager]);

  const selectedNode = resilientNodes.find((n) => n.nodeId === selectedNodeId) || resilientNodes[0];

  const handleCreateCheckout = () => {
    if (!selectedNode) {
      setActionNotice({
        type: 'error',
        text: '❌ 체크아웃 생성 실패: 선택된 유효 대상 노드가 없습니다. (위조 노드 합성 방지)',
      });
      return;
    }
    const curToken = selectedNode.fencingToken;
    const chkId = `sim_chk_${checkouts.length + 1}`;
    const newChk = {
      checkoutId: chkId,
      nodeId: selectedNode.nodeId,
      inode: `sim_ino_${49152 + checkouts.length}`,
      permissions: '0600 (read/write)',
      checkpointSha: 'sim_sha256_mock_checkpoint',
      epoch: curToken.epoch,
      status: 'active' as const,
      createdAt: new Date().toISOString(),
    };
    setCheckouts((prev) => [newChk, ...prev]);
    setActionNotice({
      type: 'info',
      text: `ℹ️ [모의 시뮬레이션] ADR-043 Writable Generation 생성: ${newChk.checkoutId} (모의 inode: ${newChk.inode}, 권한: 0600, Epoch: ${newChk.epoch}) — 백엔드 파일시스템에는 기록되지 않습니다.`,
    });
  };

  const refreshState = () => {
    setResilientNodes(recoveryManager.getNodes());
  };

  // 1. Simulate Heartbeat Drop > 60s
  const handleSimulateHeartbeatDrop = () => {
    if (!selectedNode) return;
    recoveryManager.simulateHeartbeatDelay(selectedNode.nodeId, 75);
    refreshState();
    setActionNotice({
      type: 'info',
      text: `[모의 시뮬레이션] Heartbeat age for ${selectedNode.hostname} set to 75s (>60s). Health updated to STALE (모의 시뮬레이션; 물리 AC-07 UNMEASURED).`,
    });
  };

  // 2. Simulate Network Partition / Split-Brain
  const handleSimulatePartition = () => {
    if (!selectedNode) return;
    recoveryManager.simulateNetworkPartition(selectedNode.nodeId);
    refreshState();
    setActionNotice({
      type: 'error',
      text: `[모의 시뮬레이션] Network partition simulated for ${selectedNode.hostname}. Node isolated & FENCED; Epoch advanced to ${recoveryManager.getNode(selectedNode.nodeId)?.fencingToken.epoch}.`,
    });
  };

  // 3. Attempt Zombie Late Write with Stale Token
  const handleAttemptZombieWrite = () => {
    if (!selectedNode) return;
    const curToken = selectedNode.fencingToken;
    const staleToken = {
      epoch: Math.max(1, curToken.epoch - 1),
      sequence: Math.max(1, curToken.sequence - 5),
    };

    const res = recoveryManager.attemptWrite(selectedNode.nodeId, staleToken, 'update workspace_run set status="done"');
    refreshState();

    if (!res.success) {
      setActionNotice({
        type: 'error',
        text: `🛡️ [모의 시뮬레이션] AC-07 Zombie Write Blocked: ${res.error}. Stale writes allowed: ${recoveryManager.getStaleWritesAllowed()} (모의 검증).`,
      });
    } else {
      setActionNotice({
        type: 'success',
        text: `[모의 시뮬레이션] Write accepted.`,
      });
    }
  };

  // 4. Drain & Reconcile Node
  const handleDrainAndReconcile = () => {
    if (!selectedNode) return;
    const rec = recoveryManager.reconcileNode(selectedNode.nodeId);
    refreshState();
    setActionNotice({
      type: 'success',
      text: `✔ [모의 시뮬레이션] Node ${selectedNode.hostname} reconciled! Evacuated ${rec.evacuatedWorkspacesCount} tasks. Advanced to Epoch ${rec.newEpoch}. Status restored to ONLINE.`,
    });
  };

  const lateRejections = recoveryManager.getLateRejections();
  const reconciliations = recoveryManager.getReconciliations();
  const recoveryCount = reconciliations.length;
  const successfulCount = reconciliations.filter((r) => r.recoverySuccess).length;
  const calculatedRate = recoveryCount > 0 ? Math.round((successfulCount / recoveryCount) * 100) : null;

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Unexposed API Simulation Notice Banner */}
      <div
        role="status"
        data-testid="recovery-unexposed-notice"
        style={{
          padding: '12px 16px',
          backgroundColor: 'rgba(56, 139, 253, 0.1)',
          border: '1px solid rgba(56, 139, 253, 0.4)',
          borderRadius: '6px',
          color: '#58a6ff',
          fontSize: '13px',
          lineHeight: '1.5',
        }}
      >
        ℹ️ <strong>분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출)</strong>: 현재 SaintVision 백엔드에는 분산 펜싱 토큰 갱신 및 파일시스템 체크아웃 생성 엔드포인트(/v1/recovery/*)가 배선되어 있지 않습니다. 아래의 노드 격리, Fencing Epoch 전이 및 체크아웃 목록은 장애 복구 프로토콜(ADR-043)을 검증하기 위한 클라이언트 인메모리 시뮬레이션입니다.
      </div>

      {/* KPI Top Banner (AC-07 Invariants) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
        }}
      >
        <div
          style={{
            backgroundColor: 'var(--color-bg-surface, #161b22)',
            border: '1px solid #30363d',
            borderRadius: 'var(--radius-lg, 8px)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>AC-07 이탈 감지 시간</div>
          <div
            data-testid="kpi-detection-time"
            style={{ fontSize: '20px', fontWeight: 700, color: '#8b949e', marginTop: '4px' }}
          >
            UNMEASURED (물리 실측)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>Heartbeat 60s 초과 감지 시뮬레이션 (물리 5노드 랩 실측 미실시)</div>
        </div>

        <div
          style={{
            backgroundColor: 'var(--color-bg-surface, #161b22)',
            border: '1px solid #30363d',
            borderRadius: 'var(--radius-lg, 8px)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>오래된 토큰(Zombie) 쓰기 수</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            {recoveryManager.getStaleWritesAllowed()} 건 (모의 검증; 물리 AC-07 UNMEASURED)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>단조 Fencing Token (Epoch:Seq) 클라이언트 시뮬레이션 검증</div>
        </div>

        <div
          style={{
            backgroundColor: 'var(--color-bg-surface, #161b22)',
            border: '1px solid #30363d',
            borderRadius: 'var(--radius-lg, 8px)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>분산 복구 성공률 목표</div>
          <div
            data-testid="kpi-recovery-rate"
            style={{
              fontSize: '20px',
              fontWeight: 700,
              color: calculatedRate !== null ? '#58a6ff' : '#8b949e',
              marginTop: '4px',
            }}
          >
            {calculatedRate !== null ? `${calculatedRate}% (모의 ${successfulCount}/${recoveryCount}회; 물리 AC-07 UNMEASURED)` : 'UNMEASURED (미측정)'}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {recoveryCount > 0 ? '클라이언트 인메모리 Drain & Reconcile 시뮬레이션 결과' : '복구 이력 부재 (Drain & Reconcile 실행 필요)'}
          </div>
        </div>
      </div>

      {/* Action Notice Bar */}
      {actionNotice && (
        <div
          role={actionNotice.type === 'error' ? 'alert' : 'status'}
          aria-live={actionNotice.type === 'error' ? 'assertive' : 'polite'}
          data-testid="recovery-action-notice"
          style={{
            padding: '12px 18px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor:
              actionNotice.type === 'error'
                ? 'rgba(248, 81, 73, 0.15)'
                : actionNotice.type === 'success'
                ? 'rgba(46, 160, 67, 0.15)'
                : 'rgba(56, 139, 253, 0.15)',
            border: `1px solid ${
              actionNotice.type === 'error'
                ? '#f85149'
                : actionNotice.type === 'success'
                ? '#3fb950'
                : '#58a6ff'
            }`,
            color:
              actionNotice.type === 'error'
                ? '#f85149'
                : actionNotice.type === 'success'
                ? '#3fb950'
                : '#58a6ff',
          }}
        >
          {actionNotice.text}
        </div>
      )}

      {/* Empty State Screen when nodes list is empty */}
      {resilientNodes.length === 0 ? (
        <div
          data-testid="recovery-empty-nodes-screen"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            backgroundColor: 'var(--color-bg-surface, #161b22)',
            border: '1px solid #30363d',
            borderRadius: 'var(--radius-lg, 8px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div style={{ fontSize: '32px' }}>📡</div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#f0f6fc' }}>
            클러스터에 등록된 노드가 없거나 관측 대기 중입니다
          </div>
          <div style={{ fontSize: '13px', color: '#8b949e', maxWidth: '560px', lineHeight: '1.5' }}>
            현재 백엔드 제어 평면 또는 관측 파이프라인에서 전달된 가용 노드가 없습니다 (0대 또는 관측 수집 대기).
            노드가 등록되거나 관측이 수신된 후 분산 복구 및 펜싱 시뮬레이션을 실행할 수 있습니다.
          </div>
        </div>
      ) : (
        <>
          {/* Cluster Grid */}
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f0f6fc', marginBottom: '12px' }}>
              Cluster Resilience &amp; Fencing Simulation (AC-07 모의 검증)
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
              {resilientNodes.map((node) => {
                const isSelected = selectedNode && node.nodeId === selectedNode.nodeId;
                let statusColor = '#3fb950';
                if (node.healthState === 'stale') statusColor = '#e3b341';
                if (node.healthState === 'offline') statusColor = '#f85149';
                if (node.healthState === 'fenced') statusColor = '#a371f7';
                if (node.healthState === 'recovering') statusColor = '#58a6ff';

                return (
                  <div
                    key={node.nodeId}
                    role="button"
                    tabIndex={0}
                    data-testid={`node-card-${node.nodeId}`}
                    aria-pressed={isSelected}
                    aria-current={isSelected ? 'true' : 'false'}
                    aria-label={`${node.hostname} (실제: ${node.actualStatus || 'unknown'}, 시뮬레이션: ${node.healthState.toUpperCase()})`}
                    onClick={() => setSelectedNodeId(node.nodeId)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedNodeId(node.nodeId);
                      }
                    }}
                    style={{
                      backgroundColor: '#161b22',
                      border: isSelected ? '2px solid #58a6ff' : '1px solid #30363d',
                      borderRadius: 'var(--radius-lg, 8px)',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 600, color: '#f0f6fc', fontSize: '14px' }}>
                        {node.hostname}
                      </span>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <span
                          data-testid={`node-actual-status-${node.nodeId}`}
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            color: '#8b949e',
                            backgroundColor: '#21262d',
                            border: '1px solid #30363d',
                          }}
                          title="백엔드 제어 평면 실제 보고 상태"
                        >
                          실제: {node.actualStatus || 'unknown'}
                        </span>
                        <span
                          data-testid={`node-sim-status-${node.nodeId}`}
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: `${statusColor}22`,
                            color: statusColor,
                            border: `1px solid ${statusColor}`,
                          }}
                        >
                          시뮬레이션: {node.healthState.toUpperCase()}
                        </span>
                      </div>
                    </div>

                    <div style={{ fontSize: '12px', color: '#8b949e', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <div>Fencing Token: <code>Epoch {node.fencingToken.epoch} : Seq {node.fencingToken.sequence}</code></div>
                      <div>Heartbeat: {node.heartbeatAgeSeconds >= 0 ? `${node.heartbeatAgeSeconds}s ago` : '미보고'}</div>
                      <div>Active Workspaces: {node.activeWorkspacesCount}</div>
                      <div>Partitioned: {node.isPartitioned ? '🚨 YES (Split-Brain Isolated)' : 'NO'}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Targeted Failure Injection Panel */}
          <div
            style={{
              backgroundColor: '#161b22',
              border: '1px solid #30363d',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '20px',
            }}
          >
            <h4 style={{ margin: '0 0 16px 0', fontSize: '15px', color: '#f0f6fc' }}>
              Fault Injection &amp; Recovery Actions for Target:{' '}
              <span style={{ color: '#58a6ff' }}>{selectedNode ? selectedNode.hostname : '(선택된 노드 없음)'}</span>
            </h4>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
              <Button
                data-testid="simulate-heartbeat-delay-btn"
                variant="secondary"
                disabled={!selectedNode}
                onClick={handleSimulateHeartbeatDrop}
              >
                Simulate Heartbeat Delay (75s &gt; 60s Stale Threshold)
              </Button>

              <Button
                data-testid="simulate-partition-btn"
                variant="danger"
                disabled={!selectedNode}
                onClick={handleSimulatePartition}
              >
                Simulate Network Partition / Split-Brain
              </Button>

              <Button
                data-testid="attempt-zombie-write-btn"
                variant="secondary"
                disabled={!selectedNode}
                onClick={handleAttemptZombieWrite}
              >
                Attempt Stale Token Write (Zombie Task)
              </Button>

              <Button
                data-testid="drain-reconcile-btn"
                variant="primary"
                disabled={!selectedNode}
                onClick={handleDrainAndReconcile}
              >
                Drain &amp; Reconcile Node
              </Button>
            </div>
          </div>

          {/* Audit Logs & Rejections Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px' }}>
            {/* ADR-043 Writable Generation Panel */}
            <div
              style={{
                backgroundColor: '#161b22',
                border: '1px solid #30363d',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
                  ADR-043 Writable Generation &amp; Checkouts
                </h4>
                <Button
                  data-testid="create-checkout-btn"
                  variant="primary"
                  size="sm"
                  disabled={!selectedNode}
                  onClick={handleCreateCheckout}
                >
                  새 Generation 체크아웃 생성 (모의)
                </Button>
              </div>

              <div style={{ flex: 1, minHeight: '200px', maxHeight: '260px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {checkouts.length === 0 ? (
                  <div style={{ color: '#8b949e', fontSize: '13px', textAlign: 'center', margin: 'auto' }}>
                    생성된 시뮬레이션 체크아웃이 없습니다.
                  </div>
                ) : (
                  checkouts.map((chk) => (
                    <div
                      key={chk.checkoutId}
                      style={{
                        backgroundColor: '#0d1117',
                        border: '1px solid #30363d',
                        borderRadius: '6px',
                        padding: '10px 14px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#58a6ff', fontWeight: 600 }}>
                        <span>{chk.checkoutId}</span>
                        <span style={{ color: '#3fb950' }}>{chk.status.toUpperCase()}</span>
                      </div>
                      <div style={{ color: '#8b949e', marginTop: '4px' }}>
                        Inode: <code>{chk.inode}</code> | Permissions: <code>{chk.permissions}</code> | Epoch: <code>{chk.epoch}</code>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Late Result Rejection Audit Stream */}
            <div
              style={{
                backgroundColor: '#161b22',
                border: '1px solid #30363d',
                borderRadius: 'var(--radius-lg, 8px)',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
                  Late Result Rejection Stream (Monotonic Fencing)
                </h4>
                <span style={{ fontSize: '12px', color: '#8b949e' }}>
                  Total Rejections: {lateRejections.length}
                </span>
              </div>

              <div style={{ flex: 1, minHeight: '200px', maxHeight: '260px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {lateRejections.length === 0 ? (
                  <div style={{ color: '#8b949e', fontSize: '13px', textAlign: 'center', margin: 'auto' }}>
                    No late result rejections yet. Click "Attempt Stale Token Write" to test zombie blocking.
                  </div>
                ) : (
                  lateRejections.map((rej) => (
                    <div
                      key={rej.requestId}
                      style={{
                        backgroundColor: '#0d1117',
                        border: '1px solid #f85149',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#f85149', fontWeight: 600 }}>
                        <span>BLOCKED: {rej.requestId}</span>
                        <span>{new Date(rej.rejectedAt).toLocaleTimeString()}</span>
                      </div>
                      <div style={{ color: '#8b949e', marginTop: '4px' }}>
                        Attempted: <code>Epoch {rej.attemptedToken.epoch} : Seq {rej.attemptedToken.sequence}</code> vs
                        Current: <code>Epoch {rej.currentToken.epoch} : Seq {rej.currentToken.sequence}</code>
                      </div>
                      <div style={{ color: '#f85149', fontSize: '11px', marginTop: '2px' }}>{rej.reason}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Reconciliation Audit Trail */}
          <div
            style={{
              backgroundColor: '#161b22',
              border: '1px solid #30363d',
              borderRadius: 'var(--radius-lg, 8px)',
              padding: '20px',
            }}
          >
            <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', color: '#f0f6fc' }}>
              Cluster Reconciliation Audit Trail (AC-07 Recovery KPI)
            </h4>

            {reconciliations.length === 0 ? (
              <div style={{ color: '#8b949e', fontSize: '13px', textAlign: 'center', padding: '16px' }}>
                No node reconciliations triggered yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {reconciliations.map((rec) => (
                  <div
                    key={rec.reconciliationId}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: '#0d1117',
                      padding: '10px 14px',
                      borderRadius: '6px',
                      fontSize: '13px',
                      border: '1px solid #30363d',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 600, color: '#f0f6fc' }}>Node: {rec.nodeId}</span>
                      <span style={{ color: '#8b949e', marginLeft: '12px' }}>
                        Evacuated: <strong>{rec.evacuatedWorkspacesCount}</strong> workspaces
                      </span>
                      <span style={{ color: '#8b949e', marginLeft: '12px' }}>
                        New Fencing Epoch: <strong>{rec.newEpoch}</strong>
                      </span>
                    </div>
                    <span style={{ color: '#3fb950', fontWeight: 600, fontSize: '12px' }}>RECOVERY COMPLETE</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
