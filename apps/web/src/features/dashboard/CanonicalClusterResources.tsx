import { useEffect, useState } from 'react';
import type { NodeItem, RunItem } from '@/contracts/types';
import { currentResourceRows, resourceClockCurrent } from '@/shared/api/dashboardResources';

export function sharedQuantity(value: number, kind: string): string {
  if (!Number.isSafeInteger(value) || value < 0) return '합계 범위 초과 (미관측)';
  if (kind === 'cpu') return `${value}m`;
  if (kind === 'memory' || kind === 'storage') {
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    const index = Math.min(4, value > 0 ? Math.floor(Math.log(value) / Math.log(1024)) : 0);
    return `${Number((value / 1024 ** index).toFixed(2))} ${units[index]}`;
  }
  return `${value} devices`;
}

const panel = { padding: 20, backgroundColor: 'var(--color-bg-surface)', borderRadius: 12 };
const dimensions = [{ kind: 'cpu', unit: 'millicores', label: '공유 CPU' }, { kind: 'memory', unit: 'bytes', label: '공유 메모리' }];

/** Allocation observations never become physical utilization or scheduler admission. */
export function CanonicalClusterResources({ nodes, runs, nodesState, nodeError, lastFetchedAt, onRefresh, statusConfig }: {
  nodes: NodeItem[]; runs: RunItem[]; nodesState: string; nodeError?: string | null; lastFetchedAt?: Date | null;
  onRefresh?: () => void; statusConfig: (status: unknown) => { color: string; label: string };
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const rowsFor = (node: NodeItem, kind: string, unit: string) => nodesState === 'error' ? []
    : currentResourceRows(node.resourceObservation, kind, unit, now);
  return <section data-testid="canonical-cluster-resources">
    {nodesState === 'error' && <div role="alert" data-testid="cluster-stale-warning">⚠️ [동기화 실패] {nodeError} · 이전 노드 스냅샷</div>}
    <h1>분산 Node 클러스터 개요</h1>
    <p>관측된 노드 (온라인 {nodes.filter(node => node.status === 'online').length}/{nodes.length}대, 활성 실행 {runs.filter(run => run.state === 'running').length}건)</p>
    <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
      <span data-testid="cluster-freshness-indicator">자동 갱신 (5초 주기) · 화면 확인: {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '확인 중'}</span>
      {onRefresh && <button data-testid="cluster-refresh-btn" onClick={onRefresh}>새로고침</button>}
    </div>
    <p>execution-kernel 제공량·예약량·여유량의 관측 스냅샷입니다. 물리 장비 전체 용량·OS 실사용률이 아니며 스케줄러 승인이나 실행 허용을 의미하지 않습니다.</p>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
      {dimensions.map(({ kind, unit, label }) => {
        const rows = nodes.flatMap(node => rowsFor(node, kind, unit));
        const measuredNodes = nodes.filter(node => rowsFor(node, kind, unit).length > 0).length;
        const sum = (key: 'capacity' | 'offered' | 'reserved' | 'spare') => rows.reduce((total, row) => total + (row[key] ?? 0), 0);
        return <article key={kind} style={panel} data-testid={`shared-total-${kind}`}>
          <h2>{label} 관측 합계</h2>
          <p>{measuredNodes}/{nodes.length}대 현재 관측 · 누락된 값은 합계에 포함하지 않음</p>
          {rows.length ? <>
            <strong>제공 {sharedQuantity(sum('offered'), kind)}</strong>
            <p>등록 용량 {sharedQuantity(sum('capacity'), kind)} · 예약 {sharedQuantity(sum('reserved'), kind)} · 여유 {sharedQuantity(sum('spare'), kind)}</p>
          </> : <p>현재 자원 미관측</p>}
        </article>;
      })}
    </div>
    <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
      {nodes.map(node => {
        const observation = node.resourceObservation;
        const status = statusConfig(node.status);
        const stale = nodesState === 'error' || !!observation?.error || !resourceClockCurrent(observation?.usage?.stateAsOf ?? null, now);
        return <article key={node.id} style={panel} data-testid={`node-item-${node.id}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>{node.hostname}</strong>
            <span data-testid={`node-status-badge-${node.id}`} style={{ color: status.color }}>● {status.label}</span>
          </div>
          <p data-testid={`node-heartbeat-${node.id}`}>마지막 하트비트: {node.heartbeatAt ? new Date(node.heartbeatAt).toLocaleTimeString('ko-KR') : '미관측 (Heartbeat Absent)'}</p>
          {observation?.loading && <p>자원 관측 확인 중 · 이전 관측 유지</p>}
          {observation?.error && <p role="alert">자원 조회 실패: {observation.error} · 이전 관측은 현재 합계에서 제외</p>}
          {observation?.issues.map((issue, index) => <p role="alert" key={index}>{issue.kind}: {issue.message}</p>)}
          {dimensions.map(({ kind, unit, label }) => {
            const rows = rowsFor(node, kind, unit);
            const all = observation?.usage?.resources.filter(row => row.kind === kind) ?? [];
            const complete = all.length > 0 && rows.length === all.length;
            const oldRows = all.filter(row => row.unit === unit && row.measured && row.observedAt !== null && Date.parse(row.observedAt) <= now);
            const sum = (key: 'capacity' | 'offered' | 'reserved' | 'spare', input = rows) => input.reduce((total, row) => total + (row[key] ?? 0), 0);
            return <div key={kind} data-testid={`node-${kind}-${node.id}`}>
              <h3>{label}</h3>
              {rows.length ? <>
                <strong>제공 {sharedQuantity(sum('offered'), kind)}</strong> · {complete ? '관측됨' : '부분 관측'}
                <p>등록 용량 {sharedQuantity(sum('capacity'), kind)} · 예약 {sharedQuantity(sum('reserved'), kind)} · 여유 {sharedQuantity(sum('spare'), kind)}</p>
                <p>서버 관측: {rows.map(row => row.observedAt).join(', ')}</p>
              </> : <>
                <p>{stale && oldRows.length ? '이전 관측 / stale' : '자원 미관측 / 미공유'}</p>
                {oldRows.length > 0 && <p>이전 제공 {sharedQuantity(sum('offered', oldRows), kind)} · 현재 측정값으로 사용하지 않음 · 서버 관측 {oldRows.map(row => row.observedAt).join(', ')}</p>}
              </>}
            </div>;
          })}
          <p>GPU·스토리지: {['gpu', 'storage'].map(kind => {
            const units = kind === 'gpu' ? 'devices' : 'bytes';
            const rows = rowsFor(node, kind, units);
            return `${kind} ${rows.length ? `공유 제공 ${sharedQuantity(rows.reduce((sum, row) => sum + (row.offered ?? 0), 0), kind)}` : '미관측 / 미공유 (물리 하드웨어 부재를 뜻하지 않음)'}`;
          }).join(' · ')}</p>
          <p>OS·주소·실사용률: 미관측 · 자원 측정과 실행 허용은 별개</p>
        </article>;
      })}
    </div>
  </section>;
}
