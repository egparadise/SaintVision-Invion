---
doc_id: "GEMINI-S08-FE-SCENARIO-MATRIX-20260928"
title: "S08-FE 보안 감사·Docker 소켓 차단·Kill Switch·백업 복원 시나리오 매트릭스 (Gemini)"
version: "1.0.2"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T06:50:00+09:00"
source_of_truth: "Git"
tags: ["s08-fe", "acceptance-matrix", "security-console", "docker-socket-isolation", "approval-bypass", "gpu-benchmark", "kill-switch", "audit-ledger", "wal-backup", "gemini"]
---

# S08-FE 보안 감사·Docker 소켓 차단·Kill Switch·백업 복원 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]] (S08-FE 행)
> - [[2026-09-10_01-10-00_KST_S08-FE_Gemini_보안감사_격리_관리자콘솔_개발과정]]
> - [[Frontend 최종 개발 계획]]
> - [[설계 충돌 정정 및 ADR]] (ADR-053/ADR-054/ADR-056, ADR-100)
> - PR #123 Claude r1 독립 검토 (`issuecomment-5859784561`)
> - PR #123 Codex 계약 축 독립 검토 (`issuecomment-5859831617`)
> - PR #123 Claude r2 UI 독립 재대조 (`issuecomment-5859854873`)
> - `apps/web/src/features/admin/AdminSecurityConsole.tsx`
> - `apps/web/src/features/admin/securityEngine.ts`
> - `apps/web/tests/admin-security.test.ts`
> - `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx` (lines 30-145: Priority 4)
> - `apps/web/tests/write-actions-integrity-wiring.test.tsx` (lines 249-321)
> - `services/control-plane/src/inv/app.py`
> - `services/control-plane/src/inv/containment.py`
> - `contracts/v1alpha1/core.schema.json`

---

## 1. 개요 및 수용 목표 (OUT-08 / AC-08)

본 문서는 SaintVision 보안 감사·호스트 격리·관리자 통제 평면의 **S08-FE (보안 감사·Docker 소켓 마운트 차단·승인 우회 방지·합성 GPU 벤치마크·긴급 Kill Switch·재해 복구 WAL 백업 관리자 콘솔 UX)** 트랙을 완결하기 위해, 코디네이터 지시, Codex 차단 지도([[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]), **Codex 계약 축 검토(`issuecomment-5859831617`, F-C1~F-C3)** 및 **Claude UI 독립 검토 r1/r2(`issuecomment-5859784561`, `issuecomment-5859854873`)의 지적을 전면 반영**하여 개정한 **시나리오 매트릭스 정본(v1.0.2)**이다.

본 문서는 `AdminSecurityConsole` 및 `securityEngine` 화면/엔진의 사용자 여정별 기대를 **실제 프런트엔드 프로덕션 컴포넌트 셀렉터(`data-testid`, `button:has-text`, `role="alert"`, `role="status"`, 고정 에러/안내 문구)**와 1:1로 엄격히 대응시키며, **클라이언트 인메모리 보안 시뮬레이션 결과와 백엔드 제어 평면/OS 물리 격리 경계를 철저히 분리**한다.

---

### 1.1 클라이언트 전용 모의 계층 vs 백엔드 정본 제어평면 계약 계층 분리 (F-C3)

Codex 계약 축 검토(F-C3)에 따라, 현재 UI 엔진이 사용하는 클라이언트 전용(client-only) 인메모리 규약과 백엔드 제어 평면 정본(canonical) 계약을 아래와 같이 명확한 대비표로 분리한다.

| 구분 항목 | 클라이언트 전용 모의 계층 (Client-Only UI Simulation)<br>`AdminSecurityConsole.tsx` / `securityEngine.ts` | 백엔드 정본 제어평면 계약 계층 (Backend Canonical Contract)<br>`app.py` / `containment.py` / `core.schema.json` |
|---|---|---|
| **오류 코드 규격** | `SECURITY_VIOLATION` (`securityEngine:139`),<br>`APPROVAL_REQUIRED` (`securityEngine:165`)<br>*(HTTP 계약 없는 프런트엔드 자체 문자열)* | **RFC 7807 ProblemDetails** 정본 오류 코드:<br>• `VAL-0003` (422: Idempotency-Key 누락/길이 오류, 스키마 검증 실패)<br>• `AUTH-0062` (403: operator 권한 `can_contain`/`can_resume` 부재)<br>• `GRAPH-0003` (409: version 불일치 낙관적 락 충돌)<br>• `NODE-0033` (409: recovery_epoch 불일치)<br>• `NODE-0062` (409: 격리/관측 불가 상태 전이 거절)<br>• `LEASE-0003` (409: 활성 리스/작업 미정착 시 해제 거절)<br>• `IDEM-0001` (409: 동일 키 내용 변경 충돌) |
| **승인 토큰 형식** | `apr_01JABCDEF` 등 임의의 비어있지 않은 문자열 (`securityEngine:156`은 non-empty 여부만 검사) | **UUID 형식** (`contracts/v1alpha1/core.schema.json:3051`)<br>사전 인가된 2인 containment approval(`inv.containment_approvals`)을 operation/node/body에 결속하여 서버가 단 1회 원자적 소비(consume, ADR-056) |
| **요청 헤더 및 페이로드** | 단순 JSON 객체 `{ actor: string, reason: string }`<br>*(Idempotency-Key 헤더 없음, `AdminSecurityConsole:66-69`)* | • **헤더**: `Idempotency-Key: string` (1~200자 필수, `containment.py:98`)<br>• **본문**: `ContainmentInput { expectedVersion: integer, reasonCode: "maintenance"\|"incident"\|"operator_request", approvalId: uuid }`, `additionalProperties: false` (`core.schema.json:3032`)<br>• **Actor**: 본문이 아닌 Bearer 인증 토큰(principal.subject_id)에서 추출 |
| **노드 제어 성공 상태** | UI 모의 상태 `🚨 DRAINED (스케줄링 제외)` (`AdminSecurityConsole:728`)<br>*(비계약 상태명)* | `ContainmentResult.control.nodeStatus` canonical enum (`core.schema.json:3086`):<br>**`online` \| `offline` \| `draining` \| `quarantined` \| `null`**<br>*(주의: `drained`는 백엔드 계약에 존재하지 않는 상태명임; drain 요청 시 전이 대상은 `draining`)* |
| **응답 데이터 구조** | 프런트엔드 상태 객체 (로컬 state 업데이트) | `ContainmentResult { requestId: uuid, approvalId: uuid, operation: "kill"\|"clear"\|"drain"\|"resume", control: ContainmentView }` (`core.schema.json:3128`) |
| **원장 및 카운터** | 컴포넌트 마운트 시 생성되는 인메모리 배열 `auditLogs` 및 정적/인메모리 카운터 (`dockerSocketAttemptsBlocked`, `approvalBypassesBlocked`) | PostgreSQL 불변 테이블 (`inv.containment_requests`, `inv.tenant_controls`, `inv.node_controls`) 트랜잭션 원자 기록 (ADR-053) |

---

### 1.2 핵심 합격 기준 (AC-08) 및 클라이언트 시뮬레이션 vs 커널/OS 격리 경계 분리

1. **Docker Socket 미노출 격리 (Zero Exposure Guaranteed)**:
   - **클라이언트 인메모리 정책 검증 계약 (UI Policy Contract)**:
     - `securityEngine.ts:127-140`의 `validateMountPath`는 금지 경로 패턴(`docker.sock`, `//./pipe/docker_engine`, `/var/run/docker`) 매칭을 통해 호스트 Docker 데몬 장악 시도를 원천 차단한다.
     - 차단 시 `dockerSocketAttemptsBlocked` 카운터를 증가시키고, 클라이언트 로컬 감사 원장에 `mount_docker_socket_attempt` 거부(`denied`) 이벤트를 SHA-256 해시 체이닝으로 기록한다.
     - 오류 코드 `SECURITY_VIOLATION`(`securityEngine.ts:139`)은 백엔드 HTTP 계약에 없는 **클라이언트 전용 에러 코드(client-only, HTTP 없음)**이다.
     - **[정적 리터럴 고지]**: 상단 KPI 타일의 `Docker Socket 노출 여부: 0 건 (완전 격리)`(`AdminSecurityConsole.tsx:236`)는 엔진 상태를 읽는 바인딩이 아닌 정적 JSX 리터럴이며, 엔진의 `dockerSocketExposed` 또한 불변 상수 `false`(`securityEngine.ts:78`, `admin-security.test.ts:21`에서 단언)로 고정되어 있다.
   - **백엔드/OS 커널 물리 격리 경계 (Kernel/OS Authority Boundary)**:
     - 프런트엔드의 경로 검증은 UI 마운트 입력창 필터링 게이트이다. 실제 Linux 제한 컨테이너 환경의 `/var/run/docker.sock` 언마운트, seccomp/AppArmor 프로파일 강제, Docker 데몬 소켓 권한(`0660 root:docker`) 격리는 **`UNMEASURED ('실 제한 컨테이너 환경 배선 후')`**로 엄격히 분리한다.
2. **승인 우회 방지 (Zero Bypass Allowed)**:
   - **클라이언트 2인 승인 강제 계약 (UI Approval Contract)**:
     - `securityEngine.ts:155-169`의 `validateExecutionApproval`은 L2(중위험, 승인 ID 필수) 및 L3(고위험) 등급 실행에 대해 `approvalId`가 부재할 경우 실행을 즉시 거절(`APPROVAL_REQUIRED`)한다.
     - 오류 코드 `APPROVAL_REQUIRED`(`securityEngine.ts:165`)는 백엔드 HTTP 계약에 없는 **클라이언트 전용 에러 코드(client-only, HTTP 없음)**이다.
     - L1(저위험)은 자가 승인이 가능하므로 토큰 없이 통과를 허용한다.
     - **[클라이언트 모의 한계 고지]**: 현재 UI 엔진의 L3 검사는 비어있지 않은 임의의 `approvalId` 문자열(`apr_*`) 하나만 주어지면 통과(`securityEngine.ts:156`, `admin-security.test.ts:48`)하므로, 상단 KPI 타일 부제의 `L2/L3 위험 작업 Two-Person 강제`(`AdminSecurityConsole.tsx:246`)는 UI 모의 표현이다. 실제 2인 승인 규약(`services/control-plane/src/inv/app.py:316-356`, `contracts/v1alpha1/core.schema.json:3051`, ADR-056)은 백엔드 제어 평면의 독립 수용 영역이다.
     - 20회 연속 자동화 봇 우회 공격 주입 시 20회 전수 차단되며, `approvalBypassesBlocked`는 최소 22회 이상 누적된다 (`admin-security.test.ts:51-57`). 단, 상단 KPI의 `(우회 허용 0)`(`AdminSecurityConsole.tsx:244`)은 카운터 바인딩이 아닌 정적 텍스트 리터럴이다.
3. **합성 GPU 성능 검증 및 VRAM 격리 (Synthetic GPU Capability)**:
   - **클라이언트 합성 벤치마크 계약 (UI Synthetic Probe)**:
     - `securityEngine.ts:174-199`의 `runSyntheticGpuBenchmark`는 RTX 4090 노드에 대해 82.5 TFLOPS / 4GB VRAM, 그 외 모든 노드(A4000, H100 등)에 대해 19.2 TFLOPS / 2GB VRAM을 결정론적으로 합성 도출한다.
     - 종료 코드 `exitCode: 0`과 증거 식별자(`^evi_gpu_`)를 생성하고 감사 원장에 기록한다.
     - 가용 GPU 노드가 없을 경우 `data-testid="no-gpu-nodes-notice"` 안내 배너를 렌더링하고 실행 버튼을 비활성화하여 위조 노드 합성을 차단한다 (`AdminSecurityConsole.tsx:597-610`).
     - **[정적 리터럴 고지]**: 상단 KPI 타일의 `성공 (Exit 0)`(`AdminSecurityConsole.tsx:252`)은 GPU 노드가 0대여도 상시 표시되는 정적 리터럴이다.
   - **물리 GPU 하드웨어 실행 경계 (Physical Hardware UNMEASURED)**:
     - **[주의 / 정직성 고지]**: UI의 합성 벤치마크는 프런트엔드 프로브 에뮬레이션이며, 실제 물리 GPU 하드웨어(NVIDIA 드라이버, CUDA 툴킷, 물리 Tensor Core, PCIe 버스 전송)의 실측 연산은 **`UNMEASURED ('물리 GPU 장비 및 CUDA 드라이버 배선 후')`**로 엄격히 유지한다.
4. **불변 감사 원장 및 긴급 Kill Switch (Cryptographic Ledger & Kill Switch)**:
   - **클라이언트 로컬 합성 원장 및 SHA-256 해시 체이닝**:
     - `AdminSecurityConsole.tsx:14`의 원장은 컴포넌트 마운트 시마다 새로 인스턴스화되는 **클라이언트 로컬 합성 원장 (백엔드 감사 아님)**이다. 시드 이벤트 4건(`securityEngine.ts:15-66`, `usr_malicious_attacker` 등)과 카운터 1(`:68-69`)로 시작한다.
     - `securityEngine.ts:92-121`의 `logEvent`는 이전 레코드의 `integrityHash`와 현재 이벤트 페이로드(`prevHash|timestamp|actor|action|outcome|details`)를 결합하여 SHA-256 해시를 체이닝한다.
     - **[무결성 검출 한계 고지]**: 해시 계산 페이로드에 `target`, `traceId`, `id` 필드가 누락되어 있어(`securityEngine.ts:104, :224`), `target` 변조는 검출하지 못한다. 따라서 "단 1비트의 변조도 전수 검출"은 과장이며, 결합된 6개 필드의 변조 검출로 한정된다.
     - 또한 `traceId`는 고정 접두어에 난수 1자리를 합성한 것(`securityEngine.ts:56, :102`)으로 테이블에 표출되지 않는다.
   - **긴급 비상 정지(Kill Switch) — 백엔드 API 존재·FE 미연결 및 로컬 무동작 (F-C1)**:
     - **[백엔드 API 현황 (F-C1)]**: 백엔드 제어 평면에는 `GET /v1/operations/kill-switch` (`app.py:310`), `POST /v1/operations/kill-switch` (status 202, `app.py:358`), 및 `POST /v1/operations/kill-switch/clear` (`app.py:370`) 엔드포인트가 이미 구현되어 있으며, `inv.tenant_controls.kill_switch`를 갱신한다(`containment.py:146-157`, ADR-053). POST 호출 시 Bearer identity, operator grant(`can_contain`/`can_resume`), `Idempotency-Key` 헤더, `ContainmentInput` 본문을 요구한다. 이는 물리 전원 차단이 아닌 tenant 실행 장벽과 reconciler를 통한 정합성 있는 정지 규약이다.
     - **[FE 미연결 및 제품 문구 결함 고지]**:
       - 프런트엔드 소스(`apps/web/src`)에는 해당 백엔드 API 경로 참조가 0건(**FE 미연결**)이다.
       - 현재 UI 코드의 제품 문구(`AdminSecurityConsole.tsx:181` "비상 정지 API 미노출 상태로", `AdminSecurityConsole.tsx:830` "백엔드 제어 평면 비상 정지 API가 현재 미노출 상태입니다...")는 **백엔드 실재와 모순되는 제품 문구 결함**이다 (차기 FE 결함 카드 `FE-DEFECT-S08-01`에서 "API 존재하나 FE 미연결"로 정정 필요).
       - 또한 현재 로컬 `emergencyKillSwitchActive` 플래그는 `securityEngine.ts:6, :80, :205-213` 외에 참조되지 않고 핸들러(`AdminSecurityConsole.tsx:41-157`)에 차단 가드가 없다. 즉, **Kill Switch가 켜진 상태에서도 노드 Drain 및 실제 API 호출이 그대로 진행**되며, "모든 모의 작업 디스패치 일시 중지"(`AdminSecurityConsole.tsx:835`)는 동작하지 않는 UI 결함이다 (차기 FE 결함 카드 처리 대상).
     - 물리 클러스터 전체 하드웨어 전원 차단 또는 방화벽 격리는 **`UNMEASURED`**이다.
5. **관리자 인증 세션 가드 및 재해 복구 WAL 백업 (Admin Auth Guard & WAL/PITR)**:
   - **관리자 세션 부재 0-네트워크 호출 가드 (Priority 4 결함 치유 반영)**:
     - `AdminSecurityConsole.tsx:20`은 `currentUser?.id?.trim() || null`을 통해 로그인 세션 식별자(`actor`)를 동적 바인딩한다.
     - `currentUser === null`인 경우 상단에 `data-testid="admin-auth-required-notice"`(`role="alert"`)를 렌더링하고, 노드 Drain/Undrain 클릭 시 네트워크 호출을 **0회(0 network calls)**로 차단하며 `admin-drain-error-banner`를 표출한다 (`defect-recovery-admin-recovery-editor.test.tsx:100-144`).
     - 비상 Kill Switch 토글 버튼 역시 `disabled={!actor}` 및 `aria-disabled={!actor}`로 비활성화된다 (`AdminSecurityConsole.tsx:320-322`, `write-actions-integrity-wiring.test.tsx:249-256`).
   - **[ADM-01 계약 불일치 고지 — Mock 환경 한정 통과 및 단방향 동기화 (F-C2, N3)]**:
     - 실제 백엔드 `POST /v1/nodes/{id}/drain` 및 `POST /v1/nodes/{id}/resume` (`app.py:388, :401`, ADR-054)은 `Idempotency-Key` 헤더 필수(누락 시 422 `VAL-0003`, `app.py:265`)이며, 요청 본문은 `ContainmentInput{expectedVersion, reasonCode: "maintenance"|"incident"|"operator_request", approvalId: uuid}`, `additionalProperties:false` (`contracts/v1alpha1/core.schema.json:3032`)이다. actor는 본문이 아니라 Bearer 토큰의 검증된 principal에서 취한다 (`containment.py:101, :123`).
     - 성공 시 응답은 `ContainmentResult`이며, canonical nodeStatus enum은 `online | offline | draining | quarantined | null`이다 (`core.schema.json:3086`). 백엔드 계약상 `drained`라는 상태는 존재하지 않는다 (drain 완료 대상 상태는 `draining`).
     - 409 충돌 경계로는 version 불일치 시 `GRAPH-0003`, stale recovery epoch 시 `NODE-0033`, 상태 전이 거절 시 `NODE-0062`, 활성 리스 존재 시 `LEASE-0003`, 멱등성 충돌 시 `IDEM-0001`, operator 권한 부재 시 `AUTH-0062`가 반환된다.
     - 그러나 현재 UI(`AdminSecurityConsole.tsx:66-69`)는 `{actor, reason}`만 전송하고 `Idempotency-Key`를 넘기지 않는다. 따라서 **실제 서버 환경에서는 Drain 요청이 100% 거절(422)되고 UI가 롤백**된다. 매트릭스의 DRAINED 갱신은 vitest mock(`mockResolvedValue`) 환경에서만 확인된 것이며, 실제 계약 일치 배선은 차기 FE 결함 수정 카드(`FE-DEFECT-S08-02`) 및 Codex 계약 확인 대상이다.
     - **[단방향 Drain 동기화 결함 (N3)]**: `AdminSecurityConsole.tsx:27-39`에서 컴포넌트는 서버의 draining 상태(`node.status === 'draining'`)는 초기에 가져오지만, 서버 측에서 drain이 해제되어도 이를 화면에 다시 반영하지 않으며, 화면에 표출되는 상태는 순수 로컬 state(`AdminSecurityConsole.tsx:728`)에만 의존하는 단방향 동기화 결함이 존재한다.
   - **재해 복구 및 WAL 백업 원장 표시 (Backup & PITR)**:
     - 서브탭 4의 스냅샷 WAL(`000000010000000A0000002F`), `S3 복제 완료`(`AdminSecurityConsole.tsx:690`), `4분 전 기록 완료`(`:682`), `RTO 실측치 … 12.5 분 (PASS)`(`:694-696`), 및 상단 KPI 타일(`4 분 전`, `RTO 12분`)은 모두 정적 프레젠테이션 수치/리터럴이다.
     - 실제 PostgreSQL WAL 스트리밍 아카이빙, S3 원격 오프사이트 백업, PITR 복원 훈련 및 보존 GC는 **`UNMEASURED ('독립 역할 restore/PITR 및 off-device backup 배선 후')`**로 엄격히 분류한다.

---

## 2. 5대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드/OS 격리 경계 |
|:---:|---|---|---|
| **SCK** | **Docker Socket 미노출 격리**<br>(Host Socket Mount Isolation) | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | • `/var/run/docker.sock`, `//./pipe/docker_engine`, `/var/run/docker/containerd.sock` 차단<br>• 차단 시 `mount_docker_socket_attempt` 거부 감사 로그 자동 체이닝<br>• 오류 코드 `SECURITY_VIOLATION`은 client-only (HTTP 계약 부재)<br>• 상단 KPI `0 건 (완전 격리)`는 정적 리터럴이며 `dockerSocketExposed === false`는 상수<br>• Linux 컨테이너 seccomp/호스트 소켓 격리는 **UNMEASURED** |
| **BYP** | **승인 우회 방지 및 위험 거버넌스**<br>(Approval Bypass Prevention) | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | • L1(저위험) 자가 승인 허용 vs L2/L3(중·고위험) 토큰 부재 시 `APPROVAL_REQUIRED` 즉각 거절 (client-only 에러 코드)<br>• 유효 승인 토큰(`apr_*`) 인입 시 정상 허용 (임의 문자열 통과)<br>• 20회 연속 우회 시도 전수 차단 (`approvalBypassesBlocked >= 22`), 상단 `(우회 허용 0)`은 정적 리터럴<br>• L3 2인 승인은 UI 모의 수준이며, 백엔드 정본 2인 승인 API(`app.py:316-356`, UUID `approvalId`, ADR-056)와 분리 |
| **GPU** | **합성 GPU 성능 검증 및 VRAM 격리**<br>(Synthetic GPU GEMM Benchmark) | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | • RTX 4090 (82.5 TFLOPS / 4GB VRAM) 및 A4000/기타 모델 (19.2 TFLOPS / 2GB VRAM) 합성 연산<br>• `exitCode === 0` 및 고유 증거 ID(`^evi_gpu_`) 발급 검증<br>• GPU 노드 부재 시 `no-gpu-nodes-notice` 안내 및 버튼 비활성화 (위조 합성 차단)<br>• 상단 `성공 (Exit 0)`은 노드 0대여도 표시되는 정적 리터럴<br>• 물리 GPU 하드웨어/CUDA 실측 연산은 **UNMEASURED** |
| **AUD** | **불변 감사 원장 및 긴급 Kill Switch**<br>(Audit Ledger & Emergency Stop) | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | • SHA-256 해시 체이닝 무결성 전수 검증 (`verifyLedgerIntegrity().isValid === true`, 6개 필드 한정)<br>• 클라이언트 로컬 합성 원장 (컴포넌트 마운트마다 4개 시드 이벤트로 재생성)<br>• 긴급 Kill Switch: 백엔드 API(`POST /v1/operations/kill-switch`, status 202)는 존재하나 FE 미연결 상태이며 로컬 엔진에 실제 차단 가드 부재(결함)<br>• 모달 모의 고지 배너(제품 문구 "미노출" 결함 존재) 및 최상단 경고 배너(`kill-switch-active-banner`, `role="alert"`)<br>• 물리 클러스터 전원 차단/외부망 격리는 **UNMEASURED** |
| **ADM** | **관리자 인증 가드 및 재해 복구 WAL 백업**<br>(Admin Auth Guard & WAL/PITR) | `AdminSecurityConsole.tsx`<br>`defect-recovery-admin-recovery-editor.test.tsx` | • 로그인 관리자(`currentUser.id`) 세션 시 실제 actor 동적 배선 (`usr_admin_01` 하드코딩 배제)<br>• 미인증(`currentUser === null`) 시 `admin-auth-required-notice`(`role="alert"`) 및 0-네트워크 호출 가드<br>• ADM-01 실제 서버 호출은 Idempotency-Key 누락 및 ContainmentInput 스키마 불일치로 422 거절됨 (mock 환경 한정 확인)<br>• WAL 스냅샷/RPO/RTO 프레젠테이션 리터럴 카드 렌더링<br>• 실제 off-device S3 백업 및 물리 PITR 복원은 **UNMEASURED** |

---

## 3. 세부 시나리오 매트릭스 (15대 시나리오)

### 3.1 Docker Socket 미노출 격리 (SCK-01 ~ SCK-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **SCK-01** | **호스트 Docker 데몬 소켓 마운트 차단 (Zero Exposure)** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | 관리자 로그인 상태, 소켓·승인 격리 서브탭 활성화 (`activeSubTab === 'isolation'`) | 마운트 입력창에 `/var/run/docker.sock` 입력 후 폼 제출 | • 입력창: `input[type="text"][value="/var/run/docker.sock"]`<br>• 제출 버튼: `button:has-text("마운트 요청 시험")`<br>• 결과 박스: `div[data-testid="mount-test-result"]`<br>• 결과 텍스트: `🛑 ACCESS DENIED: SECURITY_VIOLATION: Docker socket exposure is prohibited.`<br>• 상단 KPI: `div:has-text("0 건 (완전 격리)")` (정적 리터럴) | • `validateMountPath` 실행 결과 `{ allowed: false }` 반환.<br>• 거부 사유에 `SECURITY_VIOLATION: Docker socket exposure is prohibited` 명시 (client-only 에러).<br>• `dockerSocketAttemptsBlocked` 카운터 1 증가.<br>• 클라이언트 원장에 `mount_docker_socket_attempt` 거부 레코드 추가.<br>• 상단 KPI `0 건 (완전 격리)`는 상태 미참조 정적 리터럴임.<br>• (경계 고지) Linux 컨테이너 호스트 격리는 **UNMEASURED**임. | `apps/web/tests/admin-security.test.ts:9-13, 20-21`<br>*(주의: mount-test-result DOM 렌더링 시험은 미수집)* |
| **SCK-02** | **Windows Named Pipe 및 containerd 소켓 우회 마운트 차단** | `securityEngine.ts` | 격리 검증 엔진 초기화 완료 | `validateMountPath`에 Named Pipe 및 containerd 경로 전달 | • 호출 대상 1: `validateMountPath('//./pipe/docker_engine', 'usr_attacker')`<br>• 호출 대상 2: `validateMountPath('/var/run/docker/containerd.sock', 'usr_attacker')` | • 두 시도 모두 `{ allowed: false }` 반환 단언.<br>• 변형된 호스트 소켓 및 파이프 경로를 통한 우회 장악 시도가 원천 차단됨.<br>• 상태 요약의 `dockerSocketExposed`는 상수 `false` 유지. | `apps/web/tests/admin-security.test.ts:14-19` |
| **SCK-03** | **정상 데이터 볼륨 마운트 검증 허용** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | 관리자 로그인 상태 | 마운트 입력창에 `/data/datasets/medical_pacs` 입력 후 제출 | • 결과 박스: `div[data-testid="mount-test-result"]`<br>• 결과 텍스트: `✔ MOUNT ALLOWED: Path /data/datasets/medical_pacs passed security checks.`<br>• 감사 액션: `mount_volume`<br>• 감사 결과 배지: `ALLOWED` (green) | • 금지 패턴에 해당하지 않는 정상 데이터 볼륨 경로 허용 (`{ allowed: true }`).<br>• 클라이언트 원장에 `mount_volume` 승인 이벤트가 기록됨. | `apps/web/tests/admin-security.test.ts:23-26`<br>*(주의: DOM 텍스트 단언 시험은 미수집)* |

---

### 3.2 승인 우회 방지 및 위험 거버넌스 (BYP-01 ~ BYP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **BYP-01** | **L1 저위험 작업 단독 자가 승인 실행 허용** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | 격리 서브탭 내 승인 우회 방지 영역 | 위험 등급 `L1` 선택 후 `우회 실행 시험` 버튼 클릭 | • 셀렉트 드롭다운: `select` ➔ `option[value="L1"]`<br>• 시험 버튼: `button[data-testid="test-bypass-btn"]`<br>• 결과 박스: `div[data-testid="bypass-test-result"]`<br>• 결과 텍스트: `✔ TASK ALLOWED: L1 does not require two-person rule.` | • `validateExecutionApproval('L1', undefined, actor)` 실행 완료.<br>• 저위험 작업은 2인 승인 규칙 대상이 아니므로 즉시 허용(`{ allowed: true }`) 단언.<br>• *(주의: 본 시나리오의 직접적인 DOM 렌더링 단언 시험은 미수집)* | `apps/web/tests/admin-security.test.ts:33-35`<br>*(주의: DOM 단언 없음)* |
| **BYP-02** | **L2/L3 고위험 작업 승인 ID 부재 시 즉각 거절 (Zero Bypass)** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | 관리자 로그인 상태 | 위험 등급 `L2` 또는 `L3` 선택 후 `우회 실행 시험` 버튼 클릭 | • 셀렉트: `option[value="L2"]` 또는 `option[value="L3"]`<br>• 시험 버튼: `button[data-testid="test-bypass-btn"]`<br>• 결과 박스: `div[data-testid="bypass-test-result"]`<br>• 결과 텍스트: `🛑 BYPASS BLOCKED: APPROVAL_REQUIRED: Task risk level L2 cannot bypass governance approval.` | • `validateExecutionApproval` 실행 결과 `{ allowed: false }` 반환.<br>• 거절 사유에 `APPROVAL_REQUIRED` 명시 (client-only 에러).<br>• 클라이언트 원장에 `approval_bypass_attempt` 거부 레코드 기록.<br>• `approvalBypassesBlocked` 카운터 1 증가.<br>• *(주의: BYP의 유일한 DOM 단언은 actor 부재 경로 write-actions:276-278뿐이며 일반 거절 DOM 단언은 미수집)* | `apps/web/tests/admin-security.test.ts:37-46`<br>*(주의: DOM 단언 없음)* |
| **BYP-03** | **유효 승인 토큰 인입 시 허용 및 20회 연속 우회 시도 차단** | `securityEngine.ts` | 봇 스크립트 모의 실행 루프 | 1) 승인 토큰 전달 실행<br>2) 승인 토큰 없이 20회 반복 호출 루프 | • 토큰 호출: `validateExecutionApproval('L2', 'apr_01JABCDEF', 'usr_developer')`<br>• 반복 호출: `validateExecutionApproval('L2', undefined, 'usr_bot_i')` for i in 0..19 | • 유효 승인 토큰 전달 시 `{ allowed: true }` 정상 인가 (임의 비어있지 않은 문자열 통과).<br>• 20회 연속 무인가 우회 시도 전수 차단 (`res.allowed === false`).<br>• 누적 차단 카운터가 최소 22 이상(`approvalBypassesBlocked >= 22`) 유지.<br>• 상단 KPI의 `(우회 허용 0)`은 정적 텍스트 리터럴임.<br>• 실제 백엔드 정본 2인 승인 규약(`contracts/v1alpha1/core.schema.json:3051`, UUID `approvalId`, ADR-056)과 분리. | `apps/web/tests/admin-security.test.ts:47-57` |

---

### 3.3 합성 GPU 성능 검증 및 VRAM 격리 (GPU-01 ~ GPU-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **GPU-01** | **RTX 4090 노드 합성 FP16 GEMM 벤치마크 실행** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | GPU 서브탭 활성화 (`activeSubTab === 'gpu'`), GPU 노드 1대 이상 존재 | 드롭다운에서 RTX 4090 노드 선택 후 `합성 GPU 벤치마크 실행` 버튼 클릭 | • 노드 드롭다운: `select[data-testid="gpu-node-select"]`<br>• 실행 버튼: `button[data-testid="run-gpu-benchmark-btn"]`<br>• 성공 배너: `span:has-text("✔ 합성 GPU 벤치마크 정상 완료 (Exit Code: 0)")`<br>• Throughput 텍스트: `div:has-text("82.5 TFLOPS")`<br>• VRAM 텍스트: `div:has-text("4 GB")`<br>• 증거 코드: `code:has-text("evi_gpu_")`<br>• 상단 KPI: `성공 (Exit 0)` (정적 리터럴) | • `runSyntheticGpuBenchmark` 실행 완료.<br>• `exitCode === 0` 단언.<br>• 연산 처리량 > 50 TFLOPS (82.5 TFLOPS) 단언.<br>• VRAM 할당량 4GB (`4 * 1024 ** 3`) 단언.<br>• 고유 증거 ID 정규식 매칭 (`/^evi_gpu_/`).<br>• **[물리 경계 고지]**: 프런트엔드 프로브 에뮬레이션이며, 실제 물리 GPU 하드웨어 실행은 **UNMEASURED**임. | `apps/web/tests/admin-security.test.ts:64-70`<br>*(주의: DOM 단언 없음 / UI 렌더링 시험 미수집)* |
| **GPU-02** | **A4000 노드 합성 벤치마크 실행 및 격리 검증** | `securityEngine.ts` | A4000 노드 fixture 준비 | `runSyntheticGpuBenchmark(nodeId, 'NVIDIA A4000')` 직접 호출 | • 결과 객체: `resA4000.exitCode === 0`<br>• 처리량: `resA4000.computeThroughputTflops > 15` (19.2 TFLOPS)<br>• VRAM: `resA4000.vramAllocatedBytes === 2 * 1024 ** 3` (코드상 2GB 합성이나 테스트 단언은 부재)<br>• 증거 ID: `resA4000.evidenceId` | • A4000(및 4090 외 모든 GPU)에 대해 19.2 TFLOPS 합성 연산 단언.<br>• 종료 코드 0 및 유효 증거 식별자 발행 확인.<br>• (주의) `admin-security.test.ts:72-76`에는 A4000의 VRAM 단언이 누락되어 있음.<br>• 물리 GPU 실행은 **UNMEASURED** 유지. | `apps/web/tests/admin-security.test.ts:72-76` |
| **GPU-03** | **가용 GPU 노드 부재 시 빈 상태 고지 및 위조 노드 합성 차단** | `AdminSecurityConsole.tsx` | `gpuNodes.length === 0` (클러스터 내 GPU 노드 0대) | GPU 서브탭 마운트 시점 | • 드롭다운: `select[data-testid="gpu-node-select"][disabled]`<br>• 드롭다운 옵션: `option:has-text("(클러스터 내 가용 GPU 노드 없음)")`<br>• 경고 배너: `div[data-testid="no-gpu-nodes-notice"]`<br>• 안내 문구: `⚠️ 클러스터 내에 가용한 GPU 노드가 없습니다. (위조 노드 합성 차단)`<br>• 실행 버튼: `button[data-testid="run-gpu-benchmark-btn"][disabled]` | • 가용 GPU 노드가 없을 때 임의의 가짜 GPU 노드를 위조 합성하지 않고 정직하게 비활성화.<br>• `no-gpu-nodes-notice` 경고 안내 렌더링 확인.<br>• 실행 버튼 disabled로 비정상 호출 원천 차단. | `apps/web/src/features/admin/AdminSecurityConsole.tsx:574-610`<br>*(컴포넌트 렌더링 검증)* |

---

### 3.4 불변 감사 원장 및 긴급 Kill Switch (AUD-01 ~ AUD-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **AUD-01** | **클라이언트 로컬 원장 SHA-256 체이닝 무결성 검증** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | 감사 서브탭 활성화 (`activeSubTab === 'audit'`), 이벤트 누적 상태 | `원장 암호화 무결성 검사` 버튼 클릭 | • 버튼: `button:has-text("원장 암호화 무결성 검사")`<br>• 검증 결과 텍스트: `span:has-text("✔ N개 레코드 무결성 검증 완료")` (마운트 직후는 4개 시드 이벤트)<br>• 엔진 반환: `verifyLedgerIntegrity()` | • 제네시스 해시부터 SHA-256 체이닝 전수 재계산 검증.<br>• `verification.isValid === true` 단언.<br>• 시험은 `checkedRecords >= 6` 상태에서 무결성 통과를 단언 (`admin-security.test.ts:101-102`).<br>• (한계 고지) `target`, `traceId`, `id` 누락으로 대상 변조는 미검출. | `apps/web/tests/admin-security.test.ts:80-103` |
| **AUD-02** | **감사 이벤트 테이블 7대 메타데이터 렌더링** | `AdminSecurityConsole.tsx` | 감사 서브탭 마운트 완료 | 감사 로그 목록 렌더링 시점 | • 테이블 헤더: `th:has-text("Timestamp")`, `th:has-text("Actor")`, `th:has-text("Action")`, `th:has-text("Target")`, `th:has-text("Outcome")`, `th:has-text("Details")`, `th:has-text("Integrity Hash")`<br>• 결과 배지: `span:has-text("ALLOWED")` (green) / `span:has-text("DENIED")` (red)<br>• 해시 셀: `td` (12자리 축약 모노스페이스) | • 로컬 원장의 7대 컬럼이 표출됨.<br>• 허용/거부 결과 배지가 정확한 색상 스타일로 렌더링됨.<br>• 각 행의 고유 암호화 해시 앞 12자리 표기 확인.<br>• (고지) 백엔드 감사 원장이 아닌 클라이언트 합성 원장임. `traceId`는 표에 미표시. | `apps/web/src/features/admin/AdminSecurityConsole.tsx:363-407`<br>*(컴포넌트 렌더링 검증)* |
| **AUD-03** | **긴급 Kill Switch 발동 모달·모의 고지·배너 및 해제 토글** | `AdminSecurityConsole.tsx`<br>`securityEngine.ts` | 관리자 로그인 상태 (`actor !== null`), Kill Switch 비활성 상태 | 1) `🚨 긴급 Kill Switch 발동` 클릭<br>2) 모달 내 `긴급 발동 확정` 클릭<br>3) 해제 버튼 클릭 | • 토글 버튼: `button[data-testid="emergency-kill-switch-toggle-btn"]`<br>• 확인 모달: `div[data-testid="kill-switch-modal"]` (주의: `role="dialog"`, `aria-modal` 부재)<br>• 모의 고지 배너: `div[role="status"][data-testid="kill-switch-mock-notice"]`<br>• 모의 고지 현재 문구: `⚠️ [모의 시뮬레이션 고지]: 백엔드 제어 평면 비상 정지 API가 현재 미노출 상태입니다...` (주의: 실제 백엔드에 API가 존재하므로 제품 문구 결함임)<br>• 최상단 활성 배너: `div[role="alert"][data-testid="kill-switch-active-banner"]`<br>• 최상단 문구: `🚨 [모의 시뮬레이션] EMERGENCY KILL SWITCH ACTIVE — LOCAL SECURITY ENGINE ISOLATION` | • `toggleEmergencyKillSwitch` 실행으로 `emergencyKillSwitchActive === true` 전이.<br>• 최상단에 `role="alert"` 활성 경고 배너 표출 확인.<br>• 감사 원장에 `kill_switch_activated` 이벤트 기록.<br>• **[F-C1 백엔드 계약 경계]**: 백엔드에는 `GET/POST /v1/operations/kill-switch` 및 `/clear` (`app.py:310,358,370`, ADR-053)가 구현되어 있으나 FE 미연결 상태임. POST 호출에는 Bearer identity, operator grant, `Idempotency-Key`, `ContainmentInput`이 필수임.<br>• **[결함 고지]**: 로컬 Kill Switch는 실제 작업 디스패치를 차단하지 않음(FE 결함).<br>• 해제 시 `kill_switch_deactivated` 기록 및 배너 소멸 (단, 단위시험은 발동만 검증하고 해제 단언은 부재). | `apps/web/tests/admin-security.test.ts:106-118`<br>`apps/web/tests/write-actions-integrity-wiring.test.tsx:281-321`<br>`apps/web/src/features/admin/AdminSecurityConsole.tsx:162-188, 787-852` |

---

### 3.5 관리자 인증 가드 및 재해 복구 WAL 백업 (ADM-01 ~ ADM-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **ADM-01** | **인증된 관리자 세션 시 실제 actor 동적 배선 (하드코딩 배제)** | `AdminSecurityConsole.tsx`<br>`apiClient` | `currentUser: { id: 'usr_actual_admin_77', role: 'admin' }` 주입 상태 | 노드 Drain 탭 이동 후 `Node Drain` 버튼 클릭 | • 서브탭 버튼: `button:has-text("노드 Drain 통제 (ADR-038)")` (주의: ADR 번호는 ADR-054의 오기임)<br>• 액션 버튼: `button:has-text("Node Drain")`<br>• **현재 UI 요청**: `apiClient('/v1/nodes/nod_test_01/drain', { method: 'POST', body: JSON.stringify({ actor: 'usr_actual_admin_77', reason: '...' }) })`<br>• **백엔드 정본 규격 (F-C2)**:<br>  - Header: `Idempotency-Key: <key>`<br>  - Body: `ContainmentInput { expectedVersion: 1, reasonCode: "maintenance", approvalId: "<uuid>" }`<br>  - Actor: Bearer principal 자동 추출<br>  - Response: `ContainmentResult` (target status: `draining`) | • 인증 부재 배너(`admin-auth-required-notice`) 미노출 확인.<br>• `apiClient` 호출 시 실제 로그인 식별자 `usr_actual_admin_77` 전송 단언.<br>• **[F-C2 계약 불일치 및 409 경계 고지]**:<br>  - 실제 백엔드는 `Idempotency-Key` 누락 시 422 `VAL-0003`, version 불일치 시 409 `GRAPH-0003`, stale recovery epoch 시 409 `NODE-0033`, 격리 거부 시 409 `NODE-0062`, operator 권한 부재 시 403 `AUTH-0062`를 반환함.<br>  - canonical nodeStatus enum은 `online\|offline\|draining\|quarantined\|null`이며 `drained`는 계약 상태가 아님.<br>  - 본 호출은 vitest mock(`mockResolvedValue`) 환경에서만 성공 성립하며 실제 서버에서는 100% 거절됨 (차기 FE 결함 수정 대상). | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:52-98` |
| **ADM-02** | **관리자 세션 부재(`null`) 시 경고 배너(role=alert) 및 0-네트워크 가드** | `AdminSecurityConsole.tsx`<br>`apiClient` | `currentUser: null` (비로그인/세션 만료 상태) | 1) 컴포넌트 마운트<br>2) Drain 탭 이동 후 Drain 버튼 클릭 시도 | • 경고 배너: `div[role="alert"][data-testid="admin-auth-required-notice"]`<br>• 경고 문구: `⚠️ 인증된 관리자 세션 부재: 관리자 세션 식별자(actor)가 확인되지 않았습니다...`<br>• 에러 배너: `div[data-testid="admin-drain-error-banner"]`<br>• 에러 문구: `❌ 인증된 관리자 세션이 없습니다. 노드 격리(Drain) 명령은 로그인된 관리자 식별자(actor)가 필수입니다.`<br>• Kill Switch 버튼: `button[data-testid="emergency-kill-switch-toggle-btn"][disabled]` | • 마운트 즉시 `role="alert"`를 가진 인증 부재 경고 배너 렌더링 단언.<br>• Drain 버튼 클릭 시 `apiClient` 네트워크 호출이 **0회(not.toHaveBeenCalled)**로 원천 차단됨을 단언.<br>• Kill Switch 버튼 disabled 처리(`write-actions-integrity-wiring.test.tsx:249-256`에서 단언). | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:100-144`<br>`apps/web/tests/write-actions-integrity-wiring.test.tsx:249-256` |
| **ADM-03** | **재해 복구 및 PostgreSQL WAL 백업 원장 카드 렌더링** | `AdminSecurityConsole.tsx` | 백업 서브탭 활성화 (`activeSubTab === 'backup'`) | 서브탭 마운트 시점 | • 서브탭 버튼: `button:has-text("재해 복구 및 WAL 백업")`<br>• 스냅샷 카드: `div:has-text("Latest Snapshot WAL")` ➔ `000000010000000A0000002F`<br>• 복제 상태: `div:has-text("S3 복제 완료")` (정적 리터럴)<br>• RPO 카드: `div:has-text("RPO 달성도 (Target ≤ 15m)")` ➔ `div:has-text("4 분 전")` (상단 타일) / `div:has-text("4분 전 기록 완료")`<br>• RTO 카드: `div:has-text("RTO 실측치 (Target ≤ 60m)")` ➔ `div:has-text("RTO 12분")` (상단 타일) / `div:has-text("12.5 분 (PASS)")` | • 상단 KPI 타일 및 서브탭 4에서 WAL 백업 및 RPO/RTO 카드 표출 확인.<br>• 타일 및 카드의 모든 수치는 상태 비연결 정적 리터럴임.<br>• **[물리 경계 고지]**: 실제 PostgreSQL 물리 WAL 아카이빙, S3 오프사이트 복제, PITR 복원 훈련 및 보존 GC는 **UNMEASURED ('독립 역할 restore/PITR 및 off-device backup 배선 후')**임. | `apps/web/src/features/admin/AdminSecurityConsole.tsx:257-263, 654-702`<br>*(컴포넌트 렌더링 검증)* |

---

## 4. 돌연변이(Mutation) 사살 계획 및 불변식 단언 (MUT 5종)

본 매트릭스의 검증력과 견고성을 보장하기 위해, 프로덕션 코드 심볼을 의도적으로 변조했을 때 테스트 스위트가 이를 즉각 검출(KILLED)할 수 있는지 확인하는 5대 돌연변이 사살 계획을 수립한다. 실제 실행 증거(provenance)가 확보되기 전까지 상태는 **`PLANNED / NOT_RUN`** 또는 **`SURVIVED (미측정)`**으로 정직하게 기록한다.

| 돌연변이 ID | 대상 파일 및 대상 로직 | 의도적 결함 주입 (Mutation) | 사살 검증 시험 및 단언 위치 (파일:행) | 판정 상태 |
|:---:|---|---|---|:---:|
| **MUT-01** | `securityEngine.ts:127`<br>`validateMountPath` | `prohibitedPatterns` 배열(`['docker.sock', '//./pipe/docker_engine', '/var/run/docker']`)에서 `'docker.sock'` 항목을 누락 | `apps/web/tests/admin-security.test.ts:11-12`<br>※ **(주의: SURVIVED 판정)** `'docker.sock'`을 빼더라도 `test:10`(`/var/run/docker.sock`)은 `'/var/run/docker'`에 매칭되어 단언이 통과됨. `/run/docker.sock` 같은 경로 시험이 추가되기 전까지 **SURVIVED (미측정)**임. | **SURVIVED (미측정)<br>[단언 보강 필요: /run/docker.sock]** |
| **MUT-02** | `securityEngine.ts:156`<br>`validateExecutionApproval` | `if ((riskLevel === 'L2' || riskLevel === 'L3') && !approvalId)` 조건에서 `'L2'` 검사를 누락 (`riskLevel === 'L3'`만 검사하도록 완화) | `apps/web/tests/admin-security.test.ts:39-40`<br>`expect(l2.allowed).toBe(false)`, `expect(l2.reason).toContain('APPROVAL_REQUIRED')` 실패 유도 (코드 추론상 사살 예상) | **PLANNED / NOT_RUN** |
| **MUT-03** | `securityEngine.ts:227`<br>`verifyLedgerIntegrity` | `if (entry.integrityHash !== expected)` 변조 검사를 누락하고 루프 종료 후 무조건 `{ isValid: true }` 반환 | `apps/web/tests/admin-security.test.ts:99-102`<br>※ **(주의: 단언 보강 필요)** 현재 시험(`test:99-101`)은 정상 원장만 검증하므로 본 변이 주입 시 정상 통과함. 변조된 원장을 주입하여 `isValid === false`를 단언하는 테스트 케이스 추가 전까지 **SURVIVED (미측정)** 상태임. | **SURVIVED (미측정)<br>[단언 보강 필요: 변조 원장 주입]** |
| **MUT-04** | `AdminSecurityConsole.tsx:20`<br>`actor binding` | `const actor = currentUser?.id?.trim() || null;` 로직을 과거 하드코딩 `'usr_admin_01'`로 되돌림 | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:88-97`<br>`expect(apiClientSpy).toHaveBeenCalledWith('/v1/nodes/nod_test_01/drain', expect.objectContaining({ method: 'POST', body: JSON.stringify({ actor: 'usr_actual_admin_77', reason: 'Admin manual maintenance and isolation protocol' }) }))` 실패 유도 | **PLANNED / NOT_RUN** |
| **MUT-05** | `AdminSecurityConsole.tsx:191-206`<br>`admin-auth-required-notice` | `data-testid="admin-auth-required-notice"` 배너 렌더링을 누락하거나 `role="alert"` 속성을 제거 | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:113-116`<br>`expect(authNotice).not.toBeNull()`, `expect(authNotice?.getAttribute('role')).toBe('alert')` 실패 유도 | **PLANNED / NOT_RUN** |

---

## 5. 백엔드 커널 계약 및 물리/OS 격리 UNMEASURED 경계

### 5.1 백엔드/OS 커널 보안 격리 계약 및 UNMEASURED 분류
- **Linux 제한 컨테이너 호스트 격리 (Container Isolation)**:
  - 프런트엔드의 경로 검증은 마운트 입력창 필터링 계층이다.
  - Linux 컨테이너 런타임(containerd/runc)의 seccomp 프로파일 차단, AppArmor 강제, Docker 소켓 권한(`0660 root:docker`) 통제 및 호스트 네임스페이스 격리 실측은 **`UNMEASURED ('실 제한 컨테이너 환경 배선 후')`**로 엄격히 분류한다.
- **물리 GPU 하드웨어 실행 (Physical GPU Hardware)**:
  - `runSyntheticGpuBenchmark`는 클라이언트 인메모리 프로브 에뮬레이션이다.
  - 실제 PCIe 버스를 통한 NVIDIA GPU 통신, 물리 CUDA 코어 Tensor 연산, 물리 VRAM 페이징 및 드라이버 오류 처리는 **`UNMEASURED ('물리 GPU 장비 및 CUDA 드라이버 배선 후')`**로 엄격히 분류한다.
- **재해 복구 및 PostgreSQL WAL 백업 (Backup & PITR)**:
  - 화면의 WAL 및 RPO/RTO 지표는 정적 프레젠테이션 수치/리터럴이다.
  - 실제 PostgreSQL 스트리밍 WAL 아카이빙(`archive_command`), S3/오프사이트 원격 백업 복제, 독립 역할 PITR 복원 훈련 및 데이터 보존 GC는 **`UNMEASURED ('독립 역할 restore/PITR 및 off-device backup 배선 후')`**로 분류한다.
- **클러스터 긴급 Kill Switch (Physical Interruption & Kernel Contract — F-C1)**:
  - 백엔드 제어 평면에는 `GET/POST /v1/operations/kill-switch` 및 `/clear` 엔드포인트(`services/control-plane/src/inv/app.py:310, :358, :370`, ADR-053)가 구현되어 있으나, 프런트엔드가 미연결(FE 미연결)된 상태이다.
  - 또한 실제 5대 물리 노드 분산 클러스터 전체에 걸친 프로세스 즉각 사살(SIGKILL) 및 물리 네트워크 링크 차단은 **`UNMEASURED`**이다.

### 5.2 ADR-100 5노드 랩 측정 경계
- ADR-100 토폴로지 B에 따라 Control Plane 겸임 Node 1대와 독립 Ubuntu Node 4대의 물리 경계를 명시한다 (`registeredNodeCount=5`, `cpIndependentWorkerHostCount=4`, `cpColocatedNodeCount=1`).
- 현재 브라우저·빌드·전체 suite 금지(메모리 경보 유지) 하에 docs-only 검증 완료 상태를 유지한다.

---

## 6. 발견된 프런트엔드 결함 목록 (차기 FE 제품 결함 수정 카드 과제)

본 시나리오 매트릭스 수립, Claude UI 검토(r1/r2), 및 Codex 계약 축 검토 과정에서 도출된 관리자 보안 콘솔(`AdminSecurityConsole.tsx`, `securityEngine.ts`)의 제품 결함 6건을 체계화한다:

1. **FE-DEFECT-S08-01 (Kill Switch 백엔드 API 실배선, 로컬 차단 가드 누락 및 제품 문구 결함 수정 — F-C1, Claude r2 Item 1)**:
   - 백엔드의 `POST /v1/operations/kill-switch` 및 `/clear` API와 실배선 연결 (`Idempotency-Key` 헤더, `ContainmentInput`, Bearer 토큰 요구 준수, ADR-053).
   - 로컬 엔진의 `emergencyKillSwitchActive` 상태가 켜져 있을 때 노드 Drain 및 모든 액션을 차단하는 핸들러 가드 구현.
   - 제품 문구 결함 수정: `AdminSecurityConsole.tsx:181` 및 `:830`의 "비상 정지 API 미노출 상태" 문구를 "백엔드 API 존재하나 FE 미연결 상태"로 올바르게 정정.
2. **FE-DEFECT-S08-02 (ADM-01 Drain/Resume 요청 계약 불일치 및 단방향 동기화 결함 수정 — F-C2, N3)**:
   - `POST /v1/nodes/{id}/drain` 및 `/resume` 호출 시 필수 헤더 `Idempotency-Key` 부착 및 본문 스키마(`ContainmentInput{expectedVersion, reasonCode, approvalId}`) 준수 (ADR-054).
   - 응답 `ContainmentResult` 수용 및 canonical nodeStatus enum(`online|offline|draining|quarantined|null`) 처리 (비계약 상태 `drained` 제거).
   - 단방향 Drain 동기화 결함 수정: 서버의 drain 해제/변경 사항을 컴포넌트 state에 양방향 동기화.
3. **FE-DEFECT-S08-03 (정적 리터럴 제거 및 동적 상태/UNMEASURED 바인딩)**:
   - 상단 KPI 타일 4종의 정적 리터럴(`0 건 (완전 격리)`, `성공 (Exit 0)`, `(우회 허용 0)`, `4 분 전 / RTO 12분`)을 실제 엔진 상태 또는 `UNMEASURED`로 정직하게 전환.
   - 백업 서브탭의 `S3 복제 완료`, `4분 전 기록 완료`, `RTO 12.5 분 (PASS)` 등 정적 리터럴 정비.
4. **FE-DEFECT-S08-04 (해시 체이닝 페이로드 필드 보강 및 로컬 합성 명시)**:
   - SHA-256 해시 체이닝에 `target`, `traceId`, `id` 필드를 포함시켜 변조 검출력을 완성.
   - 화면에 "클라이언트 로컬 합성 원장"임을 명확히 안내.
5. **FE-DEFECT-S08-05 (접근성 보강 — Kill Switch 모달 `role="dialog"`)**:
   - `kill-switch-modal`에 `role="dialog"`, `aria-modal="true"`, `aria-labelledby` 부여.
6. **FE-DEFECT-S08-06 (ADR 번호 오기 정정 — N1)**:
   - Drain 탭 버튼 라벨의 `노드 Drain 통제 (ADR-038)`(`AdminSecurityConsole.tsx:312`)를 올바른 Node Drain ADR 번호인 **ADR-054**로 정정 (ADR-038은 샤드 결과 취소, ADR-054가 Node drain 정본임).

---

## 7. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (S08-FE 보안 감사 시나리오 매트릭스 v1.0.2 개정 완료)
- **독립 리뷰어**: Claude (UI 셀렉터, 거버넌스 불변식, DOM 단언 대조), Codex (보안 정본 계약, 커널/OS 격리 경계, ADR-053/054/056/100 규격 대조)
- **v1.0.2 조치 요약**:
  - **Codex 계약 축 검토(F-C1~F-C3) 반영**:
    - F-C1: Kill Switch를 "API 미노출"에서 "API 존재·FE 미연결"로 전면 정정, POST 호출 규격(Bearer identity, operator grant, `Idempotency-Key`, `ContainmentInput`) 및 tenant execution barrier 경계 명시.
    - F-C2: Drain/Resume canonical 계약 정본(`Idempotency-Key` 헤더, `ContainmentInput`, canonical enum `online|offline|draining|quarantined|null`, 409 충돌 경계 `GRAPH-0003`, `NODE-0033`, `NODE-0062`, `LEASE-0003`, `IDEM-0001`, `AUTH-0062`, `ContainmentResult` 응답) 명시 및 mock UI 결과와의 불일치 고지.
    - F-C3: 클라이언트 전용 모의 계층 vs 백엔드 정본 제어평면 계약 계층을 상세 대비표(Table §1.1)로 완전 분리.
  - **Claude UI 재대조 r2 지적 반영**:
    - N1: 올바른 Node drain ADR 번호 **ADR-054** 반영 (ADR-038 오기 및 FE-DEFECT-S08-06 정정).
    - N2: 스키마 파일 경로 정정 (`contracts/v1alpha1/core.schema.json`).
    - N3: 단방향 Drain 동기화 결함(`adm:27-39` 및 `:728`) 본문 기술.
    - N4: `AdminSecurityConsole:246` 문구를 KPI 타일 부제 `L2/L3 위험 작업 Two-Person 강제`로 정정.
    - Item 1: 제품 문구 결함(`adm:181`, `:830` "미노출") 명시 및 `FE-DEFECT-S08-01`에 수정 과제 포함.
    - Item 9: BYP-01/02 및 GPU-01에 "DOM 단언 없음" 명시, AUD-01 `checkedRecords >= 6` 정정.
- **다음 단계**:
  1. `check_docs.py` 및 `check_frontend_integrity.py` 검증 exit 0 확인.
  2. `agent/gemini/s08-fe-matrix` 브랜치에 v1.0.2 commit 및 push.
  3. PR #123에 조치 보고 코멘트 작성.
  4. Claude 및 Codex 승인 대기.
