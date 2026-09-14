---
doc_id: "HIST-LIVE-PROJECT-OBSERVATION-REPORT-20260914"
title: "2026-09-14 LIVE-PROJECT-OBSERVATION Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T23:17:05+09:00"
source_of_truth: "Git"
---

# 실제 프로젝트 및 Node 관측 수정 후보

제품 c38edac, 공백 정리 후 전달 SHA 7b50ae2a363097c9bd475a36b7bd5358a146fd07. branch agent/codex/frontend-mutations, base ea42657. commit/push 완료. 공유 integration/main 병합과 운영 배포는 미수행. Codex 작성, Claude 독립 검토와 Gemini UI 통합/브라우저 확인 대기.

- App과 Studio의 프로젝트를 실제 `/v1/projects` 목록에서 하나로 선택한다. 커널 business API의 `projects`/`projectId`/`displayName` 계약을 명시적으로 변환하고, 없는 owner/Workspace 수를 만들어 넣지 않는다. 고정 프로젝트 두 개 제거.
- Workspace는 실제 `projectId`/`workspaces` 응답을 읽고 목록 및 각 항목의 프로젝트 일치를 검사한다. 빈 응답에 예제 두 개를 끼워 넣던 경로를 제거했다. 목록 실패를 오류로 표시하며 초기 연결/격리/실행준비 성공 로그도 제거했다.
- Node의 누락/비정상 숫자, heartbeat 누락, 잘못된 상태, GPU 메모리 누락은 자원 미관측으로 처리한다. 알려진 0 사용량은 보존한다. 명시적 스케줄링·kill switch·drain·예약 가능량이 없으면 실행 가능으로 만들지 않는다. 이는 실제 admission 서버 검사를 대체하지 않는다.
- 대시보드/노드 목록/상세/관리 자원 표시에서 unknown을 표시하고, Studio/배치 화면에는 충분한 자원 관측이 있는 노드만 전달한다. 일부 노드 자원이 없을 때 합계를 전체 측정값처럼 표시하지 않는다. heartbeat의 나이 기반 freshness 판정은 이번 구현 범위 밖이다.
- 프로젝트 선택/로그아웃 때 요청 세대를 증가시키고 Run/승인/Workspace와 Studio 선택을 비운다. A→B→A에서도 이전 세대 응답이 현재 목록을 덮지 않도록 ref를 비교한다. 이 부분은 코드 검토이며 브라우저 지연응답 시험은 미수행이다.

검증: Windows, `npm.cmd --prefix apps/web test` 최종 23파일/163 passed, exit 0, 2.52s (23:16 KST). 새 23개는 실제 서버 코드에서 확인한 응답 계약의 API 모사 및 React SSR 시험이다. 실제 HTTP/로그인/원격 PC 시험으로 계산하지 않는다. `npm.cmd --prefix apps/web run build` TypeScript+Vite 6.4.3 exit 0, 도구 전체 9.36s. 이후 변경은 빈 줄 공백 정리뿐이다. 최초 `git diff --check`는 빈 줄 공백을 지적했고 7b50ae2에서 수정 후 exit 0.

남은 작업: App Run/Approval 응답의 정본 변환과 임의 fallback 제거, 나머지 화면의 고정 project ID 전수 정리, 조회 오류/연속 polling 순서 역전과 로그인 전환 브라우저 검증. 실제 IdP 설정·원격 PC 7개 시험·동일 SHA CI 실행·독립 검토는 여전히 미완료다. 전체 개발 성숙도는 2775/4800=57.8125% (남음42.1875%) 유지, 완료 카드로 올리지 않는다.

다음 Codex는 Run/Approval 응답 계약을 실제 커널과 맞춘다. Gemini는 이 후보를 통합하고 프로젝트 전환/빈 목록/미관측 UI를 실제 브라우저로 확인한다. Claude는 관측/권한 경계 독립 검토를 수행한다.

동일 SHA CI 4건은 23:17:17 KST 계정 결제/한도 제한으로 job 시작 전 실패했다. [CI 증거](../Evidence/live-project-ci-7b50ae2.json). 문서397개/48task와 ontology 검사는 exit0. CI 통합 검증 완료 아님.
