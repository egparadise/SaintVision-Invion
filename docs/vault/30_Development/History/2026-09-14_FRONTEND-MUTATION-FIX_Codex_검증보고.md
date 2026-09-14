---
doc_id: "HIST-FRONTEND-MUTATION-FIX-REPORT-20260914"
title: "2026-09-14 FRONTEND-MUTATION-FIX Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T20:58:26+09:00"
source_of_truth: "Git"
---

# 승인·일반 취소 수정 후보 전달

CX-01/FE-M01·02. 제품8037166348300ea9eb63fd7a69a291b98c302e70, branch agent/codex/frontend-mutations(base6212291), commit/push 완료. Codex 작성/Claude 독립 검토·Gemini 통합 pending. 공유 integration의 미커밋 작업을 보존했다. 이 후보는 아직 main/integration 병합·운영 배포되지 않았다.

- shared/api/kernelMutations.ts: 승인/반려는 challenge `{}`→nonce+화면의 고정 actionDigest+decision, opaque Idempotency-Key로 전송. await 전 digest를 고정해 중간 객체 변경으로 승인 대상이 달라지지 않는다. project/digest 누락 시 요청하지 않는다. 별도경로재전송없음.
- 일반 Run 취소는 현재 RunId/version을 조회·검증하고 `{expectedVersion}`만 전송한다. 오류/불확실응답을 cancelled로 합성하지 않고 사용자에게 확인실패를 알린다. App은 기존상태를보존하고 오류를호출자에게전파한다.
- ApprovalItem에actionDigest보존, App승인/반려연결. ApprovalDetail은 digest없으면승인을막고, 서버가저장하지않는반려사유입력/영구Evidence기록문구를제거해확인만받는다. 이유기록기능을새로추가한것은아니다.
- npm ci --offline --ignore-scripts --no-audit --no-fund:새worktree에111패키지설치/exit0. npm test -- --run: **20파일127시험통과/2.89s**(새계약12개포함). API는모사하며실제브라우저시험아님. npm run build:TypeScript및Vite6.4.3 build exit0/6.43s. 변경후최종build확인. build파일배포없음.
- tests는approve/reject·고정digest·challenge실패·누락scope/digest·최신version·오류전파·fallback없음을검사한다. 이전b95ab27의실제PG/HTTP6개증거와구분한다.
- 같은SHA CI4건(Frontend/Core/Backend/Docs)모두billing제한으로job시작전실패. [CI증거](../Evidence/frontend-mutation-fix-ci-8037166.json). 독립검토/운영인수미완료,전체57.81%유지.

## 동시 작업과 다음 담당

Gemini가공유checkout의RunDetail/DeveloperStudio를수정중이며이파일들은후보에서변경하지않았다. FE-M03/04/05전체완료를주장하지않는다. Gemini는8037166을검토해App/ApprovalDetail/타입을병합하고, 재사용helper로샤드취소를연결하거나동등계약을검증한다. 편집중인App과충돌가능하므로무조건파일덮어쓰기를하지않는다. Codex는합친새SHA에서승인·취소실패·빈관측·로딩검토를이어간다.

Claude c5c014e는b95ab27의재현시험이정본동작에근거한다고독립검토했다(실제commit내용수신). 이는8037166수정후보승인이아니다. 수동reclaim제거/부모cancel재사용에동의하며새kernelroute불필요로정정했다. 운영OIDC/실장비/CI인수는남는다.
