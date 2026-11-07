import { useEffect, useMemo, useRef, useState } from 'react';
import type { ApprovalItem } from '@/contracts/types';
import type { ControlRunView, RunResultView, WorkspaceStartView } from '../../../../../packages/contracts-ts/src';
import { apiClient, getAuthToken, onAuthTeardown } from '@/shared/api/client';
import { fetchProjectWorkspaces, type ProjectWorkspace } from '@/shared/api/projectObservation';
import { approveReviewed } from '@/shared/api/approvalReview';
import { decideApproval } from '@/shared/api/kernelMutations';
import { ApprovalReviewPanel } from '@/features/approvals/ApprovalReviewPanel';
import {
  currentFirstWorkspaceRequest, firstScopeKey,
  type WorkspaceScope, type WorkspaceStartPrepareResult,
} from '@/shared/api/firstWorkspace';
import { fetchReadyIntents, FirstIntentCreation, type WorkspaceFirstIntent, type WorkspaceFirstIntentPage } from '@/shared/api/workspaceFirstIntent';

export interface FirstWorkspacePanelProps {
  scope: WorkspaceScope;
  approvals: ApprovalItem[];
  onRunObserved?: (run: ControlRunView) => void;
  onNavigateApprovals?: () => void;
}
function approvalItem(a: NonNullable<WorkspaceStartView['approval']>): ApprovalItem {
  return { id: a.approvalId, runId: a.runId, projectId: a.projectId, requestedBy: a.requesterId,
    actionDigest: a.actionDigest, boundRunVersion: a.runVersion, status: a.status,
    policyReason: a.policyVersion, requiredApprovals: a.requiredApprovals, expiresAt: a.expiresAt };
}

/** The business source gap is explicit: a workspace summary is never a WorkloadSpec.
 * Root owns the missing selected-intent read/atomic create serving contract. Until
 * that exact contract is pinned, creation of a business Run stays unavailable.
 */
export function FirstWorkspacePanel(props: FirstWorkspacePanelProps) {
  return <ScopedFirstWorkspacePanel key={firstScopeKey(props.scope)} {...props} />;
}
function ScopedFirstWorkspacePanel({ scope, onRunObserved, onNavigateApprovals }: FirstWorkspacePanelProps) {
  const key = firstScopeKey(scope);
  const [intent, setIntent] = useState<WorkspaceFirstIntent | null>(null);
  const [page, setPage] = useState<WorkspaceFirstIntentPage | null>(null);
  const request = useMemo(() => currentFirstWorkspaceRequest(scope, intent && page ? { intent, nodeId: page.profile.nodeId } : undefined), [key, intent, page?.profile.nodeId]);
  const [workspaces, setWorkspaces] = useState<ProjectWorkspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState('');
  const [objective, setObjective] = useState('');
  const [image, setImage] = useState('');
  const [executable, setExecutable] = useState('');
  const [argumentsJSON, setArgumentsJSON] = useState('["-B","src/app.py"]');
  const [cpuMillis, setCpuMillis] = useState(500);
  const [memoryBytes, setMemoryBytes] = useState(8388608);
  const [timeoutSeconds, setTimeoutSeconds] = useState(30);
  const intentCreation = useRef<FirstIntentCreation | null>(null);
  const [path, setPath] = useState('src/app.py');
  const [content, setContent] = useState('');
  const [stepId, setStepId] = useState('');
  const [run, setRun] = useState<ControlRunView | null>(null);
  const [frozen, setFrozen] = useState<WorkspaceStartPrepareResult | WorkspaceStartView | null>(null);
  const [result, setResult] = useState<RunResultView | null>(null);
  const [commandId, setCommandId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const live = useRef(0);
  const selection = useRef(0);
  const callbacks = useRef(onRunObserved); callbacks.current = onRunObserved;
  const token = getAuthToken();
  const ready = workspaces.filter(w => w.status === 'ready');

  useEffect(() => {
    const generation = ++live.current; const credential = getAuthToken();
    setWorkspaces([]); setIntent(null); setError(null);
    const stop = onAuthTeardown(() => { live.current++; setIntent(null); setFrozen(null); setResult(null); setRun(null); setError('인증이 종료되었습니다. 다시 로그인하세요.'); });
    if (credential) fetchProjectWorkspaces(scope.projectId).then(rows => {
      if (live.current === generation && getAuthToken() === credential) setWorkspaces(rows);
    }).catch(err => { if (live.current === generation && getAuthToken() === credential) setError(err.message); });
    return () => { live.current++; selection.current++; stop(); };
  }, [key, token, refresh]);

  useEffect(() => {
    const chosen = ++selection.current; const generation = live.current; const credential = getAuthToken();
    setPage(null); setIntent(null); intentCreation.current = null;
    if (!credential || !workspaceId || !ready.some(w => w.workspaceId === workspaceId)) return;
    fetchReadyIntents(scope, workspaceId).then(loaded => {
      if (selection.current === chosen && stillCurrent(generation, credential)) { setPage(loaded); setError(null); }
    }).catch(err => { if (selection.current === chosen && stillCurrent(generation, credential)) setError(err.message); });
  }, [key, workspaceId, workspaces, token]);

  async function action(operation: () => Promise<void>) {
    const generation = live.current; const credential = getAuthToken();
    if (busy || !credential) return;
    setBusy(true); setError(null);
    try { request.assertCurrent(); await operation(); }
    catch (err) {
      if (live.current === generation && getAuthToken() === credential) {
        // A transport/shape/5xx failure cannot tell whether the server committed.
        setUncertain(true); setError(err instanceof Error ? err.message : '서버 요청이 거부되었습니다.');
      }
    } finally { if (live.current === generation && getAuthToken() === credential) setBusy(false); }
  }
  function stillCurrent(generation: number, credential: string | null) {
    return live.current === generation && getAuthToken() === credential && credential !== null;
  }
  async function observe() {
    const generation = live.current; const credential = getAuthToken();
    const observation = await request.observe();
    if (!stillCurrent(generation, credential)) return;
    setFrozen(observation); setRun(observation.run); callbacks.current?.(observation.run);
    const resultView = await apiClient<RunResultView>(`/v1/projects/${encodeURIComponent(scope.projectId)}/runs/${observation.run.runId}/result`);
    if (!stillCurrent(generation, credential)) return;
    if (resultView?.runId !== observation.run.runId) throw new Error('다른 Run의 결과 응답입니다.');
    setResult(resultView);
  }
  useEffect(() => {
    if (!frozen) return;
    let active = true; let polling = false;
    const timer = setInterval(async () => {
      if (!active || polling || busy || !getAuthToken()) return;
      polling = true;
      try { await observe(); }
      catch (err) { if (active) { setResult(null); setError(err instanceof Error ? err.message : '서버 상태 조회 실패'); } }
      finally { polling = false; }
    }, 2500);
    return () => { active = false; clearInterval(timer); };
  }, [request, Boolean(frozen), busy]);

  const approval = frozen?.approval;
  const mayEnqueue = Boolean(approval && approval.status === 'approved' && approval.requiredApprovals === 2 &&
    approval.requesterId === scope.subjectId && Date.parse(approval.expiresAt) > Date.now() &&
    approval.runVersion === run?.version && run.state === 'awaiting_approval');
  return <section id="first-workspace" data-testid="first-workspace-panel" aria-label="첫 CPU Workspace 실행" style={{ padding: 16, border: '1px solid var(--color-border-subtle)' }}>
    <h3>첫 CPU Workspace 요청</h3>
    <p>생성은 draft 등록입니다. 준비는 입력 동결과 두 사람 승인 요청입니다. Enqueue 이후에도 실행·완료는 실제 서버 관측으로 확인합니다. Terminal은 이 파일럿에서 사용하지 않습니다.</p>
    {!token && <p role="alert">현재 인증이 필요합니다.</p>}
    <label>Ready Workspace <select aria-label="Ready Workspace" disabled={busy || Boolean(run) || uncertain} value={workspaceId} onChange={e => { selection.current++; setWorkspaceId(e.target.value); setIntent(null); }}>
      <option value="">선택</option>{ready.map(w => <option key={w.workspaceId} value={w.workspaceId}>{w.name} ({w.workspaceId})</option>)}
    </select></label>
    {ready.length === 0 && <p role="status">실제 ready Workspace가 없습니다. 기존 Workspace 준비 절차가 완료되어야 합니다.</p>}
    {!intent && <p data-testid="first-intent-prerequisite" role="status">실제 ready Workspace와 현재 CPU intent를 조회·선택해야 합니다. intent가 없으면 아래에서 업무 메타데이터를 등록하세요. Workspace 준비·신원·권한·프로필이 없으면 서버가 차단합니다.</p>}
    <button disabled={busy || !token || Boolean(run) || uncertain} onClick={() => setRefresh(n => n + 1)}>Workspace 다시 조회</button>
    {page && <div>
      <p>관측 {page.observedAt} · 설정된 실행 대상 {page.profile.nodeId} · profile {page.profile.profileVersion}. Workspace의 물리 배치를 뜻하지 않습니다.</p>
      <label>현재 CPU intent <select aria-label="현재 CPU intent" value={intent?.workload.workloadId ?? ''} disabled={busy || Boolean(run) || uncertain} onChange={e => setIntent(page.items.find(item => item.workload.workloadId === e.target.value) ?? null)}>
        <option value="">명시적으로 선택</option>{page.items.map(item => <option key={item.workload.workloadId} value={item.workload.workloadId}>{item.workload.workloadId} · v{item.workloadVersion}</option>)}
      </select></label>
      {page.items.length === 0 && <p role="status">현재 Workspace에 등록된 실행 intent가 없습니다.</p>}
      {page.nextCursor && <button disabled={busy || Boolean(run) || uncertain} onClick={() => void action(async () => {
        const chosen = selection.current; const generation = live.current; const credential = getAuthToken();
        const next = await fetchReadyIntents(scope, workspaceId, page.nextCursor!);
        if (chosen === selection.current && stillCurrent(generation, credential)) {
          if (next.workspaceVersion !== page.workspaceVersion) throw new Error('Workspace가 변경되었습니다. 다시 조회하세요.');
          setPage({ ...next, items: [...page.items, ...next.items] });
        }
      })}>다음 intent 페이지</button>}
      <fieldset disabled={busy || Boolean(run) || Boolean(intentCreation.current)}>
        <legend>CPU intent 등록 (실행·준비 상태 변경 아님)</legend>
        <label>작업 목적 <input aria-label="작업 목적" maxLength={1000} value={objective} onChange={e => setObjective(e.target.value)} /></label>
        <label>허용 이미지 <select aria-label="허용 이미지" value={image} onChange={e => setImage(e.target.value)}><option value="">선택</option>{page.profile.images.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>허용 실행 파일 <select aria-label="허용 실행 파일" value={executable} onChange={e => setExecutable(e.target.value)}><option value="">선택</option>{page.profile.executables.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>인자 JSON 배열 <input aria-label="인자 JSON 배열" value={argumentsJSON} onChange={e => setArgumentsJSON(e.target.value)} /></label>
        <label>CPU millicores <input aria-label="CPU millicores" type="number" min={1} max={page.profile.maxCpuMillis} value={cpuMillis} onChange={e => setCpuMillis(Number(e.target.value))} /></label>
        <label>메모리 bytes <input aria-label="메모리 bytes" type="number" min={page.profile.minMemoryBytes} max={page.profile.maxMemoryBytes} value={memoryBytes} onChange={e => setMemoryBytes(Number(e.target.value))} /></label>
        <label>제한 seconds <input aria-label="제한 seconds" type="number" min={1} max={page.profile.maxTimeoutSeconds} value={timeoutSeconds} onChange={e => setTimeoutSeconds(Number(e.target.value))} /></label>
      </fieldset>
      <button disabled={busy || !token || Boolean(run) || !objective || !image || !executable} onClick={() => void action(async () => {
        if (!intentCreation.current) {
          const args: unknown = JSON.parse(argumentsJSON);
          if (!Array.isArray(args) || args.some(arg => typeof arg !== 'string')) throw new Error('명령 인자는 문자열 JSON 배열이어야 합니다.');
          intentCreation.current = new FirstIntentCreation(scope, workspaceId, page, { objective, imageDigest: image, command: [executable, ...args],
            resources: { cpuMillis, memoryBytes, gpuCount: 0, minVramBytes: 0 }, timeoutSeconds });
        }
        const chosen = selection.current; const generation = live.current; const credential = getAuthToken();
        const created = await intentCreation.current.submit();
        if (chosen === selection.current && stillCurrent(generation, credential)) {
          setPage({ ...page, items: [...page.items.filter(item => item.workload.workloadId !== created.workload.workloadId), created].sort((a, b) => a.workload.workloadId.localeCompare(b.workload.workloadId)) });
          setIntent(created); setUncertain(false);
        }
      })}>CPU intent 등록 / 같은 요청 재확인</button>
    </div>}
    {intent && <pre data-testid="first-intent" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(intent, null, 2)}</pre>}
    <label>입력 파일 경로 <input aria-label="입력 파일 경로" value={path} disabled={busy || Boolean(frozen) || request.inputLocked} onChange={e => setPath(e.target.value)} /></label>
    <label>CPU 입력 내용 <textarea aria-label="CPU 입력 내용" value={content} disabled={busy || Boolean(frozen) || request.inputLocked} onChange={e => setContent(e.target.value)} /></label>
    <label>Step ID <input aria-label="Step ID" maxLength={200} value={stepId} disabled={busy || Boolean(frozen) || request.inputLocked} onChange={e => setStepId(e.target.value)} /></label>
    <p>내용 합계 ≤32768 UTF-8 bytes, canonical archive ≤65536 bytes, base64·메타데이터 포함 전체 HTTP 요청 ≤65536 bytes. 해시는 입력의 실제 바이트에서 계산합니다.</p>
    <button disabled={busy || !token || Boolean(run) || !intent} onClick={() => void action(async () => {
      const generation = live.current; const credential = getAuthToken();
      const created = await request.create();
      if (stillCurrent(generation, credential)) { setRun(created); callbacks.current?.(created); setUncertain(false); }
    })}>Draft Run 생성 / 같은 요청 재확인</button>
    <button disabled={busy || !token || !run} onClick={() => void action(async () => {
      const generation = live.current; const credential = getAuthToken();
      const current = await request.recoverFrozen();
      if (stillCurrent(generation, credential)) { setFrozen(current); setRun(current.run); callbacks.current?.(current.run); }
    })}>기존 Start의 서버 동결 입력 복원</button>
    <button disabled={busy || !token || !run || !intent || !content || !stepId || Boolean(frozen)} onClick={() => void action(async () => {
      if (!intent) return;
      const generation = live.current; const credential = getAuthToken();
      const prepared = await request.prepare(intent.workload, [{ path, content }], stepId);
      if (stillCurrent(generation, credential)) { setFrozen(prepared); setRun(prepared.run); callbacks.current?.(prepared.run); setUncertain(false); }
    })}>입력 동결·승인 준비 / 같은 요청 재확인</button>
    {run && <p data-testid="first-run-state">Run {run.runId} · {run.state} · version {run.version} · attempt {run.attempt}</p>}
    {frozen && <div data-testid="first-frozen-action">
      <p>Start {frozen.startId} · input SHA-256 {frozen.workload.workspaceStart?.inputSha256} · {frozen.workload.workspaceStart?.inputSizeBytes} bytes</p>
      <p>실제 대상 {frozen.workload.workspaceStart?.nodeId} · profile {frozen.workload.workspaceStart?.profileVersion}</p>
      <p>Action digest {approval?.actionDigest} · 서버 승인 상태 {approval?.status} · 요구 인원 {approval?.requiredApprovals}</p>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(frozen.workload, null, 2)}</pre>
      {approval?.status !== 'approved' && <p role="status">서로 다른 실제 비요청자 두 사람의 현재 승인이 필요합니다. 추가 승인자 신원·권한 연결은 운영 절차이며 이 화면에서 만들 수 없습니다.</p>}
      {approval && approval.requesterId !== scope.subjectId && ['pending', 'approved'].includes(approval.status) && <ApprovalReviewPanel
        approval={approvalItem(approval)} currentUserId={scope.subjectId}
        onApprove={async (_id, _nonce, shown) => { await approveReviewed(approvalItem(approval), shown); await observe(); }}
        onReject={async () => { await decideApproval({ id: approval.approvalId, projectId: scope.projectId, actionDigest: approval.actionDigest }, 'reject'); await observe(); }} />}
      {onNavigateApprovals && <button onClick={onNavigateApprovals}>기존 승인 센터 열기</button>}
      <button disabled={busy || !token} onClick={() => void action(observe)}>현재 승인·Run·결과 조회</button>
      <button disabled={busy || !token || (!mayEnqueue && !commandId && !uncertain)} onClick={() => void action(async () => {
        const generation = live.current; const credential = getAuthToken();
        const queued = await request.enqueue();
        if (stillCurrent(generation, credential)) { setCommandId(queued.commandId); setUncertain(false); await observe(); }
      })}>원래 요청자 enqueue / 같은 요청 재확인</button>
    </div>}
    {commandId && <p data-testid="first-enqueue-accepted">서버 enqueue 접수 command {commandId}. 실제 실행·완료 증거는 아직 별도 확인이 필요합니다.</p>}
    {result && <div data-testid="first-run-result"><p>서버 결과 관측</p><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(result, null, 2)}</pre></div>}
    {error && <p role="alert">{error} 요청 결과가 미확정일 수 있습니다. 같은 요청 재확인은 원래 키와 바이트를 사용합니다. 새 Run으로 대체하지 마세요.</p>}
  </section>;
}
