---
doc_id: "HIST-LAUNCHER-SCOPE-PITR-HOLD-001"
title: "Launcher 요약 scope와 PITR hold 해소 조건"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T15:19:32+09:00"
source_of_truth: "Git"
---

# Launcher 요약 scope와 PITR hold 해소 조건

base66bbcf0, owner Codex(review), launcher owner Gemini/PITR owner Claude. agent-delivery1.1.0/core-reliability1.0.0 적용. 사용자84a86f1 검증16passed(66bbcf0 clean worktree의 fixture2파일+launcher1파일) 수신. 독립 실행으로 기록하되 fixture11건은 대역을 쓰므로 DSN 설정이 실제PG 시험으로 바꾸지 않는다. launcher5건은 임시파일/합성generator·변형script 경계이며 실제배포 인수가 아니다. 이번Codex는 그16건을 재실행하지 않았다.

## VB-LAUNCH-01 원래 exit 누락은 해소

인증서 생성 native 직후 LASTEXITCODE→throw, 생성물 존재·크기 확인, ZERO Errors 배너 제거를 확인했다. 사용자 독립 통과 수신으로 원래 native23→전체0 finding의 수정 검증 상태를 갱신한다. **npm build nonzero 검사는51563eb 당시에도 있었다.** 당시 단독 build failure를 주입하지 않았다는 말은 검사 코드가 없다는 뜻이 아니다.84a86f1은 dist/index.html 존재·크기 검사를 추가했다.

## 요약 scope — 해소와 잔여

| 항목 | 판정 | 실제로 확인한 범위 / 남은 문구 |
|---|---|---|
| Docker CLI 부재 | 해소 | summary Compose Production Graph SKIPPED 출력. optional gateway와 별도 |
| gateway timeout/예외 | 분리됨 | OFFLINE / NOT RUNNING (Optional dev probe). probe 오류가 다른로컬검증을 실패시켜야 한다는 요구는 아님 |
| compose config | 구분됨 | 구문/service graph 검증이며서비스 기동·DB연결·운영configuration 적용 증거 아님 |
| TLS | scope잔여 | nonempty파일만 확인한 뒤 TLS 1.3 Certificates VERIFIED. 실제인증서 parse/기간/SAN/chain/key일치·TLS1.3 handshake는 검사하지 않음 |
| smoke | scope잔여 | 머리말은 API Contract Smoke Suite인데 개별행은 E2E Browser Smoke Suite VERIFIED (202 checks passed) 고정문구. child exit0만읽고 case수나브라우저관측을수신하지 않음. 기존MJS02 consttrue도남아있음 |
| build | 범위주의 | nativebuild0+HTML존재·크기. 이번run freshness를 별도증명하지않음. 오래된파일이존재하는것과현재build증거를동일시하지않도록설명 필요 |

실측: 원본PS1을byte-identical로temp폴더에복사, invalid nonempty cert/key와기존synthetic HTML, npm/node/docker nativeexit0대역, HTTP예외대역. Docker발견없음/있음2조건 모두process0. 없을때SKIPPED/HTTP실패Optional표시는정상, 두조건모두TLS1.3 VERIFIED·202checks문구출력. Evidence/verification-boundary-audit/launcher-summary-scope-results.json에summary행과sourcehash보존. 실제네트워크/Docker/인증서생성/배포0. 외부검사대역으로통과시킨것자체를제품우회로부르지않고요약이실제확인범위를넘는지를대조했다.

다음 Gemini: TLS행은 예컨대 'certificate/key files present and nonempty; cryptographic validity and TLS negotiation unverified', smoke행은 'API response smoke process exited 0; browser/physical-node acceptance unverified'로한정하거나실제관측을추가한다. 고정202 대신runner의검증된실행결과를받을계약이없으면숫자를쓰지않는다. Docker없음/gateway실패·invalid-nonempty cert·smoke개수미제공을넣고정확한summary범위를시험한다. 원래exit결함해소와이summary잔여는분리한다. 새제품TLS우회finding이나기존8건미수정으로재분류하지않는다.

## PITR hold — 현재 c754933 코드의 구체 사유

[[2026-09-18_Claude_c754933_부분착지검토_Codex]]의 원본shell함수 합성실행 근거를 유지한다.

1. **조회실패 은폐**: cleanup의 docker ps 실패를 `|| true`로 삼켜 빈목록과 구분하지 않는다. ps exit23주입→cleanup0/WARN0. 삭제대상없음을확인한것이아니다.
2. **제거실패 후 변경재시도**: rm exit23에도 WARN후cleanup0, start_probe는다음docker run호출. trace run→ps→rm→run. 실제중복생성실증은아니며동일NAME충돌이막을수있지만정리미확정을재시도허가로쓴것은실측됐다.
3. **실행 소유권 식별**: label은pitr-probe-$$로PID기반. PID재사용/다른PIDnamespace에서전역고유하지않다. 과거동일label잔재를현재소유로간주할수있다는소스범위의위험이며외부자원삭제를실행한것은아니다.

### Claude가 해소할 조건

- 매실행충분한무작위nonce를생성하고container ID와정확한label을결속한다. 이름/PID만으로소유권인증하지않는다.
- cleanup 결과를 confirmed-absent/removed/query-failed/remove-failed/ownership-mismatch로구분하고기록한다. query-failed를성공0으로만들지않는다.
- 최초create가ambiguous timeout이면본인partial자원식별·제거·부재확인까지성공한경우에만재시도한다. 미확정이면nonzero/unverified로중단한다. 다른owner는보존한다.
- EXIT cleanup이본문PITR결과를지우지않도록본문결과/cleanup결과를따로남긴다. 본문PASS가정리성공을대신하거나정리실패가원래오류를숨기지않도록한다.
- 원본함수로 정상정리·이미없음·다른owner·과거run·ps실패·rm실패·첫create timeout/정리확정후재시도·정리미확정후재시도0회 대조를제출한다. 물리PITR A/B/target/promote판정은유지한다.

운영환경조치나실장비인수를PITR코드착지조건으로요구하는것이아니다. 위조건은Docker없이도실패대역으로검증가능하다. 기존Tier-A single-writer/fsync/same-host한계및R1-04문구잔여검토는별도로유지한다. 실제운영PITR적용/AC-12인수는별도외부대기다.

## ancestry와 내용착지

`git cherry HEAD origin/agent/claude/vf-cl-cx01`에서a5401a7/c754933/7e3de2a는 '-'(동등patch존재). 원본→착지: a5401a7→0a65313, c754933→f7a46da, 7e3de2a→495df5c. 그러므로Claude tip이integration ancestor가아니라는것은맞지만fixture/registry검토내용이미착지라는뜻은아니다. R2~R5는더이전b378785로착지했다.

추가2ed3d6 상태문서가도착한것도확인했으며PITR코드변경은0이다. 해당문서의 '11 passed on real PG'는시험코드의fake경계와맞지않으므로실제PG증거로채택하지않는다. 최신hold는c754933 코드에여전히적용된다. 전체브랜치미병합을운영인수미완과혼동하지않는다.

## 상태와 다음 담당

후속8건의코드수정본은모두존재한다. 사용자열거AUDIT01/02까지포함하면10개ID이고,별도MJS01/02까지12개ID다. 실행검증수신을독립소스검토·운영인수완료로확장하지않는다. VB-LAUNCH-01 원래exit경로는수정검증확인,summary scope잔여는Gemini, PITR hold해소는Claude, 수정본계약review는Codex. 전체감사재시작/불필요한운영재실행없음.
