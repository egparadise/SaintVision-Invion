---
doc_id: "HIST-CODEX-CLAUDE-LANDING-ROUTE-COVERAGE-001"
title: "Claude 8b49981 최종 착지와 route coverage 재검토"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T17:30:00+09:00"
source_of_truth: "Git"
---

# Claude 8b49981 최종 착지와 route coverage 재검토

## Claude 전체 착지

Claude `8b49981`의 세 정확성 정정은 소스 diff로 확인했다.

1. VB-FIX-01/02의 11개 시험은 실 PostgreSQL이 아니라 stub/주입 시험임을 상태 지도에 명시했다.
2. `1eaf285`의 1179 passed 회귀는 Codex 실행이 아니라 사용자 실행·보고로 정정했다.
3. PITR-R1-04의 `archive_timeout` idle floor와 `wal_keep_size` 아카이빙 필요성 서술을 PostgreSQL 동작에 맞게 정정했다.

PITR-R2-02 cleanup 코드는 앞서 Codex가 고정 SHA에서 13개 원본 대조와 5개 보강 시나리오를 통과시켜 hold를 해제했다. 따라서 `8b49981`은 문서 정정만 남은 최종 Claude 변경으로 판단한다. 최신 integration에 Claude 브랜치를 병합했고 merge SHA는 `0955202`이다. `git merge-base --is-ancestor 8b49981 integration` 조건을 병합 후 확인한다. 실제 운영 PITR 활성과 AC-12 인수는 별도 외부 조건이다.

## route coverage 6건의 최종 판정

사용자 `route_coverage.py` 결과의 6건은 현재 소스 기준으로 다음처럼 정리된다.

| 경로 | 판정 | 근거 |
|---|---|---|
| `/v1/events` | 당시 실제 불일치, 현재 해소 | 프론트 호출을 `/v1/projects/{project}/runs/{run}/events`로 정렬했고 control-plane이 같은 경로를 제공한다. |
| `/v1/projects/{}/runs/{}/evidence` | 당시 실제 불일치, 현재 해소 | EvidenceViewer가 project-scoped `/result`를 호출하도록 바뀌었다. |
| `/v1/runs/{}/evidence` | 당시 실제 불일치, 현재 해소 | EvidenceViewer의 bare evidence 호출이 제거됐다. 현재 result/artifacts 계열 계약을 사용한다. |
| `/v1/discovery/candidates` | 도구 오탐 | `src/saintvision/api/v1/pools.py`의 `/v1` prefix 조합으로 실제 제공된다. |
| `/v1/runs` | 도구 오탐 | `${...}` 템플릿의 head를 도구가 bare collection으로 추출했다. 실제 호출은 id-scoped다. |
| `/v1/workspaces` | 도구 오탐 | 같은 템플릿 head 추출이다. 실제 호출은 workspace id-scoped 경로다. |

현재 `python -m pytest -q tests/test_route_coverage.py tests/test_browser_smoke_boundary.py`는 **29 passed, exit 0**이다. `route_coverage.py`를 두 서버 트리에 대해 다시 실행하면 bare `/v1/workspaces` 하나가 남지만, 이는 위 템플릿 추출 오탐이며 실행·HTTP·인증 인수는 이 도구가 검증하지 않는다. 기존 26/0과 현재 38/6의 차이는 클라이언트 경로 확장과 템플릿/스캔 범위 오류가 섞인 결과다. 숫자를 서로 합산하거나 아침 결과를 현재 인수로 소급하지 않는다.

현재 실제 계약 판단은 “6개가 모두 미제공”이 아니다. 세 실제 불일치는 Gemini `bd82947` 이후의 `99ca23e`·`777f309` 계열에서 프론트 계약을 정렬했고, 세 오탐은 `adaec4e`에 근거를 기록했다. 이 문서는 소스 정의와 회귀 시험에 근거한 판단이며, live HTTP 404가 실제로 재현된 운영 인수 증거는 아니다.

## 오늘 최종 회귀와 정정 인계

사용자 실행 `a04c17c`: tests/integration 제외, 기본 `not docker_host`, DSN 없음에서 **1263 passed / 489 skipped / 2 deselected / 0 failed, 74초**. 아침 1074 대비 +189이지만 추가 시험의 기원을 전수 대조하지 않았으므로 감사 회귀 증가로 귀속하지 않는다. 시험 수를 완료율로 해석하지 않는다.

다음 다섯 정정은 후속 기록에 남아 있다.

1. image 4/3/2 변동은 harness와 호스트 조건이 함께 달라 인과 실험이 아니다.
2. OneDrive handle 감소·host-init 0건은 관측이며 OneDrive 단일 원인으로 확정하지 않는다.
3. `unreadable`은 이전 실행에서 host-init이 아니라 timeout 범주였다.
4. npm build nonzero 검사는 기존부터 있었고, `84a86f1`은 dist 존재·크기 검사를 추가했다.
5. route 도구의 템플릿 리터럴 누락과 설정 문자열 오인은 도구 오탐이다. 구체적으로 (a) template head를 bare collection으로 추출, (b) Claude가 기록한 prefix/스캔 범위 오탐, (c) `deploymentEngine.ts`의 nginx location/upstream 서술 문자열을 클라이언트 API 호출로 오인하는 세 유형이다.

다음 세션은 외부 대기 5건과 미감사 6영역을 기존 조건대로 재개한다. 오늘 추가된 인계는 route 도구 세 오탐 유형을 적용해 같은 조사를 반복하지 않는 것뿐이다. route 계약은 현재 실제 불일치 0건으로 기록하되, live HTTP 운영 인수로 과장하지 않는다.

## 호스트 시계열 후속 인계

사용자 보고 handle 시계열은 재시작 직후 `2,421` → 약 1시간 후 `119,773` → 현재 `296,475`이며 현재 가용 RAM은 `1,078MB`다. 과거 `641,442`에서 image host-init 실패가 관측됐다. 재시작은 임시 완화이고 OneDrive 동기화 경로의 vault 쓰기가 계속되는 동안 handle이 재증가할 수 있다. 다음 image lane 전에는 실행 직전 handle 수준·추세, RAM, Docker process 시작 상태, 동시 image 실행 부재를 확인한다. 이 관측은 원인 후보를 강화하지만 OneDrive 단일 원인이나 안전 임계치를 확정하지 않는다. 새 환경 조치 없이 같은 lane을 반복하지 않는다.

## 인계

Claude 문서 정정과 PITR cleanup은 착지했다. 남은 운영 항목은 AC-12 활성/별도 저장소, image lane의 business-kernel-role 미검증, 원격 장비와 CI 외부 조건이다. route coverage의 추가 backend endpoint 구현은 현재 필요하지 않으며, 이후 실제 HTTP 계약 변경이 생길 때 해당 owner가 새 경로와 음성 회귀를 함께 제출한다.

## Evidence 계약 최종 결론

Claude `350f5d7`의 데이터 충분성 분석과 Gemini `777f309`의 `ResultView` 경로를 대조했다. 신규 `/v1/.../evidence` 백엔드 엔드포인트는 추가하지 않는다. 기존 `/v1/projects/{project}/runs/{run}/result`가 실제 `evidence` 객체(`evidenceId`, timestamp, actor/action, policyDecisionId, input/output SHA, result)와 `stopReceipt`, state, output을 반환하고, `EvidenceViewer`가 이 응답을 사용하므로 핵심 evidence 패키지는 기존 계약으로 충분하다.

다만 `EvidenceViewer`의 fetch 실패 catch가 합성 `specDigest`, `toolCalls`, `integrityVerification: PASS`를 표시하는 것은 별도 진실성 잔여다. per-tool `toolCalls`와 wall time은 현재 백엔드 응답에 없으므로, 백엔드 계약을 늘리거나 프론트가 해당 가짜 패널을 제거해야 한다. retention/tamper는 정적 정책 라벨로 표시하되 per-run 검증 결과처럼 표현하지 않는다. 이 결론은 소스 계약 대조이며 live HTTP 운영 인수는 아니다.

Gemini `341c035`를 재검토했다. `sha256:verified`와 합성 toolCalls/wall time을 제거했고, fetch 실패는 오류 상태로 표면화한다. 무결성 상태는 `output.verified === true`일 때만 PASS, 명시적 false/실패 상태일 때 FAIL, 그 외에는 UNVERIFIED다. 정책 라벨은 동적 결과와 분리됐다. 사용자 독립 Vitest 31파일 307 passed 및 route test 27 passed와 별도로, Codex는 현재 tip에서 `apps/web/tests/evidence-viewer.test.ts` **5 passed**와 `tests/test_route_coverage.py` **26 passed**를 확인했다. 이로써 오늘 열린 evidence 잔여 세 건은 수정·검증 완료로 닫는다. 전체 Vitest 수와 Codex 수를 합산하지 않는다.
