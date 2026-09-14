---
doc_id: "HIST-RUN-APPROVAL-OBSERVATION-REPORT-20260914"
title: "2026-09-14 RUN-APPROVAL-OBSERVATION Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T23:23:06+09:00"
source_of_truth: "Git"
---

# Run·승인 관측 수정 후보

제품 b0ecb5e2d5ba1be049ec86ed326ed9fe8994b2ba, branch agent/codex/frontend-mutations, base7b50ae2. commit/push 완료. 공유 integration/main 미병합·운영 미배포. owner Codex, Claude 독립 검토/Gemini UI 통합 및 브라우저 인수 대기.

- 커널 `inv.runs.public`의 runId/projectId/state/version/attempt를 명시적으로 변환한다. 없는 Workspace/요청자/목적/생성 시각은 optional·미관측이며 현재 시각으로 채우지 않는다. 잘못된 상태/버전/시도/다른 프로젝트 응답을 거부한다.
- `inv.approvals.view`의 식별자·project·requester·actionDigest·policy·requiredApprovals·상태·만료·runVersion을 보존한다. 승인 인원수로 위험도를 추정하지 않는다. 가짜 node/workspace/명령/nonce/예산1000만원/격리반경/현재시각을 제거했다. dispatched를 pending으로 바꾸지 않는다.
- 승인 센터에서 예제 검토자 계정 선택을 제거하고 실제 로그인 계정을 표시한다. 실제 인가는 서버가 수행한다. 다른 안건 선택 시 만료 타이머를 해당 안건으로 다시 초기화한다.
- 현재 정본 ApprovalView에는 검토할 명령/위험도 자체가 없다. 화면은 이를 미관측으로 표시하고 **승인을 보류**한다. App handler와 Studio 승인 경로에서도 임의 내용으로 승인이 진행되지 않도록 막았다. 이는 승인 기능 완료가 아니라 기존 거짓 안전 표시 제거다. 반려의 기존 challenge/digest 경로는 유지한다.
- Run/승인 조회 실패는 목록을 비우고 오류를 표시하며 같은 조회가 성공하면 해당 오류를 해제한다. 프로젝트 세대 및 요청 순번을 비교해 이전 프로젝트/역순 응답 적용을 막았다. 브라우저에서 지연응답/로그인 전환 실검증은 아직 없다.

검증: Windows `npm.cmd --prefix apps/web test` 24파일 **182 passed**, exit0,4.23s(23:22 KST), 새 19개 포함. 실제 커널 소스 계약을 참고한 API 모사+React SSR이며 실 HTTP/장비 시험으로 계산하지 않는다. `npm.cmd --prefix apps/web run build` TypeScript/Vite6.4.3 exit0, Vite8.51s. 첫 컴파일에서 optional 전환에 따른 네 오류(기존 reviewer setter, 날짜, Studio RiskBadge/nonce)가 검출되어 수정 후 통과했다. `git diff --check` exit0.

남은 것: 검토 가능한 승인 action 내용과 위험도를 digest에 결속해 조회하는 커널 계약/시험이 최우선. 조회 목록은 현재 첫 페이지(기본50)이며 전체 페이지 합계라고 해석하지 않는다. 다음 페이지 UI, 나머지 화면 고정 project ID, 실제 브라우저 polling/로그인/만료 시험, 최신 Gemini 후보와 configured backend 통합, IdP/원격 PC7개/CI/독립 인수는 미완료다.

다음 Codex: 승인 요청 생성 및 action_digest 구성 소스를 확인하고, 동일 snapshot에 결속된 검토 전용 view와 변경 시 거부 시험을 구현한다. Gemini: b0ecb5e까지 통합 후 미관측/승인 보류/실제 계정 표시 브라우저 확인. Claude: 승인 관측 경계와 새 계약 독립 검토. 전체 성숙도 2775/4800=57.8125%, 남음42.1875% 유지.

동일 SHA CI4건은23:23:15KST 결제/한도 제한으로 job 시작 전 실패했다. [CI 증거](../Evidence/run-approval-ci-b0ecb5e.json). 문서399개/48task·ontology 검사 exit0.
