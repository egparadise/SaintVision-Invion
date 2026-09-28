import React, { useState, useEffect } from 'react';
import { Button } from '@/shared/ui/Button';
import { NodeItem } from '@/contracts/types';
import { DeploymentManager } from './deploymentEngine';

export interface IntranetDeploymentViewProps {
  clusterNodes?: NodeItem[];
  currentUser?: { id: string; name: string; role: string } | null;
}

export const IntranetDeploymentView: React.FC<IntranetDeploymentViewProps> = ({ clusterNodes, currentUser }) => {
  const [manager] = useState<DeploymentManager>(() => new DeploymentManager());
  const [tls] = useState(manager.getTlsDetails());
  const [nginxRules] = useState(manager.getNginxRules());
  const [nginxConfig] = useState(manager.generateNginxConfig());
  const nodes = clusterNodes ? manager.reconcileLiveClusterNodes(clusterNodes) : manager.getNodeVerifications();
  const [manifest, setManifest] = useState(manager.getReleaseManifest());
  const [trainingSteps, setTrainingSteps] = useState(manager.getTrainingSteps());
  const [operatorId, setOperatorId] = useState<string>(currentUser ? currentUser.id : '');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (currentUser?.id) {
      setOperatorId(currentUser.id);
    } else {
      setOperatorId('');
    }
  }, [currentUser]);

  const passedNodesCount = clusterNodes
    ? nodes.filter((n) => n.smokeStatus === 'passed' && n.liveStatus === 'online').length
    : 0;
  const clusterComplianceLabel = clusterNodes && clusterNodes.length > 0
    ? `${passedNodesCount}/${clusterNodes.length} Nodes PASSED (${Math.round((passedNodesCount / clusterNodes.length) * 100)}%)`
    : '미측정 (라이브 클러스터 미연결)';

  const handleSignOff = () => {
    if (!currentUser) {
      setActionNotice({ type: 'error', text: '서명 실패: 로그인된 운영자 세션이 없습니다. 로그인이 필요합니다.' });
      return;
    }
    if (currentUser.role !== 'admin' && currentUser.role !== 'operator') {
      setActionNotice({
        type: 'error',
        text: `서명 실패: 현재 사용자 권한('${currentUser.role}')은 운영 인수 서명 권한이 없습니다. (operator/admin 필요)`,
      });
      return;
    }
    const res = manager.signOffRelease(currentUser.id, { roles: [currentUser.role] });
    if (!res.success) {
      setActionNotice({ type: 'error', text: `서명 실패: ${res.error}` });
    } else {
      setManifest(res.manifest);
      setActionNotice({
        type: 'success',
        text: `✔ [모의 시뮬레이션] 파일럿 후보 릴리스 [${res.manifest.version}]에 대한 운영자 [${currentUser.id}]의 인수가 로컬 시뮬레이션 서명되었습니다. (백엔드 배포 API 미연결 · 실 환경 미배포)`,
      });
    }
  };

  const handleCompleteStep = (stepNumber: number) => {
    const res = manager.completeTrainingStep(stepNumber);
    if (res.success) {
      setTrainingSteps(res.steps);
      setActionNotice({
        type: 'success',
        text: `✔ [자율 실습 확인] 운영 교육 모듈 Step ${stepNumber} 실습이 확인되었습니다.`,
      });
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* DEF-S12-01: Accessible Skip Navigation Link */}
      <a
        href="#deployment-main-content"
        style={{
          position: 'absolute',
          left: '-9999px',
          top: 'auto',
          width: '1px',
          height: '1px',
          overflow: 'hidden',
          zIndex: 100,
        }}
        onFocus={(e) => {
          e.currentTarget.style.position = 'static';
          e.currentTarget.style.width = 'auto';
          e.currentTarget.style.height = 'auto';
        }}
        onBlur={(e) => {
          e.currentTarget.style.position = 'absolute';
          e.currentTarget.style.left = '-9999px';
          e.currentTarget.style.width = '1px';
          e.currentTarget.style.height = '1px';
        }}
      >
        본문으로 바로가기
      </a>

      {/* DEF-S12-02: Heading Level 1 */}
      <h1 id="deployment-main-content" style={{ fontSize: '20px', fontWeight: 700, color: '#f0f6fc', margin: '0 0 4px 0' }}>
        내부망 HTTPS 배포 및 운영 인수 검증 (AC-12)
      </h1>

      {/* Unexposed Deployment Notice Banner */}
      <div
        role="status"
        aria-live="polite"
        data-testid="deployment-unexposed-notice"
        style={{
          padding: '8px 16px',
          backgroundColor: 'rgba(56, 139, 253, 0.12)',
          borderBottom: '1px solid #30363d',
          borderRadius: '6px',
          color: '#58a6ff',
          fontSize: '12px',
        }}
      >
        ℹ️ <strong>내부망 HTTPS 배포 및 운영 인수 시뮬레이터 (백엔드 배포 API 미노출)</strong>: 실제 온프레미스 컨테이너 프로비저닝 및 Nginx TLS 실서버 바인딩은 CI/CD 인프라 파이프라인에서 수행되며, 본 화면은 AC-12 운영 인수 절차 검증을 위한 클라이언트 인메모리 시뮬레이션입니다.
      </div>

      {/* Auth Session Required Alert Banner */}
      {!currentUser && (
        <div
          role="alert"
          aria-live="assertive"
          data-testid="deployment-auth-required-notice"
          style={{
            padding: '8px 16px',
            backgroundColor: 'rgba(248, 81, 73, 0.15)',
            border: '1px solid #f85149',
            borderRadius: '6px',
            color: '#f85149',
            fontSize: '12px',
            fontWeight: 500,
          }}
        >
          🛑 <strong>인증 필요</strong>: 로그인된 운영자 세션이 없습니다. 프로덕션 운영 인수 서명을 수행하려면 유효한 운영자 계정으로 로그인해야 합니다.
        </div>
      )}

      {/* AC-12 Top Metrics Banner */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
        }}
      >
        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>내부망 HTTPS 암호화 (AC-12)</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            TLS 1.2 / TLSv1.3 협상 (개발용 자체서명 CA)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>HSTS 365일 (개발용 자체서명 CA)</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>5대 노드 여정 검증 [AC-12 기준 규격]</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: clusterNodes && clusterNodes.length > 0 ? '#3fb950' : '#8b949e', marginTop: '4px' }}>
            {clusterNodes && clusterNodes.length > 0
              ? `${Math.round((passedNodesCount / clusterNodes.length) * 100)}% (${passedNodesCount}/${clusterNodes.length} PASSED)`
              : '미측정 (라이브 클러스터 미연결)'}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>Windows 3대 + Linux 2대 통합 여정 규격</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>파일럿 후보 릴리스 (Pilot RC)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#58a6ff', marginTop: '4px' }}>
            {manifest.version}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>Manifest ID: <code>{manifest.releaseId}</code></div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>운영자 최종 인수 서명 (Sign-Off)</div>
          <div
            style={{
              fontSize: '24px',
              fontWeight: 700,
              color: manifest.operatorSignOff ? '#3fb950' : '#d29922',
              marginTop: '4px',
            }}
          >
            {manifest.operatorSignOff ? '모의 서명 완료 ✔' : 'SIGN-OFF 대기'}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {manifest.operatorSignOff ? `서명자: ${currentUser?.id || 'usr_operator_lead'}` : '운영자 확인 대기 중'}
          </div>
        </div>
      </div>

      {/* Dynamic Action Notice */}
      {actionNotice && (
        <div
          role={actionNotice.type === 'error' ? 'alert' : 'status'}
          aria-live={actionNotice.type === 'error' ? 'assertive' : 'polite'}
          data-testid="deployment-action-notice"
          style={{
            padding: '12px 16px',
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

      {/* Preflight vs Physical Hardware Acceptance Banner */}
      <div
        style={{
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
                backgroundColor: 'rgba(46, 160, 67, 0.2)',
                color: '#3fb950',
              }}
            >
              PREFLIGHT PASS ✔
            </span>
            <strong style={{ fontSize: '14px', color: '#f0f6fc' }}>
              내부망 배포 사전 검증 파이프라인 [설계 규격 예시 (202개 검증 항목)]
            </strong>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
            [사전 설계 규격 항목] Nginx TLS 1.2/1.3 협상, SSE 버퍼링 차단, PTY 30초 일회용 티켓, ADR-038 노드 Drain (게이트웨이 실시간 프로브 미연결)
          </p>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: '11px', color: '#8b949e' }}>온프레미스 물리 5대 실장비 기동</div>
          <div
            style={{
              fontSize: '13px',
              color: manifest.operatorSignOff ? '#3fb950' : '#d29922',
              fontWeight: 600,
              marginTop: '2px',
            }}
          >
            {manifest.operatorSignOff
              ? '모의 인수 절차 확인됨 (온프레미스 실장비 기동 별도 필요)'
              : '현장 운영자 인수 대기 (Pending Acceptance)'}
          </div>
        </div>
      </div>

      {/* Section 1: TLS Certificate & Nginx Reverse Proxy Details */}
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
            내부망 전용 TLS 인증서 정보 (AC-12) [정적 구성 예시 (실시간 인증서 조회 아님)]
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
            격리 폐쇄망 내부 도메인 보안 및 HSTS 강제 암호화
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            backgroundColor: '#0d1117',
            padding: '16px',
            borderRadius: '6px',
            border: '1px solid #30363d',
            fontSize: '12px',
          }}
        >
          <div>
            <div style={{ color: '#8b949e' }}>도메인 (Domain)</div>
            <div style={{ color: '#f0f6fc', fontWeight: 600, marginTop: '2px' }}>{tls.domain}</div>
          </div>
          <div>
            <div style={{ color: '#8b949e' }}>발급 기관 (Issuer)</div>
            <div style={{ color: '#f0f6fc', fontWeight: 600, marginTop: '2px' }}>{tls.issuer}</div>
          </div>
          <div>
            <div style={{ color: '#8b949e' }}>프로토콜 및 암호군</div>
            <div style={{ color: '#3fb950', fontWeight: 600, marginTop: '2px' }}>
              {tls.tlsVersion} · {tls.cipherSuite}
            </div>
          </div>
          <div>
            <div style={{ color: '#8b949e' }}>HSTS 보안 헤더</div>
            <div style={{ color: '#3fb950', fontWeight: 600, marginTop: '2px' }}>
              {tls.hstsEnabled ? '활성화 (31,536,000초 / includeSubDomains)' : '비활성'}
            </div>
          </div>
        </div>

        <div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '6px' }}>
            주체 대체 이름 (SAN 목록):
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {tls.sanList.map((san) => (
              <span
                key={san}
                style={{
                  fontSize: '11px',
                  fontFamily: 'monospace',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  backgroundColor: '#21262d',
                  color: '#58a6ff',
                  border: '1px solid #30363d',
                }}
              >
                {san}
              </span>
            ))}
          </div>
        </div>

        {/* Nginx Routing Table */}
        <div>
          <h4 style={{ margin: '12px 0 8px 0', fontSize: '13px', color: '#f0f6fc' }}>
            Nginx 단일 오리진 라우팅 매트릭스
          </h4>
          <p style={{ margin: '0 0 10px 0', fontSize: '11px', color: '#8b949e' }}>
            동일 Origin (<code>:443 또는 :8443</code>) 기반 정적 SPA, REST API, SSE 스트리밍, PTY 웹소켓
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                <th style={{ padding: '8px' }}>Location</th>
                <th style={{ padding: '8px' }}>Target</th>
                <th style={{ padding: '8px' }}>Protocol</th>
                <th style={{ padding: '8px' }}>버퍼링/헤더</th>
              </tr>
            </thead>
            <tbody>
              {nginxRules.map((rule) => (
                <tr key={rule.location} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={{ padding: '8px', fontFamily: 'monospace', color: '#58a6ff' }}>{rule.location}</td>
                  <td style={{ padding: '8px', color: '#8b949e' }}>{rule.targetUpstream}</td>
                  <td style={{ padding: '8px' }}>
                    <span
                      style={{
                        padding: '1px 6px',
                        borderRadius: '3px',
                        fontSize: '11px',
                        backgroundColor:
                          rule.protocol === 'WebSocket'
                            ? 'rgba(163, 113, 247, 0.2)'
                            : rule.protocol === 'SSE'
                            ? 'rgba(56, 139, 253, 0.2)'
                            : 'rgba(46, 160, 67, 0.2)',
                        color:
                          rule.protocol === 'WebSocket'
                            ? '#a371f7'
                            : rule.protocol === 'SSE'
                            ? '#58a6ff'
                            : '#3fb950',
                      }}
                    >
                      {rule.protocol}
                    </span>
                  </td>
                  <td style={{ padding: '8px', color: '#8b949e' }}>
                    {rule.bufferingOff && 'Buffering OFF'}
                    {rule.upgradeHeader && ' / Upgrade: ws'}
                    {!rule.bufferingOff && !rule.upgradeHeader && 'Standard'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Nginx Config Code Block */}
        <details style={{ marginTop: '8px', fontSize: '12px' }}>
          <summary style={{ cursor: 'pointer', color: '#58a6ff' }}>
            ▶ 배포용 nginx.conf 구성 파일 전문 보기 (실제 apps/web/nginx.conf 정합)
          </summary>
          <pre
            style={{
              marginTop: '8px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              padding: '12px',
              overflowX: 'auto',
              fontSize: '11px',
              color: '#c9d1d9',
              lineHeight: 1.5,
            }}
          >
            {nginxConfig}
          </pre>
        </details>
      </div>

      {/* Section 2: 5-Node Journey & Smoke Verification Table (AC-12) */}
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
              5-Node 통합 여정 및 Smoke 검증 매트릭스 (AC-12)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              Windows/Linux 혼합 노드 여정, 역할 격리, mTLS 보안 통신 및 저지연 상태
            </p>
          </div>
          <span
            style={{
              padding: '3px 10px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              backgroundColor: clusterNodes && clusterNodes.length > 0 ? 'rgba(46, 160, 67, 0.2)' : 'rgba(139, 148, 158, 0.2)',
              color: clusterNodes && clusterNodes.length > 0 ? '#3fb950' : '#8b949e',
            }}
          >
            {clusterComplianceLabel}
          </span>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
              <th style={{ padding: '8px' }}>Node ID / Hostname</th>
              <th style={{ padding: '8px' }}>OS</th>
              <th style={{ padding: '8px' }}>실시간 클러스터 상태</th>
              <th style={{ padding: '8px' }}>검증된 역할 (Roles)</th>
              <th style={{ padding: '8px' }}>지연시간</th>
              <th style={{ padding: '8px' }}>Smoke 상태</th>
              <th style={{ padding: '8px' }}>최근 검증 시각</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((node) => (
              <tr key={node.nodeId} data-testid={`node-row-${node.nodeId}`} style={{ borderBottom: '1px solid #21262d' }}>
                <td style={{ padding: '10px 8px' }}>
                  <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{node.hostname}</div>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontFamily: 'monospace' }}>{node.nodeId}</div>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: node.os === 'windows' ? 'rgba(56, 139, 253, 0.2)' : 'rgba(219, 109, 40, 0.2)',
                      color: node.os === 'windows' ? '#58a6ff' : '#f0883e',
                    }}
                  >
                    {node.os.toUpperCase()}
                  </span>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  {node.liveStatus ? (
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        backgroundColor:
                          node.liveStatus === 'online'
                            ? 'rgba(46, 160, 67, 0.2)'
                            : node.liveStatus === 'draining'
                            ? 'rgba(210, 153, 34, 0.2)'
                            : 'rgba(248, 81, 73, 0.2)',
                        color:
                          node.liveStatus === 'online'
                            ? '#3fb950'
                            : node.liveStatus === 'draining'
                            ? '#d29922'
                            : '#f85149',
                      }}
                    >
                      {node.liveStatus.toUpperCase()}
                      {node.liveIsDraining && ' (Draining)'}
                      {node.liveObservationOnly && ' (Obs-Only)'}
                    </span>
                  ) : (
                    <span style={{ color: '#8b949e', fontSize: '12px' }}>미측정 (미연결)</span>
                  )}
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {node.roles.map((r) => (
                      <span
                        key={r}
                        style={{
                          fontSize: '11px',
                          padding: '1px 6px',
                          borderRadius: '3px',
                          backgroundColor: '#21262d',
                          color: '#c9d1d9',
                        }}
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                </td>
                <td style={{ padding: '10px 8px', color: node.smokeStatus === 'passed' && (!node.liveStatus || node.liveStatus === 'online') ? '#3fb950' : '#8b949e', fontWeight: 600 }}>
                  {node.smokeStatus === 'passed' && (!node.liveStatus || node.liveStatus === 'online') ? `${node.latencyMs} ms` : '미측정'}
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <span
                    aria-label={`Smoke status: ${node.smokeStatus}`}
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor:
                        node.smokeStatus === 'passed' && (!node.liveStatus || node.liveStatus === 'online')
                          ? 'rgba(46, 160, 67, 0.2)'
                          : node.liveStatus === 'offline' || node.smokeStatus === 'failed'
                          ? 'rgba(248, 81, 73, 0.2)'
                          : 'rgba(139, 148, 158, 0.2)',
                      color:
                        node.smokeStatus === 'passed' && (!node.liveStatus || node.liveStatus === 'online')
                          ? '#3fb950'
                          : node.liveStatus === 'offline' || node.smokeStatus === 'failed'
                          ? '#f85149'
                          : '#8b949e',
                    }}
                  >
                    {node.smokeStatus === 'passed' && (!node.liveStatus || node.liveStatus === 'online')
                      ? 'PASSED ✔'
                      : node.liveStatus === 'offline' || node.smokeStatus === 'failed'
                      ? 'FAILED ✘'
                      : '미측정'}
                  </span>
                </td>
                <td style={{ padding: '10px 8px', fontSize: '12px', color: '#8b949e' }}>
                  {node.lastVerifiedAt ? `${node.lastVerifiedAt} (기준 시각)` : '미측정'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Section 3: Release Manifest & Operator Sign-off Workflow (AC-12) */}
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
              모의 릴리스 선언서 (Release Manifest Pilot RC) 및 운영자 인수 서명
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              품질 게이트 G0~G6 인수 및 배포용 아티팩트의 불변 다이제스트
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="text"
              data-testid="deployment-operator-id-input"
              value={operatorId}
              readOnly={true}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="운영자 계정 ID"
              title={currentUser ? '운영자 ID는 로그인된 세션 계정으로 고정됩니다' : '운영자 계정 ID'}
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '13px',
                color: '#f0f6fc',
                opacity: currentUser ? 0.8 : 1,
              }}
            />
            <Button
              data-testid="deployment-signoff-btn"
              variant={manifest.operatorSignOff ? 'secondary' : 'primary'}
              onClick={handleSignOff}
              disabled={manifest.operatorSignOff || !currentUser}
              title={
                !currentUser
                  ? '운영자 계정 로그인이 필요합니다'
                  : currentUser.role !== 'admin' && currentUser.role !== 'operator'
                  ? '운영자 권한(operator/admin)이 필요합니다'
                  : manifest.operatorSignOff
                  ? '이미 인수가 서명되었습니다'
                  : '파일럿 운영 인수를 로컬 시뮬레이션 서명합니다'
              }
              aria-disabled={manifest.operatorSignOff || !currentUser ? 'true' : 'false'}
            >
              {manifest.operatorSignOff ? '✔ 모의 서명 완료됨' : '운영 인수 모의 서명'}
            </Button>
          </div>
        </div>

        <div data-testid="deployment-manifest-static-banner" style={{ fontSize: '11px', color: '#8b949e', marginBottom: '-4px' }}>
          [정적 픽스처 / 백엔드 릴리스 매니페스트 REST API 미연결]
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            backgroundColor: '#0d1117',
            padding: '16px',
            borderRadius: '6px',
            border: '1px solid #30363d',
            fontSize: '12px',
          }}
        >
          <div>
            <div style={{ color: '#8b949e' }}>Release Version</div>
            <div style={{ color: '#58a6ff', fontWeight: 600, marginTop: '2px' }}>{manifest.version}</div>
          </div>
          <div>
            <div style={{ color: '#8b949e' }}>Immutable Image Digest</div>
            <div style={{ color: '#f0f6fc', fontFamily: 'monospace', fontSize: '11px', marginTop: '2px', wordBreak: 'break-all' }}>
              {manifest.imageDigest}
            </div>
          </div>
          <div>
            <div style={{ color: '#8b949e' }}>Git Commit SHA</div>
            <div style={{ color: '#f0f6fc', fontFamily: 'monospace', marginTop: '2px' }}>{manifest.builtCommitSha}</div>
          </div>
          <div>
            <div style={{ color: '#8b949e' }}>클러스터 적합성</div>
            <div style={{ color: clusterNodes && clusterNodes.length > 0 ? '#3fb950' : '#8b949e', fontWeight: 600, marginTop: '2px' }}>
              {clusterComplianceLabel}
            </div>
          </div>
        </div>

        <div>
          <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#f0f6fc' }}>
            알려진 제한 사항 (Known Limitations & Operating Boundary):
          </h4>
          <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '12px', color: '#8b949e', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {manifest.knownLimitations.map((lim, idx) => (
              <li key={idx}>{lim}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* Section 4: Operator Training & Education Walkthrough */}
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
            운영자 실무 교육 훈련 모듈 (AC-12 Walkthrough)
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
            현장 운영자의 L0~L3 거버넌스, 배치 정책, Kill Switch, 무중단 롤백 자율 실습
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {trainingSteps.map((step) => (
            <div
              key={step.stepNumber}
              data-testid={`training-step-${step.stepNumber}`}
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '14px 18px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '16px',
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      width: '22px',
                      height: '22px',
                      borderRadius: '50%',
                      backgroundColor: step.status === 'completed' ? '#238636' : '#8b949e',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '11px',
                      fontWeight: 700,
                    }}
                  >
                    {step.stepNumber}
                  </span>
                  <strong style={{ fontSize: '13px', color: '#f0f6fc' }}>{step.title}</strong>
                </div>
                <div style={{ fontSize: '12px', color: '#8b949e', marginLeft: '30px' }}>
                  {step.description}
                </div>
                <div style={{ fontSize: '11px', color: '#58a6ff', marginTop: '2px', marginLeft: '30px' }}>
                  실습 행동: {step.actionRequired}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: step.status === 'completed' ? 'rgba(46, 160, 67, 0.2)' : 'rgba(139, 148, 158, 0.2)',
                    color: step.status === 'completed' ? '#3fb950' : '#8b949e',
                  }}
                >
                  {step.status === 'completed' ? 'COMPLETED ✔' : 'PENDING'}
                </span>
                <Button
                  data-testid={`training-complete-btn-${step.stepNumber}`}
                  variant="secondary"
                  size="sm"
                  onClick={() => handleCompleteStep(step.stepNumber)}
                  disabled={step.status === 'completed'}
                >
                  {step.status === 'completed' ? '실습 완료됨' : '실습 완료 확인'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
