import React, { useState, useEffect } from 'react';
import { NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { DistributedRecoveryManager, ResilientNodeState } from './recoveryEngine';

interface DistributedRecoveryViewProps {
  nodes: NodeItem[];
}

interface NodeHealthConfig {
  label: string;
  color: string;
  bg: string;
  border: string;
}

export const NODE_HEALTH_CONFIG: Record<ResilientNodeState['healthState'], NodeHealthConfig> = {
  online: {
    label: 'ONLINE',
    color: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-online)',
  },
  stale: {
    label: 'STALE',
    color: 'var(--color-status-degraded)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-degraded)',
  },
  offline: {
    label: 'OFFLINE',
    color: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-offline)',
  },
  recovering: {
    label: 'RECOVERING',
    color: 'var(--color-status-active)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-active)',
  },
  fenced: {
    label: 'FENCED',
    color: 'var(--color-status-neutral)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-border-strong)',
  },
};

export const DistributedRecoveryView: React.FC<DistributedRecoveryViewProps> = ({ nodes }) => {
  const [recoveryManager] = useState<DistributedRecoveryManager>(() => {
    return new DistributedRecoveryManager(
      nodes.map((n, i) => ({
        nodeId: n.id,
        hostname: n.hostname,
        activeWorkspaces: i + 1,
        status: n.status,
        heartbeatAt: n.heartbeatAt ?? null,
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
        heartbeatAt: n.heartbeatAt ?? null,
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
          backgroundColor: 'var(--color-bg-subtle)',
          border: '1px solid var(--color-brand-hover)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-brand-hover)',
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
          data-testid="kpi-card-detection"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>AC-07 이탈 감지 시간</div>
          <div
            data-testid="kpi-detection-time"
            style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text-secondary)', marginTop: '4px' }}
          >
            UNMEASURED (물리 실측)
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>Heartbeat 60s 초과 감지 시뮬레이션 (물리 5노드 랩 실측 미실시)</div>
        </div>

        <div
          data-testid="kpi-card-zombie"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>오래된 토큰(Zombie) 쓰기 수</div>
          <div
            data-testid="kpi-zombie-writes"
            style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-status-online)', marginTop: '4px' }}
          >
            {recoveryManager.getStaleWritesAllowed()} 건 (모의 검증; 물리 AC-07 UNMEASURED)
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>단조 Fencing Token (Epoch:Seq) 클라이언트 시뮬레이션 검증</div>
        </div>

        <div
          data-testid="kpi-card-recovery"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>분산 복구 성공률 목표</div>
          <div
            data-testid="kpi-recovery-rate"
            style={{
              fontSize: '20px',
              fontWeight: 700,
              color: calculatedRate !== null ? 'var(--color-brand-hover)' : 'var(--color-text-secondary)',
              marginTop: '4px',
            }}
          >
            {calculatedRate !== null ? `${calculatedRate}% (모의 ${successfulCount}/${recoveryCount}회; 물리 AC-07 UNMEASURED)` : 'UNMEASURED (미측정)'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
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
            borderRadius: 'var(--radius-md)',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: 'var(--color-bg-subtle)',
            border: `1px solid ${
              actionNotice.type === 'error'
                ? 'var(--color-status-offline)'
                : actionNotice.type === 'success'
                ? 'var(--color-status-online)'
                : 'var(--color-brand-hover)'
            }`,
            color:
              actionNotice.type === 'error'
                ? 'var(--color-status-offline)'
                : actionNotice.type === 'success'
                ? 'var(--color-status-online)'
                : 'var(--color-brand-hover)',
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
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-lg)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div style={{ fontSize: '32px' }}>📡</div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            클러스터에 등록된 노드가 없거나 관측 대기 중입니다
          </div>
          <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', maxWidth: '560px', lineHeight: '1.5' }}>
            현재 백엔드 제어 평면 또는 관측 파이프라인에서 전달된 가용 노드가 없습니다 (0대 또는 관측 수집 대기).
            노드가 등록되거나 관측이 수신된 후 분산 복구 및 펜싱 시뮬레이션을 실행할 수 있습니다.
          </div>
        </div>
      ) : (
        <>
          {/* Cluster Grid */}
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '12px' }}>
              Cluster Resilience &amp; Fencing Simulation (AC-07 모의 검증)
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
              {resilientNodes.map((node) => {
                const isSelected = selectedNode && node.nodeId === selectedNode.nodeId;
                const healthCfg = NODE_HEALTH_CONFIG[node.healthState] || {
                  label: (node.healthState || 'UNKNOWN').toUpperCase(),
                  color: 'var(--color-status-neutral)',
                  bg: 'var(--color-bg-subtle)',
                  border: 'var(--color-border-subtle)',
                };

                return (
                  <div
                    key={node.nodeId}
                    role="button"
                    tabIndex={0}
                    data-testid={`node-card-${node.nodeId}`}
                    aria-pressed={isSelected}
                    aria-label={`${node.hostname} (실제: ${node.actualStatus || 'unknown'}, 시뮬레이션: ${node.healthState.toUpperCase()})`}
                    onClick={() => setSelectedNodeId(node.nodeId)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedNodeId(node.nodeId);
                      }
                    }}
                    style={{
                      backgroundColor: 'var(--color-bg-surface)',
                      border: isSelected ? '2px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',
                      borderRadius: 'var(--radius-lg)',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 600, color: 'var(--color-text-primary)', fontSize: '14px' }}>
                        {node.hostname}
                      </span>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <span
                          data-testid={`node-actual-status-${node.nodeId}`}
                          style={{
                            padding: '2px 6px',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '10px',
                            color: 'var(--color-text-secondary)',
                            backgroundColor: 'var(--color-bg-subtle)',
                            border: '1px solid var(--color-border-subtle)',
                          }}
                          title="백엔드 제어 평면 실제 보고 상태"
                        >
                          실제: {node.actualStatus || 'unknown'}
                        </span>
                        <span
                          data-testid={`node-sim-status-${node.nodeId}`}
                          style={{
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: healthCfg.bg,
                            color: healthCfg.color,
                            border: `1px solid ${healthCfg.border}`,
                          }}
                        >
                          시뮬레이션: {healthCfg.label}
                        </span>
                      </div>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
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
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-lg)',
              padding: '20px',
            }}
          >
            <h4 style={{ margin: '0 0 16px 0', fontSize: '15px', color: 'var(--color-text-primary)' }}>
              Fault Injection &amp; Recovery Actions for Target:{' '}
              <span style={{ color: 'var(--color-brand-hover)' }}>{selectedNode ? selectedNode.hostname : '(선택된 노드 없음)'}</span>
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
                backgroundColor: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-lg)',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: '15px', color: 'var(--color-text-primary)' }}>
                    ADR-043 Writable Generation &amp; Checkouts (모의)
                  </h4>
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                    격리된 복원 사본(0400 readonly)과 분리된 독립 private root의 수정 가능 세대(0600 file / 0700 dir, 단조 epoch 보증)
                  </p>
                </div>
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
                  <div
                    data-testid="recovery-no-checkouts"
                    style={{ color: 'var(--color-text-secondary)', fontSize: '13px', textAlign: 'center', margin: 'auto' }}
                  >
                    생성된 시뮬레이션 체크아웃이 없습니다. (모의)
                  </div>
                ) : (
                  checkouts.map((chk) => (
                    <div
                      key={chk.checkoutId}
                      style={{
                        backgroundColor: 'var(--color-bg-subtle)',
                        border: '1px solid var(--color-border-subtle)',
                        borderRadius: 'var(--radius-md)',
                        padding: '10px 14px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--color-brand-hover)', fontWeight: 600 }}>
                        <span>{chk.checkoutId}</span>
                        <span style={{ color: chk.status === 'active' ? 'var(--color-status-online)' : 'var(--color-status-neutral)' }}>
                          {chk.status.toUpperCase()} (모의)
                        </span>
                      </div>
                      <div style={{ color: 'var(--color-text-secondary)', marginTop: '4px' }}>
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
                backgroundColor: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-lg)',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, fontSize: '15px', color: 'var(--color-text-primary)' }}>
                  Late Result Rejection Stream (Monotonic Fencing)
                </h4>
                <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                  Total Rejections: {lateRejections.length}
                </span>
              </div>

              <div style={{ flex: 1, minHeight: '200px', maxHeight: '260px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {lateRejections.length === 0 ? (
                  <div style={{ color: 'var(--color-text-secondary)', fontSize: '13px', textAlign: 'center', margin: 'auto' }}>
                    No late result rejections yet. Click "Attempt Stale Token Write" to test zombie blocking.
                  </div>
                ) : (
                  lateRejections.map((rej) => (
                    <div
                      key={rej.requestId}
                      data-testid={`rejection-item-${rej.requestId}`}
                      style={{
                        backgroundColor: 'var(--color-bg-subtle)',
                        border: '1px solid var(--color-status-offline)',
                        borderRadius: 'var(--radius-md)',
                        padding: '8px 12px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--color-status-offline)', fontWeight: 600 }}>
                        <span>BLOCKED: {rej.requestId}</span>
                        <span>{new Date(rej.rejectedAt).toLocaleTimeString()}</span>
                      </div>
                      <div style={{ color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                        Attempted: <code>Epoch {rej.attemptedToken.epoch} : Seq {rej.attemptedToken.sequence}</code> vs
                        Current: <code>Epoch {rej.currentToken.epoch} : Seq {rej.currentToken.sequence}</code>
                      </div>
                      <div style={{ color: 'var(--color-status-offline)', fontSize: '11px', marginTop: '2px' }}>{rej.reason}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Reconciliation Audit Trail */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-lg)',
              padding: '20px',
            }}
          >
            <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', color: 'var(--color-text-primary)' }}>
              Cluster Reconciliation Audit Trail (AC-07 모의 복구 시뮬레이션; 물리 AC-07 UNMEASURED)
            </h4>

            {reconciliations.length === 0 ? (
              <div style={{ color: 'var(--color-text-secondary)', fontSize: '13px', textAlign: 'center', padding: '16px' }}>
                No node reconciliations triggered yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {reconciliations.map((rec) => (
                  <div
                    key={rec.reconciliationId}
                    data-testid={`reconciliation-item-${rec.reconciliationId}`}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: 'var(--color-bg-subtle)',
                      padding: '10px 14px',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '13px',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>Node: {rec.nodeId}</span>
                      <span style={{ color: 'var(--color-text-secondary)', marginLeft: '12px' }}>
                        Evacuated: <strong>{rec.evacuatedWorkspacesCount}</strong> workspaces
                      </span>
                      <span style={{ color: 'var(--color-text-secondary)', marginLeft: '12px' }}>
                        New Fencing Epoch: <strong>{rec.newEpoch}</strong>
                      </span>
                    </div>
                    <span
                      style={{
                        color: rec.recoverySuccess ? 'var(--color-status-online)' : 'var(--color-status-offline)',
                        fontWeight: 600,
                        fontSize: '12px',
                      }}
                    >
                      {rec.recoverySuccess ? 'RECOVERED (모의)' : 'FAILED'}
                    </span>
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
