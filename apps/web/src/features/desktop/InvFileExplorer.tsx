import React, { useEffect, useRef, useState } from 'react';
import { fabricObservation as api, replicaStates, type Location, type ReplicaObservation } from '@/shared/api/fabricObservation';
export const InvFileExplorer: React.FC = () => {
  const [items, setItems] = useState<Location[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [uri, setUri] = useState('');
  const [detail, setDetail] = useState<{location: Location; observation: ReplicaObservation} | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const request = useRef<AbortController | null>(null);
  const begin = () => { request.current?.abort(); const controller = new AbortController(); request.current = controller; setLoading(true); setError(''); return controller; };
  useEffect(() => {
    const controller = begin(); setItems([]); setCursor(null); setDetail(null);
    api.locations(undefined, controller.signal).then(page => {
      if (!controller.signal.aborted) { setItems(page.items); setCursor(page.nextCursor); }
    }).catch(() => { if (!controller.signal.aborted) setError('저장소 조회에 실패했습니다. 로그인과 권한을 확인하세요.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); request.current?.abort(); };
  }, [refresh]);
  const open = async (value: string) => {
    const controller = begin(); setUri(value); setDetail(null);
    try {
      const location = await api.resolve(value, controller.signal);
      const observation = await api.replicas(location, controller.signal);
      if (!controller.signal.aborted) setDetail({location, observation});
    } catch { if (!controller.signal.aborted) setError('파일을 조회할 수 없습니다. URI와 접근 권한을 확인하세요.'); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  };
  const more = async () => {
    if (!cursor) return;
    const controller = begin();
    try { const page = await api.locations(cursor, controller.signal); if (!controller.signal.aborted) { setItems(prev => [...prev, ...page.items]); setCursor(page.nextCursor); } }
    catch { if (!controller.signal.aborted) setError('다음 목록 조회에 실패했습니다.'); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  };
  return <section style={{padding: 24, overflow: 'auto', height: '100%'}} aria-label="내 저장소">
    <h2>내 저장소</h2><p>내가 등록한 활성 저장소의 파일 목록입니다. 현재 접근 가능 여부는 별도 확인이 필요합니다.</p>
    <button onClick={() => setRefresh(n => n + 1)}>목록 새로고침</button>
    <form onSubmit={event => { event.preventDefault(); void open(uri); }}>
      <label>파일 URI <input value={uri} maxLength={2048} onChange={event => { request.current?.abort(); setLoading(false); setDetail(null); setError(''); setUri(event.target.value); }} /></label>
      <button disabled={!uri || loading}>조회</button>
    </form>
    {loading && <p role="status">조회 중…</p>}{error && <p role="alert">{error}</p>}
    {!loading && !error && items.length === 0 && <p>등록된 파일이 없습니다.</p>}
    <ul>{items.map(item => <li key={item.locationId}><button disabled={loading} onClick={() => void open(item.uri)}>{item.uri}</button> · {item.byteSize} bytes</li>)}</ul>
    {cursor && <button disabled={loading} onClick={() => void more()}>더 보기</button>}
    {detail && <article><h3>{detail.location.uri}</h3><p>{detail.location.byteSize} bytes</p>
      <p>SHA-256: {detail.location.checksumSha256 ?? '미확인'}</p>
      <p>현재 가용성: 미확인 · 실행 시 재검증 필요</p><p>조회 시각: {detail.observation.observedAt}</p>
      <p>기록된 복제본 상태 (현재 파일 검사 결과가 아님)</p><ul>{replicaStates.map(state => <li key={state}>{state}: {detail.observation.recordedStates[state]}</li>)}</ul>
      <p>전체 기록: {detail.observation.totalRecords}</p></article>}
  </section>;
};
