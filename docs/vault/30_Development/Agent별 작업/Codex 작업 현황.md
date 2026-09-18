---
doc_id: "WORKBOARD-CODEX-001"
title: "Codex 작업 현황"
version: "1.0.64"
status: "review"
author: "Codex"
updated: "2026-09-18T13:40:06+09:00"
source_of_truth: "Git"
---

# Codex 작업 현황

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

- 기존 점수2775/4800: **진척57.81%, 잔여42.19%**. 9월12일 점수 정본 재합산이며 최신 구현을 재평가한 수치는 아니다. 공식done0/48, 새 VF Codex 운영인수0/5는 별도.
- PR30 실제Desktop→HTTP→PG: 관련57/브라우저2 통과. 이후 신규 검토commit 없음. 이번 Desktop 저장배치 crash2건 재현·수정, 프런트엔드256시험/build통과. [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]].
- 다음: Gemini·Claude 이번변경 독립검토, 운영owner CI billing·SSO/PITR·5대 인수. 아래 이전 기록은 당시 상태이며 최신 합격 증거와 구분한다.


- 최신배포registry: Claude검토2commit수신, 승인시간/ORM캐시/동시등록4실패재현·수정, 최종82시험통과/실제image8통과. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]]. 기존DB중복거부유지,새수정독립검토/CI/운영미완.


- 2026-09-15T16:13:30+09:00 배포레지스트리검토착수 base0db07c8. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]].


- 최신 모델커밋관측: 현재project권한·저장manifest무결성검사·최소요약GET, 최종141시험(실제image포함)통과. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]]. Claude독립검토/Gemini화면/CI·운영은미완.


- 2026-09-15T15:24:19+09:00 모델관측 착수: basec74ce2e/agent/codex/vf-model-observation. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]].


- 최신 replica 관측: 소유자·활성폴더/단일SQL/현재가용성unknown, 관련137·실제image8통과. [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]]. Claude독립검토·Gemini화면연결·CI/운영은미완.


- 2026-09-15T15:16:03+09:00 VF replica 관측 착수: base1f71d89/agent/codex/vf-replica-observation. [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]].


- 2026-09-15T15:11:55+09:00 Codex VF-CX-02 검토 finding 판정 착수, base116e6e5/agent/codex/vf-model-review. [[2026-09-15_VF-MODEL-REVIEW_Codex]].


- [[2026-09-15_VF-CX-02_Codex_검증보고]]: ModelManifest/DataLocation FK·전체 bytes hash·lease/fence commit, Windows66/Linux49 통과. 독립 검토·CI·실장비 미완료. 다음 Codex VF-CX-03 locality 결속.


- 2026-09-15T11:54:32+09:00 VF-CX-02 착수: base 3efa507, 별도 agent/codex/vf-cx-02. [[2026-09-15_VF-CX-02_Codex_착수]]. owner Codex/reviewer Claude 미수신.


- [[2026-09-15_VF-CX-01_Codex_검증보고]]: canonical factory·fixture 격리·실제 인증/DB 보강, Linux 복원/definer/tenant 41 및 factory/account 5 통과. CI/독립 검토/운영 인수 미완료. 다음 Codex VF-CX-02; [[Codex VF 작업 현황]].


- VF-CX-01 착수 (2026-09-15T11:34:04+09:00): 원격 b9752a8 기반 별도 agent/codex/vf-cx-01, canonical factory 통합·fixture 격리 후 보안/PG 검증 중. owner Codex, reviewer Claude 미수신; [[2026-09-15_VF-CX-01_Codex_착수]]. 기존 57.81%와 VF 인수율은 별도.


- [[2026-09-14_APPROVAL-REVIEW-UI_Codex_검증보고]]:ab8b645 검토 snapshot화면·표시digest결정결속·미관측거부,210시험/build통과. 서버024a817과단일통합/배포미완료. 다음Codex격리통합/브라우저,Gemini UI,Claude독립검토. 전체57.81%유지.

- [[2026-09-14_APPROVAL-REVIEW-SNAPSHOT_Codex_검증보고]]:024a817 immutable 승인 검토snapshot/GET·approve/dispatch 결속 검사. 격리PG/HTTP48·계약10통과,운영DB/UI미반영. 다음Codex review화면연결,Claude독립검토,Gemini브라우저. 전체57.81%유지.

- [[2026-09-14_RUN-APPROVAL-OBSERVATION_Codex_검증보고]]: b0ecb5e Run/승인 정본 변환·임의 명령/예산/검토자 제거,182시험/build통과. 내용 미관측 요청 승인 보류; 다음 Codex digest결속 검토view, Gemini 통합/브라우저, Claude 독립검토. 전체57.81%유지.

- [[2026-09-14_LIVE-PROJECT-OBSERVATION_Codex_검증보고]]: 7b50ae2 실제 프로젝트 선택·Workspace 계약·미관측 Node 제외, 163시험/build 통과. 공유 통합/운영 배포/브라우저/peer 미완료. 다음 Codex Run/Approval 매핑, Gemini 통합/브라우저, Claude 독립 검토. 전체57.81% 유지.


- [[2026-09-14_SHARD-OBSERVATION-FIX_Codex_검증보고]]:ea42657 Gemini최신43640ee통합후샤드관측/새로고침정본화·미확인receipt성공표시제거·초기fixture제거. 최종140시험/build통과,공유integration/운영배포전. 다음응답unknown/project선택·브라우저/peer인수,전체57.81%유지.


- [[2026-09-14_FRONTEND-MUTATION-FIX_Codex_검증보고]]:별도frontend후보8037166 승인challenge/digest·일반취소version/실패상태보존,Vitest127/최종build통과. 공유App/RunDetail편집보존,아직통합/브라우저/peer미완료. Gemini후보병합·샤드연결/Codex재검토. Claude c5c014e는기존재현시험만독립확인. 전체57.81%유지.


- [[2026-09-14_FRONTEND-MUTATION-REVIEW_Codex_검증보고]]:frontend70ea3fb 독립검토 changes requested(FE-M01~05). 승인nonce/digest·취소version누락,취소실패성공표시,flat회수/fallback·임의관측·로딩오류. 실제격리PG/HTTP6개통과로현body422/상태보존·정본200확인(b95ab27). 다음Gemini수정/Codex재검토,전체57.81%유지.

- 최신 [[2026-09-14_CLI-OUTPUT-BOUNDARY_Codex_검증보고]]:dcd5f79 Agent CLI 수집 중 메모리 상한·timeout/incomplete·stderr 잘림 판정 보완. 실제 로컬 subprocess Windows24/Linux24 통과(동일24개). 실제 Provider/원격 인수·독립검토 미완료,전체57.81% 유지.

- 최신 [[2026-09-14_BACKUP-OPEN-GUARD_Codex_검증보고]]:3eced3b 보관 백업을 기존 ReadRoot로 읽도록 통합, Windows 관련42개 및 clean SHA 독립 PostgreSQL 복원130테이블/0037/tenant격리 통과. .225 TCP 불가·CI billing 차단·독립검토 pending, 전체57.81% 유지.

- 최신 [[2026-09-14_LEGACY-ROLE-REPAIR_Codex_검증보고]]:공용LOGIN재발관측,구Codex상주코드경로의위험fixture를4da131f로backport수정·격리PG21개통과. 실제재활성화주체는불명. 기존승인으로17:54:35 재폐기·권한보존. [[2026-09-14_INDEPENDENT-RESTORE_Codex_검증보고]]:33785f2 보관백업130테이블독립cluster복원/0037·replay/definer9·tenant격리통과. 원격/CI/운영인수미완료,전체57.81% 유지.

- 최신 [[2026-09-14_ROUTE-SURFACE_Codex_검증보고]]:8ef06eb Claude fef3292 경로도구통합·configured factory 측정/BusinessDispatch 선택범위·미등록fixture제외. 관련24개통과,추가lazyWS unit23개통과(중복합산안함). 다음Gemini 실제정본API/브라우저·Claude 독립검토·Codex 원격준비후7개. CI/운영인수미완료,전체57.81% 유지.

- 최신 [[2026-09-14_PROJECT-OBSERVATION_Codex_검증보고]]:4f518ea project 승인목록/상세·샤드조회·생성계약 연결. PG/HTTP16+승인계약10+실제후보컨테이너8 통과. 부모전체취소는 기존cancel,회수는receipt자동처리 정본. .225 접속불가·CI결제차단,전체57.81% 유지. 다음Gemini 정본계약 화면연결/Claude 독립검토/Codex 원격재연결 후7개시험.

- 최신 [[2026-09-14_MIGRATION-GUARD_Codex_검증보고]]:3742f11 Alembic 실제 진입점 그룹검사/별도PG13개 통과,221d253 CI opt-in 연결. 운영inv_app LOGIN 재발을 기존승인으로13:45:50 재폐기·권한/schema보존. 재활성화 원인 미확인. .225 offline/stale/observe,DB0023·kill switch유지. CI결제차단·독립검토/운영인수 미완료,전체57.81% 유지.

- 최신 [[2026-09-12_OFFER-SNAPSHOT_Codex_독립확인]]:51f4004 실제 offer중간 release는 기존Node/Resource잠금으로 차단·재시도성공, 관련12개통과. F1의 lease행만 잠근다는 전제는 실제호출과 달라 Claude재확인 요청. 새migration없음/0037유지. 업무·영속설정27개검증과 운영전환입력 준비 완료,실제OIDC/critical전환/원격7개/CI남음. 전체57.81% 유지.

- 최신 [[2026-09-12_BUSINESS-WORKSPACE_Codex_검증보고]]:14de71d 업무DSN/401정합·Windows설정volume·영속Workspace overlay, 실제컨테이너/DB/재시작/설정경계27개 통과. 운영 .225 fresh/observe·kill switch=true·DB0023 유지. 다음Codex role독립검토/운영전환계획,Claude 운영OIDC·계정/검토,Gemini 정본연결. CI차단,전체57.81% 유지.

- 최신 [[2026-09-12_SERVER-CONTAINER_Codex_검증보고]]:2bfd5fa 후보 backend 실제 image build/UID65532·DB·Workspace 설정/권한거부5개 통과. 일반 PostgreSQL16 head0037 적용. 원격 실행·운영SSO·Windows bind·영속Workspace 인수 미완료. 다음Codex business 활성화/영속volume·설정전달 검증,Claude 독립 검토. CI 결제 차단,전체57.81% 유지.

- 최신 [[2026-09-12_CONFIGURED-SERVER_Codex_검증보고]]:510ced4 정본 factory 필수 설정·readonly mount·/readyz 연결, 격리 PostgreSQL/실제 HTTP/Compose 경계14개 통과. 운영 SSO·후보 컨테이너·Workspace 활성화/원격 시험 미완료. 다음Codex 후보 backend build/비root mount/DB 확장 검증,Claude 독립 검토. CI 결제 차단,전체57.81% 유지.

- 최신 [[2026-09-12_DB-ROLE-REVOKE_Codex_운영적용보고]]:사용자 승인 후20:47:51 KST 운영inv_app NOLOGIN/password폐기 완료. 기존credential 인증거부·runtimeDB 접근·변경후Node fresh 확인,grant/RLS/membership 보존. **운영 로그인 폐기 승인대기 해소**. 다음Codex 정본server candidate/인증·DB 연결,각Agent 구fixture 갱신. 전체57.81% 유지.

- 최신 [[2026-09-12_DB-TEST-ROLE_Codex_검증보고]]:4ec4c5d 공용inv_app LOGIN/password 변경 제거·시험별 난수login/정리·배포 기본credential 제거. 별도PostgreSQL/Compose51개 통과,remediation SQL 별도컨테이너 거부/적용/replay 확인. **기존 운영credential 폐기는 critical 승인 대기**. 다음Codex 승인 후 서비스 의존 재확인/조치,각Agent 구fixture 갱신. 전체57.81% 유지.

- 최신 [[2026-09-12_LAN-RETAINED-BACKUP_Codex_검증보고]]:7a0a25b private 로컬 보관 파일 재검증→실제130테이블/조회행합계28726 복원·0037 upgrade/replay 통과,경계11 통과. 18100은 SQLite 로컬 작업대임을 확인. 다음Codex 별도 정본 server candidate/설정·인증·DB 검증,Claude 독립 검토. off-device/운영 인수 미완료,전체57.81% 유지.

- 최신 [[2026-09-12_LAN-RESTORE-UPGRADE_Codex_검증보고]]:04bd617 실제snapshot130테이블/조회행합계28165 복원,0037upgrade/전체replay/기존열보존·definer9·runtimeDBtransaction 통과,경계5통과. 원본0023/Node fresh 유지·폐기DB정리. 영속백업/독립클러스터/HTTP·운영인수미완료. 다음Codex 서비스호환성·실제배포계획,Claude독립검토. 전체57.81% 유지.

- 최신 [[2026-09-12_LAN-MIGRATION-PLAN_Codex_검증보고]]: b5493d7 운영0023→코드0037 미적용20개 계획, 열별SELECT/schema USAGE 판정 보완. 실제PG 포함15개/폐기용0023 upgrade·replay 통과. 운영 변경 없음. 다음Codex 복원 사본 리허설/호환성, Claude 독립 검토. 전체57.81% 유지.

- 최신 [[2026-09-12_LAN-STORAGE-READINESS_Codex_검증보고]]: f2a7fbc 읽기 전용 실제 운영 점검/경계6 통과. .225 online/fresh이나 observe 전용·kill switch 활성, storage 증명 관계2개 없음, 관측 역할 조회 제한, 공개 묶음 구형. 다음 Codex 실제 서비스 migration/역할/등록 연결 검토 후 후보 묶음, Claude 독립 검토. CI 결제 차단, 전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-WINDOWS_Codex_검증보고]]:e512b60 Windows 진입점/WSL request hash 준비·교체·재개 연결. 경계121(실제 PowerShell+모사WSL10 포함), 실제 Linux bridge1 통과. 본 서버 Ubuntu 없음, 실제 원격 경로·mTLS/Evidence 인수/CI/독립 검토 미완료. 다음 Codex 실제 PC 경로와 receipt 확인,전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-REPLACE_Codex_검증보고]]: f766146 보존 컨테이너/durable 교체/forward 재개, 실제 Docker11·경계111 통과. Windows/WSL 진입점·원격 .225·서버 인수/CI/Claude 검토 미완료. 다음 Codex wrapper/실제 mTLS·Evidence 연결, 전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-REPLACE-PREFLIGHT_Codex_검증보고]]:823b4b8 교체 전 읽기 점검·상태 해시·stale 재검사. 경계90/실제 Docker3 통과. **교체 실행기/forward 재개는 후속**이며 운영 Node 변경 없음. CI 결제 제한/Claude 검토 pending,전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-BUNDLE_Codex_검증보고]]: 9848afb 새 LAN 컨테이너 readonly mount·policy/Go receipt 대조, 실제 Docker2/경계62 통과. 기존 Node 교체·Windows WSL/원격 설치·서버 인수 미완료, CI 결제 제한/Claude 검토 pending. 다음 Codex 통제된 교체·forward 재개, 전체57.81% 유지.

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Codex. 독립 reviewer: Claude. 현재 착수/검토 기록은 아래 실제 SHA와 History로 확인한다. 작성자 보고를 독립 승인으로 바꾸지 않는다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill core-reliability v1.0.0. 계획: [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.29.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

- [[2026-09-12_STORAGE-POLICY_Codex_검증보고]]:f9d69a8 기존 Node journal에 폴더/channel 독립 최소 버전·hash 영속화, 역행/같은 버전 변경 거부 및 로컬 시작 receipt. 실제 재시작 포함 Linux85 통과. 다음 LAN bundle 읽기 mount·policy 전달/교체·receipt 대조 연결. CI/독립 검토/운영 인수 미완료, 전체57.81% 유지.

- [[2026-09-12_STORAGE-VIEW_Codex_검증보고]]:9d7559e 인증 GET/현재 권한·소유자/저장 서명·Evidence 재검증, pending·expired·recorded와 currentHealth unknown 분리. Linux153/Windows25 통과. 다음 폴더-root policy 설치·교체/receipt 계약, Claude 독립 검토·Gemini 화면 연결. 전체57.81% 유지, CI/물리 원격 인수 미완료.

- [[2026-09-12_STORAGE-COMMIT_Codex_검증보고]]:fd0c081/0037 현재 프로젝트 요청 권한+등록 소유자·durable challenge/nonce·기존 Evidence/StorageCheck 원자 기록. Linux156/Windows DB22 통과. Studio 시작 바로가기 복구/로그인 세션 생성 확인. 다음 조회·운영 설치 연결, CI/Claude 독립 검토/원격 인수 pending. 전체57.81% 유지.

- [[2026-09-12_STORAGE-NODE-TRANSPORT_Codex_검증보고]]:688678d Go opt-in 폴더 설정/mTLS/실제 서명 sample과 Python 검증 연결. Linux 실제 통합130, Windows98 및 Go 경계 시험 통과. durable challenge/nonce 소비·기존 StorageCheck/Evidence 원자 쓰기는 다음 작업. 운영 .225/Windows native 수집/CI/독립 검토 미완료, 전체57.81% 유지.

- [[2026-09-12_STORAGE-SIGNED-SAMPLE_Codex_검증보고]]:124fe97 실제 ReadRoot sample·불변 Run/ChannelProof/root/catalog/nonce challenge·Ed25519 서명 검증, Windows124/Linux129 통과. 내부 Python 수집/검증 모듈이며 Go 배포·durable nonce·StorageCheck/inv.evidence 원자 기록은 아직 남음. CI 계정 제한/독립 검토/물리 장비 인수 별도, 전체57.81% 유지.

- [[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]]:2830887 ASGI 인증서 오류 거부·proxy fallback 우회 차단·heartbeat 기록 transaction에서 현재 certificate/node row lock. 원본3개 오류 재현, Windows89/Linux89 통과. storage challenge/Evidence 쓰기 자체는 아직 미구현이며 다음 기존 Go nonce/ChannelProof/epoch와 Run-bound inv.evidence 연결 계약을 진행한다. 전체57.81% 유지, CI/peer/운영 인수 pending.

- [[2026-09-12_STORAGE-CHECK_Codex_검증보고]]:8c6805f/a7d0f5e 실제 local sample/READ ONLY·ReadRoot·hash/size 검증, Linux138/Windows105 통과. 입력 Node 이름은 신원 증명이 아니므로 운영 기록0. zero sample/과거 잘못된 healthy 판정을 보완했다. 다음 기존 Node 인증·epoch·challenge·root 버전/Evidence 원자 연결, Claude 독립 검토. S12-ST25→50, 전체57.81%/잔여42.19%, CI/원격 인수 미완료.

- [[2026-09-12_BACKUP-ROOT_Codex_검증보고]]:6a72b9d에서 허용 root·링크/교체 차단·시간 정보가 같을 때도 bounded 재읽기 hash 비교를 구현했다. 최종 Linux103/Windows80 통과. 다음71cf2c0 storage_check 실제 node binding·root 조율/독립 검토, 이후 durable 관측/Evidence. PR19 draft/CI 계정 차단/reviewer pending/실장비 인수 미완료. 전체57.29% 유지.

- 최신 복구 목표 판정: [[2026-09-12_RPO-CAPABILITY_Codex_검증보고]]. b49ecd3 Linux69 / core53 / upgrade23 통과. 설정만으로 운영 RPO를 확정하지 않고 실패/중단의 목표 달성 오기록을 서비스·0036 DB 제약으로 차단. 운영 PITR·CI·peer 인수는 별도.


- 최신 자격증명 등록·회전·회수: [[2026-09-12_CREDENTIAL-PROVISION_Codex_검증보고]], [[Codex 자격증명 등록 회전 회수 운영 절차]]. 76ba5ba Linux90/CLI4 통과. 운영 적용·Provider·CI·독립 인수 별도.


- 최신 자격증명 backend·Context/readiness 통합: [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]]. 제품0f5f4e8 Linux154/core53, migration22(74012b3) 통과. 실제 Linux/DB backend 확보, 외부 Provider·CI·peer·물리 원격 인수는 남음.


제품 c5f2154: 편집/PTY/Git와 최신 account/tenant/offer kernel 통합. 로컬 통합 402개·기본 301개·Linux Go 고유 43개·20개 migration 경로 확인. 전달 02e6188, PR19 draft. CI/독립 검토/물리 원격 인수는 남는다.

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| CX-01 | P0 | in_progress | S01-DB S04-DB S08-DB | 최신 3 Agent 변경 통합과 보안 검토 |
| CX-02 | P0 | in_progress | S01-BE S01-ST S08-ST | 운영·credential·Storage 공통 계약 확정 |
| CX-03 | P0 | blocked | S03-BE S04-BE S12-BE | 실제 원격 Node 실행 프로필과 7개 시험 |
| CX-04 | P1 | planned | S06-BE S06-DB S06-ST | 원격 개발 작업공간과 실제 Git 인수 |
| CX-05 | P1 | planned | S05-BE S05-DB S05-ST S07-BE S07-DB S07-ST | 5대 배치·지역성·샤드 통신·복구 |
| CX-06 | P1 | planned | S08-BE | Windows·GPU·BuildKit 실행과 격리 |
| CX-07 | P1 | planned | S04-ST S08-ST S11-ST | 제품 Storage 규모와 복구 무결성 |
| CX-08 | P1 | planned | S09-BE | 제한 Agent·Reverse-Ontology 실행 루프 |
| CX-09 | P1 | planned | S11-BE S11-DB S12-BE | 릴리스 통합·5대 부하/장애·최종 인수 |

### CX-01 — 최신 3 Agent 변경 통합과 보안 검토

- owner / reviewer: Codex / Claude; status: in_progress; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-04, OUT-08 / AC-01, AC-04, AC-08.
- 다음 첫 행동: F1 잠금29c810f/F2 intent1460634 이후 Claude Context/readiness를 0f5f4e8에 통합했다. 새 backend/0035/ADR-077/078 독립 검토를 받고 CX-02 후속을 진행한다. Gemini 858763c의 정본 API/운영 인수 finding도 추적한다.
- 필요한 합격 증거: review finding별 해결 SHA/독립 검토, 현재 적용 DB 함수의 실제 다른 tenant 거부, 계약·migration 이력 보존. CI와 main 상태 별도.
- 선행/차단과 해소 담당: 검토할 코드 확보됨. 독립 승인자는 CL-01.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-02 — 운영·credential·Storage 공통 계약 확정

- owner / reviewer: Codex / Claude; status: in_progress; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-08 / AC-01, AC-08.
- 다음 첫 행동: 서명 sample/0037 Evidence 원자 기록과 Windows bundle 연결은 구현·로컬 검증됐으며, 최신 보고를 따른다. 운영 OIDC 입력·최신 migration/프로필 배포 조건을 확인하고 실제 .225 설치 후 mTLS/7개 시험을 수행한다. 독립 검토·CI·운영 인수는 미완료다.
- 필요한 합격 증거: 미확인 항목에 결정 담당·차단 범위 명시, 비밀값 없는 버전 계약, Claude/Gemini가 구현할 입력·출력 합의. 실제 계정값은 운영자 확인 필요.
- 선행/차단과 해소 담당: 초안/계약 검토는 즉시 가능. 운영 권한/장비 정보 확정은 운영자 입력 필요.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-03 — 실제 원격 Node 실행 프로필과 7개 시험

- owner / reviewer: Codex / Claude; status: blocked; priority: P0.
- 원래 목표/합격 조건: OUT-03, OUT-04, OUT-12 / AC-03, AC-04, AC-12.
- 다음 첫 행동: 192.168.45.225 설치 결과의 profile/image·identity/journal 보존을 확인한 뒤 Python·CPU AI·시작 전 취소·실행 중 취소·실패·timeout·출력 복구를 원격에서 실행한다.
- 필요한 합격 증거: 실제 .225 endpoint·Node/이미지·Run/receipt/Evidence·hash·중복 방지·물리 정리/자원 반환 증거 7개. 관측 전용 상태 해소.
- 선행/차단과 해소 담당: 원격 설치 결과 미수신. 현재 lan-observe-v1; SSH/WinRM 실행 경로 미확보. 기존 설치 안내 사용.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-04 — 원격 개발 작업공간과 실제 Git 인수

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-06 / AC-06.
- 다음 첫 행동: c5f2154 편집/PTY 계약을 실제 worker에 배포해 Node 재기동/대체 Node 재개를 확인하고, 지정 sandbox Git 저장소에서 CAS·2인 승인·응답 유실·reconcile을 시험한다.
- 필요한 합격 증거: 실제 원격 편집 bytes→승인→PTY/실행→결과 복원 일치. 지정 원격 Git의 실제 commit/충돌/불확실 dispatch 비재전송.
- 선행/차단과 해소 담당: CX-03, CL-02. 실제 Git 대상/credential/검증된 승인자 필요; 로컬 메모리 provider 시험은 이미 확보.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-05 — 5대 배치·지역성·샤드 통신·복구

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-05, OUT-07 / AC-05, AC-07.
- 다음 첫 행동: 실제 제공량/lease/데이터 위치·링크 대역폭을 연결하고 다중 Node 샤드/부모 집계, partition·중단·중복 전달·재시작과 50동시 예약을 시험한다.
- 필요한 합격 증거: offered/lease/가용량 원자성, 데이터 해시·대체 Node 계보, Scheduler P95≤2초·취소≤10초·이탈≤60초·복구≥95%의 표본/기간/실측.
- 선행/차단과 해소 담당: CX-02/03과 추가 실제 Node 확보. 단일 호스트의 두 Node 시험을 5대 인수로 세지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-06 — Windows·GPU·BuildKit 실행과 격리

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-08 / AC-08.
- 다음 첫 행동: 현재 Linux CPU 프로필 외 실행 backend와 GPU device 배정을 구현하고 허용 이미지·경로/ACL·권한·정지·자원 반환 경계를 시험한다.
- 필요한 합격 증거: 실장비 GPU/Windows/BuildKit 정상·거부·실패·취소 Evidence; Windows 호스트의 WSL Linux를 native Windows 실행으로 오인하지 않음.
- 선행/차단과 해소 담당: CX-02, 실제 장비/driver/격리 프로필 조사. 무제한 shell/host 권한으로 대체하지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-07 — 제품 Storage 규모와 복구 무결성

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-04, OUT-08, OUT-11 / AC-04, AC-08, AC-11.
- 다음 첫 행동: 선정 Storage에서 50GiB 전송/중단 재개/hash·pin/GC/용량·다중 Node 복제를 검증하고 DB/object/Node journal의 epoch·fencing 복원 계약을 보강한다.
- 필요한 합격 증거: 대용량 실제 bytes/전송시간/정리 증거, 손상·보존 참조·빈/미확인 복원을 성공 처리하지 않음.
- 선행/차단과 해소 담당: CX-02, CL-03/04. 전체 복원 도구 구현은 Claude, 고위험 복원 계약·독립 검토는 Codex.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-08 — 제한 Agent·Reverse-Ontology 실행 루프

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-09 / AC-09.
- 다음 첫 행동: Claude Context/Adapter 위에서 Prompt→Context→계획→제한 수정/시험→Evidence를 연결하고 버전·예산·종료 조건·정책 우회를 검증한다.
- 필요한 합격 증거: 실제 100 Prompt/30 coding 과제와 secret/주입/권한 평가, Prompt/Context/Harness/Skill/ROOF/Graph/Agent 버전 역추적.
- 선행/차단과 해소 담당: CX-02, CL-05. 고정 예시 평가 점수는 증거가 아님.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-09 — 릴리스 통합·5대 부하/장애·최종 인수

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-11, OUT-12 / AC-11, AC-12.
- 다음 첫 행동: 전체 Agent 산출물을 같은 SHA에서 검토하고 장시간·5대 장애·upgrade/rollback·실제 복원·SLO와 최종 release manifest를 확정한다.
- 필요한 합격 증거: CI·독립 검토·운영 환경·5대 사용자 여정·복원/롤백·보안 합격 증거. 미측정 지표에 합격 수치 금지.
- 선행/차단과 해소 담당: CX-03~08, CL-06/07, GM-05/06, OR-02/03. CI 계정 해소는 운영자 외부 선행.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

## 작업 후 갱신할 최신 기록

아래 항목은 담당자가 매 작업 단위마다 갱신한다. 상세 기록은 History에 새 페이지로 남기며 이전 검증/실패 이력을 덮어쓰지 않는다.

| 항목 | 현재 기록 |
|---|---|
| 마지막 작업 / 카드 | CREDENTIAL-CONFORMANCE / CX-02 공통 검증 전달, 실제 backend 인수 대기 |
| owner / 진행판 / KST | Codex / 1.0.20 / 2026-09-12T00:47:43+09:00 |
| branch / base / 구현·검증 | agent/codex/workspace-bridge / 34d457c / clean8222f0b |
| 작업 | 내부 credential Protocol·39개 재사용 conformance·실제/모델 marker 분리 |
| 검증 | 합성 모델39+결함검출8=47 pass/skip0; backend 선택 exit5(모델 제외) |
| CI / peer / 운영 | CI 시작 전 계정 제한, Claude reviewer pending, 실제 backend/운영 인수 미완료 |
| 다음 첫 행동 / owner | 실제 backend 연결 / Claude; 독립 scope·회수·descriptor 검토·경합 시험 / Codex |
| History / PR / sync | [[2026-09-12_CREDENTIAL-CONFORMANCE_Codex_검증보고]] / PR19 / History 영수증 |

## 2026-09-11 18:53 Codex 수신·검증·후속 기록

- 실제 owner Codex, 진행판 시작 v1.0.14→현재 v1.0.15, base d14db0a→구현 5fc1116. CX-01/CX-07 일부 구현 전달, 카드 전체 done 아님.
- 작업: 단일 recovery_drill에 정본 감사·false-pass 거부·양쪽 RLS·시각/fencing·실제 DB 기록 연결.
- 확인: Linux64/core22/Go3 exit0, CI6 시작 전 계정 제한, 독립 reviewer Claude pending, 운영 인수 미완료.
- **다음 첫 행동 CX-01**: Claude cdf98ad F1을 두 session의 실제 함수 시험으로 재현하고 held를 단일 snapshot으로 고정하는 forward 변경. F2는 Node 중복 방어 유지하며 pre-dispatch intent/감사 정합성 검토.
- 이어 CX-02 credential/Storage 계약. CX-03 실제 원격 설치 receipt 미수신으로 blocked. PR19에 같은 변경 전달, Obsidian hash는 최종 영수증에 기록.

상세: [[2026-09-11_RECOVERY-INTEGRATION_Codex_검증보고]]. 작성자 원래 기록/진척 주장은 보존하며 위 검토와 구분한다.

## OFFER-SNAPSHOT 최신 작업 → 확인 → 다음

- 2026-09-11T23:56:33+09:00 / CX-01 / owner Codex / reviewer Claude pending. base ade6721 → clean 검증29c810f, PR19.
- 작업: F1 실제 API/lease release 경합 회귀. 확인: 실 PostgreSQL36개 exit0, 잠금 한 줄 제거 변이 exit1, 원본 복구. d14db0a에도 잠금이 있어 F1 전제 재검토를 요청한다. 제품/migration 변경 없음.
- 다음 첫 행동: F2 pre-dispatch intent/sequence/hash 감사와 응답 유실 정합성 보강; 이후 CX-02. 과거 snapshot 수정 계획은 최신 실험으로 대체.
- [[2026-09-11_OFFER-SNAPSHOT_Codex_검증보고]], [[2026-09-11_OFFER-SNAPSHOT_오류와해결]]. 전체57.29%(표시55%) 유지. CI 계정 제한·peer·원격 인수 미완료.

## PTY-INTENT 최신 작업 → 확인 → 다음

- 2026-09-12T00:24:11+09:00 / CX-01 / owner Codex / reviewer Claude pending. base fd32eda →1460634, PR19.
- 작업/확인: intent/완료 분리와 replay 보호, Linux61/core25/upgrade21 통과. [[2026-09-12_PTY-INTENT_Codex_검증보고]]. 다음 첫 행동은 CX-02 운영 credential 참조/회수/로그 및 Storage 계약이다. F1/F2 독립 검토·원격 실행 인수·CI는 남는다.

## OPERATING-CONTRACT 최신 작업 → 확인 → 다음

- 2026-09-12T00:32:00+09:00 / CX-02: [[Codex 운영 자격증명과 Storage 계약]], [[운영 환경 입력과 Agent 인계]] 전달. 내부 reference 문법 결정과 runtime resolver 구현/운영 계정 등록을 구분한다. 다음 Codex 보안 conformance와 독립 검토, Claude provider 구현, Gemini unknown/readiness 반영. 전체 진척은 운영 인수 전 임의 가산하지 않는다.

## CREDENTIAL-CONFORMANCE 최신 작업 → 확인 → 다음

- 2026-09-12T00:47:43+09:00 / CX-02:8222f0b 공통 Protocol/39개 suite 및 모델 검출력47개 확인. [[Codex 자격증명 보안 검증 인계]]에 actual harness 요구·모델 한계를 고정했다. 다음 Claude 실제 provider 연결, Codex 구현 독립 검토와 실제 inode/회수 경합 검증. 운영/실장비 증거는 아직 없다.


## 최신 작업 — BACKUP-LEDGER

420b81c Linux63/core50 완료, [[2026-09-12_BACKUP-LEDGER_Codex_검증보고]]. PR19 draft/CI 계정 차단/Claude 독립 검토 pending. 다음 첫 행동: d63717f snapshot 프로젝트/관측시점/순서 계약 확정 및 수정본 검토, ade5bb8 AC-12 집계의 운영 증거 범위 검토. CX-03 프로필 미수신 상태는 별도.


## 최신 작업 — PERMISSION-SNAPSHOT

9755c60 Linux74/core55, [[2026-09-12_PERMISSION-SNAPSHOT_Codex_검증보고]]. d63717f P1/P2 보완, ade5bb8 원본 집계 과장4개 재현/수정. PR19 draft/CI 계정 제한/Claude 독립 review pending. 다음: 실제 운영 Evidence 수집·검증 경로와 최신 변경 공통 계약 검토; 원격 profile 수신 시 CX-03 실제7개.


## 최신 작업 — BACKUP-VERIFY

4ddb622 Linux78/Windows DB60, 원본 실제5개 오류를 보완. [[2026-09-12_BACKUP-VERIFY_Codex_검증보고]]. PR19 draft/CI 계정 차단/Claude review pending. 다음 첫 행동: hash_file의 허용 root·descriptor/handle·링크/교체 경계; 그 뒤 durable 검증 관측/Evidence 연결. 02:30 .225 online/fresh, lan-observe-v1로 원격7개 미수행.


## 최신 작업 — BACKUP-ROOT

[[2026-09-12_BACKUP-ROOT_Codex_검증보고]]:6a72b9d에서 허용 root·링크/교체 차단·시간 정보가 같을 때도 bounded 재읽기 hash 비교를 구현했다. 최종 Linux103/Windows80 통과. 다음71cf2c0 storage_check 실제 node binding·root 조율/독립 검토, 이후 durable 관측/Evidence. PR19 draft/CI 계정 차단/reviewer pending/실장비 인수 미완료. 전체57.29% 유지.


## 최신 작업 — STORAGE-CHECK

[[2026-09-12_STORAGE-CHECK_Codex_검증보고]]:8c6805f/a7d0f5e 실제 local sample/READ ONLY·ReadRoot·hash/size 검증, Linux138/Windows105 통과. 입력 Node 이름은 신원 증명이 아니므로 운영 기록0. zero sample/과거 잘못된 healthy 판정을 보완했다. 다음 기존 Node 인증·epoch·challenge·root 버전/Evidence 원자 연결, Claude 독립 검토. S12-ST25→50, 전체57.81%/잔여42.19%, CI/원격 인수 미완료.


## 최신 작업 — NODE-AUTH-COMMIT

[[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]]:2830887 ASGI 인증서 오류 거부·proxy fallback 우회 차단·heartbeat 기록 transaction에서 현재 certificate/node row lock. 원본3개 오류 재현, Windows89/Linux89 통과. storage challenge/Evidence 쓰기 자체는 아직 미구현이며 다음 기존 Go nonce/ChannelProof/epoch와 Run-bound inv.evidence 연결 계약을 진행한다. 전체57.81% 유지, CI/peer/운영 인수 pending.


다음 Codex 첫 행동: ADR-094 preflight를 전제로 durable 교체 단계와 중단 지점별 forward 재개 구현.


다음 첫 행동: Codex Windows/WSL 교체 진입점과 명시적 정책/receipt 전달·출력 검증 연결.

다음 Codex 첫 행동: 실제 원격 Ubuntu/Docker 경로·현재 policy와 receipt를 확인하고 서버 mTLS/Evidence를 연결한다.


## 2026-09-12 RETAINED-BACKUP 외부 보고와 우선순위 정정

Evidence/obsidian-proposals-20260912-retained-backup의 원문3개와hash를 보존했다. Gemini는 Idempotency-Key/route404 판별·WebTerminal apiClient와Vitest114를 보고했다. 작성자 보고이며 실제 커널의 idempotency 저장·응답 계약과 운영 인수는 검토 대기다.

Claude는 저장소의 기본 시험 credential로 운영DB 로그인이 가능하다고 보고했다. Codex가 실제 READ ONLY metadata를 확인한 결과 inv_app LOGIN=true,superuser=false,bypassrls=false,inv_kernel LOGIN=false이며 조회 순간 해당 그룹과inv_lan_runtime active session은0이었다(상시 미사용 증거 아님). 실제 password 인증은 이번 Codex 확인에서 재시도하지 않았다. deploy/init-db.sql의 고정 password LOGIN 생성뿐 아니라 tests/conftest.py의 기존 app_engine fixture에도 공용 inv_app 역할을 고정 password LOGIN으로 바꾸는 코드가 있어 재발 경로다. 폐기용 DB라도 역할은 클러스터 전역이라는 점을 반드시 수정해야 한다.

최우선 다음 Codex: init SQL/compose 고정 로그인 제거, 테스트별 난수 login 역할 생성·정리로 공용 그룹 역할 변경 금지, 해당 회귀 검증. 그 뒤 실제 서비스 의존성과 권한 확인을 마치고 운영 inv_app NOLOGIN/password 폐기 조치를 별도 critical 운영 변경으로 제시한다. 현재 사용자 지침에서 critical 변경은 자동 승인 범위에서 제외되어 있으므로 이번에는 운영 credential/역할을 변경하지 않았다. 기존 정본 서버 candidate 작업보다 이 항목을 먼저 수행한다. 미래KST 원문은 현재 실측 시각으로 채택하지 않으며 전체57.81% 유지한다.

## VF 서비스 통합 최신 기록

2026-09-15T14:27:00+09:00 / Codex / base dd04562 / agent/codex/vf-service-integration. Claude7ef9a3c 독립 검토에서 pin 이탈·URI 경계 결함4개 재현,0043·용량·parser 수정. 최종통합d237d30/PR23: 전체1779 passed/139 skipped, 최종통합115/115, image/설정거부 통과. CI billing차단. [[2026-09-15_VF-SERVICE-REVIEW_Codex]]. Claude 재검토/CI/운영 인수 pending. 다음 Codex 전달·Claude 수정 재검토.

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

## 이전 공유판 수신 기록

외부 공유판 원문과 hash는 Evidence/cx01-landing/shared-codex-before.txt 및 shared-codex-proposal.json에 보존했다. 아래 세 항목은 당시 고정 SHA의 기록이며 현재 착지 검증과 구분한다.

- 사용자 후속 브랜치 정리: VF-CX-01/04 기록은 파일동일, dev-environment 수정은 현 helper와AST동일/격리PG3시험통과로중복제외. workspace-bridge 신규36개 기록 수신. [[2026-09-18_Codex_미착지브랜치_정리]]. 다음VF-CX-02/03/05 준비범위 진행.

## 2026-09-18 후속 검토와 인수 준비

- Claude 8bafb60 추가3파일을 Codex 독립 검토, 관련36시험 통과 후 공유 반영. 작성자76과 중복 합산하지 않는다. VF-CX-02/03 관련104시험 통과; VF-CX-05 오프라인 패키지 검사14시험 통과, 실제 인증서/peer policy 유효기간 실패(exit1). [[2026-09-18_VF-CX-020305_인수준비_Codex]].
- Docker 정리는 사용자 완료 보고 수신. 동일 image 재검증4통과/4실패; Docker I/O·HTTP500·정리 오류 잔존. 다음 Claude VF-CL-R-001 진단/정리 개선, Codex 수신 후 재검증. 운영자는 .225 갱신 준비, CI billing 대기.

- 사용자 finding MIGRATION-PREREQUISITE-001 수용: DSN 부재가 migration 손상 신호로 변환되는 검증 결함 수정·로컬 검증 완료. CLI exit2와 공통 local-skip/CI-fail fixture; 무DSN1074통과/489skip/0실패, 실제PG account·29경로upgrade 포함10통과. [[2026-09-18_마이그레이션_DSN_선행조건_Codex]]. 다음 Codex: 공유 착지·선택 동기화, Claude 수정본 독립검토. CI billing 대기.

- [[2026-09-18_IMAGE_정리후재검증_Codex]]: 동일digest·시험소스 재검증, 첫 시도PG inspect timeout/0시험, 두 번째4passed/4failed. 이전7건중4통과/3미완, writable 정리실패 추가. 제품 단언 실패 미관측이나 전체보안검증 미완. DSN finding은 사용자 독립 검증1074/489/0수신.

- [[2026-09-18_Docker_호스트분류_Claude변경검토_Codex]]: 사용자 보고0xC0000142를 host-process-initialization-failure로 분리. HTTP500과 동일원인은 미확정, business-kernel-role 거부 미검증 유지. Claude83c0163 문서 채택;911aed8/9e69dcc는 동시prune 강제삭제·timeout전파·DSN마스킹 findings로 보류, 다음 Claude 수정/Codex 재검토.

- [[2026-09-18_Workspace_아카이브무결성_Codex]]: VF-CX-05 오프라인 내부image archive SHA-256 검사 추가(합계8GiB한도),21시험통과·실제2archive일치. 인증서/정책만료로exit1 유지. OneDrive는 쓰기버스트상관으로 정정, 일정누수/NTSTATUS인과미확정. 다음Claude 독립검토/R2수정, Codex 수정수신 후검증.

- [[2026-09-18_모델레지스트리_명시결속_Codex]]: VF-CX-02 명시registryVersionId↔manifest/content/policy 불변결속·현재권한·동시성구현,0044head,격리PG100/100통과. 실행permit연결/원격provider는후속,운영DB미변경. 사용자image XML3pass/host-init3/timeout2 직접확인, business-kernel-role미검증유지. Claude07bae29는과도한NTSTATUS재시도/R2-03미해소로보류.

- 최신 image 독립판별(XML/JSON직접확인): 동일digest3회4/3/2pass,최신2pass/6fail(host-init5/timeout1). 재시도구제실패·전체반복인수미확보, 제품보안단언실패관측0≠미통과합격. business-kernel-role미검증유지. 환경조치후조용한조건까지image추가실행중단;모델결속100PG시험은이미완료. [[2026-09-18_모델레지스트리_명시결속_Codex]].

- 원격 읽기 기반: NodeTransfer의 bounded chunk 검증 공통화·공격 입력 회귀 포함 오프라인79통과, Docker/실장비 실행 없음. 사용자 독립 5b783d2 전체비integration1081/489/0·DSN exit2 유지 수신. provider/runtime 결속·PG통합재실행/Claude검토 미완료. [[2026-09-18_모델레지스트리_명시결속_Codex]].

- 원격모델 bounded reader 구현·합성loopback mTLS 포함106시험통과, runtime/DB현재권한 연결은 후속. Claude b5f770a 재검토: R2-01/사전prune R2-02 수정인정, R3-01 오분류·변경명령재시도/R2-03 libpq미마스킹 재현으로전체착지보류. [[2026-09-18_원격모델읽기_Codex]].

- **미착지 후보** 원격권한 snapshot 전후검사·frozen source hash·승인/delivery/claim 결속 구현.132passed/29PGskip(DSN없음), 실제DB검증전 integration5e4d6ae유지. Claude71fc9f5 timeout개선인정/R3-01·R2-03·OSError잔여로보류. [[2026-09-18_원격모델권한결속_Codex]].

- **DB검증 보류해제**: 사용자disposablePG16에서파일별79passed/0failed/0skip(원격6/runtime23/registry16/locality26/retry8). 최초3fixture CAS오류수정,제품코드변경0.8c347b7권한결속을integration반영판정. 기존489skip전체검증아님/image중단유지. Claude56aa7cb의기존재현해소인정, b809fbe timeout타입불일치R4-01은mock재현/전체브랜치보류. [[2026-09-18_원격모델권한결속_Codex]].

- 사용자e89a415 독립4파일/실PG75passed·0failed수신,착지판정유지. Claude816346c 오프라인15passed/실Docker2제외,R4-01해소. cleanup skip이합성본문실패를1skip/exit0로덮는R5-01(P1), 격리소스docker_diag누락R5-02(P2) 재현으로전체착지보류. [[2026-09-18_Claude816346c_재검토_Codex]].

- 후속사용자 clean816346c 두파일17passed/0failed(실Docker포함)수신,R4-01해소확인. 새R5-01/02는해당시험밖의경계로보류유지. Claude e89a415/8c347b7 소스검토배정수신·결과대기.

- VF-CX-02/03 registry 트랜잭션 재검사 구현(base f2297ae), 실제PG 신규7+기존16=23passed/0skip/0failed. 기존 결속만 허용하고 호출자 잠금 유지. frozen workload/승인 연결은 다음 Codex, 독립검토는 Claude 대기. [[2026-09-18_Registry_트랜잭션재검사_Codex]].

- VF-CX-02/03 registry frozen workload·승인/dispatch/delivery/claim 결속 구현(base1b39d40), 실제PG84+오프라인60=144passed/0failed/0skip. policy 제거·변경/retired 거부. 독립검토 Claude 대기, 운영 정책 구성 연결은 후속. 사용자 helper 독립23통과 수신, 외부대기4건 유지. [[2026-09-18_Registry_실행권한결속_Codex]].

- Claude d59b8a6 전체 착지 보류해제: 사용자독립24/작성자24, Codex오프라인22+실Docker2제외와 격리import통과(미합산). R2~R5 blocker 해소. image미검증6/business-kernel-role 미검증은 운영인수 항목으로 유지. e2908a5 registry 실행결속은 별도 독립검토대기. [[2026-09-18_Registry_실행권한결속_Codex]].

- 기본 Docker 의존 분리: 실제prune2건만 docker_host로 기본 deselect, mock22건 유지/Core CI 명시lane 추가. 사용자1157/489/0·62초 수신, 작성자 비integration1179passed/489skip/2deselected/0failed,66.23초. 기존 Compose2건 CLI부재가드 보강, 실제CLI2통과. e2908a5 registry 독립검토는 다음 Claude. [[2026-09-18_Docker_시험선택경계_Codex]].

- 사용자1eaf285 독립1179/489skip/2deselected/0failed(75초), Claude c9e6ddf의 e2908a5 sound 소스검토/부재22pass2skip 수신. registry 운영자 설정 연결 구현, offline34+실PG12=46passed. 최초 관측용DSN application_name 차이12setup오류는 원본DSN재실행으로 분리. 이번 설정 변경 독립검토 Claude 대기. [[2026-09-18_Registry_운영정책설정_Codex]].

- 호스트조치후 사용자image4pass/2fail/2skip(exit1),XML/JSON직접확인. host-init0회/OneDrive인과미확정,잔여timeout4건·business-kernel-role미검증유지. [[2026-09-18_IMAGE_OneDrive재시작후판별_Codex]].
