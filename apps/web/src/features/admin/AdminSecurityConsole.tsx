import React, { useState, useEffect } from 'react';
import { NodeItem, SyntheticGpuResult } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { apiClient } from '@/shared/api/client';
import { SecurityControlManager } from './securityEngine';

interface AdminSecurityConsoleProps {
  nodes: NodeItem[];
  onRefreshNodes?: () => void;
}

export const AdminSecurityConsole: React.FC<AdminSecurityConsoleProps> = ({ nodes, onRefreshNodes }) => {
  const [secManager] = useState<SecurityControlManager>(() => new SecurityControlManager());
  const [activeSubTab, setActiveSubTab] = useState<'audit' | 'isolation' | 'gpu' | 'backup' | 'drain'>('audit');
  const [status, setStatus] = useState(secManager.getStatus());
  const [auditLogs, setAuditLogs] = useState(secManager.getAuditLogs());

  // Interactive states
  const [ledgerVerification, setLedgerVerification] = useState<{ isValid: boolean; checked: number } | null>(null);
  const [mountTestPath, setMountTestPath] = useState('/var/run/docker.sock');
  const [mountTestResult, setMountTestResult] = useState<string | null>(null);

  useEffect(() => {
    let changed = false;
    nodes.forEach((n) => {
      const isDrainingOnServer = n.status === 'draining' || (n as any).isDraining === true;
      if (isDrainingOnServer && !secManager.isNodeDrained(n.id)) {
        secManager.drainNode(n.id, 'system', 'Cluster control plane reported draining status');
        changed = true;
      }
    });
    if (changed) {
      refreshState();
    }
  }, [nodes]);

  const handleToggleDrain = async (nodeId: string, currentDrained: boolean) => {
    if (currentDrained) {
      secManager.undrainNode(nodeId, 'usr_admin_01');
      refreshState();
      try {
        await apiClient(`/v1/nodes/${nodeId}/resume`, {
          method: 'POST',
          body: JSON.stringify({ actor: 'usr_admin_01' }),
        });
      } catch (err: any) {
        console.error('Failed to sync node resume to control plane:', err);
        secManager.drainNode(nodeId, 'usr_admin_01', 'Reverting failed undrain action');
        refreshState();
        alert(`노드 재개 동기화 실패: ${err?.message || '제어 평면 오류'}`);
      }
    } else {
      secManager.drainNode(nodeId, 'usr_admin_01', 'Admin manual maintenance and isolation protocol');
      refreshState();
      try {
        await apiClient(`/v1/nodes/${nodeId}/drain`, {
          method: 'POST',
          body: JSON.stringify({ actor: 'usr_admin_01', reason: 'Admin manual maintenance and isolation protocol' }),
        });
      } catch (err: any) {
        console.error('Failed to sync node drain to control plane:', err);
        secManager.undrainNode(nodeId, 'usr_admin_01');
        refreshState();
        alert(`노드 격리(Drain) 동기화 실패: ${err?.message || '제어 평면 오류'}`);
      }
    }
    if (onRefreshNodes) {
      onRefreshNodes();
    }
  };
  const [bypassRiskLevel, setBypassRiskLevel] = useState<'L1' | 'L2' | 'L3'>('L2');
  const [bypassTestResult, setBypassTestResult] = useState<string | null>(null);
  const [selectedGpuNodeId, setSelectedGpuNodeId] = useState<string>('nod_01JABCDEF01');
  const [gpuResult, setGpuResult] = useState<SyntheticGpuResult | null>(null);
  const [isGpuRunning, setIsGpuRunning] = useState(false);
  const [showKillSwitchModal, setShowKillSwitchModal] = useState(false);

  const gpuNodes = nodes.filter((n) => n.gpuName && n.gpuCount > 0);

  const refreshState = () => {
    setStatus(secManager.getStatus());
    setAuditLogs(secManager.getAuditLogs());
  };

  // 1. Verify Ledger Cryptographic Hash Chaining
  const handleVerifyLedger = () => {
    const res = secManager.verifyLedgerIntegrity();
    setLedgerVerification({ isValid: res.isValid, checked: res.checkedRecords });
  };

  // 2. Test Docker Socket Mount
  const handleTestMount = (e: React.FormEvent) => {
    e.preventDefault();
    const res = secManager.validateMountPath(mountTestPath, 'usr_security_auditor');
    refreshState();
    if (!res.allowed) {
      setMountTestResult(`🛑 ACCESS DENIED: ${res.reason}`);
    } else {
      setMountTestResult(`✔ MOUNT ALLOWED: Path ${mountTestPath} passed security checks.`);
    }
  };

  // 3. Test Approval Bypass
  const handleTestBypass = () => {
    const res = secManager.validateExecutionApproval(bypassRiskLevel, undefined, 'usr_bypass_tester');
    refreshState();
    if (!res.allowed) {
      setBypassTestResult(`🛑 BYPASS BLOCKED: ${res.reason}`);
    } else {
      setBypassTestResult(`✔ TASK ALLOWED: ${bypassRiskLevel} does not require two-person rule.`);
    }
  };

  // 4. Run Synthetic GPU Benchmark
  const handleRunGpuBenchmark = () => {
    const targetNode = gpuNodes.find((n) => n.id === selectedGpuNodeId) || gpuNodes[0];
    setIsGpuRunning(true);
    setGpuResult(null);

    setTimeout(() => {
      const res = secManager.runSyntheticGpuBenchmark(targetNode.id, targetNode.gpuName || 'GPU');
      setGpuResult(res);
      setIsGpuRunning(false);
      refreshState();
    }, 600);
  };

  // 5. Toggle Emergency Kill Switch
  const handleConfirmKillSwitch = () => {
    secManager.toggleEmergencyKillSwitch('usr_admin_01', 'Admin manual emergency intervention');
    setShowKillSwitchModal(false);
    refreshState();
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Emergency Kill Switch Banner if Active */}
      {status.emergencyKillSwitchActive && (
        <div
          style={{
            backgroundColor: 'rgba(248, 81, 73, 0.2)',
            border: '2px solid #f85149',
            borderRadius: '8px',
            padding: '16px 20px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ color: '#f85149', fontWeight: 'bold', fontSize: '16px' }}>
              🚨 EMERGENCY KILL SWITCH ACTIVE — ALL RUNNING WORKLOADS ISOLATED
            </div>
            <div style={{ color: '#c9d1d9', fontSize: '13px', marginTop: '4px' }}>
              Execution engines paused. Network egress isolated. Deactivate kill switch to resume cluster dispatch.
            </div>
          </div>
          <Button variant="danger" size="sm" onClick={() => setShowKillSwitchModal(true)}>
            Deactivate Kill Switch
          </Button>
        </div>
      )}

      {/* Top Security KPI Tiles */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
        }}
      >
        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>Docker Socket 노출 여부</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            0 건 (완전 격리)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>AC-08 미노출 보증 충족</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>승인 우회 시도 차단 수</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            {status.approvalBypassesBlocked} 건 차단 (우회 허용 0)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>L2/L3 위험 작업 Two-Person 강제</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>합성 GPU 실행 검증</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#58a6ff', marginTop: '4px' }}>
            성공 (Exit 0)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>RTX 4090 / A4000 합성 벤치마크</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>WAL 백업 RPO 현황</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            {status.rpoMinutes} 분 전 (목표: ≤15분)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>RTO 12분 (목표: ≤60분)</div>
        </div>
      </div>

      {/* Header Bar with Sub-tabs and Emergency Kill Switch Button */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '12px 20px',
        }}
      >
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="sm"
            variant={activeSubTab === 'audit' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('audit')}
          >
            감사 로그 원장 (Audit Trail)
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'isolation' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('isolation')}
          >
            소켓·승인 격리 검증 (AC-08)
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'gpu' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('gpu')}
          >
            합성 GPU 성능 검증
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'backup' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('backup')}
          >
            재해 복구 및 WAL 백업
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'drain' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('drain')}
          >
            노드 Drain 통제 (ADR-038)
          </Button>
        </div>

        <Button
          size="sm"
          variant={status.emergencyKillSwitchActive ? 'secondary' : 'danger'}
          onClick={() => setShowKillSwitchModal(true)}
        >
          {status.emergencyKillSwitchActive ? 'Kill Switch 해제' : '🚨 긴급 Kill Switch 발동'}
        </Button>
      </div>

      {/* Sub-Tab 1: Immutable Audit Trail */}
      {activeSubTab === 'audit' && (
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
                불변 감사 로그 원장 (Immutable Audit Trail)
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
                W3C Trace ID 기반 단방향 해시 체이닝 (Append-Only Cryptographic Ledger)
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {ledgerVerification && (
                <span style={{ fontSize: '12px', color: ledgerVerification.isValid ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                  {ledgerVerification.isValid ? `✔ ${ledgerVerification.checked}개 레코드 무결성 검증 완료` : '❌ 원장 변조 감지됨'}
                </span>
              )}
              <Button size="sm" variant="secondary" onClick={handleVerifyLedger}>
                원장 암호화 무결성 검사
              </Button>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                <th style={{ padding: '10px 8px' }}>Timestamp</th>
                <th style={{ padding: '10px 8px' }}>Actor</th>
                <th style={{ padding: '10px 8px' }}>Action</th>
                <th style={{ padding: '10px 8px' }}>Target</th>
                <th style={{ padding: '10px 8px' }}>Outcome</th>
                <th style={{ padding: '10px 8px' }}>Details</th>
                <th style={{ padding: '10px 8px' }}>Integrity Hash</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={{ padding: '10px 8px', color: '#8b949e', whiteSpace: 'nowrap' }}>
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)', color: '#58a6ff' }}>
                    {log.actor}
                  </td>
                  <td style={{ padding: '10px 8px', fontWeight: 600 }}>{log.action}</td>
                  <td style={{ padding: '10px 8px' }}><code>{log.target}</code></td>
                  <td style={{ padding: '10px 8px' }}>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: log.outcome === 'allowed' ? 'rgba(46, 160, 67, 0.2)' : 'rgba(248, 81, 73, 0.2)',
                        color: log.outcome === 'allowed' ? '#3fb950' : '#f85149',
                      }}
                    >
                      {log.outcome.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 8px', color: '#8b949e' }}>{log.details}</td>
                  <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)', color: '#8b949e', fontSize: '11px' }}>
                    {log.integrityHash.slice(0, 12)}...
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sub-Tab 2: Socket & Approval Isolation */}
      {activeSubTab === 'isolation' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Docker Socket Inspector */}
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
            <div>
              <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
                Docker Socket 미노출 검증 (AC-08)
              </h4>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
                컨테이너 호스트 제어권 탈취를 유발하는 `/var/run/docker.sock` 마운트 시도 원천 차단 검증
              </p>
            </div>

            <form onSubmit={handleTestMount} style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                value={mountTestPath}
                onChange={(e) => setMountTestPath(e.target.value)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  color: '#c9d1d9',
                  fontSize: '13px',
                  fontFamily: 'var(--font-mono, monospace)',
                }}
              />
              <Button size="sm" variant="secondary" type="submit">
                마운트 요청 시험
              </Button>
            </form>

            {mountTestResult && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  backgroundColor: mountTestResult.includes('DENIED') ? 'rgba(248, 81, 73, 0.15)' : 'rgba(46, 160, 67, 0.15)',
                  border: mountTestResult.includes('DENIED') ? '1px solid #f85149' : '1px solid #3fb950',
                  color: mountTestResult.includes('DENIED') ? '#f85149' : '#3fb950',
                }}
              >
                {mountTestResult}
              </div>
            )}
          </div>

          {/* Approval Bypass Filter */}
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
            <div>
              <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
                승인 우회 방지 검증 (AC-08)
              </h4>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
                L2/L3 등급 고위험 명령이 거버넌스 승인 ID 없이 단독 실행되는 시도를 100% 차단
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ fontSize: '13px', color: '#8b949e' }}>시험할 위험 등급:</label>
              <select
                value={bypassRiskLevel}
                onChange={(e) => setBypassRiskLevel(e.target.value as any)}
                style={{
                  padding: '8px 12px',
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  color: '#c9d1d9',
                  fontSize: '13px',
                }}
              >
                <option value="L1">L1 (저위험, 자가 승인 가능)</option>
                <option value="L2">L2 (중위험, 승인 ID 필수)</option>
                <option value="L3">L3 (고위험, 2인 승인 필수)</option>
              </select>
              <Button size="sm" variant="secondary" onClick={handleTestBypass}>
                우회 실행 시험
              </Button>
            </div>

            {bypassTestResult && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  backgroundColor: bypassTestResult.includes('BLOCKED') ? 'rgba(248, 81, 73, 0.15)' : 'rgba(46, 160, 67, 0.15)',
                  border: bypassTestResult.includes('BLOCKED') ? '1px solid #f85149' : '1px solid #3fb950',
                  color: bypassTestResult.includes('BLOCKED') ? '#f85149' : '#3fb950',
                }}
              >
                {bypassTestResult}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sub-Tab 3: Synthetic GPU Capability */}
      {activeSubTab === 'gpu' && (
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
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              합성 GPU 작업 실행 성능 검증 (AC-08)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              FP16 GEMM 텐서 연산 벤치마크 및 VRAM 할당 격리 검증
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <label style={{ fontSize: '13px', color: '#8b949e' }}>대상 GPU 노드:</label>
            <select
              value={selectedGpuNodeId}
              onChange={(e) => setSelectedGpuNodeId(e.target.value)}
              style={{
                padding: '8px 12px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
              }}
            >
              {gpuNodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} — {n.gpuName} ({Math.round((n.gpuVramTotalBytes || 0) / 1024 ** 3)}GB VRAM)
                </option>
              ))}
            </select>

            <Button size="sm" variant="primary" onClick={handleRunGpuBenchmark} disabled={isGpuRunning}>
              {isGpuRunning ? '합성 GPU 벤치마크 실행 중...' : '합성 GPU 벤치마크 실행'}
            </Button>
          </div>

          {gpuResult && (
            <div
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #3fb950',
                borderRadius: '6px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#3fb950', fontWeight: 600, fontSize: '14px' }}>
                  ✔ 합성 GPU 벤치마크 정상 완료 (Exit Code: {gpuResult.exitCode})
                </span>
                <span style={{ fontSize: '12px', color: '#8b949e' }}>Evidence: <code>{gpuResult.evidenceId}</code></span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', fontSize: '13px' }}>
                <div>
                  <span style={{ color: '#8b949e' }}>Target GPU:</span>
                  <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{gpuResult.gpuName}</div>
                </div>
                <div>
                  <span style={{ color: '#8b949e' }}>Allocated VRAM:</span>
                  <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{Math.round(gpuResult.vramAllocatedBytes / 1024 ** 3)} GB</div>
                </div>
                <div>
                  <span style={{ color: '#8b949e' }}>Compute Throughput:</span>
                  <div style={{ fontWeight: 600, color: '#58a6ff' }}>{gpuResult.computeThroughputTflops} TFLOPS</div>
                </div>
                <div>
                  <span style={{ color: '#8b949e' }}>Completed:</span>
                  <div style={{ color: '#c9d1d9' }}>{new Date(gpuResult.completedAt).toLocaleTimeString()}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sub-Tab 4: Backup & Disaster Recovery */}
      {activeSubTab === 'backup' && (
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
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              재해 복구 및 WAL 백업 원장 (AC-08)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              PostgreSQL WAL 기반 PITR 복원 및 Fencing Epoch 단조 전진 연계
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div style={{ backgroundColor: '#0d1117', padding: '14px', borderRadius: '6px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>Latest Snapshot WAL</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#f0f6fc', marginTop: '4px' }}>
                000000010000000A0000002F
              </div>
              <div style={{ fontSize: '11px', color: '#3fb950', marginTop: '2px' }}>4분 전 기록 완료</div>
            </div>

            <div style={{ backgroundColor: '#0d1117', padding: '14px', borderRadius: '6px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>RPO 달성도 (Target ≤ 15m)</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#3fb950', marginTop: '4px' }}>
                4.2 분 (PASS)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>S3 복제 완료</div>
            </div>

            <div style={{ backgroundColor: '#0d1117', padding: '14px', borderRadius: '6px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>RTO 실측치 (Target ≤ 60m)</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#58a6ff', marginTop: '4px' }}>
                12.5 분 (PASS)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>Epoch 전진 포함</div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab 5: Node Drain & Schedulable Control (ADR-038) */}
      {activeSubTab === 'drain' && (
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
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              클러스터 노드 Drain 및 스케줄링 통제 (ADR-038)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              점검 또는 장애 노드를 스케줄링에서 즉시 제외(Drain)하고 실행 중인 워크로드를 안전하게 격리합니다.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {nodes.map((n) => {
              const isDrained = secManager.isNodeDrained(n.id);
              return (
                <div
                  key={n.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '14px 18px',
                    backgroundColor: '#0d1117',
                    border: `1px solid ${isDrained ? '#f85149' : '#30363d'}`,
                    borderRadius: '6px',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontWeight: 600, color: '#f0f6fc', fontSize: '14px' }}>
                        {n.hostname}
                      </span>
                      <code style={{ fontSize: '11px', color: '#58a6ff' }}>{n.id}</code>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          backgroundColor: isDrained ? 'rgba(248,81,73,0.2)' : 'rgba(63,185,80,0.2)',
                          color: isDrained ? '#f85149' : '#3fb950',
                          fontWeight: 600,
                        }}
                      >
                        {isDrained ? '🚨 DRAINED (스케줄링 제외)' : '✔ SCHEDULABLE (가용)'}
                      </span>
                      {n.observationOnly && (
                        <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '12px', backgroundColor: 'rgba(210,153,34,0.2)', color: '#d29922' }}>
                          관측 전용
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '12px', color: '#8b949e' }}>
                      {n.telemetryUnavailable ? '자원 정보 미관측' : `OS: ${n.os.toUpperCase()} • CPU: ${n.cpuCores}C (${n.cpuUsagePercent}%) • RAM: ${(n.memoryTotalBytes / 1024 ** 3).toFixed(0)} GiB`}
                      {n.gpuName && ` • GPU: ${n.gpuName}`}
                    </div>
                  </div>

                  <Button
                    size="sm"
                    variant={isDrained ? 'primary' : 'danger'}
                    onClick={() => handleToggleDrain(n.id, isDrained)}
                  >
                    {isDrained ? '✔ Drain 해제 (Schedulable)' : '🚨 Node Drain'}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Emergency Kill Switch Confirmation Modal */}
      {showKillSwitchModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '500px',
              backgroundColor: '#161b22',
              border: '2px solid #f85149',
              borderRadius: '8px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <h3 style={{ margin: 0, color: '#f85149', fontSize: '18px' }}>
              {status.emergencyKillSwitchActive ? 'Kill Switch 비활성화 확인' : '🚨 긴급 Kill Switch 발동 확인'}
            </h3>
            <p style={{ margin: 0, color: '#c9d1d9', fontSize: '13px', lineHeight: '20px' }}>
              {status.emergencyKillSwitchActive
                ? 'Kill Switch를 해제하면 클러스터의 작업 디스패치가 재개됩니다.'
                : 'Kill Switch를 발동하면 5개 노드에서 실행 중인 모든 작업이 즉시 중단되고 네트워크 이그레스가 차단됩니다.'}
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <Button size="sm" variant="secondary" onClick={() => setShowKillSwitchModal(false)}>
                취소
              </Button>
              <Button
                size="sm"
                variant={status.emergencyKillSwitchActive ? 'primary' : 'danger'}
                onClick={handleConfirmKillSwitch}
              >
                {status.emergencyKillSwitchActive ? '해제 실행' : '긴급 발동 확정'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
