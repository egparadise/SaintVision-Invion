---
doc_id: "WORKBOARD-VF-CODEX-001"
title: "Codex VF 작업 현황"
version: "1.0.24"
status: "in_progress"
author: "Codex"
updated: "2026-09-21T13:14:00+09:00"
source_of_truth: "Git"
---

# Codex VF 작업 현황

## 2026-09-21 보안·migration timeout 독립 검토

- `npm audit` moderate 2건은 Vitest 3.2.7와 하위 `@vitest/mocker`가 함께 보고한 동일 GHSA 하나다. 현재 production dependency/bundle에는 없음. 수정은 Vitest 4.1.11+ 메이저 업그레이드 후보이며 아직 적용하지 않았다. [[2026-09-21_Vitest_audit와_migration_timeout_독립검토_Codex]]
- Claude `79487cb`의 600초 timeout은 현재 보고된 211초 idle/324초 부하 대비 단기 예산으로 수용 가능하나, Codex DB 재현은 DSN 부재로 미실행. timeout이 hang형 migration 결함도 skip할 수 있고 외부 종료로 cleanup이 보장되지 않는 잔여가 있어 timeout-as-skip 의미와 자원 회수 hardening은 미승인/후속 검토다.

## 최신 상태 지도 (기준 d7e7d13)

[[Codex 검증 상태 지도와 재개 조건]]이 현재 검증완료/미검증/외부대기와 재시도조건 정본이다. e2908a5 Claude sound 수신, 11e9f44 설정연결은 로컬46통과/독립검토대기. 기본회귀1eaf285 사용자1179/489skip/2제외/0failed. 최신image는f4b3f73에서4통과/2daemon-timeout실패/2operation-timeout skip, business-kernel-role미검증. VF운영인수0/5·formal0/48 유지. 외부4건과 AC-12 운영PITR 적용은 별도대기. 아래 고정SHA별 과거의 완료/차단 표현을 현재상태로 자동승계하지 않는다.

## CX-01 공유 개발 정본 착지 (2026-09-18)

- 사용자 우선 지시에 따라 `agent/codex/cx-01-canonical-landing`에서 최신 보안 제어 평면과 공유 integration 47a423e/810ab3b를 병합했다. PR34로 원격 integration에 병합 완료(fe4c04c). 검증·착지 SHA는 [[2026-09-18_CX-01_정본착지_Codex]]에 기록한다.
- 다음 작업의 계약/branch/필수 migration/Agent별 첫 행동: [[CX-01 제어 평면 정본과 Agent 재개 계약]]. 개별 storage API 파일 복사 대신 deps·0043·서비스가 일치하는 통합 SHA를 사용한다.
- 사용자 진행 승인은 유효하다. 공유 개발 정본 착지와 main 릴리스/운영 배포/CI/독립검토/5대 인수는 별도 상태다. 다른 Agent 수신은 미확인이다.
- 아래 과거 항목의 'CX-01 정본 미병합'은 당시 상태다. 최신 착지 결과는 위 History가 우선하며 전체 완료율은 재평가하지 않는다.


## Codex 승인과 연속 진행

- 사용자 Codex 담당영역 후속작업 승인 OK. 구현·검증·통합·인계를 반복확인 없이 진행한다. 승인과 실제CI/독립검토/운영인수 결과는 별도다.
- 로그인·프로젝트조회·승인상태 보강 누락을 실제browser실패로 확인하고 통합,273시험/build 및 실제HTTP browser6/6 통과. [[2026-09-18_VF-BROWSER-AUTH_Codex]].
- 다음ready 운영복원리허설 진행: source0023→복사본0043 업그레이드·기존row보존통과, 원본변경없음. 원격.225:18443은3회timeout,실장비인수대기.


## 2026-09-18 현재 확인

- 2026-09-18 재채점: **2800/4800 = 58.33%, 잔여41.67%**. 48 task 동일가중 산식을 유지하고 S11-DB의 물리 PITR 양·음성 게이트만 50→75로 반영했다. formal 0/48과 VF 운영인수 0/5는 별도 분모다. [[2026-09-18_Codex_진척률재채점]]
- PR30 실제Desktop→HTTP→PG: 관련57/브라우저2 통과. 이후 신규 검토commit 없음. 이번 Desktop 저장배치 crash2건 재현·수정, 프런트엔드256시험/build통과. [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]].
- 다음: Gemini·Claude 이번변경 독립검토, 운영owner CI billing·SSO/PITR·5대 인수. 아래 이전 기록은 당시 상태이며 최신 합격 증거와 구분한다.


- 최신배포registry: Claude검토2commit수신, 승인시간/ORM캐시/동시등록4실패재현·수정, 최종82시험통과/실제image8통과. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]]. 기존DB중복거부유지,새수정독립검토/CI/운영미완.


- 2026-09-15T16:13:30+09:00 배포레지스트리검토착수 base0db07c8. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]].


- 최신 모델커밋관측: 현재project권한·저장manifest무결성검사·최소요약GET, 최종141시험(실제image포함)통과. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]]. Claude독립검토/Gemini화면/CI·운영은미완.


- 2026-09-15T15:24:19+09:00 모델관측 착수: basec74ce2e/agent/codex/vf-model-observation. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]].


- 최신 replica 관측: 소유자·활성폴더/단일SQL/현재가용성unknown, 관련137·실제image8통과. [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]]. Claude독립검토·Gemini화면연결·CI/운영은미완.


- 2026-09-15T15:16:03+09:00 VF replica 관측 착수: base1f71d89/agent/codex/vf-replica-observation. [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]].


- 2026-09-15T15:11:55+09:00 Codex VF-CX-02 검토 finding 판정 착수, base116e6e5/agent/codex/vf-model-review. [[2026-09-15_VF-MODEL-REVIEW_Codex]].


기준 ROADMAP-VIRTUAL-COMPUTER-001/ARCH-WEB-FABRIC-001/GOV-CONTINUOUS-001 1.0.0, integration 원격b9752a8. owner Codex, reviewer Claude(실제 수신·검토 미확인). 현재 branch agent/codex/vf-deployment-guard, base 0db07c8. 개별 source SHA/명령/exit code는 연결된 History/Evidence가 정본이다.

| 카드 | 구현·로컬 검증 | CI/검토/운영 | 다음 행동 |
|---|---|---|---|
| VF-CX-01 | canonical factory·fixture 격리·인증 경계, code290aba5, Windows1613/139 skipped·Linux41 | CI billing, 독립 검토/운영 미완 | 실제 route/UI 정합, 운영 SSO/PITR |
| VF-CX-02 | ModelManifest·bytes hash·기존 Lease/FK commit, coded6d9d87, Windows66/Linux49 | CI billing, 독립 검토/운영 미완 | Claude Catalog/API 연결·독립 검토 |
| VF-CX-03 | 측정 locality·원자 예약·model input, codebc8797c, 상세 회귀 증거 인계 | CI billing, 독립 검토/운영 미완 | 04 입력 freeze/실행과 연결됨 |
| VF-CX-04 | CPU 모델 입력 freeze·기존 permit·최대3세대 대체 실행, Windows1716/139 skipped·Linux140/140 | CI billing/독립 검토/운영 미완 | Claude 독립 검토·runtime 서비스 연결 |
| VF-CX-05 | read-only preflight15/15, TCP3회 실패, DB0023→0042 미적용25개 | blocked: 실제5대/W2~W4/backup·운영 변경 | 운영 owner 연결 복구/백업, Claude 검토 후 재점검 |

## 작업한 것

[[2026-09-15_VF-CX-01_Codex_인계]], [[2026-09-15_VF-CX-02_Codex_인계]], [[2026-09-15_VF-CX-03_Codex_검증보고]], [[2026-09-15_VF-CX-04_Codex_검증보고]]. 정본 API/실행 권한을 복제하지 않고 기존 Catalog/Lease/승인/Node/Result를 연결했다. apps/web와 다른 Agent 작업판을 수정하지 않았다.

## 확인한 것

140개 최종 Linux 시험에서 모델 입력 실행·출력 복구·취소·실제 만료·Node 이탈 거부·두 Go Node 대체 실행을 확인했다. Evidence는 한 Docker host의 격리 시험이며 실제 두 PC/5대 인수가 아니다. [[모델 실행 입력과 대체 Node 복구 계약]]의32KiB CPU 범위를 넘어선 GPU/collective/대용량 provider는 미지원으로 표시한다. 실패와 수정은 [[2026-09-15_VF_오류와_해결]].

## 이어서

Codex: [[2026-09-15_VF-CX-05_Codex_선행조건_점검]]에 실제 선행조건·변경 계획·재개 순서를 인계했다. 후속 운영 변경 승인이 확인되면 preflight부터 재검증한다. Claude: kernel migration/동시성/보안 독립 검토와 서비스 API. Gemini: canonical route/모델 상태/UI 연결 및 browser 검증. 운영 owner: CI billing, SSO/credential/PITR,5대 장비 및 검증된 runtime profile.

기존2775/4800=57.81% 유지. 새 VF 운영 인수0/5(0%). 구현/로컬/CI/독립 검토/운영 인수를 별도로 관리한다. 다른 Agent의 수신·착수·승인을 대신 기록하지 않는다.

최종 로컬 회귀1716 passed/139 skipped/0 failed; Linux140/140은 한 Docker host이다. GPU/대용량/routing/data/tensor-pipeline 및 W2~W4 전체 인수는 여전히 별도 미완 범위다. 05 준비 점검을 제품 인수 성공으로 바꾸지 않았다.

## 후속 서비스 검토 착수

2026-09-15T14:23:32+09:00 / Codex / dd04562 / agent/codex/vf-service-integration. Claude7ef9a3c 검토. [[2026-09-15_VF-SERVICE-REVIEW_Codex]].

## 최신 인계

VF-CX-01 진단출력 보강: [[2026-09-15_VF-CX-01_진단출력_보강]]. branch agent/codex/vf-cx-01-diagnostics / base dd04562. owner Codex, reviewer Claude 미수신. 공개 Evidence의 예외·응답 원문 노출 및 환경 제거 부작용 수정. 실제 PG 포함25/25 통과, code f885553 push 완료. CI34929945096/128/111 billing 차단, 독립 검토 대기.

## 서비스 통합 최종 인계

PR23,code08ece3b 제품·진단c8168e1 통합. 전체1779/139skip,최종통합115/115, image build/설정거부통과. [[2026-09-15_VF-SERVICE-REVIEW_Codex]]. CI billing/Claude 재검토/운영미완. 다음 Claude0043/URI/이탈잠금 검토, Codex 실제API 연결.

## VF 저장소 API 착수

2026-09-15T14:59:30+09:00 / Codex / base58f0370 / agent/codex/vf-storage-api. [[2026-09-15_VF-STORAGE-API_Codex]]. 등록자 소유권과 조회전용 dispatch 검증.

## VF 저장소 API 검증·다음 행동

등록자scope·active·메서드경계 구현,123/123·image8/8·문서/ontology통과. [[2026-09-15_VF-STORAGE-API_Codex]]. 다음 Claude 독립검토, Gemini 실제FileExplorer조회연결, Codex replica/ModelManifest 관측API계약. 운영인수/CI별도.

VF-STORAGE-API 최종: b3faf98/PR24,123시험·image8시험통과,CI6run billing차단,Claude재검토/Gemini조회UI연결대기. [[2026-09-15_VF-STORAGE-API_Codex]].


## 모델 독립 검토 판정 인계

[[2026-09-15_VF-MODEL-REVIEW_Codex]]: Claude 실제 소스검토3commit 수신, 기존Schema1024상한 확인/117시험통과/상한제거 mutation1실패. [[모델 레지스트리와 실행 Manifest 권한 경계]] 결정. 이번 판정 재검토·CI·운영 미완; 다음Codex 소유자범위 replica관측API.


- 전달완료: 모델검토e735df9/PR25 및replica fc34f37/PR26 push. 후자137+image8통과,CI34936437627/572/523 billing차단. 제한Obsidian동기화완료. Claude독립재검토/Gemini4GET실화면/Codexfinding통합이 다음이며 운영인수0/5유지.


- 모델관측20ff7c2/PR27 push·로컬141(image8포함)통과·Obsidian제한동기화완료. CI34937280022/029/005 billing차단. 다음Claude독립검토/GeminiModelStudio관측/Codexfinding통합, 운영인수0/5유지. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]].


- 배포registry653aea0/PR28 push·최종82시험/image8통과·제한Obsidian동기화완료. CI6run billing차단. 다음Claude신규수정검토/Gemini실화면/Codexfinding통합. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]].


- Desktop통합착수 base7d18b62. [[2026-09-15_VF-DESKTOP-INTEGRATION_Codex]].

- Desktop 실조회 통합: GET 저장소/모델 관측, fake-success 제거, 로그인·프로젝트 경계 유지. build/242 tests 통과; 실제 Chromium HTTP-fixture 검증. [[2026-09-15_VF-DESKTOP-INTEGRATION_Codex]]. CI/독립검토/운영 별도, 다음 Gemini·Claude 검토.

- PR29/코드81987d3 push 완료. build242시험/브라우저fixture7항목통과, CI billing 실행전차단; scoped Obsidian 전달. 다음 Gemini·Claude 독립검토, 실backend/SSO/운영 미완료.

- 2026-09-15T18:54:05+09:00 Desktop 실HTTP 검증 착수, base0fcbea4/agent/codex/vf-desktop-http. [[2026-09-15_VF-DESKTOP-HTTP_Codex]].

- Desktop 실HTTP/PG: 관련57통과, 명시적browser2재검증통과/0skip. Claude b30a723 배포권한보강 독립검토 수신(Desktop검토 아님). 전용browser CI 추가. [[2026-09-15_VF-DESKTOP-HTTP_Codex]]. 다음 Gemini·Claude 이번변경검토/운영owner CI·SSO·장비.

- PR30/7c55fea push: 실제브라우저→canonical HTTP→비소유자PG 검증, 관련57/최종browser2통과. 전용Desktop CI도 billing실행전차단. [[2026-09-15_VF-DESKTOP-HTTP_Codex]], 다음 Gemini·Claude 독립검토/운영owner 선행조건.

- 2026-09-18 잔여42.19% 기준 재확인 및 Desktop 배치 복원 보강 착수(baseb947b1c). [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]].

- PR31/546ec50 push·256시험/build통과, 9월18일 CI6check billing실행전차단 재확인. [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]], Gemini·Claude검토/운영인수미완료.

- 사용자 Codex 영역 후속작업 승인 확인: 반복승인 없이 연속진행. 실제로그인/승인browser 통합착수 base54f3206. [[2026-09-18_VF-BROWSER-AUTH_Codex]].

- PR32/325554c:273시험/build·실HTTP브라우저6통과. 사용자승인 후 보관백업+독립PG복원/0043업그레이드·row보존/권한격리통과. [[2026-09-18_VF-RECOVERY-REHEARSAL_Codex]]. 원격3timeout·CI billing/peer/운영SSO·PITR/5대 인수미완. 승인재요청없이외부조건복구후이어감.

- 자동연속진행: Claude 신규4commit 수신/PITR출력·인수경계검토 착수basef00341e. [[2026-09-18_VF-PITR-BOUNDARY_Codex]].

- PITR 후속: Claude 4 commit 통합, 비밀출력·설정/복구 판정 경계 수정. 격리 PG16 관련 40/40 통과, 운영 archive_mode off 실측. [[2026-09-18_VF-PITR-BOUNDARY_Codex]]. CI/Claude 독립검토/운영인수는 별도 미완료. 다음 Claude는 수정본 독립검토, Codex는 실제 WAL·목표시각 복구 증거 확보 가능한 환경에서 후속 검증. 기존 잔여 42.1875%, VF 운영인수 0/5 유지.

- 사용자 후속 브랜치 정리: VF-CX-01/04 기록은 파일동일, dev-environment 수정은 현 helper와AST동일/격리PG3시험통과로중복제외. workspace-bridge 신규36개 기록 수신. [[2026-09-18_Codex_미착지브랜치_정리]]. 다음VF-CX-02/03/05 준비범위 진행.

## 2026-09-18 후속 검토와 인수 준비

- Claude 8bafb60 추가3파일을 Codex 독립 검토, 관련36시험 통과 후 공유 반영. 작성자76과 중복 합산하지 않는다. VF-CX-02/03 관련104시험 통과; VF-CX-05 오프라인 패키지 검사14시험 통과, 실제 인증서/peer policy 유효기간 실패(exit1). [[2026-09-18_VF-CX-020305_인수준비_Codex]].
- Docker 정리는 사용자 완료 보고 수신. 동일 image 재검증4통과/4실패; Docker I/O·HTTP500·정리 오류 잔존. 다음 Claude VF-CL-R-001 진단/정리 개선, Codex 수신 후 재검증. 운영자는 .225 갱신 준비, CI billing 대기.

- [[2026-09-18_IMAGE_정리후재검증_Codex]]: 동일digest·시험소스 재검증, 첫 시도PG inspect timeout/0시험, 두 번째4passed/4failed. 이전7건중4통과/3미완, writable 정리실패 추가. 제품 단언 실패 미관측이나 전체보안검증 미완. DSN finding은 사용자 독립 검증1074/489/0수신.

- [[2026-09-18_Workspace_아카이브무결성_Codex]]: VF-CX-05 오프라인 내부image archive SHA-256 검사 추가(합계8GiB한도),21시험통과·실제2archive일치. 인증서/정책만료로exit1 유지. OneDrive는 쓰기버스트상관으로 정정, 일정누수/NTSTATUS인과미확정. 다음Claude 독립검토/R2수정, Codex 수정수신 후검증.

- [[2026-09-18_모델레지스트리_명시결속_Codex]]: VF-CX-02 명시registryVersionId↔manifest/content/policy 불변결속·현재권한·동시성구현,0044head,격리PG100/100통과. 실행permit연결/원격provider는후속,운영DB미변경. 사용자image XML3pass/host-init3/timeout2 직접확인, business-kernel-role미검증유지. Claude07bae29는과도한NTSTATUS재시도/R2-03미해소로보류.

- 최신 image 독립판별(XML/JSON직접확인): 동일digest3회4/3/2pass,최신2pass/6fail(host-init5/timeout1). 재시도구제실패·전체반복인수미확보, 제품보안단언실패관측0≠미통과합격. business-kernel-role미검증유지. 환경조치후조용한조건까지image추가실행중단;모델결속100PG시험은이미완료. [[2026-09-18_모델레지스트리_명시결속_Codex]].

- 호스트조치후 사용자image4pass/2fail/2skip(exit1),XML/JSON직접확인. host-init0회/OneDrive인과미확정,잔여timeout4건·business-kernel-role미검증유지. [[2026-09-18_IMAGE_OneDrive재시작후판별_Codex]].

## PITR 준비안 검토 수신

[[2026-09-18_PITR_준비안_검토_Codex]]: Claude 8c72fbf 검토 결과 R1-01~04 수정 전 착지 보류. 논리 복원을 PITR로 간주한 판정, same-host MinIO의 off-host 보장, archive 재시도·용량 설명을 수정해야 한다. 따라서 남은 사항이 모두 외부 조치인 것은 아니다. 다음 내부 담당 Claude: 준비안/격리 PITR 증거 보강; Codex: 수정본 재검토. Docker 실행/운영 적용 없음. 사용자 image 방법론 정정 수신, 동일 lane 반복 없음.

## MJS 수치 보증 범위 정정

[[2026-09-18_MJS_수치인용_정정_Codex]]: 지도v1.2.0에67/200·202/59 checks의 응답조건·로컬계산 범위와 실제장비/화면 미보증을 명시. 공통판202/202 문구 직접정정, VF01~05 인수조건에 실제bytes/identity/장비·UI 관측 요건 보강. 실제browser6은 별도범위 유지. 운영0/5 변경없음. PITR2468912 보류사유와 다음owner 명시.
