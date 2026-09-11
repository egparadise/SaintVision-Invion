---
doc_id: "CONTRACT-RESULT-OBSERVATION-001"
title: "Codex 실제 실행 결과 조회 계약"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-09-11T15:54:00+09:00"
source_of_truth: "Git"
---

# 실제 결과와 실행 준비 상태

2026-09-11 후속: [[2026-09-11_Claude_잔여보고_Codex_독립검토]]에 따라 f4fe37e에서 업무 results.py와 중복 결과 라우터를 제거하고 readiness.py를 별도 연결했다. 기존 migration/데이터는 보존한다. 새 입력 준비 진단은 현재 epoch·동일 Workspace/project·대기 중인 attempt의 입력만 선택한다. 별도 kernel_request_permission과 input_prepared를 포함한 checks는 7개다. UI는 개수를 고정하지 말고 check ID와 배열을 사용한다. executable=false/admissionRequired=true는 유지한다. 코드 통합과 운영 배포·CI·독립 검토·물리 원격 인수는 별도 상태다.

[[2026-09-11_RESULT-OBSERVATION_Codex_착수]] 및 [[Codex 계정과 실행 커널 통합 계약]]의 후속이다. Codex는 결과 무결성·권한 경계와 DB 이력 통합을 소유한다. Claude의 결과 조회·진단 서비스 원저자 이력은 보존하며 Codex 수정의 독립 검토는 Claude 대기다.

## ADR-066: 결과의 정본과 다운로드

`public.runs`, public RunRecord/Evidence는 `inv.runs`의 자동 동기화 사본이 아니다. 실제 Node 작업을 마친 뒤에도 public Run이 draft일 수 있다. 실행 화면은 inv의 현재 RunAttempt, 인증된 Node stop receipt, result completion, immutable Evidence 및 출력 바이트를 조회한다. 업무 역할에 inv 테이블 전체 읽기 권한을 주지 않는다.

| GET 경로 | 응답과 의미 |
|---|---|
| `/v1/projects/{project}/runs/{run}/result` | `source=execution-kernel`, `state/version/attemptCount`, `executionConfirmed`, `stopReceipt`, `sealed/evidence/output`, `resourceReleasePending` |
| 같은 Run 경로의 `/artifacts` | 실제 Workspace snapshot의 `artifacts[]`에 `path/checksumSha256/byteSize/evidenceId`. 미확인은 빈 목록과 absentReason |
| 같은 Run 경로의 `/artifacts/content?path=outputs/metrics.json` | 검증된 파일 바이트, attachment, X-Content-SHA256, application/octet-stream |
| 같은 Run 경로의 `/logs` | 완료 출력의 stdout/stderr, redacted/truncated. 없으면 null과 absentReason |
| 같은 Run 경로의 `/attempts?after=0&limit=50` | 실제 attempt 번호·Node·command·stop receipt·exit code·Evidence. limit 최대 200, nextCursor |

`/v1/runs/{run}/...`도 같은 커널 조회로 연결한다. 첫 실행에 public Run 행이 없어도 조회 가능하다. 현재 프로젝트 grant와 업무 멤버십의 교집합을 매 요청 확인하며 Run 잠금과 권한 공유 잠금을 응답 검증까지 유지한다. JWT role이나 브라우저 사용자 ID를 권한으로 쓰지 않는다. 본문·인증·Origin·no-store 정책은 기존 공통 HTTP 경계를 통과한다.

`executionConfirmed=true`는 프로세스가 시작됐다는 Node 영수증이다. 결과 성공을 뜻하지 않는다. `sealed=true`는 현재 attempt의 실제 completion/Evidence/출력 무결성 확인이며 성공 상태와 함께 해석한다. 출력 수집 복구 중에는 stop receipt가 있어도 Evidence/output은 null이다. 실행 전 취소의 tombstone은 attempt 0과 processStarted=false로 표시한다. 없는 해시·크기·Evidence는 만들어 넣지 않는다.

다운로드는 receipt의 bounded bytes SHA-256/크기를 storage object 및 Evidence와 비교하고, 승인된 입력에 연결된 Workspace snapshot을 다시 검증한다. 파일 path는 snapshot 내 정확한 portable path만 허용하며 로컬 파일 경로를 열지 않는다. 응답 파일은 attachment이고 HTML로 렌더링하지 않는다. 로그 미리보기에는 기존 redaction을 적용한다. 임의 파일 내용의 무조건 비밀 제거를 보장하지 않으며 작업 파일 다운로드와 로그 표시를 구분한다.

JSON Schema 정본 `contracts/v1alpha1/core.schema.json`의 RunResultView/RunArtifactList/RunLogView/RunAttemptList로 응답을 검사하고 Python/TS/Go 타입을 생성한다. Gemini는 실제 응답을 이 계약에 연결하며 표본·랜덤 heartbeat·고정 출력 값을 대신 쓰지 않는다.

## ADR-067: 준비 상태는 실행 승인이 아니다

`GET /v1/workspaces/{workspace}/execution-readiness`는 업무 라우터에서 현재 계정/프로젝트 접근권을 확인한 후 여섯 조건을 설명한다. project link, 실제 subject 등록, 역할, Workspace 상태, 현재 kernel request grant, 선택 도구의 Node 준비 상태다. CP PC의 PATH/CLI 로그인 파일은 원격 도구 준비 상태로 사용하지 않는다. 아직 검증된 Node 도구 관측이 없으므로 nodeReadiness=unknown, executable=false이며 admissionRequired=true다. 실제 Node·정책·자원·kill switch·고정 입력·승인은 start/prepare 및 start/enqueue 경계에서 다시 확인한다.

이 조회는 운영 권한을 부여하거나 Node를 설치하지 않는다. subject 및 실행 권한 definer는 현재 transaction tenant만 조회하고 활성 계정/실제 subject 일치와 명시적 grant를 요구한다. `0026_subject_kernel_link`와 `0027_business_api_guards`를 고치지 않고 `0028_result_readiness_merge`에서 두 이력을 보존해 합친 후 tenant guard를 보강한다. downgrade는 거부한다.

실제 IdP/Workspace provisioning·원격 도구 관측/실행·웹 인수는 후속 작업이다. 운영 DB/profile을 변경하지 않은 격리 시험을 실제 원격 PC·GPU·5대 검증이라고 표시하지 않는다.

## 사용자 요청에 따른 구현 정본 확정

실제 실행 결과 구현의 정본은 `services/control-plane/src/inv/result_view.py`, 데이터 정본은 inv Run/attempt/Node receipt/result completion/immutable Evidence다. Claude는 `src/saintvision/services/results.py`의 중복 실행 결과·artifact·attempt·raw output 구현과 해당 중복 route를 제거한다. canonical API의 current grant/출력 검증을 독립 검토하고 필요한 회귀 사례를 그 경로로 이전한다. 공개 migration·실행/감사 데이터는 삭제·개명하지 않는다.

Workspace readiness는 별도 업무 진단 서비스 `execution_readiness.py`로 유지하며 그 route는 필요하면 독립 router로 옮긴다. 업무 Project/Workspace CRUD·메타데이터도 유지한다. public Run을 별도 성공/실패/Evidence 원장으로 동기화하지 않는다. handoff/binding은 kernel의 실제 승인·실행·복원 기록에서 읽는 업무 참조로 통일하며 별도 상태 머신을 만들지 않는다. Codex는 계약/분산 상태·무결성, Claude는 업무 서비스 정리/독립 검토, Gemini는 canonical API 화면 연결을 소유한다.

구현 제거는 Claude의 다음 작업이다. 이 계약 확정 자체를 삭제 구현 완료나 독립 검토 승인으로 표시하지 않는다. 전체 인수 순서는 [[3 Agent 원격 실행과 운영 인수 확정]]이다.
