---
doc_id: "HIST-RPO-CAPABILITY-REPORT-20260912"
title: "2026-09-12 RPO-CAPABILITY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:46:04+09:00"
source_of_truth: "Git"
---

# 2026-09-12 RPO-CAPABILITY Codex 검증보고

CX-01/09 / S11-DB·S12-DB, owner Codex / reviewer Claude pending. basef46b399, 1차08cd83d, 최종 구현·검증 **b49ecd3bcc8836350f972392759851f6c05f9b58**, branch agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_RPO-CAPABILITY_Codex_착수]]. 기존 복원 정본의 실제 role/fencing/기록 수정을 보존하면서 Claude4b09dfc/c632d3f의 운영 RPO 구분을 보완 통합했다.

## 독립 검토와 수정

| 지적 | 확인 | 최종 처리 |
|---|---|---|
| R1 archive_timeout을 운영 RPO 상한으로 확정 | 원본4b09dfc의 실제 pure 함수는 /bin/true와 /bin/false 모두 timeout300→목표900 합격을 반환했다 | timeout은 전환 설정으로만 보고, operationalRpoBoundSeconds=null·operationalRpoVerified=false 유지 |
| R2 archive_command 원문 노출 | 원본 capability가 pg_settings의 shell 원문을 settings에 담는다. 실제 운영 키 노출을 관측한 것은 아님 | SQL에서 command/library를 configured/not configured로 변환하여 원문을 가져오지 않음 |
| R3 CLI 목표 거부와 기록 판정 불일치 | 8a8f3b4까지 record는 기능 _passed만 사용하고 CLI만 operational gate를 사용 | CLI와 record 모두 _accepted를 사용하고 목표·기능 통과·운영 검증을 notes에 구분 |
| R4 실패 행이 met_targets=true | 첫 실제 시험08cd83d에서 outcome=failed이나 소요시간이 작으면 pilot 서비스가 met_targets=true로 기록 | 서비스가 outcome=passed를 필수로 확인, 0036의 DB 제약으로 신규 직접 쓰기도 차단 |

archive_timeout은 WAL segment 전환을 유도하지만 archiving 실패/보관 누락까지 막지 않는다. 회복 가능한 base backup·연속 WAL·목적지 내구성과 장애 범위·실제 replay 및 손실 구간 증거가 필요하다. [PostgreSQL16 WAL 설정](https://www.postgresql.org/docs/16/runtime-config-wal.html), [Continuous Archiving/PITR](https://www.postgresql.org/docs/16/continuous-archiving.html), 2026-09-12 확인. 이 근거와 별개로 실제 no-op/failure archiver를 격리 PostgreSQL에서 실행해 검증했다. data_checksums 설정도 원본 손상 부재의 보증으로 승격하지 않는다.

## 확인한 증거

| 명령·환경 | 실제 결과 | 증거 |
|---|---|---|
| check_kernel_docker.py, Linux PostgreSQL·실제 dump/restore·CLI 기록·추가 archiver2개 | **69 passed, 0 skipped, exit0** | [SHA·case·이미지·정리](../Evidence/rpo-capability-b49ecd3.json) |
| pytest recovery_capability/recovery_verdict/workspace_api_boundary, Windows | **53 passed, 0 skipped, exit0** | [보조 검증](../Evidence/rpo-verification-20260912.json) |
| check_migration_upgrade.py, 일회용 PostgreSQL | **23개 prior→0036→replay, exit0** | 같은 보조 검증;0035의 잘못된 기존 행 보존과 신규 UPDATE 거부 포함 |
| git push origin agent/codex/workspace-bridge |08cd83d 및b49ecd3, exit0 | PR19 |
| 동일 SHA GitHub Actions6개 | 계정 결제/한도로 job 시작 전 failure | [CI ID·annotation](../Evidence/rpo-capability-b49ecd3-ci.json) |

Linux는 실제 복원15개·definer22개·pilot32개다. 새 archiver2개는 포트 공개 없는 test 내부 network의 별도 소유 PostgreSQL이며 /bin/true는 archived_count 증가, /bin/false는 failed_count 증가를 관측했다. 두 설정 모두 timeout300이어도 운영 RPO 목표900을 거부한다. CLI end-to-end는 기능 복원 성공 + 운영 목표 거부 + DB outcome failed/met_targets false/notes 일치를 확인했다. failed/aborted 행의 수치가 목표 이내여도 목표 달성으로 기록할 수 없다. 소유 test DB/runner/network/archiver만 정리했고 운영 DB/Node는 변경하지 않았다.

이전 회차90/154개와 합산하지 않는다. 첫08cd83d의67개 중1개 실패는 R4 재현이며 합격으로 표시하지 않는다. 전체 PITR·객체 저장소·별도 failure domain·5대 운영 복원이나 CI 성공이 아니다.

## ADR-080과 기존 기록

[[Codex DB 함수 감사와 복원 판정 검토]] v1.2.0/ADR-080을 따른다. 기존 목표 시간 측정값은 유지하되 실패/중단 결과의 met_targets는 false로 계산한다. 0036은 NOT VALID 제약으로 과거 잘못된 기록을 고치거나 삭제하지 않고 신규 INSERT/UPDATE를 제한한다. 기존 잘못된 행의 정정/재판정은 운영자·Claude의 명시적 검토 대상이다. NOT VALID를 전체 과거 데이터 정합성 검증 완료라고 쓰지 않는다. definer9개의 정의/권한은 바꾸지 않고 정책 revision만0036으로 갱신했다.

보호 DSN 환경에서 기존 recovery_drill.py에 --require-operational-rpo 900을 붙이면 운영 목표 인수 조건을 요구한다. 현재 도구의 설정 관측은 이 조건을 충족하지 못해 기능 복원이 정상이어도 exit1이다. 플래그가 없는 exit0은 계속 database_rehearsal 범위다. JSON acceptance와 DB notes를 함께 읽는다. 새 관리/API·PITR 배포를 만든 것이 아니다.

## 다음 담당·첫 행동

- Codex: Claude8a8f3b4 backup ledger 연결의 파일 내구성/정본 보존을 독립 검토해 기존 복원 도구에 조율한다. d63717f permission snapshot도 최신 readiness와 대조한다. 원격 profile 수신 시7개 실제 시험을 재개한다.
- Claude: b49ecd3/0036/ADR-080을 독립 검토하고 복원/운영 절차에서 timeout=운영RPO 및 met_targets만으로 전체 합격이라는 표현을 제거한다. 8a8f3b4의 engine/DrillMeasurement/기록 fault3개는 최신 Codex 도구에서는 이미 수정·실DB 검증됐으므로 미수정으로 재전파하지 않는다. backup ledger 새 연결은 별도 검토다.
- Gemini: functionalDrillPassed, operationalRpoVerified, requiredOperationalRpoSeconds를 구분하고 unknown/목표 거부를 성공으로 표시하지 않는다. 기존 실제 API/PTY/다운로드 finding 검토와 원격 브라우저 인수는 별도다.
- 운영자/Orca: 보관 매체·PITR/WAL·운영 복구 목표와 CI 계정, 2-PC/5대 설정 입력을 추적한다. 운영 DB 재설정·키/Node 변경은 실행하지 않았다.

전체 추정 **57.29% 완료 /42.71% 잔여(기존 표시55/45) 유지**. 이번은 판정·무결성 보완이며 실제 운영 RPO 목표를 달성한 것이 아니다. 공식 task done·CI/독립 검토/운영 인수는 승격하지 않는다.

## 전달 검사

check_docs.py(원문24·문서291·작업48), check_ontology.py, git diff --check 모두 exit0. 선택적 Black 검사는 7개 중3개 통과,4개 재포맷 요구(exit1)이며 동일4개는 basef46b399에서도 미통과함을 확인했다. 전체 formatter 통과로 보고하지 않으며 광범위한 기존 코드 재포맷은 이번 변경에 섞지 않았다. 최종 push·Obsidian 영수증은 이어서 기록한다.
