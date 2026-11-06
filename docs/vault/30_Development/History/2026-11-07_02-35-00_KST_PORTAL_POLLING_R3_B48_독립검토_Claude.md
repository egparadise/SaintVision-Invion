---
doc_id: "HISTORY-PORTAL-POLLING-R3-B48-REVIEW-20261107-CLAUDE"
title: "2026-11-07 포털 폴링 R3 SOURCE b48c2c44 좁은 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Gemini"
audience: "agent"
updated: "2026-11-07T02:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b48c2c4492f8aea4b55c33161733a9a6fb9eed8c"
task_ids: ["PORTAL-REFRESH-POLLING-R3-20261106"]
tags: ["portal", "frontend", "independent-review", "polling", "healthz", "abort-signal", "claude"]
---

# 포털 폴링 R3 SOURCE b48c2c44 좁은 독립 검토

이 검토는 Orca `task_7143a8fe0491`, dispatch `ctx_8d5d03bf83b3`로 진행했다. owner는 Gemini `task_8dfd2a5d01a2 / ctx_c8a99a3645b0`이다. 이전 author task는 닫혔고 새 author agent는 없다. 검토자는 Claude 하나이며 보조 agent는 쓰지 않았다.

- **대상:** SOURCE `b48c2c44`. 첫 commit은 `9cd017ab`이고, 수락된 R2 delivery base는 `9c25f3c9`이다. 원격 branch `agent/gemini/portal-refresh-polling-r3-20261106`의 head는 검토 시점에 `b48c2c44`였다. 부모 관계는 b48^ = 9cd, 9cd^ = 9c25이다.
- **범위 확인:** R2에서 b48까지 바뀐 경로는 정확히 3개다. `apps/web/src/app/App.tsx`, `apps/web/src/shared/ui/Header.tsx`, `apps/web/tests/portal-refresh-fleet-ui.test.tsx`이다. 9cd에서 b48까지는 fetchApprovals의 `catch (err: any)`를 `catch`로 바꾼 한 줄뿐이다. backend·auth·deps·workflow·wire·config 변경은 없다. `client.ts`, `nodeCertificateObservation.ts`, `ResourceExplorer.tsx`의 blob은 R2와 같다.
- **판정 경계:** 이 판정은 SOURCE b48에만 적용된다. 작성자 최종 보고서는 아직 고정되지 않은 초안이어서 입력으로 쓰지 않았다. 최종 보고서의 NONDOCS가 b48과 같은지, 최종 Docs가 정확한지는 Root가 배포 전에 따로 확인한다. 이 gate들은 면제되지 않았다. 배포·preview·실제 browser·TLS·SSO·5PC 수용도 이 판정에 들어가지 않는다. FE registry 전체 완료나 global 100도 부여하지 않는다.
- **기계 판독 결과:** `docs/vault/30_Development/Evidence/portal-polling-r3-b48-review-20261107-claude/review.json`
- **검토자 실행 증거:** 같은 폴더의 `reviewer-verify-b48.json`(스크립트 `reviewer_verify_b48.py.txt`), `commands.json`, `local-doc-gates.txt`

## 판정

**SOURCE_AXIS_ACCEPT (좁은 SOURCE 축).** 남아 있던 R2 지적 UI-R2-M1, L1, L2, L3는 모두 종결이다. 실질적인 새 문제는 없다. 차단하지 않는 Info만 6건 있다.

| 지적 | 상태 | 근거 |
|---|---|---|
| UI-R2-M1 인증서 두 번째 leg 무제한 대기 | CLOSED | `apps/web/src/app/App.tsx:355-363`에서 같은 `controller.signal`을 넘긴다. 중단된 inner catch는 다시 throw하고, 중단이 아니면 `certObs = null`로 둔다. 10s 타이머(`apps/web/src/app/App.tsx:333-335`)는 두 leg를 모두 덮는다. timeout이면 outer catch가 오류와 10s 문구를 설정한다. 이때 session/scope/applied fence는 그대로 적용된다. R1(인증서 hang)과 R1b(60s 504)는 current-0으로 남지 않고 10s 안에 stale 경고로 바뀐다. T1은 실제 client wrapper를 쓰고 전역 fetch만 mock한 상태에서 `/node-certificates` fetch에 signal이 실리고 10.5s에 abort됨을 확인한다. |
| UI-R2-L1 supersede abort를 timeout으로 오분류 | CLOSED | 네 resource 모두 timeout을 소유 `controller.signal.reason`(REQUEST_TIMEOUT)으로만 판정한다(`apps/web/src/app/App.tsx:376-382`, `apps/web/src/app/App.tsx:431-437`, `apps/web/src/app/App.tsx:489-495`, `apps/web/src/app/App.tsx:546-552`). 그 밖의 abort는 상태를 건드리지 않고 return한다. `err.name`/`err.message` 분류식은 하나도 남지 않았다(regex 0건). REQUEST_TIMEOUT abort를 거는 곳은 소유 타이머 4곳뿐이다. 수동 supersede, project 전환, logout, unmount는 모두 reason 없이 abort()한다. finally의 clearTimeout과 applied fence는 바뀌지 않았다. |
| UI-R2-L2 Header body가 deadline 밖에 있음 | CLOSED | clearTimeout은 finally에만 1곳 있다(`apps/web/src/shared/ui/Header.tsx:88-90`). `res.json()`은 4s deadline 안에서 실행된다. abort된 body는 다시 throw되어 Offline이 된다. abort가 아닌 malformed JSON은 degraded(비정상 응답)가 된다. body를 읽은 뒤 seq/mount fence를 다시 확인한다(`apps/web/src/shared/ui/Header.tsx:76`). 해당 테스트는 H3/H3b/H4/H5/H1/H2다. |
| UI-R2-L3 실제 App 테스트가 약함 | CLOSED | R8은 approvals 오류가 관찰된 상태에서 실제 reject 버튼과 '반려 확인'을 누르고, decideApproval이 0회 호출되며 실패 문구가 나오는지 확인한다. R8c는 같은 경로가 정상일 때 decideApproval이 정확히 1회 호출되는지 확인한다. R9는 실제 Explorer 재시도를 누른 뒤 오류 배너가 지워지고 foreground loading이 보이는지 확인한다. Root PC3 MD는 R8 하나만, ME는 R9 하나만 실패시켰다(인과 증거). |

## 새 상호작용 점검(차단 아님)

- **UI-R3-I1:** R2b에서 `bgReq.reject(new Error('REQUEST_TIMEOUT'))`는 아무 효과가 없다. mock의 abort listener가 이미 promise를 reject했기 때문이다. R2b가 증명하는 것은 AbortError supersede가 timeout으로 분류되지 않는다는 점까지다. "늦게 도착한 err.message REQUEST_TIMEOUT"이 timeout이 아니라는 점은 b48 source를 정확히 읽어서 확인했다. 정적 추론으로는 err.message fallback을 다시 넣어도 현재 suite가 잡지 못한다. 보강은 선택 사항이다.
- **UI-R3-I2:** T1은 abort 여부만 단언하고, reason과 UI 결과는 단언하지 않는다. UI 결과는 R1/R1b(mock apiClient)가 덮는다.
- **UI-R3-I3:** 인증서 leg만 계속 hang해도 노드 view는 stale이 되고 노드 timeout 문구가 나온다. R3 계약대로의 동작이다. 문구가 어느 leg에서 timeout이 났는지 구분하지 않는다는 점만 남는다.
- **UI-R3-I4:** P9의 회복 단언이 R9의 loading 단언으로 대체되었다. 수동 재시도 후 회복은 App 수준에서 단언하지 않는다. 배경 회복은 P2가 덮는다.
- **UI-R3-I5:** handleReject rethrow로 생기는 unhandled rejection은 R2 이전부터 있던 harness 한계다(UI-R2-I3). 새 auth 재설계가 아니고, 제품 성공을 숨긴 것도 아니다.
- **UI-R3-I6:** reason 문자열 비교 분기는 중복이지만 해가 없다. success 경로는 abort를 다시 확인하지 않는다. 이것도 R2 이전부터 있었고, fetch로는 도달할 수 없다.

## 증거 귀속과 한계

- **검토자가 직접 실행한 것:** 읽기 전용 Git(rev-parse, ls-remote, diff, ls-tree, show)과 Python `-I` 검증 스크립트를 실행했다. 스크립트가 확인한 항목은 범위, 한 줄 lint delta, 분류식 regex, 테스트 46건(it 41 + it.each 5)이다. 또 Root receipt 5개의 SHA-256, PC3 control 입력 446/446이 b48 bytes와 같다는 점, MD/ME가 바꾼 파일 집합도 확인했다. 그 밖에 gh로 Frontend run 2건을 읽기 전용으로 재확인했고, 로컬 doc gate를 돌렸다. Node·Vite·Vitest·browser·Docker는 실행하지 않았다. 호스트 메모리 제약 때문이며 Root 지시에 따른 것이다.
- **Root가 실행한 것:** Frontend `42254157322`(head b48, frontend.yml, workflow_dispatch, attempt 1, job 128016761183 12/12, 128016761717 14/14 성공. 검토자도 읽기 전용으로 재확인했다). 호스트 Vitest는 103 files/1264 tests, 실패 0, skip 0이었다. artifact `13520599988`(1119300B, SHA-256 7212b487…)도 Root가 받았다. PC3 guard는 control 46/0, MD 45/1(R8), ME 45/1(R9)이었고, 각 container exit는 0/1/1이었다. 이것들은 Root의 실행이며 검토자의 실행이 아니다. 같은 46건을 세 번 돌린 것이므로 새 고유 coverage로 주장하지 않는다. Root가 남긴 infrastructure 실패(source export preflight, contracts 입력 누락으로 인한 첫 control 0건, install ledger cwd 필드)는 제품 실패도 mutant kill도 아니다.
- **보존된 실패:** 초기 9cd의 Frontend `42247974625`는 Run ESLint 단계에서 실패했다(unused catch). 그 뒤 Vitest·type·build·upload 단계는 건너뛰었고, container job은 성공했다. b48이 이 실패를 고친 commit이다.
- **한계:** 테스트는 happy-dom, fake timer, mock apiClient/session 위에서 돈다. T1은 전역 fetch만 mock했다. 실제 browser, TLS, SSO, nginx, 5PC는 아니다. mutant patch는 SHA로만 남아 있다. 검토자는 바뀐 파일 집합만 확인했고 patch 본문은 확인하지 않았다.

## 다음 첫 행동

Root가 작성자 최종 보고서의 NONDOCS가 b48과 같은지, 최종 Docs가 정확한지 확인한다. 그다음 canonical checkpoint로 receipt를 게시하고 staging을 판단한다. source 수정은 필요 없다. UI-R3-I1 테스트 보강은 선택 사항이다. 배포·실제 browser·TLS·SSO·5PC는 Root 소유의 별도 gate로 남는다.
