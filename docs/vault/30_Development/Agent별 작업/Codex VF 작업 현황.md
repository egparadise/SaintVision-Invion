---
doc_id: "WORKBOARD-VF-CODEX-001"
title: "Codex VF 작업 현황"
version: "1.0.16"
status: "in_progress"
author: "Codex"
updated: "2026-09-15T18:57:10+09:00"
source_of_truth: "Git"
---

# Codex VF 작업 현황

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
