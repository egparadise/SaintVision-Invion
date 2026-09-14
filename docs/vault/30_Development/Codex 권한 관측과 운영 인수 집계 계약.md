---
doc_id: "CONTRACT-PERMISSION-OBSERVATION-001"
title: "Codex 권한 관측과 운영 인수 집계 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:08:57+09:00"
source_of_truth: "Git"
---

# Codex 권한 관측과 운영 인수 집계 계약

owner Codex / reviewer Claude pending. GUIDE-001·ADR-078/080/081을 보완하며 기존 PermissionSnapshot·pilot 서비스·operational_readiness.py가 정본이다. 구현9755c60, [[2026-09-12_PERMISSION-SNAPSHOT_Codex_검증보고]]. 공개 인증/API나 실행 허가를 새로 만들지 않는다.

## ADR-082 — 권한 관측 기록

- 기본 조회는 REPEATABLE READ + READ ONLY, 쓰기0이다. --snapshot만 기존 PermissionSnapshot을 쓴다. 보호 INV_READINESS_DSN(또는 --dsn-env가 지정한 환경변수)의 DB owner/superuser 권한을 확인한다. runtime login은 거부한다. CLI 입력/실패에서 DSN·인자 원문을 반사하지 않는다.
- 비교 scope는 permission-observation-v1 + tenant + project + user다. 프로젝트와 사용자가 같은 tenant에 실제 존재해야 한다. 이전 unversioned snapshot은 삭제하지 않고 새 비교에서 제외한다. 첫 관측은 changed=null, 같은 범위의 동일 digest는 false다.
- 별도 connection의 transaction advisory lock을 대상별로 획득한 다음 관측 transaction을 시작한다. lock timeout5초, SQLAlchemy REPEATABLE READ와 transaction-local tenant에서 입력·권한·선택적 AC-12 집계·snapshot 기록을 수행한다. 관측 중 다른 writer의 권한 변경을 막지는 않는다. 그 변화는 다음 관측에서 확인한다.
- taken_at/observedAt은 관측 transaction의 시작 시각이다. commit 시각이나 현재 권한이라는 뜻이 아니다. 같은 범위의 직전 taken_at보다 시각이 전진하지 않으면 기록을 거부한다. 동시 정상 collector는 순서를 가지며 실패 시 snapshot rollback·lock 해제, 성공 식별자는 commit 이후 공개한다. 비교 lock은 이 collector의 writer를 조율하며 DB owner의 임의 직접 쓰기까지 막는 불변 ledger는 아니다.
- operator enabled/person/subject mapping/can_approve를 관측한다. observedOperatorApprovalCapability는 관측값이고 mayApproveAsOperator/mayApprove/mayRequestWork는 null을 유지한다. 실행·승인은 kernel이 현재 조건과 별도 2인 규칙을 재검증한다.

## ADR-083 — 인수 기록 목록과 운영 검증 분리

--acceptance-evidence는 같은 관측 transaction에서 기존 pilot_readiness를 호출한다. --release가 없으면 acceptanceAssessed=false이며 기존 release가 있으면 같은 tenant/manifest/AC-12 기록을 비교한다. --release 단독 입력은 거부한다.

| 필드 | 의미 |
|---|---|
| catalogComplete | 해당 release의 제한된 기록 목록 충족 여부. AC-12 기록/manifest 일치·거절 부재·목표/무결성/fencing을 통과한 DB drill·보존 기간 내 verified backup/off_site 선언·폴더 점검을 검사 |
| evidenceComplete | 현재 false. 이 집계에는 전체 운영 인수를 검증하는 수집기·계약이 없으므로 metadata 존재를 전체 증거 완성으로 승격하지 않음 |
| operationalAcceptanceAssessed | false. 별도 장애 영역의 bytes 증거, 운영 RPO/전체 서비스 복원, 실제 Node/인증 브라우저 인수는 unverified에 표시 |
| acceptanceAssessed | release를 지정하여 기록 비교를 했는지. 사람이 운영 인수를 승인했다는 뜻 아님 |

기존 evidenceComplete=true를 녹색 운영 완료로 사용하던 consumer는 catalogComplete와 scope/unverified를 구분하도록 변경해야 한다. 수집·검증 계약 없이 evidenceComplete를 true로 켜는 옵션은 없다. 과거 missed target은 목록에 남기되 목표를 충족한 다른 정상 drill이 있으면 과거 실패만으로 영원히 차단하지 않는다. 과거 행은 수정하지 않는다.

## 운영 CLI

보호 DSN 환경이 이미 설정된 운영자 셸에서 다음을 사용한다. tenant/project/user/release는 실제 ID로 지정하며 예시 값을 운영 값으로 만들지 않는다.

- 조회: python tools/operational_readiness.py --tenant TENANT --project PROJECT --user USER --json
- 관측 기록: 위 명령에 --snapshot 추가
- 인수 목록: --acceptance-evidence 추가, 필요하면 --release RELEASE 추가

JSON/text는 같은 _exit_code를 따른다. 0은 요청한 진단에서 누락 조건을 찾지 않았다는 뜻이다. 1은 진단 미충족, 2는 입력/관측 실패다. **--snapshot과 --acceptance-evidence를 함께 사용하면 snapshot은 commit됐어도 운영 증거 미검증 때문에 exit1일 수 있다.** permissionSnapshot의 영수증과 acceptanceEvidence를 따로 읽고, exit1을 쓰기 실패로 간주해 자동 재시도하지 않는다. 새 관측 자체는 새 기록이며 멱등 요청 API가 아니다.

운영 DB/키/Node에 이번 변경을 적용하지 않았다. 실제 Provider·운영 복원 수집·브라우저 인수·CI/독립 review는 별도다.
