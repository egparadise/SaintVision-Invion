---
doc_id: "HISTORY-PORTAL-POLLING-R2-9C25-REVIEW-20261106-CLAUDE"
title: "2026-11-06 포털 폴링 R2 UI delta 9c25f3c9 좁은 독립 재검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Gemini"
audience: "agent"
updated: "2026-11-06T22:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9c25f3c9cab162f424744d79f9a4e21729c40404"
task_ids: ["PORTAL-REFRESH-POLLING-R2-20261106"]
tags: ["portal", "frontend", "independent-review", "polling", "healthz", "abort-signal", "claude"]
---

# 포털 폴링 R2 UI delta 9c25f3c9 좁은 독립 재검토

Orca `task_855e5f3977e0`, dispatch `ctx_ed14d0be16a1`이다. 작성자는 Gemini `task_9d814a8270e1 / ctx_d855f1849f6b`이고, 질문 `msg_ee333237c962`가 이 판정을 기다린다. 검토자는 Claude 하나다. 보조 agent는 쓰지 않았다.

- **대상:** 최종 `9c25f3c9`. source는 `22c20a83`이고, 불변 base는 `854a8eab`이다. 원격 branch `agent/gemini/portal-refresh-polling-r2-20261106`의 head는 검토 시점에 `9c25f3c9`였다. 작성자가 처음 보고한 `9c25f3c95e1e…`는 존재하지 않는 SHA라서 쓰지 않았다.
- **Git 확인:** 854→9c의 non-doc 변경은 6개 경로다(App, Header, ResourceExplorer, projectObservation, runApprovalObservation, portal-refresh 테스트). 22c→9c의 non-doc 변경은 0이다. docs 쪽은 작성자 `verification.json` 수정과 History 1건 추가다. nginx·Vite·auth·ClusterOverview·lock blob은 854와 같다.
- **실행한 tree:** 9c를 `git archive`로 session scratch에 풀었다(apps/web·contracts·tools·packages). 662개 blob의 hash가 9c tree와 모두 같다(apps/web 281/281). 의존성은 `supervision-integration-20261104` 설치본을 junction으로 연결했다. 설치된 215개의 버전이 lock과 같고, 없는 50개는 모두 optional platform 패키지다. 설치나 lock 변경은 하지 않았다. 작성자 worktree의 src는 실행하지 않았다.
- **CI(읽기 전용 재확인):** Frontend `42219574051`(head 22c, frontend.yml, workflow_dispatch, attempt 1, job 127897973932 12/12, 127897974300 14/14 성공). Docs `42221567010`(head 9c, docs.yml, attempt 1, Root 상관값 `Root-UIR2-FINAL-DOCS-9c25f3c9-…`, job 127904637893 19/19 성공). 검토자는 CI를 다시 실행하지 않았다.
- **기계 판독 결과:** `docs/vault/30_Development/Evidence/portal-polling-r2-9c25-review-20261106-claude/review.json`
- **명령·exit·log hash:** 같은 폴더의 `commands.json`, `reviewer-results.json`. probe와 도구 원문은 `*.txt`로 보관했다.

## 판정

**REVISION_REQUIRED.** Medium 1건(UI-R2-M1), Low 3건, Info 6건이다. 854 검토 지적의 처리 상태는 다음과 같다. L1·L3는 종결이다. M1·L2·L4는 부분 종결이다. 9c는 배포 판단 대상으로 승인하지 않는다. 854도 계속 배포 불가다.

## 종결 확인

- **M1(부분):** 굶주림은 해결됐다. 적용 fence를 `request > appliedRef` 단조 증가로 바꿔서, 늦게 온 응답도 더 최신이면 반영된다. 모든 /nodes 응답을 6초로 늦춘 120초 probe(R3)에서 노드가 표시되고 오류는 없다. 동시 요청은 최대 2개다. /nodes가 무응답이면(R4) 15.5초 안에 role=alert stale과 '응답 시간 초과'가 뜬다. 60초에도 '정상 0대'로 돌아가지 않고, 복구 후에는 해제된다. 늦게 온 옛 응답 폐기(P4), 프로젝트 전환(R5), 로그아웃(R6), unmount(R7) fence도 확인했다. 실제 apiClient로 돈 T1에서 /nodes·/runs·/approvals·/workspaces fetch가 모두 signal을 받고, 10초에 `REQUEST_TIMEOUT`으로 abort된다.
- **L1(종결):** 상태가 unknown·healthy(RTT)·degraded '비정상 응답'·offline으로 나뉜다. HTML 200, JSON 404/503, status≠ok는 '비정상 응답'이다. 네트워크 실패와 4초 timeout은 'Offline'이다. 작성자 H1이 통과하고, MF mutant는 작성자 테스트 6개에서 죽는다.
- **L2(부분):** 순서 fence는 동작한다(H2, MC mutant 죽음). fetch 단계의 4초 deadline도 동작한다(H4).
- **L3(종결):** 모든 수동 호출자가 인자 없는 callback을 받는다. `isBackground === true`로 엄격 비교한다. 실제 `nodes-retry-btn` 클릭(R9) 시 오류 배너가 사라지고 loading이 표시된다.
- **L4(부분):** 실제 App mount와 fake timer 테스트가 추가됐다. 작성자 테스트가 guard 제거 mutant MA, MB, MC, MF를 죽인다.

## 지적

- **UI-R2-M1 Medium:** `App.tsx:357`의 `fetchProjectNodeCertificates(targetPrj)`가 controller signal을 받지 않는다. 이 함수는 signal 인자를 이미 지원한다. 그래서 /node-certificates가 무응답이면 10초 abort가 아무 효과가 없다. 이미 받은 노드 목록도 반영되지 않는다. R1에서는 15초, 30초, 60초 모두 '정상 조회 결과: 0대'가 남았고, stale 표시는 없었다. 그동안 인증서 요청 13개가 쌓였고, signal이 붙은 것은 0개였다. nginx 기본값과 같은 60초 504(R1b)에서도 30초 시점까지 현재 0대로 표시됐다. **최소 수정:** `fetchProjectNodeCertificates(targetPrj, controller.signal)`. scratch에서 R1/R1b가 통과하고 작성자 35/35도 그대로임을 확인했다.
- **UI-R2-L1 Low:** 수동 재시도가 진행 중인 background 요청을 reason 없이 abort한다. 그 catch가 `AbortError`를 timeout으로 분류해 적용한다. 그래서 사용자가 누르자마자(0ms) '10s Timeout' 오류와 stale 배너가 뜬다(R2). runs, approvals, workspaces도 같은 모양이다. **최소 수정:** abort됐는데 reason이 REQUEST_TIMEOUT이 아니면 적용하지 않는다. timeout 판정은 `signal.reason`으로 한다. scratch에서 R2가 통과함을 확인했다.
- **UI-R2-L2 Low:** `Header.tsx:59`에서 header를 받은 직후 timer를 해제한 뒤 `res.json()`을 await한다. body가 멈추면 deadline이 없다. H3에서는 60초, 13회 동안 마지막 healthy 표시가 그대로 남았다. **최소 수정:** timer는 finally에서만 해제한다. scratch에서 H3이 통과함을 확인했다.
- **UI-R2-L3 Low(테스트):** P8은 승인이나 반려 버튼을 누르지 않는다. P9는 foreground 실행 여부를 보지 않는다. 그래서 approvalsState guard 제거(MD)와 event-as-background 복원(ME) mutant가 작성자 suite에서 살아남는다. 검토자 R8(실제 반려 클릭, R8c 성공 대조군 포함)과 R9만 이 둘을 죽인다. R8·R9·R1·R2·H3·로그아웃 모양의 테스트를 추가해야 한다.

세 최소 수정을 함께 적용하면 작성자와 검토자 테스트 49/49가 통과했다. 원본 blob은 복원했고, hash로 다시 확인했다. 이 결과는 수정 방향을 보여 주는 검토자 실험이다. 작성자 source를 고친 것이 아니다.

## Info

- I1: Root가 문구로 요구한 "background tick 건너뛰기 + 소유 요청만 finally에서 해제"와 설계가 다르다. 대신 모든 tick을 보내고, 마지막 적용보다 새 응답만 적용한다. probe 기준으로 굶주림이 없고(R3), 동시 요청은 최대 3개이며, 역전 덮어쓰기도 없다.
- I2: 자원별로 최신 controller만 보관한다. 그래서 unmount, 로그아웃, 전환 때 이전에 겹친 요청은 자기 10초 timer로 끝난다(R7). 데이터 누출은 없다.
- I3: 승인·반려 guard는 실제로 동작한다(R8 결정 호출 0회, R8c 1회). 다만 handleReject가 다시 던진 오류가 미처리 rejection 1건을 남긴다. R2 이전부터 있던 동작이다.
- I4: '비정상 응답'은 계약 오류와 unhealthy를 한 라벨로 묶고, HTTP status를 보여 주지 않는다.
- I5: `isBackground: boolean | any` 타입이 넓다.
- I6: '(10s Timeout)' 문구가 하드코딩돼 있다.

## 검토자 실행

모든 실행은 정확한 9c bytes에서 직렬로, worker 1개로 했다. 작성자 targeted 35/35, acc09 46/46, certificate freshness 9/9, live-observation 27/27, run-approval contract 6/6이 통과했다. `tsc -p app/node --noEmit`은 exit 0이다. 변경된 6개 파일에 대한 eslint `--max-warnings 0`도 exit 0이다. 검토자 probe는 10개 통과, 반례 4개(R1·R1b·R2·H3)이고, transport T1은 1/1이다. 처음 실행한 `tsc -b`는 export에 `packages/contracts-ts`가 없어서 오류 35건으로 실패했다. 이는 환경 누락이고, 후보의 결과가 아니다. 그 `tsc -b`는 junction을 통해 `supervision-integration-20261104/apps/web/node_modules/.tmp`의 gitignored tsbuildinfo 두 개를 다시 썼다. 추적 파일 변경과 삭제는 없다. 이후로는 build mode를 쓰지 않았다. full Vitest와 vite build는 정확한 22c의 CI Frontend가 독립 증거다. 로컬 문서 게이트 10개와 canonical Root sync CHECK 전·후는 모두 exit 0이다(`local-doc-gates.txt`). 두 CHECK 사이에 canonical state hash가 바뀌었다. 파일 시각과 Root commit `5146f18c`로 보아 외부 Root apply다. 검토자의 각 CHECK는 실행 중에 state를 바꾸지 않았다.

## 한계

happy-dom, mock apiClient·fetch, fake timer 기반이다. 실제 browser, TLS, fleet SSO, live 3100/8080/8443/r5, Docker는 다루지 않았다. 옛 Portal Harness 42207878338은 쓰지 않았다. 작성자의 로컬 수치는 작성자 증거로만 둔다. 854 검토의 parallel crash와 no-git fixture 결과는 그 검토자의 fixture 결과이고, 새 작성자 통과로 인용하지 않는다.

## 다음 행동

Gemini가 같은 task에서 UI-R2-M1(필수)과 L1~L3를 새 불변 후보로 고친다. 그 후보에 대해 정확한 Frontend·Docs CI를 새로 돌린다. 그다음 Root가 Claude에게 좁은 재검토 1회를 요청한다. Root는 9c를 stage하거나 배포하지 않는다. 공유 진행판, registry, ADR은 Root가 갱신한다.
