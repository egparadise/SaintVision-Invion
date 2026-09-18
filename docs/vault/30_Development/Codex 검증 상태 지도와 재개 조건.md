---
doc_id: "STATUS-CODEX-VERIFICATION-001"
title: "Codex 검증 상태 지도와 재개 조건"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T13:40:06+09:00"
source_of_truth: "Git"
---

# Codex 검증 상태 지도와 재개 조건

기준 코드 d7e7d13, 공유 branch integration/all-agents-unified. 사용자 요청에 따른 상태 감사이며 새 제품 구현/운영 재실행은 하지 않았다. 각 행의 SHA·범위에만 결과를 적용한다. 통과 건수는 중복 합산하지 않는다. 작성자 실행, 사용자 독립 실행, Claude 소스 검토, CI, 운영 인수는 서로 대체하지 않는다.

## 1. 실제 검증 완료 — 명시한 범위만

| 범위 / 고정 SHA | 실제 증거 | 독립 확인과 한계 |
|---|---|---|
| CX-01 canonical 제어 평면 / fe4c04c | 실제 인증/PG·owner scope·통합 route, 별도 실제 HTTP browser6통과 | 개발 기준선 병합. 합성 IdP와 격리PG이며 운영 SSO/실장비 완료 아님. [[2026-09-18_CX-01_정본착지_Codex]] |
| 원격 모델 권한 결속 / 8c347b7→e89a415 | 파일별 실제PG79passed/0skip. CAS fixture 정상화 후 remote6건 도달·통과 | 사용자 명시4파일75통과, Claude c9e6ddf 이전8c/e89 sound 소스검토. 합산하지 않음. [[2026-09-18_원격모델권한결속_Codex]] |
| 호출자 transaction registry 재검사 / 0a16658→1b39d40 | 실제PG 신규7+기존16=23passed/0skip | 사용자 같은2파일23통과. 기존 binding만 허용·SHARE 잠금 유지. [[2026-09-18_Registry_트랜잭션재검사_Codex]] |
| frozen registry→승인/dispatch/delivery/claim / e2908a5 | 명시5파일실PG84+오프라인60=144passed | Claude c9e6ddf sound/finding없음 **소스검토**. 원격 전송/실행 장비 인수 아님. [[2026-09-18_Registry_실행권한결속_Codex]] |
| 운영자 policy 설정 연결 / 11e9f44→d7e7d13 | offline34+실PG 기존catalog API12=46passed/0skip | **이번 설정 변경 독립검토 대기**. 초기 관측용DSN application_name 차이12setup오류 별도 보존. [[2026-09-18_Registry_운영정책설정_Codex]] |
| Claude diagnostics/cleanup R2~R5 / d59b8a6→b378785 | 사용자독립24passed(실Docker2포함), Codex22passed/실Docker2제외·격리import통과 | 브랜치 blocker 해소. image 보안8케이스 합격 아님. [[2026-09-18_Registry_실행권한결속_Codex]] |
| 기본 시험 선택 / 3afe227→1eaf285 | 비integration1179passed/489skip/2deselected,66.23초 | 사용자같은선택1179/489/2/0,75초. CI설정은 수정만 했고 CI실행 없음. Claude Docker부재22pass/2skip은 marker분리 전 세파일 시험. [[2026-09-18_Docker_시험선택경계_Codex]] |
| VF-CX-05 패키지 무결성 / 50fbb1a | offline21passed, 실제패키지2archive hash일치 | certificate/peer policy 만료로 전체exit1. 설치가능/운영인수 아님. [[2026-09-18_Workspace_아카이브무결성_Codex]] |
| 복원 관측 도구 경계 / 22059e9 | 격리PG 관련40passed/0skip, 설정·실제PITR 증거 분리 | 운영 --require-pitr는exit1/archive_mode off/pitrVerified false. **운영 RPO 충족 증거가 아님**. [[2026-09-18_VF-PITR-BOUNDARY_Codex]] |

이전 VF-CX-04 Linux140/140은 한 Docker host의 격리 Node 시험이었다. 실제2PC/5PC·GPU 인수로 바꾸지 않는다. 기존 점수2775/4800=57.8125%,잔여42.1875%는 과거 산식이며 최신 구현을 재채점하지 않았다.

## 2. 미검증/미완으로 기록된 것

| 항목 | 정확한 현재 상태 | 다음 내부 행동 / 담당 |
|---|---|---|
| 최신 image lane | b5f770a harness + b93b5ef1f944… digest:2passed/6failed. unreadable timeout1, writable/public-signing-key/business/business-workspace/business-kernel-role host-init5. 해당6건 보안단언 미도달 | 아래 호스트 재개 조건 충족 전 추가실행 중단. Codex |
| business-kernel-role | 잘못된 DB role의 image 기동 거부 단언은 세 실행 모두 미검증 | 전체image실행에서 해당 단언 도달·거부를 별도case evidence로 확인. classifier24통과로 대체 금지 |
| 나머지489skip | 1eaf285 비integration 실행에서 DB/플랫폼 등 선행조건별 미실행 | 전체가 해소됐다고 하지 않음. 필요 변경별 파일 단위 실PG 검증, skip이유·SHA 기록. Codex |
| 2deselected Docker host 시험 | 기본 경로에서 의도적 제외. 과거사용자d59실제2건통과와 최신선택에서의 미실행은 별도 | 격리host의 명시 docker_host lane/Core CI에서 실행. 공유host에서 자동prune 금지 |
| 11e9f44 policy 설정 | 로컬46통과, 독립검토/운영rollout 미완 | Claude 독립검토. 모든worker에 같은시작policy 전달·구프로세스 종료 계획 필요. hot reload/전역policyepoch 없음 |
| 공개 registry/runtime 준비 서비스 | trusted worker 및 승인 경계는 구현. 신규 공개 prepare API·대용량/GPU/routing/data/tensor-pipeline은 이 증거에 없음 | 미지원/후속구현과 미검증을 구분. 현재 상태정리 요청에서 새 구현 생성하지 않음 |
| .225/실5대 | 18443 연결3회timeout 과거증거, 유효profile/mTLS·장비 실행·이탈/복구 인수 없음 | 운영자 준비 후 아래 단계별 재개. 소프트웨어 mock/loopback시험으로 대체 금지 |
| AC-12 RPO/PITR | 목표 달성 **미입증**. 최신 운영관측 archive_mode off/pitrVerified false. 백업 직후의 거의0초 간격은 RPO 인수 증거가 아님 | Claude는 사용자 배정 compose변경안·격리리허설·용량/저장소 요구 준비. Codex는 인수지표·증거 독립검토. 실제 적용은 운영자 결정 |

4/3/2 image 통과수 변동은 harness가90c07c6/9e69dcc/b5f770a로 달라 호스트 조건만 통제한 인과실험이 아니다. OneDrive 핸들 증가와 쓰기버스트 상관은 기록하되 NTSTATUS의 원인으로 확정하지 않는다. 제품단언 실패관측0은 미도달 단언의 통과가 아니다.

## 3. 외부 조치 대기와 재시도 조건

| 대기 / 담당 | 재개를 여는 확인 가능한 조건 | 재개 첫 행동 / 합격에 필요한 증거 |
|---|---|---|
| GitHub Actions 결제·지출한도 / 운영자 | 계정 한도 해소 및 runner가 실제 job을 시작할 수 있음 | Codex가 검사할integration SHA를 고정하고 필수workflows 실행 확인. run ID/commit/exit/artifact·선택범위 기록. job시작 전billing 실패는 코드시험실패/통과 어느 것도 아님 |
| gh CLI 인증 / 운영자 | 저장소의 run/artifact를 읽을 수 있는 인증 복구 | Codex가 동일SHA run상태 조회. 인증은 조회조건이고 결제·CI통과를 대신하지 않음. 현재조회재시도 요청 없음 |
| 호스트 환경 / 사용자 | 사용자 환경조치 완료 보고, 메모리/핸들·Docker process 시작 상태 관측, 동시agent의image실행이 없는 조용한 구간 확보 | Codex가 **같은 고정 harness SHA·같은image digest**로8케이스를 순차 재실행. 각 보안단언 도달/결과·cleanup미확정·JUnit/JSON·환경조건 기록. b5f770a와최신harness 결과를 섞어 인과판정하지 않음. 8건 도달/통과 전 전체합격 금지 |
| 원격192.168.45.225 profile/mTLS / 원격운영자 | 승인된 설치 대상·접근경로와 유효한서버/peer인증서·신뢰root/endpoint/Node/epoch/profile 제공, 장비 접속 가능 | Codex는 읽기전용 preflight→패키지archive/digest/인증서/peer policy검사→fresh mTLS/Node identity확인. 통과 후 승인된 운영계획에 따라 실제workspace/terminal·storage/model·거부·Node이탈/복구를 순서대로 검증. 5대 전체 확인·인수기록 없으면 VF05완료 금지 |
| AC-12 운영PITR 적용 / 운영자, 준비Claude | 변경안 검토·운영적용 결정, 실제archive저장소/용량·보존기간·키/접근·실패감시·복원대상 확보 | Claude격리리허설을 Codex가 먼저검토. 적용 후 실제설정/연속WAL·basebackup을 확인하고 격리복원대상에서 목표시각 전후transaction으로 도달/제외를 증명. 실패기준시각 대비 복구된 최신 durable transaction 시각의 차이를 RPO로 측정하고 승인된 AC-12 목표와 비교. 복구시작~서비스사용가능 RTO·무결성·tenant권한도 별도 기록 |

기존 사용자 대기4건(CI결제,gh인증,호스트,원격설치)은 유지한다. **AC-12 운영PITR 적용은 이번에 별도로 명시한 운영준비도 의존성**이며 routine 코드승인으로 해소되지 않는다. 설정명 존재나 백업복원 성공만으로 목표를 충족 처리하지 않는다. 운영정량목표는 승인된 인수 manifest의 수치를 사용하며 이 문서에서 새 숫자를 만들지 않는다.

두 compose의 archive_mode/archive_command/wal_level/archive_timeout/data_checksums 명시문자열은 기준SHA에서 없음(rg exit1). 이는 배포정의 확인이며 실제서버 값을 새로 측정한 것이 아니다. 운영 archive_mode off는 앞선 고정증거다. archive/checksum 설정 자체도 PITR/RPO 합격의 충분조건은 아니다.

## VF 운영인수 0/5의 의미와 카드별 재개

| 카드 | 이미 있는 개발 기반 | 운영인수에 추가로 필요한 조건 |
|---|---|---|
| VF-CX-01 | canonical factory/실제JWT/PG·route·image 일부단언 | 해당SHA CI·전체image보안단언·운영IdP/HTTPS/역할경계·복구준비, 독립리뷰와 운영자 인수 |
| VF-CX-02 | ModelManifest/hash/lease·registry binding/정책 검사 | 실제Node 저장·손상/repair/retention·권한거부 증거, 운영policy와profile확정, 전체필수검사/리뷰 |
| VF-CX-03 | locality/예약·bounded remote 읽기·frozen authority | 실제 장비 topology·현재grant/channel/location·실제전송/스케줄실행·장애경계와 측정값 |
| VF-CX-04 | CPU32KiB bounded adapter·fence/retry·단일host 격리Node시험 | 실제장비에서 승인/취소/stale permit/Node-loss·대체실행과결과 무결성. 미지원GPU/collective를 합격범위에 포함하지 않음 |
| VF-CX-05 | 오프라인패키지검사·preflight·복사본migration/복원준비 | 선행카드 인수+5대 전체여정·운영권한/HTTPS·장애복구·AC-12정량증거·사용자 인수 |

0/5는 위5개 운영인수 카드의 완료0건이다. 구현0%, 모든시험미실행, 또는 실제PC0/5라는 뜻으로 쓰지 않는다. formal48task done0/48과도 다른 분모다. 현재 문서감사로 어느 카드도 done으로 바꾸지 않는다.

## 이번 정리의 검증 및 인계

owner Codex, reviewer Claude(지도 자체는미검토), branch agent/codex/model-registry-binding. agent-delivery1.1.0 적용. 공통판1.0.96/Codex1.0.63/VF1.0.22, History·image-tests.json·AC-12 registry 기준을 대조했다. 사용자 CL-07 정정·compose관측 수신, compose텍스트 독립확인. CI/Docker/원격/DB 재실행0,제품코드변경0. 다음 Claude: PITR준비안/실측증거 제출, 이번지도 및11e9f44 설정검토. 다음 Codex: 제출증거의 도달여부/실측범위 검토. 외부조건 변화 전 동일인수 재시도를 반복하지 않는다.
