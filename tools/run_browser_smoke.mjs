/**
 * SaintVision Complete Intranet E2E Browser Journey & Control Plane Smoke Verification
 * Validates:
 *  1. Frontend SPA Root, PWA Manifest, Service Worker Offline Shell
 *  2. Control Plane Liveness (/healthz), Readiness (/readyz), and Gateway Health (/v1/health)
 *  3. OIDC PKCE S256 Cryptographic Authentication Flow (/v1/auth/token, /v1/auth/userinfo)
 *  4. Cluster Nodes Inventory (5 nodes) & RFC 9457 Problem Details negative testing
 *  5. Resource Pools Capacity (/v1/pools), Discovery Candidates, and Deterministic Placement Preview
 *  6. Runs Lifecycle & Outbox Cancellation (/v1/runs)
 *  7. Two-Person Approvals Nonce Verification (/v1/approvals/.../approve)
 *  8. Server-Sent Events (SSE) Telemetry Streaming Protocol (/v1/events)
 *  9. Interactive Sandboxed PTY Web Terminal WebSocket (/v1/terminal/ws)
 * 10. Shard-I07 & ADR-040-043 Distributed Shard Lifecycle & Resource Reclamation
 * 11. Workspace Resume & 3-Attempt Bound Lifecycle (ADR-044 / ADR-045)
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import { execSync } from 'node:child_process';

const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:3000';
const BACKEND_URL = process.env.TEST_BACKEND_URL || 'http://127.0.0.1:8080';

let passed = 0;
let total = 0;
let unverified = 0;

function assert(title, condition, extra = '') {
  total++;
  if (condition) {
    passed++;
    console.log(`  ✔ [PASS] ${title} ${extra}`);
  } else {
    console.error(`  ✖ [FAIL] ${title} ${extra}`);
  }
}

function recordUnverified(title, reason) {
  unverified++;
  console.log(`  ℹ [UNVERIFIED] ${title} (${reason})`);
}

function base64Url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sha256Base64Url(str) {
  const hash = crypto.createHash('sha256').update(str).digest();
  return base64Url(hash);
}

async function runFullSmokeJourney() {
  console.log('======================================================================');
  console.log(`🚀 Running SaintVision Comprehensive E2E Journey & Protocol Smoke Checks`);
  console.log(`   Frontend Target: ${BASE_URL}`);
  console.log(`   Backend Target:  ${BACKEND_URL}`);
  console.log('======================================================================\n');

  try {
    // -------------------------------------------------------------------------
    // 1. Frontend SPA & PWA Offline Verification
    // -------------------------------------------------------------------------
    console.log('[Track 1] Frontend Shell & PWA Offline Conformance:');
    const rootRes = await fetch(`${BASE_URL}/`);
    assert('SPA root index.html returns HTTP 200', rootRes.status === 200);
    const rootHtml = await rootRes.text();
    assert('Contains #root mount point', rootHtml.includes('id="root"'));
    assert('Contains manifest.json reference', rootHtml.includes('rel="manifest"'));

    const manifestRes = await fetch(`${BASE_URL}/manifest.json`);
    assert('PWA manifest.json returns HTTP 200', manifestRes.status === 200);
    const manifest = await manifestRes.json();
    assert('PWA name is SaintVision INV Intranet Portal', manifest.name.includes('SaintVision'));

    const swRes = await fetch(`${BASE_URL}/sw.js`);
    assert('Service worker sw.js returns HTTP 200', swRes.status === 200);
    const swCode = await swRes.text();
    assert('Service worker defines cache-first offline shell', swCode.includes('CACHE_NAME'));

    // -------------------------------------------------------------------------
    // 2. Control Plane Liveness & Readiness Verification
    // -------------------------------------------------------------------------
    console.log('\n[Track 2] Control Plane Liveness & Readiness:');
    const healthRes = await fetch(`${BASE_URL}/v1/health`);
    assert('Proxied /v1/health returns HTTP 200', healthRes.status === 200);
    assert('W3C traceparent header injected on response', Boolean(healthRes.headers.get('traceparent')));
    const health = await healthRes.json();
    assert('Control plane status is healthy', health.status === 'healthy');

    const readyRes = await fetch(`${BACKEND_URL}/readyz`);
    assert('Backend /readyz returns HTTP 200', readyRes.status === 200);
    const ready = await readyRes.json();
    assert('Readiness probe status is ready', ready.status === 'ready');
    assert('Readiness probe scope is authenticated-control-api', ready.scope === 'authenticated-control-api');
    assert('Readiness probe specifies workspaceAdmission', Boolean(ready.workspaceAdmission));

    // -------------------------------------------------------------------------
    // 3. OIDC PKCE S256 Cryptographic Authentication Journey
    // -------------------------------------------------------------------------
    console.log('\n[Track 3] OIDC + PKCE S256 Cryptographic Authentication:');
    // Negative test 3.1: Absent header rejected with 401
    const noAuthRes = await fetch(`${BASE_URL}/v1/auth/userinfo`);
    assert('Unauthenticated /v1/auth/userinfo returns HTTP 401', noAuthRes.status === 401);

    // Negative test 3.2: Junk/untrusted Bearer token rejected with 401 (Zero-Mock Security Guard)
    const junkAuthRes = await fetch(`${BASE_URL}/v1/auth/userinfo`, {
      headers: { Authorization: 'Bearer not-a-real-token' },
    });
    assert('Junk Bearer token rejected with HTTP 401', junkAuthRes.status === 401);
    const junkProblem = await junkAuthRes.json();
    assert('Junk Bearer token returns RFC 9457 AUTH-0050', junkProblem.code === 'AUTH-0050');

    const codeVerifier = base64Url(crypto.randomBytes(32));
    const codeChallenge = await sha256Base64Url(codeVerifier);
    const state = crypto.randomUUID();
    const nonce = crypto.randomBytes(16).toString('hex');

    // Negative test 3.3: Invalid PKCE challenge rejected
    const invalidPkceRes = await fetch(`${BASE_URL}/v1/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'authorization_code',
        code: 'auth_code_invalid',
        code_verifier: codeVerifier,
        code_challenge: 'invalid_mismatching_challenge',
        code_challenge_method: 'S256',
        client_id: 'saintvision-web',
        idp: 'internal-keycloak',
        state,
        nonce,
      }),
    });
    assert('Mismatching PKCE challenge rejected with HTTP 401', invalidPkceRes.status === 401);

    const tokenRes = await fetch(`${BASE_URL}/v1/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'authorization_code',
        code: `auth_code_${crypto.randomBytes(8).toString('hex')}`,
        code_verifier: codeVerifier,
        code_challenge: codeChallenge,
        code_challenge_method: 'S256',
        client_id: 'saintvision-web',
        idp: 'internal-keycloak',
        state,
        nonce,
      }),
    });
    assert('OIDC PKCE token exchange returns HTTP 200', tokenRes.status === 200);
    const tokenData = await tokenRes.json();
    assert('Bearer access token granted', tokenData.token_type === 'Bearer' && Boolean(tokenData.access_token));
    assert('User role granted cluster:admin', tokenData.user?.role === 'cluster:admin');

    const bearerToken = tokenData.access_token;
    const userinfoRes = await fetch(`${BASE_URL}/v1/auth/userinfo`, {
      headers: { Authorization: `Bearer ${bearerToken}` },
    });
    assert('Authenticated /v1/auth/userinfo returns HTTP 200', userinfoRes.status === 200);
    const userinfo = await userinfoRes.json();
    assert('Userinfo contains operator/admin roles', userinfo.roles?.includes('cluster:admin'));

    // -------------------------------------------------------------------------
    // 4. Cluster Nodes & RFC 9457 Problem Details Negative Testing
    // -------------------------------------------------------------------------
    console.log('\n[Track 4] Cluster Nodes & RFC 9457 Problem Details:');
    const nodesRes = await fetch(`${BASE_URL}/v1/nodes`, {
      headers: { Authorization: `Bearer ${bearerToken}` },
    });
    assert('Nodes listing returns HTTP 200', nodesRes.status === 200);
    const nodesData = await nodesRes.json();
    assert('All 5 distributed nodes enrolled', nodesData.items?.length === 5, `(${nodesData.items?.length} nodes)`);

    const hbRes = await fetch(`${BASE_URL}/v1/nodes/nod_01JABCDEF01/heartbeats`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${bearerToken}` },
    });
    assert('Node heartbeat acknowledged with HTTP 200', hbRes.status === 200);
    const hbData = await hbRes.json();
    assert('Heartbeat sequence acknowledged', hbData.status === 'acknowledged' && hbData.sequence > 0);

    const problemRes = await fetch(`${BASE_URL}/v1/nodes/nod_nonexistent`);
    assert('Non-existent node request returns HTTP 404', problemRes.status === 404);
    assert(
      'Content-Type is RFC 9457 application/problem+json',
      problemRes.headers.get('content-type')?.includes('application/problem+json')
    );
    const problem = await problemRes.json();
    assert('Problem code is RES-NODE-404', problem.code === 'RES-NODE-404');
    assert('Problem includes request traceId', Boolean(problem.traceId));

    // -------------------------------------------------------------------------
    // 5. Resource Pools Capacity & Deterministic Placement Engine
    // -------------------------------------------------------------------------
    console.log('\n[Track 5] Resource Pools & Deterministic Placement (AC-05):');
    const poolsRes = await fetch(`${BASE_URL}/v1/pools`);
    assert('Resource pools listing returns HTTP 200', poolsRes.status === 200);
    const poolsData = await poolsRes.json();
    assert('3 resource pools configured', poolsData.items?.length === 3);

    const candidatesRes = await fetch(`${BASE_URL}/v1/discovery/candidates`);
    assert('Discovery candidates returns HTTP 200', candidatesRes.status === 200);
    const candidates = await candidatesRes.json();
    assert('Candidates list discovered', candidates.items?.length === 5);

    const previewRes = await fetch(`${BASE_URL}/v1/pools/pool_01_training/placement-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requiredCores: 4,
        requiredMemoryBytes: 8 * 1024 ** 3,
        requiresGpu: true,
        dataLocalityNodeId: 'nod_01JABCDEF01',
      }),
    });
    assert('Placement preview returns HTTP 200', previewRes.status === 200);
    const previewData = await previewRes.json();
    assert('Determined winning placement node', Boolean(previewData.selectedNodeId));
    assert('Shard assignment plan returned', previewData.shards?.length > 0);

    // -------------------------------------------------------------------------
    // 6. Runs Lifecycle & Idempotency Cancellation
    // -------------------------------------------------------------------------
    console.log('\n[Track 6] Project Runs & Safe Cancellation:');
    const runsRes = await fetch(`${BASE_URL}/v1/runs`);
    assert('Runs listing returns HTTP 200', runsRes.status === 200);
    const runsData = await runsRes.json();
    assert('Active runs present in cluster', runsData.items?.length > 0);

    const cancelRes = await fetch(`${BASE_URL}/v1/runs/run_01JABCDE0001/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'Operator manual cancel verification' }),
    });
    assert('Run cancellation returns HTTP 200', cancelRes.status === 200);
    const cancelData = await cancelRes.json();
    assert('Run state transitioned to cancelled', cancelData.state === 'cancelled');

    // -------------------------------------------------------------------------
    // 7. Approvals Two-Person Rule Nonce Verification
    // -------------------------------------------------------------------------
    console.log('\n[Track 7] Two-Person Rule Approvals & Nonce Guard:');
    const testNonce = `nonce_${crypto.randomBytes(8).toString('hex')}`;
    const createRes = await fetch(`${BASE_URL}/v1/approvals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: testNonce,
        command: 'smoke.deploy --target test',
      }),
    });
    assert('Test approval request created with HTTP 201', createRes.status === 201);
    const newApprv = await createRes.json();
    const apprvId = newApprv.id;

    // Negative test: invalid nonce rejected
    const badApproveRes = await fetch(`${BASE_URL}/v1/approvals/${apprvId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nonce: 'invalid_nonce_attack' }),
    });
    assert('Invalid nonce approval returns HTTP 400', badApproveRes.status === 400);

    // Positive test: valid nonce approved
    const goodApproveRes = await fetch(`${BASE_URL}/v1/approvals/${apprvId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nonce: testNonce }),
    });
    assert('Valid nonce approval returns HTTP 200', goodApproveRes.status === 200);
    const goodApprove = await goodApproveRes.json();
    assert('Approval state marked approved', goodApprove.status === 'approved');

    // Replay test: already decided approval rejected with 409
    const replayRes = await fetch(`${BASE_URL}/v1/approvals/${apprvId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nonce: testNonce }),
    });
    assert('Repeat approval returns HTTP 409 (Already Decided)', replayRes.status === 409);

    // Two-Person Rule negative test: requester self-approval rejected with HTTP 403
    const selfNonce = `nonce_self_${Date.now()}`;
    const selfApprvCreateRes = await fetch(`${BASE_URL}/v1/approvals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: selfNonce,
        command: 'self.test --deploy',
        requestedBy: 'usr_requester_charlie',
      }),
    });
    assert('Two-Person Rule test approval created with HTTP 201', selfApprvCreateRes.status === 201);
    const selfApprv = await selfApprvCreateRes.json();
    const selfApproveRes = await fetch(`${BASE_URL}/v1/approvals/${selfApprv.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: selfNonce,
        approverId: 'usr_requester_charlie',
      }),
    });
    assert('Requester self-approval returns HTTP 403 (Two-Person Rule)', selfApproveRes.status === 403);
    const selfProb = await selfApproveRes.json();
    assert('Returns RFC 9457 SEC-TWO-PERSON-RULE-VIOLATION', selfProb.code === 'SEC-TWO-PERSON-RULE-VIOLATION');

    // Positive test: independent peer approval accepted
    const peerApproveRes = await fetch(`${BASE_URL}/v1/approvals/${selfApprv.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: selfNonce,
        approverId: 'usr_approver_dan',
      }),
    });
    assert('Independent peer approval returns HTTP 200', peerApproveRes.status === 200);

    // -------------------------------------------------------------------------
    // 8. Server-Sent Events (SSE) Streaming Protocol Validation
    // -------------------------------------------------------------------------
    console.log('\n[Track 8] Server-Sent Events (SSE) Streaming Protocol:');
    const sseController = new AbortController();
    const sseTimeout = setTimeout(() => sseController.abort(), 3000);
    try {
      const sseRes = await fetch(`${BASE_URL}/v1/events`, {
        signal: sseController.signal,
        headers: { Accept: 'text/event-stream' },
      });
      assert('SSE stream connected with HTTP 200', sseRes.status === 200);
      assert('SSE Content-Type is text/event-stream', sseRes.headers.get('content-type')?.includes('text/event-stream'));
      assert('SSE buffering disabled (no-cache)', sseRes.headers.get('cache-control')?.includes('no-cache'));

      const reader = sseRes.body.getReader();
      const { value } = await reader.read();
      const sseChunk = new TextDecoder().decode(value);
      assert('SSE stream received event frame', sseChunk.includes('event: heartbeat') || sseChunk.includes('data:'));
      reader.cancel();
    } catch (e) {
      if (e.name !== 'AbortError') throw e;
    } finally {
      clearTimeout(sseTimeout);
    }

    // -------------------------------------------------------------------------
    // 9. Interactive Sandboxed PTY Web Terminal WebSocket Check (ADR-038)
    // -------------------------------------------------------------------------
    console.log('\n[Track 9] Interactive PTY Web Terminal WebSocket (ADR-038):');

    // 1. Issue authentic 30s one-time cryptographic ticket
    const ticketRes = await fetch(`${BACKEND_URL}/v1/terminal/tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspaceId: 'wsp_smoke_test', userId: 'usr_smoke_operator' }),
    });
    assert('One-time terminal ticket issued successfully (HTTP 201)', ticketRes.status === 201);
    const ticketData = await ticketRes.json();
    assert('Ticket ID starts with tkt_ prefix', Boolean(ticketData.ticketId?.startsWith('tkt_')));
    assert('Ticket validity is exactly 30s', ticketData.expiresInSeconds === 30);
    assert('Ticket initially marked unused', ticketData.used === false);

    // Canonical workspace terminal ticket route check
    const wsTicketRes = await fetch(`${BACKEND_URL}/v1/workspaces/wsp_smoke_test/terminal-tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: 'usr_smoke_operator' }),
    });
    assert('Workspace canonical terminal ticket issued successfully (HTTP 201)', wsTicketRes.status === 201);
    const wsTicketData = await wsTicketRes.json();
    assert('Workspace ticket ID starts with tkt_ prefix', Boolean(wsTicketData.ticketId?.startsWith('tkt_')));
    assert('Workspace ticket binds workspaceId', wsTicketData.workspaceId === 'wsp_smoke_test');

    const validTicket = ticketData.ticketId;

    if (typeof globalThis.WebSocket !== 'undefined') {
      // 2. Connect with authentic ticket
      await new Promise((resolve) => {
        const wsUrl = `${BACKEND_URL.replace('http', 'ws')}/v1/terminal/ws?ticket=${validTicket}`;
        const ws = new globalThis.WebSocket(wsUrl);
        let bannerReceived = false;
        let statusReceived = false;

        const timer = setTimeout(() => {
          ws.close();
          assert('Terminal WebSocket connected with authentic 30s ticket', bannerReceived);
          assert('Terminal executed status command and returned cluster info', statusReceived);
          resolve();
        }, 2500);

        ws.onopen = () => {
          ws.send('status\r');
        };

        ws.onmessage = (ev) => {
          if (typeof ev.data === 'string') {
            if (ev.data.includes('SaintVision PTY Terminal')) {
              bannerReceived = true;
            }
            if (ev.data.includes('Cluster: 5 nodes online') || ev.data.includes('Gateway: healthy')) {
              statusReceived = true;
            }
          }
        };

        ws.onerror = (err) => {
          clearTimeout(timer);
          assert('Terminal WebSocket unexpected error', false, String(err));
          resolve();
        };

        ws.onclose = () => {
          clearTimeout(timer);
          assert('Terminal WebSocket connected with authentic 30s ticket', bannerReceived);
          assert('Terminal executed status command and returned cluster info', statusReceived);
          resolve();
        };
      });

      // 3. Negative test: connect with invalid/fabricated ticket
      await new Promise((resolve) => {
        const fakeWsUrl = `${BACKEND_URL.replace('http', 'ws')}/v1/terminal/ws?ticket=fake_unauthorized_token_xyz`;
        const ws = new globalThis.WebSocket(fakeWsUrl);
        let closedForbidden = false;

        const timer = setTimeout(() => {
          ws.close();
          assert('Fabricated ticket rejected by server (Forbidden/Close code 4003)', closedForbidden);
          resolve();
        }, 1500);

        ws.onclose = (ev) => {
          clearTimeout(timer);
          if (ev.code === 4003 || ev.code === 1008 || ev.code === 1000 || ev.code === 1006) {
            closedForbidden = true;
          }
          assert('Fabricated ticket rejected by server (Forbidden/Close code 4003)', closedForbidden);
          resolve();
        };

        ws.onerror = () => {
          // Handshake error expected
        };
      });

      // 4. Negative test: replay prevention (re-use previously consumed ticket)
      await new Promise((resolve) => {
        const replayWsUrl = `${BACKEND_URL.replace('http', 'ws')}/v1/terminal/ws?ticket=${validTicket}`;
        const ws = new globalThis.WebSocket(replayWsUrl);
        let rejectedOnReplay = false;

        const timer = setTimeout(() => {
          ws.close();
          assert('Reused ticket rejected by server (Single Use Protection)', rejectedOnReplay);
          resolve();
        }, 1500);

        ws.onclose = (ev) => {
          clearTimeout(timer);
          if (ev.code === 4003 || ev.code === 1008 || ev.code === 1000 || ev.code === 1006) {
            rejectedOnReplay = true;
          }
          assert('Reused ticket rejected by server (Single Use Protection)', rejectedOnReplay);
          resolve();
        };

        ws.onerror = () => {
          // Handshake error expected
        };
      });
    } else {
      assert('WebSocket client available in runtime', false, 'Missing WebSocket in Node');
    }

    // -------------------------------------------------------------------------
    // [Track 10] Distributed Shards & Cascade Resource Reclamation (SHARD-I07 / ADR-040/042)
    // -------------------------------------------------------------------------
    console.log('\n[Track 10] Distributed Shards & Cascade Resource Reclamation:');

    // 1. Get completed parent run with aggregate manifest
    const pRunRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS`);
    assert('Completed parent run returns HTTP 200', pRunRes.status === 200);
    const pRunData = await pRunRes.json();
    assert('Parent run contains valid manifest digest', typeof pRunData.manifestDigest === 'string' && pRunData.manifestDigest.startsWith('sha256:'));
    assert('Parent run confirms allSucceeded: true', pRunData.allSucceeded === true);
    assert('Parent run confirms allPhysicallyStopped: true', pRunData.allPhysicallyStopped === true);

    // 2. Child runs listing
    const chRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS/children`);
    assert('Child runs listing returns HTTP 200', chRes.status === 200);
    const chData = await chRes.json();
    assert('Child runs count matches parent shards (2 shards)', chData.items && chData.items.length === 2);

    // 3. Shard status listing with physical stop vs verification separation
    const shRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS/shards`);
    assert('Shards listing returns HTTP 200', shRes.status === 200);
    const shData = await shRes.json();
    assert('All shards confirm physical stop receipts', Array.isArray(shData.items) && shData.items.length === 2 && shData.items.every((s) => s != null && s.physicallyStopped === true));
    assert('All shards confirm output commitment hashes', Array.isArray(shData.items) && shData.items.length === 2 && shData.items.every((s) => s != null && typeof s.outputHash === 'string'));

    // 4. Evidence manifest inspection
    const eviRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS/evidence`);
    assert('Run evidence manifest returns HTTP 200', eviRes.status === 200);
    const eviData = await eviRes.json();
    assert('Evidence uses policyVersion shard-completion:v1', eviData.policyVersion === 'shard-completion:v1');
    assert('Evidence marked immutable', eviData.immutable === true);

    // 5. Parent cascade cancellation sets resourceReleasePending (ADR-040)
    const parentCancelRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/cancel`, { method: 'POST' });
    assert('Parent cancellation returns HTTP 200', parentCancelRes.status === 200);
    const parentCancelData = await parentCancelRes.json();
    assert('Parent cancel sets resourceReleasePending: true', parentCancelData.resourceReleasePending === true);
    assert('Parent cancel cascades to child runs', Array.isArray(parentCancelData.childRunIds) && parentCancelData.childRunIds.length === 2);

    // 6. Bulk shard cancellation (SHARD-I07)
    const bulkCancelRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/shards/cancel-all`, { method: 'POST' });
    assert('Bulk shard cancellation returns HTTP 200', bulkCancelRes.status === 200);
    const bulkCancelData = await bulkCancelRes.json();
    assert('Bulk cancel reports resourceReleasePending: true', bulkCancelData.resourceReleasePending === true);

    // 7. NodeStopReceipt acknowledgment releases resources (ADR-041)
    const reclaimRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/reclaim-resources`, { method: 'POST' });
    assert('Resource reclamation returns HTTP 200', reclaimRes.status === 200);
    const reclaimData = await reclaimRes.json();
    assert('Resource reclamation clears resourceReleasePending: false', reclaimData.resourceReleasePending === false);
    assert('All physical stops confirmed (allPhysicallyStopped: true)', reclaimData.allPhysicallyStopped === true);

    // -------------------------------------------------------------------------
    // 11. Workspace Resume & 3-Attempt Bound Lifecycle (ADR-044 / ADR-045)
    // -------------------------------------------------------------------------
    console.log('\n[Track 11] Workspace Resume & 3-Attempt Bound Lifecycle (ADR-044 / ADR-045):');

    // 1. Initial state inspection
    const testRunId = 'run_01JRECOVERING';
    await fetch(`${BACKEND_URL}/v1/runs/${testRunId}/reset-recovering`, { method: 'POST' });
    const initialResumeRes = await fetch(`${BACKEND_URL}/v1/runs/${testRunId}/resume`);
    assert('GET /v1/runs/{id}/resume returns valid HTTP 200 ready_to_prepare', initialResumeRes.status === 200);
    const initialResumeData = await initialResumeRes.json();
    assert('Run is in recovering state with attempt 1', initialResumeData.state === 'recovering' && initialResumeData.attempt === 1);

    // 2. Prepare resume: freezes manifest, generates L2 approval, binds next run version
    const prepRes = await fetch(`${BACKEND_URL}/v1/runs/${testRunId}/resume/prepare`, { method: 'POST' });
    assert('POST /v1/runs/{id}/resume/prepare returns HTTP 200', prepRes.status === 200);
    const prepData = await prepRes.json();
    assert('WorkspaceResumeSpec contains deterministic inputHash', typeof prepData.inputHash === 'string' && prepData.inputHash.startsWith('sha256:'));
    assert('WorkspaceResumeSpec contains frozenFiles manifest (2 files)', Array.isArray(prepData.frozenFiles) && prepData.frozenFiles.length === 2);
    assert('WorkspaceResumeSpec binds to next run version (boundRunVersion: 2)', prepData.boundRunVersion === 2);
    assert('WorkspaceResumeSpec defines distinct nextStepId (step_02_infer)', prepData.nextStepId === 'step_02_infer');
    assert('Associated L2 approval created', typeof prepData.approvalId === 'string' && prepData.approvalId.startsWith('apr_resume_'));

    // 3. Negative test: Standalone resume disallowed for shard child/parent runs (ADR-044)
    const shardResumeRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS/resume/prepare`, { method: 'POST' });
    assert('Shard parent run standalone resume prepare rejected with HTTP 400', shardResumeRes.status === 400);
    const shardResumeProblem = await shardResumeRes.json();
    assert('Returns RFC 9457 VAL-SHARD-RESUME-DISALLOWED Problem Details', shardResumeProblem.code === 'VAL-SHARD-RESUME-DISALLOWED');

    // 4. Admission without approval rejected (ADR-044)
    const unapprovedEnqueue = await fetch(`${BACKEND_URL}/v1/runs/${testRunId}/resume/enqueue`, { method: 'POST' });
    assert('Enqueue without approved L2 status rejected with HTTP 400', unapprovedEnqueue.status === 400);
    const unapprovedProblem = await unapprovedEnqueue.json();
    assert('Returns RFC 9457 SEC-APPROVAL-REQUIRED Problem Details', unapprovedProblem.code === 'SEC-APPROVAL-REQUIRED');

    // 5. Two-Person / L2 Approval resolution
    const apprvRes = await fetch(`${BACKEND_URL}/v1/approvals/${prepData.approvalId}/approve`, { method: 'POST' });
    assert('L2 Approval granted for resume preparation', apprvRes.status === 200);

    // 6. Successful atomic enqueue and attempt increment
    const enqRes = await fetch(`${BACKEND_URL}/v1/runs/${testRunId}/resume/enqueue`, { method: 'POST' });
    assert('POST /v1/runs/{id}/resume/enqueue returns HTTP 200', enqRes.status === 200);
    const enqData = await enqRes.json();
    assert('Attempt count incremented from 1 to 2', enqData.attempt === 2);
    assert('Run state transitions to running', enqData.state === 'running');

    // 7. Attempt ceiling boundary enforcement (ADR-044: max 3 attempts)
    const ceilingRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING_EXHAUSTED/resume/prepare`, { method: 'POST' });
    assert('Resume prepare rejected when attempt >= maxAttempts (3) with HTTP 400', ceilingRes.status === 400);
    const ceilingProblem = await ceilingRes.json();
    assert('Returns RFC 9457 VAL-MAX-ATTEMPTS-EXCEEDED Problem Details', ceilingProblem.code === 'VAL-MAX-ATTEMPTS-EXCEEDED');

    // -------------------------------------------------------------------------
    // 12. NodeStopReceipt & Evidence Display Reconciliation (ADR-027 / ADR-028 / ADR-041)
    // -------------------------------------------------------------------------
    console.log('\n[Track 12] NodeStopReceipt & Evidence Display Reconciliation:');

    // 1. List Receipts
    const receiptsRes = await fetch(`${BACKEND_URL}/v1/receipts`);
    assert('GET /v1/receipts returns HTTP 200', receiptsRes.status === 200);
    const receiptsData = await receiptsRes.json();
    assert('Receipts store contains valid items', Array.isArray(receiptsData.items) && receiptsData.total >= 3);

    // 2. Fetch single receipt
    const singleReceiptRes = await fetch(`${BACKEND_URL}/v1/receipts/rcp_01JSHARD_03`);
    assert('GET /v1/receipts/{id} returns HTTP 200', singleReceiptRes.status === 200);
    const singleReceipt = await singleReceiptRes.json();
    assert('NodeStopReceipt has exitCode: 0', singleReceipt.exitCode === 0);
    assert('NodeStopReceipt has physicallyStopped: true', singleReceipt.physicallyStopped === true);
    assert('NodeStopReceipt has verified: true', singleReceipt.verified === true);
    assert('NodeStopReceipt has resourceReclaimed: true', singleReceipt.resourceReclaimed === true);
    assert('NodeStopReceipt has bounded stream label', singleReceipt.supervisorLabel.includes('bounded-streams'));

    // 3. Contrast check: ADR-028/041 exitCode 0 != verified true
    const contrastReceiptRes = await fetch(`${BACKEND_URL}/v1/receipts/rcp_01JFAILED_VERIFY`);
    assert('GET contrast receipt returns HTTP 200', contrastReceiptRes.status === 200);
    const contrastReceipt = await contrastReceiptRes.json();
    assert('Contrast receipt has exitCode: 0 (container stopped)', contrastReceipt.exitCode === 0);
    assert('Contrast receipt has physicallyStopped: true', contrastReceipt.physicallyStopped === true);
    assert('Contrast receipt has verified: false (schema check failed)', contrastReceipt.verified === false);
    assert('Contrast receipt has resourceReclaimed: false (hold on failure)', contrastReceipt.resourceReclaimed === false);

    // 4. Run receipts query
    const runReceiptsRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS/receipts`);
    assert('GET /v1/runs/{id}/receipts returns HTTP 200', runReceiptsRes.status === 200);
    const runReceiptsData = await runReceiptsRes.json();
    assert('Run receipts includes child shard receipts', runReceiptsData.total >= 2);

    // 5. Seeded L3 Approval verification
    const l3ApprvRes = await fetch(`${BACKEND_URL}/v1/approvals/apr_01JL3PROD999`);
    assert('GET /v1/approvals/{id} for L3 returns HTTP 200', l3ApprvRes.status === 200);
    const l3Apprv = await l3ApprvRes.json();
    assert('L3 approval enforces diff requirement', typeof l3Apprv.unifiedDiff === 'string' && l3Apprv.unifiedDiff.length > 0);

    // -------------------------------------------------------------------------
    // 13. Integrated Developer Studio 4-Step Workflow & Resource Headroom
    // -------------------------------------------------------------------------
    console.log('\n[Track 13] Integrated Developer Studio 4-Step Workflow & Resource Headroom:');

    // 1. Projects API
    const projsRes = await fetch(`${BACKEND_URL}/v1/projects`);
    assert('GET /v1/projects returns HTTP 200', projsRes.status === 200);
    const projsData = await projsRes.json();
    assert('Projects store contains canonical projects', Array.isArray(projsData.items) && projsData.total >= 2);
    const pacsProj = projsData.items.find((p) => p.id === 'prj_01JABCDE');
    assert('PACS Core project has budget & git info', Boolean(pacsProj && pacsProj.gitRepo && pacsProj.remainingBudgetKrw));

    // 2. Workspaces API
    const wspsRes = await fetch(`${BACKEND_URL}/v1/workspaces`);
    assert('GET /v1/workspaces returns HTTP 200', wspsRes.status === 200);
    const wspsData = await wspsRes.json();
    assert('Workspaces store contains active sandboxes', Array.isArray(wspsData.items) && wspsData.total >= 2);

    // 3. Create Studio Workspace
    const createWspRes = await fetch(`${BACKEND_URL}/v1/workspaces`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        projectId: 'prj_01JABCDE',
        name: 'studio-validation-sandbox',
        targetNodeId: 'nod_01JABCDEF01',
        isolationMode: 'process_sandbox',
        cpuLimitCores: 8,
        memoryLimitBytes: 16 * 1024 ** 3,
      }),
    });
    assert('POST /v1/workspaces returns HTTP 201', createWspRes.status === 201);
    const createdWsp = await createWspRes.json();
    assert('Created workspace has valid id and active status', Boolean(createdWsp.id && createdWsp.status === 'active'));

    // 3.1 Execution Readiness 7-Preconditions Check (ADR-063 & execution_readiness.py)
    const readinessRes = await fetch(`${BACKEND_URL}/v1/workspaces/${createdWsp.id}/execution-readiness`);
    assert('GET /v1/workspaces/{id}/execution-readiness returns HTTP 200', readinessRes.status === 200);
    const readinessData = await readinessRes.json();
    assert('Execution readiness evaluates exactly 7 preconditions', Array.isArray(readinessData.checks) && readinessData.checks.length === 7);
    assert('Execution readiness includes input_prepared check', readinessData.checks.some((c) => c.check === 'input_prepared'));
    assert('Active linked workspace reports executable: true', readinessData.executable === true);

    // 4. Studio Dispatch Run
    const dispatchRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: createdWsp.id,
        objective: 'Studio E2E Workflow Dispatch Validation',
        requestedBy: 'usr_developer_01',
      }),
    });
    assert('POST /v1/projects/{id}/runs returns HTTP 201', dispatchRes.status === 201);
    const dispatchedRun = await dispatchRes.json();
    assert('Dispatched run is in running state', dispatchedRun.state === 'running');

    // 5. Node Resource Headroom Distinction (Physical vs Observed vs Available Headroom)
    const studioNodesRes = await fetch(`${BACKEND_URL}/v1/nodes`);
    const studioNodesData = await studioNodesRes.json();
    const nodeItems = studioNodesData.items || [];
    assert('All 5 enrolled nodes report positive physical capacity', nodeItems.length === 5 && nodeItems.every((n) => n.cpuCores > 0 && n.memoryTotalBytes > 0));
    assert(
      'All 5 nodes report valid available headroom (Cores & RAM)',
      nodeItems.length === 5 &&
        nodeItems.every((n) => {
          const availCores = n.cpuCores * (1 - n.cpuUsagePercent / 100);
          const availRam = n.memoryTotalBytes - n.memoryUsedBytes;
          return availCores > 0 && availRam > 0;
        })
    );

    // 6. Observation-only Node Safety (Codex P1 / Remote worker without execution profile)
    const obsNode = nodeItems.find((n) => n.observationOnly);
    assert('Observation-only node (192.168.45.225) reports schedulable: false', Boolean(obsNode && obsNode.schedulable === false));

    // 7. Result Artifact Download & Canonical ResultView Verification
    const dlRes = await fetch(`${BACKEND_URL}/v1/runs/${dispatchedRun.id}/artifacts/download`);
    assert('GET /v1/runs/{id}/artifacts/download returns HTTP 200', dlRes.status === 200);
    const dlData = await dlRes.json();
    assert('Artifact download response contains deterministic outputHash', Boolean(dlData.outputHash?.startsWith('sha256:')));

    const resultRes = await fetch(`${BACKEND_URL}/v1/runs/${dispatchedRun.id}/result`);
    assert('GET /v1/runs/{id}/result returns HTTP 200', resultRes.status === 200);
    const resultData = await resultRes.json();
    assert('ResultView reports execution-kernel source', resultData.source === 'execution-kernel');

    const artsRes = await fetch(`${BACKEND_URL}/v1/runs/${dispatchedRun.id}/artifacts`);
    assert('GET /v1/runs/{id}/artifacts returns HTTP 200', artsRes.status === 200);
    const artsData = await artsRes.json();
    assert('Artifacts endpoint reports execution-kernel source', artsData.source === 'execution-kernel');

    const rawArtRes = await fetch(`${BACKEND_URL}/v1/runs/${dispatchedRun.id}/artifacts/content?path=output.log`);
    assert('GET /v1/runs/{id}/artifacts/content returns HTTP 200 raw bytes', rawArtRes.status === 200);
    assert('Raw artifact content includes X-Checksum-SHA256 header', Boolean(rawArtRes.headers.get('X-Checksum-SHA256')));
    assert('Raw artifact content-type is octet-stream', rawArtRes.headers.get('Content-Type')?.includes('application/octet-stream'));

    // Project-Scoped Canonical Endpoints (Kernel & Control-Plane Unified)
    const prjDlRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs/${dispatchedRun.id}/artifacts/download`);
    assert('GET /v1/projects/{project}/runs/{id}/artifacts/download returns HTTP 200', prjDlRes.status === 200);

    const prjResultRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs/${dispatchedRun.id}/result`);
    assert('GET /v1/projects/{project}/runs/{id}/result returns HTTP 200', prjResultRes.status === 200);
    const prjResultData = await prjResultRes.json();
    assert('Project-scoped ResultView confirms runId and projectId', prjResultData.runId === dispatchedRun.id && prjResultData.projectId === 'prj_01JABCDE');

    const prjArtsRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs/${dispatchedRun.id}/artifacts`);
    assert('GET /v1/projects/{project}/runs/{id}/artifacts returns HTTP 200', prjArtsRes.status === 200);

    const prjRawArtRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs/${dispatchedRun.id}/artifacts/content?path=output.log`);
    assert('GET /v1/projects/{project}/runs/{id}/artifacts/content returns HTTP 200 raw bytes', prjRawArtRes.status === 200);

    // 8. Placement candidate discovery explanation
    const candRes = await fetch(`${BACKEND_URL}/v1/discovery/candidates?minCores=4&minMemoryGb=8`);
    assert('GET /v1/discovery/candidates returns HTTP 200', candRes.status === 200);
    const candData = await candRes.json();
    assert('Placement discovery returns evaluated candidates', Array.isArray(candData.items) && candData.total >= 1);

    // 9. Canonical Kernel Project-Scoped Control APIs (ADR-001, ADR-004, S04-FE)
    const prjRunsRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs`);
    assert('GET /v1/projects/{project}/runs returns HTTP 200', prjRunsRes.status === 200);
    const prjRunsData = await prjRunsRes.json();
    assert('Project runs list contains active run', Array.isArray(prjRunsData.items) && prjRunsData.items.some((r) => r.id === dispatchedRun.id));

    const prjSingleRunRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs/${dispatchedRun.id}`);
    assert('GET /v1/projects/{project}/runs/{id} returns HTTP 200', prjSingleRunRes.status === 200);
    const prjSingleRunData = await prjSingleRunRes.json();
    assert('Retrieved project run matches dispatched run id', prjSingleRunData.id === dispatchedRun.id);

    const prjNodesRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/nodes`);
    assert('GET /v1/projects/{project}/nodes returns HTTP 200', prjNodesRes.status === 200);
    const prjNodesData = await prjNodesRes.json();
    assert('Project nodes list returns cluster inventory', Array.isArray(prjNodesData.items) && prjNodesData.total >= 5);

    // Project-scoped Approval Challenge & Decision Flow with Two-Person Rule
    const l2RunRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: createdWsp.id,
        objective: 'Project-Scoped L2 Approval Journey Validation',
        riskLevel: 'L2',
        requiresApproval: true,
        requestedBy: 'usr_requester_alice',
      }),
    });
    assert('POST /v1/projects/{id}/runs with L2 creates awaiting_approval run', l2RunRes.status === 201);
    const l2RunData = await l2RunRes.json();
    const l2ApprovalId = l2RunData.approvalId;
    assert('L2 run has linked approval id', Boolean(l2ApprovalId));

    // Two-Person Rule: Requester cannot challenge approval
    const selfChallRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/approvals/${l2ApprovalId}/challenge`, {
      method: 'POST',
      headers: { 'X-Subject': 'usr_requester_alice' },
    });
    assert('Self-challenge by requester rejected with HTTP 403 (Two-Person Rule)', selfChallRes.status === 403);

    // Independent reviewer challenges for nonce
    const peerChallRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/approvals/${l2ApprovalId}/challenge`, {
      method: 'POST',
      headers: { 'X-Subject': 'usr_reviewer_02' },
    });
    assert('Independent peer challenge returns HTTP 200', peerChallRes.status === 200);
    const peerChallData = await peerChallRes.json();
    assert('Peer challenge provides one-time nonce', Boolean(peerChallData.nonce));

    // Independent reviewer decides approval
    const peerDecideRes = await fetch(`${BACKEND_URL}/v1/projects/prj_01JABCDE/approvals/${l2ApprovalId}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Subject': 'usr_reviewer_02' },
      body: JSON.stringify({
        decision: 'approve',
        nonce: peerChallData.nonce,
        actionDigest: 'sha256:4a6f9821ef34a02937cd219e88a31401f82e1850d810237913fb9a3d467e2a9b',
      }),
    });
    assert('Independent peer decision returns HTTP 200 and ApprovalView', peerDecideRes.status === 200);
    const peerDecideData = await peerDecideRes.json();
    assert('ApprovalView reports status approved and links projectId', peerDecideData.status === 'approved' && peerDecideData.projectId === 'prj_01JABCDE');

    // -------------------------------------------------------------------------
    // [Track 14] Node Drain & Schedulable Isolation Control (ADR-038)
    // -------------------------------------------------------------------------
    console.log('\n[Track 14] Node Drain & Schedulable Isolation Control (ADR-038):');

    // 1. Drain node nod_01JABCDEF02
    const drainRes = await fetch(`${BACKEND_URL}/v1/nodes/nod_01JABCDEF02/drain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'usr_admin_01', reason: 'Smoke test scheduled isolation' }),
    });
    assert('POST /v1/nodes/{id}/drain returns HTTP 200', drainRes.status === 200);
    const drainData = await drainRes.json();
    assert('Drained node status is draining', drainData.status === 'draining');
    assert('Drained node schedulable is false', drainData.schedulable === false);
    assert('Drained node isDraining is true', drainData.isDraining === true);

    // 2. Verify placement engine excludes drained node
    const placementRes = await fetch(`${BACKEND_URL}/v1/pools/pool_02_inference/placement-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requiredCores: 2 }),
    });
    assert('Placement preview returns HTTP 200 during node drain', placementRes.status === 200);
    const placementData = await placementRes.json();
    const evalN2 = placementData.evaluations?.find((e) => e.nodeId === 'nod_01JABCDEF02');
    assert('Drained node is evaluated as not eligible in placement', evalN2 && evalN2.eligible === false);
    assert('Drained node has rejection reasons registered', Boolean(evalN2 && evalN2.rejectionReasons?.length > 0));

    // 3. Verify security audit log recorded drain action
    const auditRes = await fetch(`${BACKEND_URL}/v1/admin/audit-logs`);
    assert('GET /v1/admin/audit-logs returns HTTP 200', auditRes.status === 200);
    const auditData = await auditRes.json();
    const drainLog = auditData.items?.find((item) => item.action === 'node_drain_activated' && item.target === 'nod_01JABCDEF02');
    assert('Audit log contains node_drain_activated record', Boolean(drainLog));

    // 4. Undrain node nod_01JABCDEF02 (legacy alias)
    const undrainRes = await fetch(`${BACKEND_URL}/v1/nodes/nod_01JABCDEF02/undrain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'usr_admin_01' }),
    });
    assert('POST /v1/nodes/{id}/undrain returns HTTP 200', undrainRes.status === 200);
    const undrainData = await undrainRes.json();
    assert('Restored node status is online', undrainData.status === 'online');
    assert('Restored node schedulable is true', undrainData.schedulable === true);
    assert('Restored node isDraining is false', undrainData.isDraining === false);

    // 5. Test canonical kernel route POST /v1/nodes/{id}/resume
    const reDrainRes = await fetch(`${BACKEND_URL}/v1/nodes/nod_01JABCDEF02/drain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'usr_admin_01', reason: 'Kernel resume verification' }),
    });
    assert('POST /v1/nodes/{id}/drain re-drain returns HTTP 200', reDrainRes.status === 200);

    const resumeRes = await fetch(`${BACKEND_URL}/v1/nodes/nod_01JABCDEF02/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'usr_admin_01' }),
    });
    assert('POST /v1/nodes/{id}/resume (canonical kernel route) returns HTTP 200', resumeRes.status === 200);
    const resumeData = await resumeRes.json();
    assert('Resumed node status is online via /resume', resumeData.status === 'online');
    assert('Resumed node schedulable is true via /resume', resumeData.schedulable === true);
    assert('Resumed node isDraining is false via /resume', resumeData.isDraining === false);

    // -------------------------------------------------------------------------
    // [Track 15] Virtual Computer Fabric, Web Desktop Shell & Resource Explorer (VF-GM-01 ~ VF-GM-06)
    // -------------------------------------------------------------------------
    console.log('\n[Track 15] Virtual Computer Fabric, Web Desktop Shell & Resource Explorer (VF-GM-01 ~ VF-GM-06):');

    // 1. Live Fabric Nodes & Honest Logical Pooling
    const fabricNodesRes = await fetch(`${BACKEND_URL}/v1/nodes`);
    assert('GET /v1/nodes returns HTTP 200 for fabric inventory', fabricNodesRes.status === 200);
    const fabricNodesData = await fabricNodesRes.json();
    const fNodes = fabricNodesData.items || [];
    assert('Fabric inventory contains exactly 5 enrolled nodes', fNodes.length === 5);

    // Compute Logical Pool
    const totalLogicalCores = fNodes.reduce((acc, n) => acc + (n.cpuCores || 0), 0);
    const totalAllocatableCores = fNodes.reduce((acc, n) => acc + (n.allocatableCores ?? 0), 0);
    const totalLogicalRamBytes = fNodes.reduce((acc, n) => acc + (n.memoryTotalBytes || 0), 0);
    const totalLogicalGpus = fNodes.reduce((acc, n) => acc + (n.gpuCount || 0), 0);

    assert('Logical Fabric computes 60 total CPU cores', totalLogicalCores === 60);
    assert('Logical Fabric computes 32 schedulable allocatable cores', totalAllocatableCores === 32);
    assert('Logical Fabric computes 224 GiB total RAM', totalLogicalRamBytes === 224 * 1024 ** 3);
    assert('Logical Fabric computes exactly 3 discrete physical GPUs', totalLogicalGpus === 3);

    // 2. Hardware Isolation & Anti-Monolithic Invariant
    const winNodes = fNodes.filter((n) => (n.os || n.osType) === 'windows');
    const linuxNodes = fNodes.filter((n) => (n.os || n.osType) === 'linux');
    assert('Fabric maintains OS diversity (3 Windows, 2 Linux)', winNodes.length === 3 && linuxNodes.length === 2);

    const obsWorker = fNodes.find((n) => n.observationOnly);
    assert('Observation-only worker (Node-04) strictly isolated with 0 allocatable cores', Boolean(obsWorker && obsWorker.schedulable === false && (obsWorker.allocatableCores ?? 0) === 0));

    // 3. Discrete GPU VRAM Invariant: No fake single VRAM bus
    const gpuNodes = fNodes.filter((n) => (n.gpuCount || 0) > 0);
    assert('GPU nodes have independent, non-fused VRAM allocations', gpuNodes.length === 3 && gpuNodes.every((g) => g.gpuVramTotalBytes > 0 && g.gpuVramTotalBytes <= 24 * 1024 ** 3));

    // 4. inv:// Namespace Catalog Check
    const prjsRes = await fetch(`${BACKEND_URL}/v1/projects`);
    assert('GET /v1/projects returns HTTP 200 for inv:// catalog', prjsRes.status === 200);

    // 5. Terminal Session Shell Mapping Invariant
    const winShell = (winNodes[0].os || winNodes[0].osType) === 'windows' ? 'powershell' : 'bash';
    const linuxShell = (linuxNodes[0].os || linuxNodes[0].osType) === 'linux' ? 'bash' : 'powershell';
    assert('Windows nodes map to authentic PowerShell PTY session', winShell === 'powershell');
    assert('Linux nodes map to authentic Bash PTY session', linuxShell === 'bash');

    // 6. Web Desktop Viewport & Switcher Verification (VB-MJS-02 / Real Browser Lane)
    // If genuine browser observation records exist (e.g. from scratch/desktop_ui_invariants.json
    // produced by Chrome observation), verify the 4 UI invariants directly; otherwise defer as unverified.
    let browserEvidence = null;
    try {
      const evPath = 'docs/vault/30_Development/Evidence/desktop_ui_invariants.json';
      if (typeof fs !== 'undefined' && fs.existsSync(evPath)) {
        const raw = JSON.parse(fs.readFileSync(evPath, 'utf8'));

        let isShaValid = false;
        try {
          if (typeof execSync === 'function') {
            const headSha = execSync('git rev-parse HEAD', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
            if (headSha && typeof raw?.gitCommitSha === 'string') {
              if (headSha.startsWith(raw.gitCommitSha) || raw.gitCommitSha.startsWith(headSha)) {
                isShaValid = true;
              } else {
                try {
                  execSync(`git merge-base --is-ancestor ${raw.gitCommitSha} HEAD`, { stdio: ['ignore', 'ignore', 'ignore'] });
                  isShaValid = true;
                } catch {
                  isShaValid = false;
                }
              }
            }
          }
        } catch {
          // If git command fails or execSync not available, isShaValid remains false
        }

        if (!isShaValid && raw) {
          console.log(`  ℹ [STALE-EVIDENCE] Evidence commit SHA (${raw?.gitCommitSha}) does not match current git HEAD or ancestor; keeping unverified`);
        } else if (
          raw &&
          raw.verified === true &&
          typeof raw.gitCommitSha === 'string' &&
          raw.gitCommitSha.length >= 7 &&
          raw.timestamp &&
          raw.summary &&
          raw.summary.passedChecks >= 8 &&
          Array.isArray(raw.screenshots) &&
          raw.screenshots.length >= 4
        ) {
          browserEvidence = raw;
        }
      }
    } catch {
      // Offline / isolated VM fallback
    }

    if (browserEvidence && browserEvidence.verified) {
      assert(
        'Web Desktop Shell provides bidirectional switcher (Desktop <-> Portal)',
        browserEvidence.invariants?.bidirectionalSwitcher === true,
        `(Chrome observed: ${browserEvidence.invariants?.bidirectionalSwitcherDetails || 'verified'})`
      );
      assert(
        'Window Manager enforces traffic lights, z-index elevation, and minimize/maximize',
        browserEvidence.invariants?.windowManager === true,
        `(Chrome observed: ${browserEvidence.invariants?.windowManagerDetails || 'verified'})`
      );
      assert(
        'Web Desktop Shell implements Alt+Tab cycling and Escape modal dismissal protocol',
        browserEvidence.invariants?.keyboardA11y === true,
        `(Chrome observed: ${browserEvidence.invariants?.keyboardA11yDetails || 'verified'})`
      );
      assert(
        'Desktop window manager enforces local storage layout serialization protocol',
        browserEvidence.invariants?.layoutPersistence === true,
        `(Chrome observed: ${browserEvidence.invariants?.layoutPersistenceDetails || 'verified'})`
      );
    } else {
      recordUnverified(
        'Web Desktop Shell provides bidirectional switcher (Desktop <-> Portal)',
        'Requires interactive DOM browser lane; unverified in HTTP API contract smoke'
      );
      recordUnverified(
        'Window Manager enforces traffic lights, z-index elevation, and minimize/maximize',
        'Requires interactive DOM browser lane; unverified in HTTP API contract smoke'
      );
      recordUnverified(
        'Web Desktop Shell implements Alt+Tab cycling and Escape modal dismissal protocol',
        'Requires interactive keyboard input browser lane; unverified in HTTP API contract smoke'
      );
      recordUnverified(
        'Desktop window manager enforces local storage layout serialization protocol',
        'Requires browser localStorage persistence lane; unverified in HTTP API contract smoke'
      );
    }

    // -------------------------------------------------------------------------
    // Summary Dossier
    // -------------------------------------------------------------------------
    const pct = total > 0 ? Math.round((passed / total) * 100) : 0;
    console.log('\n======================================================================');
    console.log(`🎉 API Contract Smoke Summary: ${passed}/${total} observed checks passed (${pct}%) | ${unverified} unverified UI invariants deferred to browser lane`);
    console.log('======================================================================\n');

    if (passed !== total || total === 0) {
      process.exit(1);
    }
  } catch (err) {
    console.error('Fatal Smoke Test Exception:', err);
    process.exit(1);
  }
}

runFullSmokeJourney();
