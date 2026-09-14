---
doc_id: "HIST-ROUTE-SURFACE-REPORT-20260914"
title: "2026-09-14 ROUTE-SURFACE Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:44:05+09:00"
source_of_truth: "Git"
---

# 소스 선언과 구성된 서버 경로를 구분

CX-01 owner Codex/reviewer Claude pending. 제품8ef06eb, base3dc96f0, branch agent/codex/workspace-bridge. [[2026-09-14_ROUTE-SURFACE_Codex_착수]]. Claude fef3292의 tools/route_coverage.py 및 tests/test_route_coverage.py를 원저자기여로 가져와 확장했다. 원래client 추출의 동적prefix 생략/불완전성은 유지하며 이를 전체호출계약 검증으로 주장하지 않는다.

## 구현과 실제검증

`--configured-surface`는 INV_API_CONFIG/INV_RUNTIME_DSN/INV_RECOVERY_EPOCH로 실제factory를 구성하고 등록된 HTTP/OpenAPI 및 WebSocket 경로를 읽는다. BusinessDispatch가 선택한 경로만 더하고 shadow된 kernel경로를 제거한다. 업무앱에 있지만 dispatcher가 선택하지 않은 route·미포함router·demo소스는 합산하지 않는다. 포함router의해석된WebSocket prefix도 반영한다. 설정실패는exit2이며 private진단을 출력하거나 소스스캔으로 fallback하지 않는다. 잘못된입력폴더도0건성공이 아니라exit2다.

기존 `--served`는 source-declarations라고 출력한다. 두모드모두 operationalAcceptanceAssessed=false 및 static path한계를 항상 표시한다. method·payload·권한·실제availability·전체동적호출은 검증하지 않는다. factory구성은 /readyz 성공과 다르며, 비활성Workspace 기능의등록경로가 있어도 실행허용을 뜻하지 않는다.

`python -m pytest -q tests/test_route_coverage.py tests/integration/test_route_surface.py`: **24 passed/5.81초/exit0**. 실제 격리PostgreSQL16·합성JWT설정의CLI subprocess에서새승인/샤드경로포함·fixture-only미포함확인. DB사용가능성은 이경로측정의판정대상이 아니다. 이후 lazy included WebSocket 대응을 추가하고 unit23개를 재실행해 **23 passed/0.78초/exit0**. 중복시험을47개로합산하지 않는다.

최초 unit에서1failed/22passed: 테스트가 실제업무dispatcher에없는 /v1/settings를 shadow대상으로 가정한 오류. 실제선택경로 /v1/projects/{project}/members로 수정한 뒤 위검증통과. 새기능이운영실패를고쳤다고과장하지 않는다. Evidence route-surface-20260914.xml 및 route-surface-unit-final-20260914.xml.

## 사용과인계

운영설정을 안전하게 공급한환경에서 `python tools/route_coverage.py --configured-surface --client apps/web/src --json` 실행. 소스일치검토만필요할때는 기존 --served 유지. --configured-surface가실패하면실제설정/환경부터복구하며 --served 결과를운영인수로바꾸지않는다. 비밀값을명령줄/문서에직접넣지않는다.

다음Gemini: 최신SPA와구성된서버를위도구로측정하고 [[승인 샤드 화면 정본 API 계약]]의payload/권한/취소후pending을실제브라우저에서검증. Claude: 기존도구의확장과scope조합독립검토. Codex: 원격PC준비응답후연결/프로필/7개실행검증및운영OIDC/CI의존연결.

원격 .225는17:34 TCP18443/22접속불가였고사용자준비응답은미수신. CI결제제한·독립검토·운영SSO/전환·원격7개·5대인수미완료. 전체 **57.81% 완료/42.19% 잔여** 유지. 이코드·도구전달은최종제품완료가아니다.

최종 문서379개/48작업·ontology·diff검사 exit0. 동일8ef06eb CI6건은계정결제/한도로job미시작/failure(Core34824172356/34824168488,Backend34824172367/34824168546,Docs34824172452/34824168544). Evidence route-surface-8ef06eb-ci.json.
