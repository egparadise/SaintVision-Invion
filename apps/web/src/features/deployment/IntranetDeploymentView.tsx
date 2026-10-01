import React, { useState, useEffect } from 'react';
import { Button } from '@/shared/ui/Button';
import { NodeItem } from '@/contracts/types';
import { DeploymentManager } from './deploymentEngine';
import {
  fetchReleaseManifests,
  fetchReleaseManifestDetail,
  ReleaseManifestResponse,
  ReleaseManifestDetailResponse,
} from '@/shared/api/releaseObservation';

export interface IntranetDeploymentViewProps {
  clusterNodes?: NodeItem[];
  currentUser?: { id: string; name: string; role: string } | null;
  autoFetch?: boolean;
  initialManifests?: ReleaseManifestResponse[];
  initialDetail?: ReleaseManifestDetailResponse | null;
}

export const IntranetDeploymentView: React.FC<IntranetDeploymentViewProps> = ({
  clusterNodes,
  currentUser,
  autoFetch,
  initialManifests,
  initialDetail,
}) => {
  const [manager] = useState<DeploymentManager>(() => new DeploymentManager());
  const [tls] = useState(manager.getTlsDetails());
  const [nginxRules] = useState(manager.getNginxRules());
  const [nginxConfig] = useState(manager.generateNginxConfig());
  const nodes = clusterNodes ? manager.reconcileLiveClusterNodes(clusterNodes) : manager.getNodeVerifications();
  const [manifest, setManifest] = useState(manager.getReleaseManifest());
  const [localSimulationCompleted, setLocalSimulationCompleted] = useState(false);
  const [signedOperatorId, setSignedOperatorId] = useState<string | null>(null);
  const [trainingSteps, setTrainingSteps] = useState(manager.getTrainingSteps());
  const [operatorId, setOperatorId] = useState<string>(currentUser ? currentUser.id : '');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Server Release Manifest Observation State (GET /v1/release-manifests, GET /v1/release-manifests/{release_id})
  const [serverManifests, setServerManifests] = useState<ReleaseManifestResponse[]>(() => initialManifests ?? []);
  const [selectedReleaseId, setSelectedReleaseId] = useState<string | null>(
    () => initialDetail?.release?.releaseId ?? initialManifests?.[0]?.releaseId ?? null
  );
  const [serverManifestDetail, setServerManifestDetail] = useState<ReleaseManifestDetailResponse | null>(
    () => initialDetail ?? null
  );
  const [isLoadingServerManifests, setIsLoadingServerManifests] = useState<boolean>(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [serverManifestError, setServerManifestError] = useState<{
    status: number;
    code?: string;
    message: string;
  } | null>(null);
  const [hasFetchedServerReleases, setHasFetchedServerReleases] = useState<boolean>(
    () => Boolean(initialManifests || initialDetail)
  );

  useEffect(() => {
    const shouldFetch = autoFetch ?? true;
    if (!shouldFetch) return;

    let isMounted = true;
    const controller = new AbortController();

    async function loadServerReleases() {
      setIsLoadingServerManifests(true);
      setServerManifestError(null);
      try {
        const page = await fetchReleaseManifests({ signal: controller.signal });
        if (!isMounted) return;
        const items = page.items || [];
        setServerManifests(items);
        setNextCursor(page.nextCursor ?? null);
        setHasFetchedServerReleases(true);

        if (items.length > 0) {
          const firstId = items[0].releaseId;
          setSelectedReleaseId(firstId);
          setIsLoadingDetail(true);
          try {
            const detail = await fetchReleaseManifestDetail(firstId, controller.signal);
            if (!isMounted) return;
            setServerManifestDetail(detail);
          } catch (detailErr: any) {
            if (!isMounted) return;
            const isContractViolation = Boolean(detailErr?.isContractViolation || detailErr?.name === 'ContractViolationError');
            const prob = detailErr?.problem;
            const status = isContractViolation ? 0 : prob?.status || detailErr.status || 0;
            setServerManifestError({
              status,
              code: isContractViolation ? 'CONTRACT-VIOLATION' : prob?.code || (status === 404 ? 'RES-0004' : status === 403 ? 'AUTH-0030' : 'FETCH_DETAIL_ERROR'),
              message: isContractViolation ? detailErr.message : prob?.detail || detailErr.message || '릴리스 상세 조회 실패',
            });
            setServerManifestDetail(null);
          } finally {
            if (isMounted) {
              setIsLoadingDetail(false);
            }
          }
        } else {
          setSelectedReleaseId(null);
          setServerManifestDetail(null);
        }
      } catch (err: any) {
        if (!isMounted) return;
        if (err.name === 'AbortError') return;
        setHasFetchedServerReleases(true);
        const isContractViolation = Boolean(err?.isContractViolation || err?.name === 'ContractViolationError');
        const prob = err?.problem;
        const status = isContractViolation ? 0 : prob?.status || err.status || 0;
        setServerManifestError({
          status,
          code: isContractViolation ? 'CONTRACT-VIOLATION' : prob?.code || (status === 403 ? 'AUTH-0030' : status === 404 ? 'RES-0004' : 'NET-ERROR'),
          message: isContractViolation ? err.message : prob?.detail || err.message || '릴리스 선언서 목록 조회 실패',
        });
        setServerManifests([]);
        setServerManifestDetail(null);
      } finally {
        if (isMounted) {
          setIsLoadingServerManifests(false);
        }
      }
    }

    loadServerReleases();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [autoFetch]);

  const handleSelectServerRelease = async (releaseId: string) => {
    setSelectedReleaseId(releaseId);
    setIsLoadingDetail(true);
    setServerManifestError(null);
    try {
      const detail = await fetchReleaseManifestDetail(releaseId);
      setServerManifestDetail(detail);
    } catch (err: any) {
      const isContractViolation = Boolean(err?.isContractViolation || err?.name === 'ContractViolationError');
      const prob = err?.problem;
      const status = isContractViolation ? 0 : prob?.status || err.status || 0;
      setServerManifestError({
        status,
        code: isContractViolation ? 'CONTRACT-VIOLATION' : prob?.code || (status === 403 ? 'AUTH-0030' : status === 404 ? 'RES-0004' : 'NET-ERROR'),
        message: isContractViolation ? err.message : prob?.detail || err.message || '릴리스 상세 조회 실패',
      });
      setServerManifestDetail(null);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  useEffect(() => {
    if (currentUser?.id) {
      setOperatorId(currentUser.id);
    } else {
      setOperatorId('');
    }
  }, [currentUser]);

  const onlineNodesCount = clusterNodes
    ? nodes.filter((n) => n.liveStatus === 'online' && n.smokeStatus === 'passed').length
    : 0;
  const clusterComplianceLabel = clusterNodes && clusterNodes.length > 0
    ? `${onlineNodesCount}/${clusterNodes.length} online (heartbeat 기준, smoke 미측정)`
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
      setLocalSimulationCompleted(true);
      setSignedOperatorId(currentUser.id);
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
      {/* DEF 외 접근성 추가: Accessible Skip Navigation Link */}
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

      {/* DEF 외 접근성 추가: Heading Level 1 with tabIndex for focus targeting */}
      <h1 id="deployment-main-content" tabIndex={-1} style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text-primary)', margin: '0 0 4px 0', outline: 'none' }}>
        내부망 HTTPS 배포 및 운영 인수 검증 (AC-12)
      </h1>

      {/* Unexposed Deployment Notice Banner */}
      <div
        role="status"
        aria-live="polite"
        data-testid="deployment-unexposed-notice"
        style={{
          padding: '8px 16px',
          backgroundColor: 'var(--color-bg-subtle)',
          borderBottom: '1px solid var(--color-border-subtle)',
          borderRadius: '6px',
          color: 'var(--color-brand-hover)',
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
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-offline)',
            borderRadius: '6px',
            color: 'var(--color-status-offline)',
            fontSize: '12px',
            fontWeight: 500,
          }}
        >
          🛑 <strong>인증 필요</strong>: 로그인된 운영자 세션이 없습니다. 내부망 모의 운영 인수 서명을 수행하려면 유효한 운영자 계정으로 로그인해야 합니다.
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
        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>내부망 HTTPS 암호화 (AC-12)</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-status-online)', marginTop: '4px' }}>
            TLS 1.2 / TLSv1.3 협상 (개발용 자체서명 CA)
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>HSTS 365일 (개발용 자체서명 CA)</div>
        </div>

        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>5대 노드 여정 검증 [AC-12 기준 규격]</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: clusterNodes && clusterNodes.length > 0 ? 'var(--color-status-online)' : 'var(--color-text-secondary)', marginTop: '4px' }}>
            {clusterComplianceLabel}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>Windows 3대 + Linux 2대 통합 여정 규격</div>
        </div>

        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>파일럿 후보 릴리스 (Pilot RC)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-brand-hover)', marginTop: '4px' }}>
            {manifest.version}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>Manifest ID: <code>{manifest.releaseId}</code></div>
        </div>

        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>[로컬 모의] 운영자 인수 서명 (Sign-Off)</div>
          <div
            style={{
              fontSize: '24px',
              fontWeight: 700,
              color: localSimulationCompleted ? 'var(--color-status-online)' : 'var(--color-status-degraded)',
              marginTop: '4px',
            }}
          >
            {localSimulationCompleted ? '모의 서명 완료 ✔' : 'SIGN-OFF 대기 (로컬 모의)'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            {localSimulationCompleted
              ? `모의 서명자: ${signedOperatorId || currentUser?.id || '미확인'} (실서버 서명은 3-A 섹션 관측)`
              : '운영자 확인 대기 중 [로컬 시뮬레이션 전용 — 실서버 연동은 3-A]'}
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
            backgroundColor: actionNotice.type === 'error' ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
            border: `1px solid ${actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)'}`,
            color: actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)',
          }}
        >
          {actionNotice.text}
        </div>
      )}

      {/* Preflight vs Physical Hardware Acceptance Banner */}
      <div
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
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
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-secondary)',
              }}
            >
              미측정 (설계 규격 예시)
            </span>
            <strong style={{ fontSize: '14px', color: 'var(--color-text-primary)' }}>
              내부망 배포 사전 검증 파이프라인 [설계 규격 예시 (202개 검증 항목)]
            </strong>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            [사전 설계 규격 항목] Nginx TLS 1.2/1.3 협상, SSE 버퍼링 차단, PTY 30초 일회용 티켓, ADR-038 노드 Drain (게이트웨이 실시간 프로브 미연결)
          </p>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>온프레미스 물리 5대 실장비 기동</div>
          <div
            style={{
              fontSize: '13px',
              color: localSimulationCompleted ? 'var(--color-status-online)' : 'var(--color-status-degraded)',
              fontWeight: 600,
              marginTop: '2px',
            }}
          >
            {localSimulationCompleted
              ? '모의 인수 절차 확인됨 (온프레미스 실장비 기동 별도 필요)'
              : '현장 운영자 인수 대기 (Pending Acceptance)'}
          </div>
        </div>
      </div>

      {/* Section 1: TLS Certificate & Nginx Reverse Proxy Details */}
      <div
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
        <div>
          <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
            내부망 전용 TLS 인증서 정보 (AC-12) [정적 구성 예시 (실시간 인증서 조회 아님)]
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            격리 폐쇄망 내부 도메인 보안 및 HSTS 강제 암호화
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            backgroundColor: 'var(--color-bg-subtle)',
            padding: '16px',
            borderRadius: '6px',
            border: '1px solid var(--color-border-subtle)',
            fontSize: '12px',
          }}
        >
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>도메인 (Domain)</div>
            <div style={{ color: 'var(--color-text-primary)', fontWeight: 600, marginTop: '2px' }}>{tls.domain}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>발급 기관 (Issuer)</div>
            <div style={{ color: 'var(--color-text-primary)', fontWeight: 600, marginTop: '2px' }}>{tls.issuer}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>프로토콜 및 암호군</div>
            <div style={{ color: 'var(--color-status-online)', fontWeight: 600, marginTop: '2px' }}>
              {tls.tlsVersion} · {tls.cipherSuite}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>HSTS 보안 헤더</div>
            <div style={{ color: 'var(--color-status-online)', fontWeight: 600, marginTop: '2px' }}>
              {tls.hstsEnabled ? '활성화 (31,536,000초 / includeSubDomains)' : '비활성'}
            </div>
          </div>
        </div>

        <div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
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
                  backgroundColor: 'var(--color-bg-subtle)',
                  color: 'var(--color-brand-hover)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                {san}
              </span>
            ))}
          </div>
        </div>

        {/* Nginx Routing Table */}
        <div>
          <h4 style={{ margin: '12px 0 8px 0', fontSize: '13px', color: 'var(--color-text-primary)' }}>
            Nginx 단일 오리진 라우팅 매트릭스
          </h4>
          <p style={{ margin: '0 0 10px 0', fontSize: '11px', color: 'var(--color-text-secondary)' }}>
            동일 Origin (<code>:443 또는 :8443</code>) 기반 정적 SPA, REST API, SSE 스트리밍, PTY 웹소켓
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-secondary)' }}>
                <th style={{ padding: '8px' }}>Location</th>
                <th style={{ padding: '8px' }}>Target</th>
                <th style={{ padding: '8px' }}>Protocol</th>
                <th style={{ padding: '8px' }}>버퍼링/헤더</th>
              </tr>
            </thead>
            <tbody>
              {nginxRules.map((rule) => (
                <tr key={rule.location} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                  <td style={{ padding: '8px', fontFamily: 'monospace', color: 'var(--color-brand-hover)' }}>{rule.location}</td>
                  <td style={{ padding: '8px', color: 'var(--color-text-secondary)' }}>{rule.targetUpstream}</td>
                  <td style={{ padding: '8px' }}>
                    <span
                      style={{
                        padding: '1px 6px',
                        borderRadius: '3px',
                        fontSize: '11px',
                        backgroundColor:
                          rule.protocol === 'WebSocket'
                            ? 'var(--color-brand-subtle)'
                            : rule.protocol === 'SSE'
                            ? 'var(--color-bg-subtle)'
                            : 'var(--color-bg-subtle)',
                        color:
                          rule.protocol === 'WebSocket'
                            ? 'var(--color-brand-hover)'
                            : rule.protocol === 'SSE'
                            ? 'var(--color-brand-hover)'
                            : 'var(--color-status-online)',
                      }}
                    >
                      {rule.protocol}
                    </span>
                  </td>
                  <td style={{ padding: '8px', color: 'var(--color-text-secondary)' }}>
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
          <summary style={{ cursor: 'pointer', color: 'var(--color-brand-hover)' }}>
            ▶ 배포용 nginx.conf 구성 파일 발췌 보기 [발췌 예시 — 전문은 apps/web/nginx.conf]
          </summary>
          <pre
            style={{
              marginTop: '8px',
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              padding: '12px',
              overflowX: 'auto',
              fontSize: '11px',
              color: 'var(--color-text-secondary)',
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
              5-Node 통합 여정 및 Smoke 검증 매트릭스 (AC-12)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
              Windows/Linux 혼합 노드 여정, 역할 격리, mTLS 설계 규격 [정적 예시]
            </p>
          </div>
          <span
            style={{
              padding: '3px 10px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              backgroundColor: clusterNodes && clusterNodes.length > 0 ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
              color: clusterNodes && clusterNodes.length > 0 ? 'var(--color-status-online)' : 'var(--color-text-secondary)',
            }}
          >
            {clusterComplianceLabel}
          </span>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-secondary)' }}>
              <th style={{ padding: '8px' }}>Node ID / Hostname</th>
              <th style={{ padding: '8px' }}>OS</th>
              <th style={{ padding: '8px' }}>실시간 클러스터 상태</th>
              <th style={{ padding: '8px' }}>검증된 역할 (Roles)</th>
              <th style={{ padding: '8px' }}>지연시간</th>
              <th style={{ padding: '8px' }}>Smoke 상태</th>
              <th style={{ padding: '8px' }}>기준 시각 (예시) / heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((node) => (
              <tr key={node.nodeId} data-testid={`node-row-${node.nodeId}`} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                <td style={{ padding: '10px 8px' }}>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{node.hostname}</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', fontFamily: 'monospace' }}>{node.nodeId}</div>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: node.os === 'windows' ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
                      color: node.os === 'windows' ? 'var(--color-brand-hover)' : 'var(--color-status-degraded)',
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
                            ? 'var(--color-bg-subtle)'
                            : node.liveStatus === 'draining'
                            ? 'var(--color-bg-subtle)'
                            : 'var(--color-bg-subtle)',
                        color:
                          node.liveStatus === 'online'
                            ? 'var(--color-status-online)'
                            : node.liveStatus === 'draining'
                            ? 'var(--color-status-degraded)'
                            : 'var(--color-status-offline)',
                      }}
                    >
                      {node.liveStatus.toUpperCase()}
                      {node.liveIsDraining && ' (Draining)'}
                      {node.liveObservationOnly && ' (Obs-Only)'}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--color-text-secondary)', fontSize: '12px' }}>미측정 (미연결)</span>
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
                          backgroundColor: 'var(--color-bg-subtle)',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                </td>
                <td style={{ padding: '10px 8px', color: node.liveStatus === 'online' && node.smokeStatus === 'passed' ? 'var(--color-status-online)' : 'var(--color-text-secondary)', fontWeight: 600 }}>
                  {node.liveStatus === 'online' && node.smokeStatus === 'passed' ? `${node.latencyMs} ms` : '미측정'}
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <span
                    aria-label={`Smoke status: ${node.liveStatus === 'online' && node.smokeStatus === 'passed' ? 'passed' : node.liveStatus === 'offline' || node.smokeStatus === 'failed' ? 'failed' : 'unmeasured'}`}
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor:
                        node.liveStatus === 'online' && node.smokeStatus === 'passed'
                          ? 'var(--color-bg-subtle)'
                          : node.liveStatus === 'offline' || node.smokeStatus === 'failed'
                          ? 'var(--color-bg-subtle)'
                          : 'var(--color-bg-subtle)',
                      color:
                        node.liveStatus === 'online' && node.smokeStatus === 'passed'
                          ? 'var(--color-status-online)'
                          : node.liveStatus === 'offline' || node.smokeStatus === 'failed'
                          ? 'var(--color-status-offline)'
                          : 'var(--color-text-secondary)',
                    }}
                  >
                    {node.liveStatus === 'online' && node.smokeStatus === 'passed'
                      ? 'PASSED ✔'
                      : node.liveStatus === 'offline' || node.smokeStatus === 'failed'
                      ? 'FAILED ✘'
                      : '미측정'}
                  </span>
                </td>
                <td style={{ padding: '10px 8px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                  {node.liveStatus
                    ? node.liveHeartbeatAt
                      ? `${node.liveHeartbeatAt} (heartbeat)`
                      : '미측정'
                    : `${node.lastVerifiedAt || '미측정'} [정적 예시]`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Section 3-A: Server Release Manifest & Operator Sign-off Observation (GET /v1/release-manifests) */}
      <div
        data-testid="deployment-server-manifest-section"
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
              서버 릴리스 선언서 (Release Manifest) 및 운영자 인수 관측
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
              공식 REST API (GET /v1/release-manifests, GET /v1/release-manifests/:release_id) 결속 및 수락 진위 관측
            </p>
          </div>

          <div
            data-testid="deployment-manifest-server-banner"
            style={{
              padding: '4px 10px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: '6px',
              border: '1px solid var(--color-brand-hover)',
              color: 'var(--color-brand-hover)',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            [서버 REST API 결속: GET /v1/release-manifests, GET /v1/release-manifests/:release_id]
          </div>
        </div>

        {/* Loading State for List */}
        {isLoadingServerManifests && (
          <div
            data-testid="deployment-manifest-loading"
            role="status"
            aria-live="polite"
            style={{ padding: '16px', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '13px' }}
          >
            ⏳ 서버 릴리스 선언서 목록 동기화 중...
          </div>
        )}

        {/* Empty State: Zero fabricated defaults (F10: role="status" aria-live="polite") */}
        {!isLoadingServerManifests && !serverManifestError && hasFetchedServerReleases && serverManifests.length === 0 && (
          <div
            data-testid="deployment-manifest-empty-state"
            role="status"
            aria-live="polite"
            style={{
              padding: '24px',
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px dashed var(--color-border-subtle)',
              borderRadius: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
              ℹ️ 기록 없음 (등록된 릴리스 선언서 부재)
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
              현재 테넌트에 등록된 릴리스 선언서(Release Manifest)가 없습니다. (등록된 릴리스 0건)
            </div>
            <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              서버 빈 목록 응답(items: []) 정상 수신 · 가짜 릴리스 기본값 표출을 엄격히 차단합니다.
            </div>
          </div>
        )}

        {/* When items exist, render Selector and Detail/Error Area (F7: selector preserved on detail error) */}
        {!isLoadingServerManifests && serverManifests.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {serverManifests.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label htmlFor="deployment-release-selector" style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                  관측 대상 릴리스 선택:
                </label>
                <select
                  id="deployment-release-selector"
                  data-testid="deployment-release-selector"
                  value={selectedReleaseId || ''}
                  onChange={(e) => handleSelectServerRelease(e.target.value)}
                  style={{
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    padding: '4px 8px',
                    color: 'var(--color-text-primary)',
                    fontSize: '12px',
                  }}
                >
                  {serverManifests.map((item) => (
                    <option key={item.releaseId} value={item.releaseId}>
                      {item.version} ({item.releaseId}) - 미서명 (사람 확인 {item.confirmedOperatorCount}/{item.requiredDistinctOperatorCount} · 해시 일치 {item.matchingAcceptedUserCount}건)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Next cursor indicator if present (F8) */}
            {nextCursor && (
              <div data-testid="deployment-manifest-next-cursor" style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                다음 페이지 커서: <code>{nextCursor}</code>
              </div>
            )}

            {/* Detail Loading State */}
            {isLoadingDetail && (
              <div
                data-testid="deployment-manifest-detail-loading"
                role="status"
                aria-live="polite"
                style={{ padding: '16px', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '13px' }}
              >
                ⏳ 릴리스 상세 정보 조회 중...
              </div>
            )}

            {/* Detail Error State (F6: no fabricated 500 on network failure) */}
            {!isLoadingDetail && serverManifestError && (
              <div
                data-testid={
                  serverManifestError.code === 'CONTRACT-VIOLATION'
                    ? 'deployment-manifest-error-contract'
                    : serverManifestError.status === 403
                    ? 'deployment-manifest-error-403'
                    : serverManifestError.status === 404
                    ? 'deployment-manifest-error-404'
                    : 'deployment-manifest-error'
                }
                role="alert"
                aria-live="assertive"
                style={{
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  border: '1px solid var(--color-status-offline)',
                  borderRadius: '6px',
                  color: 'var(--color-status-offline)',
                  fontSize: '13px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <div style={{ fontWeight: 600 }}>
                  🛑 {serverManifestError.code === 'CONTRACT-VIOLATION'
                    ? '계약 위반 응답: 잘못된 서버 응답 규격'
                    : serverManifestError.status === 403
                    ? '403 Forbidden: 접근 권한 없음'
                    : serverManifestError.status === 404
                    ? '404 Not Found: 릴리스 선언서 부재'
                    : serverManifestError.status
                    ? `HTTP 오류 (${serverManifestError.status})`
                    : '네트워크 통신 오류'}
                </div>
                <div style={{ fontSize: '12px', opacity: 0.9 }}>
                  {serverManifestError.message} (에러 코드: {serverManifestError.code || 'UNKNOWN'})
                </div>
              </div>
            )}

            {/* Loaded Release Manifest Observation View */}
            {!isLoadingDetail && !serverManifestError && serverManifestDetail && (
              <div data-testid="deployment-server-manifest-detail" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '16px',
                borderRadius: '6px',
                border: '1px solid var(--color-border-subtle)',
                fontSize: '12px',
              }}
            >
              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Release Version</div>
                <div data-testid="server-release-version" style={{ color: 'var(--color-brand-hover)', fontWeight: 600, marginTop: '2px' }}>
                  {serverManifestDetail.release.version}
                </div>
              </div>

              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Release ID</div>
                <div style={{ marginTop: '2px' }}>
                  <code data-testid="server-release-id" style={{ color: 'var(--color-text-primary)', fontSize: '11px' }}>
                    {serverManifestDetail.release.releaseId}
                  </code>
                </div>
              </div>

              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Manifest SHA-256 (Pinned)</div>
                <div style={{ marginTop: '2px' }}>
                  <code
                    data-testid="server-manifest-sha"
                    style={{ color: 'var(--color-text-primary)', fontFamily: 'monospace', fontSize: '11px', wordBreak: 'break-all' }}
                  >
                    {serverManifestDetail.release.manifestSha256}
                  </code>
                </div>
              </div>

              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>컴포넌트 수</div>
                <div data-testid="server-component-count" style={{ color: 'var(--color-text-primary)', fontWeight: 600, marginTop: '2px' }}>
                  {serverManifestDetail.release.componentCount} 개
                </div>
              </div>

              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>운영자 인수 서명 관측 (operatorSignOff)</div>
                <div data-testid="server-operator-signoff" style={{ marginTop: '2px' }}>
                  <span style={{ color: 'var(--color-status-degraded)', fontWeight: 600 }}>
                    미서명 (operatorSignOff: false)
                  </span>
                  <div
                    data-testid="server-operator-signoff-blocked-by"
                    style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '2px' }}
                  >
                    미서명 — 릴리스 수락 전제 조건 미충족 (<code>{serverManifestDetail.release.operatorSignOffBlockedBy}</code>)
                  </div>
                </div>
              </div>

              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>운영자 확인 현황 (Operator Quorum)</div>
                <div data-testid="server-operator-quorum" style={{ marginTop: '2px' }}>
                  <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>
                    사람 확인 {serverManifestDetail.release.confirmedOperatorCount} / {serverManifestDetail.release.requiredDistinctOperatorCount} (서명 아님)
                  </span>
                  <div data-testid="server-matching-user-count" style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                    해시 일치 수락 기록 {serverManifestDetail.release.matchingAcceptedUserCount}건 (사람 확인 아님)
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                    서비스 주체 포함 가능 — 2명 고유 사람 확인 계약 구현 전 서명 불인정
                  </div>
                </div>
              </div>

              <div>
                <div style={{ color: 'var(--color-text-secondary)' }}>수락 결정 기록 (Acceptance Count)</div>
                <div data-testid="server-acceptance-count" style={{ color: 'var(--color-text-primary)', fontWeight: 600, marginTop: '2px' }}>
                  {serverManifestDetail.release.acceptanceCount} 건
                </div>
              </div>
            </div>

            {/* Acceptances Decision Log */}
            <div data-testid="server-acceptances-section" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-primary)' }}>
                기록된 수락 결정 이력 (Server Acceptances):
              </h4>
              {serverManifestDetail.acceptances && serverManifestDetail.acceptances.length > 0 ? (
                <div data-testid="server-acceptances-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {serverManifestDetail.acceptances.map((acc) => (
                    <div
                      key={acc.acceptanceId}
                      data-testid={`server-acceptance-${acc.acceptanceId}`}
                      style={{
                        backgroundColor: 'var(--color-bg-subtle)',
                        border: '1px solid var(--color-border-subtle)',
                        borderRadius: '6px',
                        padding: '10px 14px',
                        fontSize: '12px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <span style={{ color: 'var(--color-text-secondary)' }}>결정 ID: </span>
                          <code style={{ color: 'var(--color-brand-hover)' }}>{acc.acceptanceId}</code>
                          <span style={{ color: 'var(--color-text-secondary)', marginLeft: '8px' }}>기준 참조: </span>
                          <code style={{ color: 'var(--color-text-primary)' }}>{acc.acceptanceIdRef}</code>
                        </div>
                        <div>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: 600,
                              backgroundColor:
                                acc.outcome === 'accepted'
                                  ? 'var(--color-bg-subtle)'
                                  : acc.outcome === 'conditional'
                                  ? 'var(--color-bg-subtle)'
                                  : 'var(--color-bg-subtle)',
                              color:
                                acc.outcome === 'accepted'
                                  ? 'var(--color-status-online)'
                                  : acc.outcome === 'conditional'
                                  ? 'var(--color-status-degraded)'
                                  : 'var(--color-status-offline)',
                            }}
                          >
                            결과: {acc.outcome}
                          </span>
                        </div>
                      </div>
                      <div style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}>
                        해시 일치 여부:{' '}
                        <strong style={{ color: acc.manifestMatches ? 'var(--color-status-online)' : 'var(--color-status-offline)' }}>
                          {acc.manifestMatches ? '일치 (Verified Match)' : '불일치 (Mismatch)'}
                        </strong>
                        {' · '}
                        결정 시각: {acc.decidedAt}
                      </div>
                      {acc.knownLimitations && acc.knownLimitations.length > 0 && (
                        <div style={{ marginTop: '4px' }}>
                          <span style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}>조건부 제한 사항:</span>
                          <ul style={{ margin: '2px 0 0 0', paddingLeft: '18px', color: 'var(--color-status-degraded)', fontSize: '11px' }}>
                            {acc.knownLimitations.map((lim, idx) => (
                              <li key={idx}>{lim}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div
                  data-testid="server-acceptances-empty"
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-text-secondary)',
                    padding: '10px 14px',
                    backgroundColor: 'var(--color-bg-subtle)',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border-subtle)',
                  }}
                >
                  기록된 수락 결정 없음 (미서명 사유: 아무도 승인 결정을 등록하지 않았거나 조건부/해시 불일치 상태입니다)
                </div>
              )}
            </div>

            {/* Components list */}
            {serverManifestDetail.release.components && serverManifestDetail.release.components.length > 0 && (
              <div data-testid="server-components-section" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-primary)' }}>
                  포함된 컴포넌트 목록 ({serverManifestDetail.release.components.length}개):
                </h4>
                <div
                  data-testid="server-components-list"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: '8px',
                  }}
                >
                  {serverManifestDetail.release.components.map((comp, idx) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: 'var(--color-bg-subtle)',
                        border: '1px solid var(--color-border-subtle)',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '11px',
                      }}
                    >
                      <div style={{ color: 'var(--color-brand-hover)', fontWeight: 600 }}>{comp.name}</div>
                      <div style={{ color: 'var(--color-text-secondary)', marginTop: '2px' }}>종류: {comp.kind}</div>
                      <div style={{ color: 'var(--color-text-primary)', fontFamily: 'monospace', marginTop: '2px', wordBreak: 'break-all' }}>
                        {comp.digest}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Write Boundary Notice: Strictly No Write UI */}
            <div
              data-testid="server-write-boundary-notice"
              style={{
                fontSize: '11px',
                color: 'var(--color-text-secondary)',
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              ℹ️ <strong>수락 및 서명 쓰기 경계</strong>: 릴리스 수락 등록은 테넌트 전역 보안 경계 작업으로, 인증된 사람의 서명 증거 및 감사 계약 수립 후 제공됩니다 (본 화면은 읽기 전용 관측 표출 전용이며 임의 쓰기 서명 UI는 엄격히 금지됩니다).
            </div>
            </div>
          )}
          </div>
        )}

        {/* Error when list fetch failed (items: 0) */}
        {!isLoadingServerManifests && serverManifests.length === 0 && serverManifestError && (
          <div
            data-testid={
              serverManifestError.code === 'CONTRACT-VIOLATION'
                ? 'deployment-manifest-error-contract'
                : serverManifestError.status === 403
                ? 'deployment-manifest-error-403'
                : serverManifestError.status === 404
                ? 'deployment-manifest-error-404'
                : 'deployment-manifest-error'
            }
            role="alert"
            aria-live="assertive"
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-status-offline)',
              borderRadius: '6px',
              color: 'var(--color-status-offline)',
              fontSize: '13px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            <div style={{ fontWeight: 600 }}>
              🛑 {serverManifestError.code === 'CONTRACT-VIOLATION'
                ? '계약 위반 응답: 잘못된 서버 응답 규격'
                : serverManifestError.status === 403
                ? '403 Forbidden: 접근 권한 없음'
                : serverManifestError.status === 404
                ? '404 Not Found: 릴리스 선언서 부재'
                : serverManifestError.status
                ? `HTTP 오류 (${serverManifestError.status})`
                : '네트워크 통신 오류'}
            </div>
            <div style={{ fontSize: '12px', opacity: 0.9 }}>
              {serverManifestError.message} (에러 코드: {serverManifestError.code || 'UNKNOWN'})
            </div>
          </div>
        )}
      </div>

      {/* Section 3-B: [로컬 모의 시뮬레이션] 파일럿 릴리스 선언서 및 운영자 사전 실습 */}
      <div
        data-testid="deployment-simulation-manifest-section"
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
              모의 릴리스 선언서 (Release Manifest Pilot RC) 및 운영자 인수 서명
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
              품질 게이트 G0~G6 인수 및 배포용 아티팩트의 불변 다이제스트 (로컬 시뮬레이션 실습용)
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="text"
              data-testid="deployment-operator-id-input"
              value={operatorId}
              readOnly={true}
              placeholder="운영자 계정 ID"
              title={currentUser ? '운영자 ID는 로그인된 세션 계정으로 고정됩니다' : '운영자 계정 ID'}
              style={{
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '13px',
                color: 'var(--color-text-primary)',
                opacity: currentUser ? 0.8 : 1,
              }}
            />
            <Button
              data-testid="deployment-signoff-btn"
              variant={localSimulationCompleted ? 'secondary' : 'primary'}
              onClick={handleSignOff}
              disabled={localSimulationCompleted || !currentUser}
              title={
                !currentUser
                  ? '운영자 계정 로그인이 필요합니다'
                  : currentUser.role !== 'admin' && currentUser.role !== 'operator'
                  ? '운영자 권한(operator/admin)이 필요합니다'
                  : localSimulationCompleted
                  ? '이미 인수가 서명되었습니다'
                  : '파일럿 운영 인수를 로컬 시뮬레이션 서명합니다'
              }
              aria-disabled={localSimulationCompleted || !currentUser ? 'true' : 'false'}
            >
              {localSimulationCompleted ? '✔ 모의 서명 완료됨' : '운영 인수 모의 서명'}
            </Button>
          </div>
        </div>

        <div data-testid="deployment-manifest-static-banner" style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginBottom: '-4px' }}>
          [정적 픽스처 / 백엔드 릴리스 매니페스트 REST API 미연결]
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            backgroundColor: 'var(--color-bg-subtle)',
            padding: '16px',
            borderRadius: '6px',
            border: '1px solid var(--color-border-subtle)',
            fontSize: '12px',
          }}
        >
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>Release Version</div>
            <div style={{ color: 'var(--color-brand-hover)', fontWeight: 600, marginTop: '2px' }}>{manifest.version}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>Immutable Image Digest</div>
            <div style={{ color: 'var(--color-text-primary)', fontFamily: 'monospace', fontSize: '11px', marginTop: '2px', wordBreak: 'break-all' }}>
              {manifest.imageDigest}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>Git Commit SHA</div>
            <div style={{ color: 'var(--color-text-primary)', fontFamily: 'monospace', marginTop: '2px' }}>{manifest.builtCommitSha}</div>
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)' }}>클러스터 적합성</div>
            <div style={{ color: clusterNodes && clusterNodes.length > 0 ? 'var(--color-status-online)' : 'var(--color-text-secondary)', fontWeight: 600, marginTop: '2px' }}>
              {clusterComplianceLabel}
            </div>
          </div>
        </div>

        <div>
          <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--color-text-primary)' }}>
            알려진 제한 사항 (Known Limitations & Operating Boundary):
          </h4>
          <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '12px', color: 'var(--color-text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {manifest.knownLimitations.map((lim, idx) => (
              <li key={idx}>{lim}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* Section 4: Operator Training & Education Walkthrough */}
      <div
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
        <div>
          <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
            운영자 실무 교육 훈련 모듈 (AC-12 Walkthrough)
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            현장 운영자의 L0~L3 거버넌스, 배치 정책, Kill Switch, 무중단 롤백 자율 실습
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {trainingSteps.map((step) => (
            <div
              key={step.stepNumber}
              data-testid={`training-step-${step.stepNumber}`}
              style={{
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
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
                      backgroundColor: 'var(--color-bg-subtle)',
                      border: step.status === 'completed' ? '1px solid var(--color-status-online)' : '1px solid var(--color-border-subtle)',
                      color: step.status === 'completed' ? 'var(--color-status-online)' : 'var(--color-text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '11px',
                      fontWeight: 700,
                    }}
                  >
                    {step.stepNumber}
                  </span>
                  <strong style={{ fontSize: '13px', color: 'var(--color-text-primary)' }}>{step.title}</strong>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginLeft: '30px' }}>
                  {step.description}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--color-brand-hover)', marginTop: '2px', marginLeft: '30px' }}>
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
                    backgroundColor: step.status === 'completed' ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
                    color: step.status === 'completed' ? 'var(--color-status-online)' : 'var(--color-text-secondary)',
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
