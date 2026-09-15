import React, { useEffect, useRef, useState } from 'react';
import { fabricObservation as api } from '@/shared/api/fabricObservation';
export const ModelStudioView: React.FC<{projectId: string}> = ({projectId}) => {
  const [modelId, setModelId] = useState(''); const [version, setVersion] = useState('');
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.model>> | null>(null);
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  const clear = () => { request.current?.abort(); setResult(null); setError(''); setLoading(false); };
  useEffect(() => { clear(); setModelId(''); setVersion(''); return () => request.current?.abort(); }, [projectId]);
  const query = async () => {
    clear(); const controller = new AbortController(); request.current = controller; setLoading(true);
    try { const value = await api.model(projectId, modelId, version, controller.signal); if (!controller.signal.aborted) setResult(value); }
    catch { if (!controller.signal.aborted) setError('모델 기록을 조회할 수 없습니다. 프로젝트 권한과 모델 ID·버전을 확인하세요.'); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  };
  return <section style={{padding: 24, overflow: 'auto', height: '100%'}} aria-label="모델 기록 조회">
    <h2>모델 기록 조회</h2><p>프로젝트: {projectId}</p><p>정확한 모델 ID와 버전으로 과거 커밋 기록을 조회합니다.</p>
    <form onSubmit={event => {event.preventDefault(); void query();}}>
      <label>모델 ID <input value={modelId} maxLength={30} onChange={event => {clear(); setModelId(event.target.value);}} /></label>
      <label>버전 <input value={version} maxLength={64} onChange={event => {clear(); setVersion(event.target.value);}} /></label>
      <button disabled={!projectId || !modelId || !version || loading}>기록 조회</button>
    </form>
    {loading && <p role="status">조회 중…</p>}{error && <p role="alert">{error}</p>}
    {result && <article><h3>{result.modelId} · {result.version}</h3><p>커밋 시각: {result.committedAt}</p>
      <p>Manifest SHA-256: {result.manifestHash}</p><p>원본 Run: {result.sourceRunId}</p>
      <p>{result.format} · {result.totalBytes} bytes · {result.shardCount} shards</p>
      <p>라이선스: {result.licensePolicy} · 분류: {result.classification}</p>
      <p>현재 가용성: 미확인 · 실행 시 재검증 필요</p></article>}
  </section>;
};
