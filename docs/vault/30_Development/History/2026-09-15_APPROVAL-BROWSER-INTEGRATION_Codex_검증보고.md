---
doc_id: "HIST-APPROVAL-BROWSER-INTEGRATION-REPORT-20260915"
title: "2026-09-15 APPROVAL-BROWSER-INTEGRATION Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:20:53+09:00"
source_of_truth: "Git"
---

# 실제 Edge 승인 화면·커널 연결 검증

제품fa21264, 공백 정리 후 e0b4b4f, branch agent/codex/approval-browser. basef011db3(서버024a817 포함)에 frontendab8b645의 apps/web을 가져온 격리 후보다. 기존 LiveApp/liveData/시험과 production main 진입점은 보존했다. 최신 공유efd61a7 전체 통합·main병합·배포는 아니다. commit/push 완료. 작성Codex/reviewerClaude·Gemini브라우저/접근성 인수 대기.

실제 Edge headless + Playwright1.62.0을 사용했다. production ApprovalCenter/API helper를 시험 전용 Vite 진입점에 mount하고, `saintvision.server:create_app --factory` 설정 기반 프로세스와 localhost HTTP로 통신했다. PostgreSQL16은 도구가 만든 별도 tmpfs클러스터/새 DB/비소유자runtime이며 Alembic head0038 적용. JWT는 합성 RS256이다. 브라우저에서 요청을 모사하거나 API응답을 intercept하지 않았다. App 로그인/실IdP/전체 Studio/원격Node 시험이라고 확대하지 않는다.

`python tools/run_approval_browser_test.py`:최종 **2passed**, exit0,16.51s. 실제 클릭·DB검사로 첫 검토자 승인 후 pending/중복거부, 두번째 검토자 승인 후 approved·vote2개·승인/반려 버튼 disabled를 확인했다. 검토 후 Run취소는 challenge409/AUTH-0032·vote0개, outsider전환은 목록실패/기존snapshot미표시. [증거](../Evidence/approval-browser-e0b4b4f.json), [합성 화면](../Evidence/approval-browser-e0b4b4f.png).

처음 두 실행은 `<pre>`2개 때문에 positive 시험 선택자가 strict mode 오류였다(각1fail/1pass). 선택 범위를 실제 command가 있는 snapshot으로 좁히고 계정전환이 보인 뒤 다음 클릭을 수행하도록 수정했다. 첫 negative pass는 origin거부와 상태거부를 구분하지 않아 합격증거로 쓰지 않았다. 시험Origin을 명시하고 response409/AUTH-0032를 검사한 최종결과만 채택했다. 테스트선택자 오류를 제품오류로 보고하지 않는다.

브라우저 화면 확인 후 제품2곳도 수정: 이미 approved인 안건의 반려 버튼 비활성화, 응답에 Diff/rollback이 없는데 파일변경없음/롤백정의없음이라고 단정하던 표시를 미관측으로 정정. 두 수정 후 브라우저 최종2개와 관련 unit47개(0.962s) 재검증. 이전 전체unit은26파일214passed/5.83s. 최종TypeScript/Vite build exit0(Vite3.08s), main은 기존LiveApp이므로 이 bundle을 승인센터 전체App 배포검증이라고 하지 않는다. 공백만 정리한 e0b4b4f는 추가기능변경없음. 최초 importeddiff 공백지적4건 수정 후 diffcheck exit0.

재현: requirements-browser.txt, apps/web/tests/browser/README.md, tools/run_approval_browser_test.py. 명시적 INV_BROWSER_TEST=1에서만 브라우저 pytest 실행, 미설치 상태에서 기본 suite가 브라우저 성공으로 집계되지 않는다. 전용 runner는 opt-in을 설정하고 소유컨테이너라벨확인 후 해당컨테이너만삭제했다. 설정파일/DSN/토큰은 비공개 시험환경 및 메모리, 공개증거는 합성화면/요약만이다. TestClient 경고2개는 남았다.

남은 것: actual App 로그인→프로젝트선택→승인센터 라우팅과 configured business API의 응답 계약 통합, 최신 공유frontend 변경 독립검토, 운영0038 이행·기존승인처리·retained backup upgrade·실IdP/원격PC/CI인수. 다음 Codex는 production LiveApp 진입점과 새 Studio/App 기능을 하나의 운영 경로로 연결하기 전에 현재 화면/API 차이를 확인한다. Gemini는 실제 브라우저 화면/키보드/작은화면 검토, Claude는 snapshot/권한/통합후보 독립검토. 전체57.8125%(2775/4800),남음42.1875% 유지. 이번 실제 browser 증거가 새로 생겼지만 전체 운영인수나 peer승인을 대신하지 않는다.

동일SHA CI4건은00:21:00KST 결제/한도 제한으로 job 시작 전 실패. [CI증거](../Evidence/approval-browser-ci-e0b4b4f.json). 문서406개/48task·ontology 검사exit0.
