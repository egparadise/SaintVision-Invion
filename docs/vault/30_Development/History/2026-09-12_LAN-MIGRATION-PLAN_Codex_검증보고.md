---
doc_id: "HIST-LAN-MIGRATION-PLAN-REPORT-20260912"
title: "2026-09-12 LAN-MIGRATION-PLAN Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T18:18:23+09:00"
source_of_truth: "Git"
---

# 구현·검증·다음 담당

CX-02 무결성 지원 owner Codex/reviewer Claude pending. 상위 S12-ST owner Claude/reviewer Codex 유지. basec5d1d39 → 제품b5493d79121eae84c654f98e172d54414a01990c, agent/codex/workspace-bridge. commit/push exit0. [[2026-09-12_LAN-MIGRATION-PLAN_Codex_착수]].

## 변경

`plan_lan_migration.py`가 명시적 관리 연결로 Alembic metadata만 READ ONLY 조회한다. 코드 DAG의 ancestor 집합을 계산해 적용되지 않은 분기도 포함하고, 미확인/중복/서로 조상인 DB heads는 거부한다. 계획에는 revision/file SHA256/불가역 여부와 인수 전제만 기록한다. SQL 실행·migration 적용 기능은 없으며 migrationAuthorized=false/schemaIntegrityAssessed=false다. 파일 hash는 계획 수립 시 코드 고정 증거이지 DB 내부 schema 검증이 아니다.

`check_lan_storage_readiness.py`는 필수 열별 SELECT와 schema USAGE를 확인한다. 테이블 전체 SELECT가 없어도 필요한 열 권한이 있으면 인정하며, schema 권한이 없는 역할을 점검할 때 전체 쿼리를 실패시키지 않는다. RLS 적용 후 실제 row 접근/소유권 검증을 대체하지 않는다.

`check_migration_upgrade.py --from-revision`으로 기존 published 경로 하나를 선택 검증할 수 있다. 기본 전체 경로 검증은 유지하며0036 출발점도 추가했다.

## 실제 결과

운영 Alembic은0023_containment_approvals, 코드 head는0037_storage_sample_commit. 분기·병합 포함 미적용20개. 운영 runtime은inv_kernel 구성원이나0023에는0037의 열 권한이 아직 없다. 기존 권한 제한 관측은 실제였지만 이전 도구 판정은 향후 열 권한을 잘못 거부할 수 있어 수정했다. 운영 DB/역할/Node/배포 묶음 변경 없음.

동일 clean SHA에서 다음을 실행했다.

- `python -m pytest tests/core/test_lan_migration_plan.py tests/core/test_lan_storage_readiness.py -q --junitxml=.work/lan-migration-tests.xml`: exit0,15 passed/0 skipped. 실제 PostgreSQL1개, DAG8개, 기존 bundle/boundary6개. Alembic path_separator deprecation warning1개.
- `python tools/check_migration_upgrade.py --from-revision 0023_containment_approvals`: exit0. 새로 할당한 폐기용 DB에서0023→head→head, 표본 tenant 보존/runtime grant/definer catalogue 정책 확인. 다른 출발점 전체는 이번 재실행하지 않았다. 운영 데이터 복사본·백업복원 리허설은 아니다.
- `python tools/plan_lan_migration.py --state <pilot> --output .work/lan-migration-plan.json`: exit1, 읽기 성공/미적용20개.
- `python tools/check_lan_storage_readiness.py --state <pilot> --output .work/lan-migration-readiness.json`: exit1, 기존5개 차단 조건 유지.
- CI 같은 제품 SHA/18:17:20 KST:6개 모두 billing 제한으로 job 미시작/failure. 로컬 검증을 통합CI 성공으로 쓰지 않는다.

Evidence: [[lan-migration-plan-b5493d7.json]], [[lan-migration-validation-b5493d7.json]], [[lan-migration-readiness-b5493d7.json]], [[lan-migration-tests-b5493d7.xml]], [[lan-migration-b5493d7-ci.json]].

## 이어서 할 일

1. Codex: 운영 backup 복원 사본에서20개 migration의 실제 데이터 보존/불변 조건과 현재 관측 서비스 호환성을 확인할 리허설 절차를 준비한다. 기존 운영 DB를 바로 upgrade하거나 role 권한을 넓히지 않는다.
2. Claude: 상위S12 운영 복구 훈련/실제 등록 owner·project·Node 연결과 새 계획/열 권한 판정 독립 검토. 검토 수신·완료를 대신 기록하지 않는다.
3. Codex: 검증된 복구·DB 적용 계획과 별도 Node 후보 묶음을 연결하고, 원격 Windows/WSL 경로 확인 후 실제 mTLS/Evidence·7개 실행/취소/복구 인수 진행.

전체2775/4800=57.8125%, 잔여42.1875% 유지. PR19 draft/CI/독립 검토/원격 인수 미완료. Obsidian 최종 동기화는 후속 기입.

## 최종 전달

문서346개/48task·ontology exit0. 외부 동시 편집3개가 두 번 감지되어 각각 원문/hash 보존 후 동일bytes adopt로만 동기화했다. 18:20:24 KST/e1acb7e 로컬 Obsidian683개 hash 일치/pending0/conflicts0, [[lan-migration-obsidian-20260912.json]]. OneDrive cloud 미확인. 이 영수증 추가 후 최종 commit/push/sync를 수행한다.
