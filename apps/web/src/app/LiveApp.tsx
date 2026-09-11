import React, { useEffect, useState } from 'react';
import { LiveOverview, freshNodes, parseOverview, total } from '@/features/dashboard/liveData';
import './live.css';

const testNames: Record<string,string> = {
  isolation: '프로세스 격리·자원 제한', output: '실제 출력 수집·해시 검증',
  fail: '작업 실패 감지', sleep: '제한 시간 종료·정리', 'receipt-recovery': '송신 프로세스 중단 후 영수증 복구',
};
const stamp = (value?: string|null) => value ? new Date(value).toLocaleString('ko-KR', { hour12:false }) : '관측 없음';
const gib = (value: number|null) => value === null ? '—' : (value/1024**3).toFixed(2);

export const LiveApp: React.FC = () => {
  const [data,setData] = useState<LiveOverview|null>(null);
  const [error,setError] = useState<string|null>(null);
  const [tab,setTab] = useState('overview');
  const [revision,setRevision] = useState(0);
  const [theme,setTheme] = useState<'dark'|'light'>('dark');
  useEffect(() => { document.documentElement.setAttribute('data-theme',theme); },[theme]);
  useEffect(() => {
    let stopped=false;
    let timer: ReturnType<typeof setTimeout>;
    let abort: AbortController;
    async function refresh() {
      abort=new AbortController();
      const timeout=setTimeout(() => abort.abort(),8000);
      try {
        const response=await fetch('/pilot/v1/overview',{cache:'no-store',signal:abort.signal});
        if (!response.ok) throw new Error('관측 서버에 연결할 수 없습니다.');
        const next=parseOverview(await response.json());
        if (!stopped) { setData(next);setError(null); }
      } catch {
        if (!stopped) { setError('관측 서버에 연결할 수 없습니다. 마지막 정보를 현재 상태로 표시하지 않습니다.');setData(null); }
      } finally {
        clearTimeout(timeout);
        if (!stopped) timer=setTimeout(refresh,5000);
      }
    }
    void refresh();
    return () => { stopped=true;clearTimeout(timer);abort?.abort(); };
  },[revision]);
  const online=data ? freshNodes(data) : [];
  const cpu=total(online,'cpuCores');
  const memory=total(online,'memoryTotalBytes');
  const used=total(online,'memoryUsedBytes');
  const active=data?.runs.filter(r => ['scheduled','running','verifying','recovering'].includes(r.state)).length ?? 0;
  const passed=data?.tests.filter(t => t.passed).length ?? 0;
  return <div className="live-shell">
    <header className="live-header">
      <div><strong>SaintVision · INV</strong><span>실제 연결 콘솔</span></div>
      <nav aria-label="주 메뉴">{[['overview','전체 현황'],['nodes','연결된 Node'],['tests','실행·복구 기록'],['guide','사용 안내']].map(([key,label]) =>
        <button key={key} aria-current={tab===key?'page':undefined} onClick={() => setTab(key)}>{label}</button>)}</nav>
      <button aria-label="화면 테마 변경" onClick={() => setTheme(theme==='dark'?'light':'dark')}>{theme==='dark'?'밝게':'어둡게'}</button>
      {['localhost','127.0.0.1','192.168.45.99'].includes(window.location.hostname) && <a href="http://127.0.0.1:18100" target="_blank" rel="noreferrer">개발 Studio ↗</a>}
    </header>
    <main className="live-main">
      <section className="live-banner">
        <div><h1>실제 연결된 Node 현황</h1><p>서버 {data?.serverAddress ?? '—'} · 온라인 {data ? online.length : '—'} / 등록 {data?.nodes.length ?? '—'}대 · 활성 작업 {data ? active : '—'}건</p></div>
        <button onClick={() => setRevision(v => v+1)}>새로고침</button>
      </section>
      <p className="live-meta">5초마다 서버 조회 · 마지막 조회 {stamp(data?.generatedAt)} · Node 응답은 mTLS 인증으로 확인합니다.</p>
      {error && <div className="live-error" role="alert">{error}</div>}
      {!data && !error && <p role="status">실제 연결 정보를 불러오는 중입니다…</p>}
      {data && (tab==='overview'||tab==='nodes') && <>
        <div className="live-metrics">
          <article><h2>관측 CPU</h2><strong>{cpu===null?'—':cpu} <small>논리 코어</small></strong><p>응답이 확인된 Linux 환경</p></article>
          <article><h2>관측 메모리 사용 / 전체</h2><strong>{gib(used)} / {gib(memory)} <small>GiB</small></strong><p>PC별 자원을 관측한 합계</p></article>
          <article><h2>제공 승인된 실행 자원</h2><strong>{(data.offered.cpu ?? 0)/1000} <small>CPU 코어</small></strong><p>메모리 {gib(data.offered.memory ?? 0)} GiB · 관측 용량과 구분</p></article>
          <article><h2>실행·복구 시험</h2><strong>{data.tests.length ? <>{passed} / {data.tests.length} <small>통과</small></> : '대기 중'}</strong><p>{data.tests.length?'실제 Node 실행 기록':'아직 시험 기록이 없습니다'}</p></article>
        </div>
        <p className="live-note">GPU·VRAM·디스크 용량은 아직 수집하지 않았습니다. 서버 PC는 현재 Control Plane 역할이며 실행 Node로 등록되지 않았습니다.</p>
        <section className="live-panel"><h2>등록된 Node</h2>
          {!data.nodes.length && <p>등록된 Node가 없습니다.</p>}
          {data.nodes.map(node => <article className="live-node" key={node.nodeId}>
            <div className="live-node-title"><h3>{node.address ?? node.nodeId}</h3><span className={'live-badge '+(online.includes(node)?'ok':'warn')}>{online.includes(node)?'ONLINE':node.status==='online'?'응답 지연':node.status.toUpperCase()}</span></div>
            <dl><div><dt>Node ID</dt><dd>{node.nodeId}</dd></div><div><dt>실행 환경</dt><dd>{node.osType ?? '미수집'} · Node가 관측한 환경</dd></div>
              <div><dt>마지막 heartbeat</dt><dd>{stamp(node.lastHeartbeatAt)}</dd></div><div><dt>자원 관측 시각</dt><dd>{stamp(node.lastSnapshotAt)}</dd></div>
              <div><dt>CPU 가동률</dt><dd>{online.includes(node)&&node.cpuUsagePercent!==null?node.cpuUsagePercent+'%':'미확인'}</dd></div>
              <div><dt>실행 범위</dt><dd>{node.profileVersion==='lan-test-v1'?'지정된 합성 시험 작업':'연결·자원 관측'}</dd></div></dl>
          </article>)}
        </section>
        <section className="live-panel"><h2>실제 사용자 작업</h2>{!data.runs.length ? <p>등록된 사용자 작업이 없습니다.</p> : data.runs.map(run => <p key={run.runId}>{run.runId} · {run.state}</p>)}
          <p className="live-note">서버 PC의 개발 Studio에서 프로젝트·AI 도구·CPU 작업을 사용할 수 있습니다. 이 목록은 원격 Node의 제품 Run이며 로컬 개발 작업 기록과 구분합니다.</p>
        </section>
      </>}
      {data && (tab==='overview'||tab==='tests') && <section className="live-panel"><h2>실행·복구 시험 기록</h2>
        <p className="live-note">별도 합성 입력으로 수행한 Node 구성요소 시험입니다. 일반 사용자 Run·승인·Evidence 통합 시험과 구분합니다.</p>
        {!data.tests.length && <p>아직 실행된 시험이 없습니다. 결과가 도착하면 자동으로 표시됩니다.</p>}
        {data.tests.map((test,index) => <details className="live-test" key={test.test+index}>
          <summary><span>{testNames[test.test] ?? test.test}</span><span className={'live-badge '+(test.passed?'ok':'warn')}>{test.passed?'통과':'실패'}</span><time>{stamp(test.completedAt)}</time></summary>
          <dl><div><dt>실행 식별자</dt><dd>{test.commandId ?? '—'}</dd></div><div><dt>종료 코드 / 사유</dt><dd>{test.exitCode ?? '—'} / {test.reason ?? (test.sameReceipt?'기존 종료 영수증 복구':'—')}</dd></div>
            <div><dt>프로세스 종료 확인</dt><dd>{test.stopped?'확인됨':test.sameReceipt?'기존 영수증과 일치':'—'}</dd></div><div><dt>출력 SHA-256</dt><dd>{test.outputSha256 ?? '해당 없음'}</dd></div></dl>
          {test.stdout && <><h3>표준 출력</h3><pre>{test.stdout}</pre></>}{test.stderr && <><h3>표준 오류</h3><pre>{test.stderr}</pre></>}
        </details>)}
      </section>}
      {tab==='guide' && <section className="live-panel live-guide"><h2>처음 사용하는 순서</h2>
        <ol><li><strong>서버 PC에서 접속</strong><p>브라우저에서 현재 주소 <code>http://localhost:3000</code>을 엽니다. 다른 PC에서는 <code>http://192.168.45.99:3000</code>으로 접속합니다.</p></li>
          <li><strong>연결된 Node 확인</strong><p>‘연결된 Node’에서 실제 IP, ONLINE 표시, 마지막 heartbeat를 확인합니다. 숫자가 늘어나려면 해당 PC에 Node를 설치하고 등록해야 합니다.</p></li>
          <li><strong>실행·복구 기록 확인</strong><p>각 항목을 눌러 실제 종료 코드, 출력과 해시를 확인합니다. ‘통과’는 해당 시험의 기대 결과를 확인했다는 뜻입니다. 실패 감지 시험의 종료 코드 7도 기대한 결과입니다.</p></li>
          <li><strong>개발 업무 시작</strong><p>서버 Windows의 ‘SaintVision 개발 시작’ 바로가기를 엽니다. 개발 Studio에서 프로젝트와 Workspace를 선택해 Orca·Codex·Claude·Antigravity를 열고, Python 테스트·CPU 학습과 결과 다운로드를 사용할 수 있습니다. 원격 Node 작업·GPU 학습은 아직 활성화되지 않았습니다.</p></li>
        </ol><h3>연결이 끊겼을 때</h3><p>다른 PC의 Docker Desktop과 Node 컨테이너가 실행 중인지 확인합니다. ‘응답 지연’ 또는 OFFLINE이면 자원을 현재 사용 가능한 것으로 계산하지 않습니다. 서버 PC 재시작 후에는 관측 서비스를 다시 시작해야 합니다.</p>
        <p className="live-note">현재는 개발·검증용 내부망 연결입니다. 재부팅 자동 시작, 인증서 갱신과 일반 사용자 로그인은 후속 구성 항목입니다.</p>
      </section>}
    </main>
  </div>;
};
