---
doc_id: "HISTORY-PORTAL-REFRESH-854-REVIEW-20261106-CLAUDE"
title: "2026-11-06 포털 주기 조회·Gateway 상태 UI delta 854a8eab 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Gemini"
audience: "agent"
updated: "2026-11-06T21:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "854a8eab0b6e236b62878f49ee941c700e458af0"
task_ids: ["PORTAL-REFRESH-FLEET-20261106"]
tags: ["portal", "frontend", "independent-review", "polling", "healthz", "claude"]
---

# 포털 주기 조회·Gateway 상태 UI delta 854a8eab 독립 검토

Orca `task_599e55626b4a`, dispatch `ctx_15e621fbe050`이다. 작성자는 Gemini `task_9d814a8270e1 / ctx_d855f1849f6b`이고, 질문 `msg_31779385396e`가 이 판정을 기다린다. 선행 Claude 검토 `ctx_63ce6b6612b7`의 종료·해제는 Root가 확인했다. 검토자는 Claude 하나다. 보조 agent는 쓰지 않았다.

- **대상:** 최종 `854a8eab`. source는 `2d87d7aa`, 최초 후보는 `3a837076`, 불변 base는 `53683020`이다. 원격 branch head는 검토 시점에 `854a8eab`이었다.
- **Git 확인:** base→854에서 non-doc 경로 변경은 8개다. 2d87→854에서 non-doc 변경은 0이다. 8개 파일 모두 854와 2d87의 blob이 같다. 작성자 History·Evidence 2개가 추가됐다. Root의 `.work/ui854-source-root-verified.json`, 3a 지적 `portal-refresh-3a-root-contract-findings.json`, Root 미리보기 설정 `ui854-preview.config.mjs`는 읽기만 했다.
- **실행한 tree:** 854를 `git archive`로 session scratch에 풀었다. apps/web·contracts·tools의 모든 blob hash가 854 tree와 같다(apps/web 281/281). 의존성은 `supervision-integration-20261104`의 설치본을 junction으로 빌렸다. 설치 버전은 854 lock과 265/265 같다. 설치·lock 변경은 없다. 작성자 worktree의 src는 실행하지 않았다.
- **기계 판독 결과:** `docs/vault/30_Development/Evidence/portal-refresh-854-review-20261106-claude/review.json`
- **명령·exit·log hash:** 같은 폴더의 `commands.json`, `reviewer-results.txt`. 검토용 probe 원문은 `reviewer_probe_portal854.test.tsx.txt`다.

## 판정

**REVISION_REQUIRED.** Medium 1건(UI-854-M1), Low 4건, Info 5건이다. 사용자가 본 빈 클러스터 5초 깜빡임과 `/v1/health` 404로 생긴 거짓 Offline은 고쳐졌다. 그러나 R-UI-M1과 R-UI-M2는 **둘 다 부분 종결**이다. 854는 배포 판단 대상으로 승인하지 않는다.

### R-UI-M1 — 부분 종결

- **닫힘:** Header는 정본 `GET /healthz`를 부른다. 이 경로는 `app.py:347`에서 익명으로 `{status:'ok', version}`을 돌려준다. online은 `res.ok`, `application/json`, `status==='ok'`가 모두 맞을 때만이다. probe H1에서 HTML 200, JSON 404, JSON 503, JSON 200 `status:'down'`, 네트워크 오류는 모두 online이 아니었다. base에서는 HTML 200과 `status:'down'`이 online이었다.
- **닫힘:** 초기 상태는 `확인 중...`과 unknown 점이다. 가짜 8ms와 5/5 기본값은 없어졌다.
- **닫힘:** nginx 443 `location = /healthz`는 기존 `/readyz`와 같은 upstream 설정이다. add_header가 없으므로 server 수준의 보안 header include를 상속한다. HTTP 80의 평문 `OK`는 그대로다. Vite dev·preview proxy에 `/healthz`가 추가됐다. Root의 3100 미리보기 설정도 `/healthz`를 proxy한다.
- **남음 — UI-854-L1:** 받은 HTTP 응답이 계약에 맞지 않을 때와 네트워크 실패가 모두 `Offline`으로 표시된다. Root M1은 이 둘의 구분을 요구했다.

### R-UI-M2 — 부분 종결

- **닫힘:** App 수준 probe(fake timer, mock apiClient)로 확인했다. 빈 카드는 6주기 동안 같은 DOM 요소로 유지되고 metric 카드로 바뀌지 않는다(P1). 초기 대기 중에는 `정상 조회 결과: 0대`가 나오지 않는다(P1). 빠른 갱신 실패에서는 `role=alert` stale 배너, 오류 문구, 스냅샷 시각, 재시도 버튼이 보이고, 회복하면 사라진다(P2). 비어 있지 않은 스냅샷은 실패 중에도 유지된다(P3). 늦게 온 이전 응답은 무시된다(P4). 프로젝트를 바꾸면 상태가 unknown으로 돌아가고 이전 프로젝트의 늦은 응답은 버려진다(P5). base에서는 P1·P2·P3·P5가 실패한다.
- **남음 — UI-854-M1:** 응답이 5초보다 늦으면 다음 poll이 요청 번호를 올린다. 그래서 이전 요청의 성공과 실패가 **모두** 버려진다. background 모드에서는 상태도 `success`에서 바뀌지 않는다. P6(매 응답 6초): 60초 동안 13번 호출했지만 새 노드는 안 보이고 stale 배너도 없다. 화면은 계속 `정상 조회 결과: 0대`다. P7(응답이 멈췄다가 60초 뒤 504 형태로 실패): 배너도 오류도 없이 `정상 조회 결과: 0대`가 남는다. base에서 같은 상황은 현재 성공 문장을 보여 주지 않았다. M2의 "실패했는데 정상 0대로 보임"이 지연 조건에서 남는다.

## 지적과 최소 수정

| id | 심각도 | 위치 | 반례 | 최소 수정 |
|---|---|---|---|---|
| UI-854-M1 | Medium | `App.tsx:287-336`, `428-437` (runs·approvals·workspaces도 같은 패턴) | P6, P7 | 자원별로 이전 요청이 아직 진행 중이면 background tick을 건너뛴다(in-flight ref). poll마다 `AbortSignal.timeout`을 걸고 시간 초과를 오류 경로로 보낸다. 또는 `lastFetchedAt`이 N주기보다 오래되면 stale로 표시한다. P6·P7 형태의 App 시험을 추가한다. |
| UI-854-L1 | Low | `Header.tsx:39-73`, `225-232` | H1의 5가지가 모두 Offline | 받은 응답이 계약에 맞지 않으면 `응답 오류 (HTTP n)` 같은 상태로 표시한다. Offline은 fetch 거부와 시간 초과에만 쓴다. |
| UI-854-L2 | Low | `Header.tsx:39-73` | H2: 느린 이전 성공이 더 새로운 실패를 덮어씀(base에도 있음) | 순번 fence와 5초 미만 timeout을 둔다. |
| UI-854-L3 | Low | `App.tsx:785` → `ResourceExplorer.tsx:1172` | `onClick={onRetryNodes}`이 MouseEvent를 `isBackground`로 넘겨 수동 재시도가 background로 실행됨 | `() => fetchNodes(false)`로 넘긴다. |
| UI-854-L4 | Low | `portal-refresh-fleet-ui.test.tsx` | 20개 시험이 App을 mount하지 않는다. 9절은 시험 안에서 만든 대체 함수를 검사한다. | P1–P7 형태의 App 시험을 추가한다. `approvalsState=error`에서 승인·반려 클릭이 decision API를 부르지 않는지 확인한다. |

## accept한 부분과 Info

- **수용:** 깜빡임 원인은 매 poll의 `loading`과 metric 분기로의 이탈이었고, 고쳐졌다. `/studio` callback은 dashboard 탭으로 도착한다(`App.tsx:560`). 그곳이 보고된 화면이다. 위조된 5/5·자원·시각은 없다. `chooseProject`는 네 가지 요청 번호를 모두 올리고 상태와 `lastFetchedAt`를 초기화한다. 로그아웃 경로도 원래 모두 초기화한다. nginx의 다른 경로, 보안 header, Authorization 전달은 바뀌지 않았다.
- **I1 timeout:** `fixture-problem-codes-integrity.test.ts`는 시험 하나의 timeout만 20000ms로 늘렸다. 검사 pattern과 정본 형식 `/^[A-Z]+-[0-9]{4}$/`는 그대로다. 전역 timeout 변경도 없다. 단독 실행은 100ms였다. 작성자 기록에는 첫 실패도 이유도 없다. 약화는 아니지만 이유를 남기거나 되돌려야 한다.
- **I2 auth:** `preferred_username`·`name`·`email`은 기존 nonce·iss·aud·azp·exp·iat 검사와 `/v1/session` 검증(`oidc:<64hex>`, tenant, 만료 상한)을 모두 통과한 뒤에만 읽는다. 이 값은 `user.name`에만 들어간다. `id`·`tenantId`·role은 서버 session 값 그대로다. `user.name`은 Header 표시에만 쓰인다. completeLogin의 서명 검증이 `config.jwks`가 있을 때만 이뤄지는 것은 원래 동작이다. 그래서 JWKS가 없으면 표시 이름은 claim 검사만 통과한 token에서 올 수 있다. 권한에는 영향이 없다.
- **I3 승인:** `approvalsState==='error'`이면 승인·반려가 거부된다(정적 확인). 최종 권한은 backend에 있다. workspace 목록은 실패 중에도 유지되지만 목록 자체에는 마지막 성공 시각이 없다. 앱 상단의 `role=alert`로만 실패를 알린다.
- **I4 preview:** preview 기본 port가 Vite 기본 4173에서 3000으로 바뀐다. host `0.0.0.0`은 원래 server 설정에서 상속되던 값이다.
- **I5:** stale `role=alert`가 빈 카드의 `role=status` 안에 들어 있다. 둘 다 읽히므로 문제없다.

## 실행 결과 요약

| 항목 | exit | 결과 |
|---|---|---|
| 작성자 targeted 시험 | 0 | 20/20 |
| 전체 Vitest(직렬) | 1 | 101/103 file, 1232/1238 test. 실패 6개는 scratch에 `.git`이 없어서 생겼다. |
| 위 2개 file, GIT_DIR를 HEAD 854에 고정 | 0 | 44/44(위 6개 포함) |
| 검토자 probe(854 / base) | 0 / 1 | 13/13. base는 6개 실패로 수정 효과를 구분한다. |
| tsc -b / vite build | 0 / 0 | build 5.48s |
| frontend integrity / contract bindings / route coverage | 0 / 0 / 0 | 94 file·9 rule / 57·21·14 / 41 passed |
| ESLint(변경 7개 file) | 0 | 경고 0 |
| sync `--check`(문서 작성 전) | 0 | 2829 managed, 0 conflicts. state hash가 실행 전후 같다. |

첫 병렬 전체 실행은 node 프로세스가 비정상 종료했다(exit -1073740791). 남은 메모리가 약 200MB였다. 그 실행은 apps/web만 푼 불완전 tree였고, 제품 실패가 아니다.

## 한계

- live 3100·8080·8443, 브라우저, TLS, Docker는 실행하지 않았다. nginx와 proxy는 설정 원문으로 검토했다. 컨테이너 수준 증거는 Root가 검증한 hosted Frontend `42211235450`의 Portal Container smoke job `127870097238`뿐이다.
- probe는 happy-dom, mock fetch·apiClient, fake timer에서 돌았다. 실제 브라우저나 fleet SSO 인수가 아니다. 작성자가 인용한 Portal Login Harness `42207878338`은 2d87·854 이전 실행이다. 게다가 mock이 많다.
- 로컬 bundle 이름(`index-jJ3-copl.js`)은 작성자 로컬과 다르다. artifact 동일성은 Root가 CI artifact로 판단한다.
- UI 수용 판정은 5PC·자원 수용이 아니다. 배포, artifact, 전체 프로그램 완료를 뜻하지 않는다.

## 다음 행동

1. **Gemini (같은 task):** UI-854-M1을 반드시 고친다. L1–L4도 고친다. 새 불변 후보, fresh exact Frontend·Docs CI, 자기 History·Evidence를 낸 뒤 Root에 다시 요청한다.
2. **Root:** 854는 배포하지 않는다. 수정 delta에 대해 Claude 좁은 재검토를 한 번 배정한다.
3. **Claude:** 재검토 때 P6·P7·H1·H2·L3 반례를 새 후보에서 다시 실행한다.
