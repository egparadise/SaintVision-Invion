---
doc_id: "HIST-APPROVAL-REVIEW-UI-REPORT-20260914"
title: "2026-09-14 APPROVAL-REVIEW-UI Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T23:41:19+09:00"
source_of_truth: "Git"
---

# 승인 스냅샷 화면 연결 후보

제품ab8b645, branch agent/codex/frontend-mutations, baseb0ecb5e. 서버024a817의 ApprovalReviewView와 연결한다. commit/push 완료, 공유integration/main/운영 미배포. Codex 작성, Claude 독립검토/Gemini UI 인수 대기.

- 승인 센터는 선택한 안건의 project-scoped `/review`만 조회한다. 안건/project/Run/digest/version/requester/policy/인원/상태/만료 일치와 명령 배열·이미지 digest·자원·timeout을 검사한다. 미지원/실패/불일치는 승인 보류, 다른 endpoint fallback 없음.
- 검토 성공 시 명령 인자를 JSON 배열 그대로 표시하고 자원/image/timeout/start/resume/terminal 등을 포함한 전체 workload 및 policyDigest를 보여준다. 사용자 입력은 React 텍스트로 이스케이프한다. 작업과 정책의 해시 재계산·결속은 서버에서 수행하며 브라우저가 자체 해시 검증을 했다고 주장하지 않는다.
- 화면에서 검토한 approvalId/projectId/actionDigest/runVersion을 결정 핸들러에 전달한다. 현재 목록과 다르면 challenge 전에 거부하고, 승인 중에는 기존 kernelMutations가 표시 digest를 캡처해 nonce 왕복에도 고정한다. 서버의 현재 상태/epoch/version/nonce 검사가 최종 권한이다.
- 안건 binding·사용자·project가 바뀌면 컴포넌트 key 및 effect 정리로 이전 응답을 버리고 검토 proof를 비운다. 조회 실패 후 수동 재조회가 가능하다. 다만 실제 브라우저에서 빠른 전환/지연 네트워크/키보드 포커스까지 시험한 것은 아니다.
- Studio의 검토 없는 즉시 승인 경로는 승인 센터 이동으로 바꿨다. L2 단일승인이라는 잘못된 설명을 실제 커널의 2인 승인으로 정정하고 L3 기본차단을 표시한다. 모르는 risk를 L0로 만들지 않는다. 현재 투표 내역이 없는데 1차 대기라고 추정하던 표시를 제거했다.

Windows `npm.cmd --prefix apps/web test`:25파일 **210passed**, exit0,3.97s(23:40KST). 새28개는 API 모사/SSR 및 지연 Promise 시험: bindings 변경·미지원404·불완전 내용 거부, 조회중 source 변경, challenge동안 digest고정, proof누락시 요청0회, 인자 경계/XSS escape/승인 enable. 실제 브라우저·IdP·원격 장비를 대체하지 않는다.

`npm.cmd --prefix apps/web run build`:TypeScript/Vite6.4.3 exit0,Vite5.20s. 처음 컴파일에서는 React/onApprove 미사용 import/destructure2개가 검출되어 제거한 뒤 성공. `git diff --check`:exit0.

다음 Codex: 최신 Gemini 공유후보와 서버024a817/프론트ab8b645를 격리 통합해 configured backend+SPA 실제 승인 브라우저 여정 검증. 현재 두 후보는 별도 브랜치이며 단일 배포물 검증이 아니다. 서버migration0038 미반영 환경/기존 snapshot 없는 승인은 계속 보류된다. 기존 승인의 운영 전환/retained backup upgrade, 실제 IdP/원격PC·CI·독립검토는 미완료. Gemini UI·접근성 검토, Claude snapshot/결정 결속 독립검토 대기. 전체57.8125%(2775/4800),남음42.1875%유지.

동일SHA CI4건은23:41:26KST 결제/한도 제한으로 job시작전 실패. [CI증거](../Evidence/approval-review-ui-ci-ab8b645.json). 문서404개/48task·ontology 검사exit0. CI/운영인수 완료 아님.
