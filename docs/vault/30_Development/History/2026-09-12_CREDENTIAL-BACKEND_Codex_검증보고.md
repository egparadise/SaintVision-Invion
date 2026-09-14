---
doc_id: "HIST-CREDENTIAL-BACKEND-REPORT-20260912"
title: "2026-09-12 CREDENTIAL-BACKEND Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:12:51+09:00"
source_of_truth: "Git"
---

# 2026-09-12 CREDENTIAL-BACKEND Codex 검증보고

CX-01/02, S01-BE·S08-ST·Context 보안 통합. owner Codex, reviewer Claude pending. base408cb547, backend74012b3, Claude Context dcad652→35c88e0, 최종 구현·검증 **0f5f4e870b3a8bbb361cd5d98476a2989ee9f2d7**, branch agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_CREDENTIAL-BACKEND_Codex_착수]].

## 작업한 것

기존 Credential Protocol에 실제 LinuxFileCredentials와 PostgresCredentialRegistry를 연결했다. 0035에 immutable credential version과 Run별 현재 grant를 추가했다. FORCE tenant RLS·복합 FK·runtime SELECT-only·현재 scope/만료/회수/epoch/kill/종료 Run 검사를 수행한다. 허용 조회 event는 인가 관측이며 byte 읽기·외부 효과 완료로 해석하지 않는다.

파일은 service-owned private root, 등록 basename/inode, no-follow descriptor, 정규 파일·단일 링크·owner/mode·64KiB 한도, 읽기 전후 상태·실제 SHA-256 및 현재 root/name을 확인한다. 읽는 사이 commit된 grant 회수는 마지막 registry 조회에서 거부한다. callback 동안 DB 잠금을 유지하지 않으며 자동 재시도하지 않는다. ADR-077은 [[Codex 운영 자격증명과 Storage 계약]]을 따른다. 운영용 secret 등록·외부 Provider 호출·Windows ACL·KEK provider까지 구현됐다는 뜻은 아니다.

Claude dcad652의 Context 보안 검사와 5995b8b의 readiness 도구/전용 시험을 통합했다. Context는 raw item_id/cause_ref를 오류에 담지 않고 content/item_id/source_uri의 알려진 비밀 패턴을 저장 전에 거부한다. kind/retrieval 오류도 입력값을 반사하지 않는다. Claude의 미커밋 0031/recovery 파일은 건드리지 않았다. 오래된 migration-head 시험은 반영하지 않았다.

## ADR-078 — 진단 결과와 실행 인가, Context 오류 경계

운영 readiness CLI의 관측 조건이 열려 있어도 `wouldAdmit=null`이며 `observedGatesOpen`과 미검증 항목을 별도로 반환한다. 닫힌 실행 조건은 wouldAdmit=false다. 프로젝트·승인 권한의 일부 행을 읽은 것으로 실행/승인 권한을 확정하지 않으므로 `mayRequestWork`/`mayApprove`는 null, 관측 교집합은 별도 필드다. 진짜 인가는 현재 kernel/ToolGateway에서 수행한다. 이것은 CLI 진단 계약이며 기존 공개 readiness API를 바꾼 것이 아니다.

DSN은 명령행 값으로 전달하지 않고 기본 INV_READINESS_DSN 또는 `--dsn-env`가 지정한 보호 환경 변수에서 읽는다. 인자/DB 실패는 원문 없이 고정 오류와 exit2를 반환한다. 조회는 REPEATABLE READ, READ ONLY와 transaction-local tenant binding으로 수행한다. exit0은 관측 입력/교집합/제공량 불일치가 없다는 CLI 의미이며 실행·운영 인수 허가가 아니다. `--help`와 운영자 보호 설정으로 실행하며 DSN을 문서/PR에 기록하지 않는다.

Context는 알려진 ADR-014 패턴만 인식한다. 미인식 비밀이나 전체 DLP 안전성을 증명하지 않는다. 오류 위치는 ordinal·서버 소유 field/label로 표시하고 원본 식별자나 원문을 causeRef에 넣지 않는다.

## 확인한 증거

| 명령·환경 | 실제 결과 | 고정 SHA·Evidence |
|---|---|---|
| check_kernel_docker.py --prepare-only 및 --prepared, Linux Docker/실제 PostgreSQL·파일 | **154 passed, 0 skipped, exit0**, 소유 test runner/DB/network 정리 성공 | 0f5f4e870b3a8bbb361cd5d98476a2989ee9f2d7, [Linux 증거](../Evidence/credential-backend-0f5f4e8.json) |
| pytest credential model + workspace API graph + readiness CLI, Windows | **53 passed, 0 skipped, exit0** | 같은 SHA, [별도 검증](../Evidence/credential-backend-verification-20260912.json) |
| check_migration_upgrade.py, 별도 실제 PostgreSQL | **22개 prior→0035→replay 통과, exit0** | clean74012b3; 이후 migration 변경 없음, 같은 별도 검증 파일 |
| git push origin agent/codex/workspace-bridge | backend74012b3와 최종0f5f4e8, exit0 | PR19 |
| 같은 SHA GitHub CI 6건 | 모두 account billing/spending 제한으로 job 시작 전 실패 | [CI ID·annotation](../Evidence/credential-backend-0f5f4e8-ci.json) |

Linux154개는 실제 backend39+추가경합/권한9, DB definer22, 복원12, PTY7, Context 본문·metadata26, Context/eval DB29, readiness DB10이다. 첫 dirty 통합65개, backend740의89개는 위154개와 중복이므로 더하지 않는다. Windows47개 모델은 실제 backend48개와 검증 수준이 다르다. 외부 API/모델, 물리2-PC/5대, 전체 서비스 복원·운영 CI 합격을 뜻하지 않는다. Linux 실행 명령의 test 파일 목록과 파일 SHA는 Evidence에 남겼다. 개별 parameter는 합성 secret 문자열을 반복 노출하지 않도록 test 이름·ID hash로 기록했다.

## 현재 운영 관측과 다음 담당

01:09:55 KST pilot overview는 worker1대 online/fresh, lan-observe-v1, killSwitch=true, 업무 제출=false, 웹 인증=false를 반환했다. 이번 새 mTLS handshake나 실제 원격 업무 시험의 증거가 아니다. 원격 PC 프로필 설치 결과·실행 경로는 여전히 미확인이다.

- Codex: backend/Context/readiness 독립 검토 지적을 반영한다. 다음 구현 범위는 Provider 연결에 필요한 protected registry 등록/회전·회수 운영 절차와 Storage 무결성 인수다. 원격 profile 수신 시 CX-03의 실제7개 실행/취소/복구 시험을 재개한다.
- Claude: 74012b3·0f5f4e8·0035/ADR-077/078을 독립 검토한다. 기존 resolver를 재작성하지 않고 실제 Provider adapter에 연결하여 스트림/취소/usage/오류 비노출을 검증한다. 본인 Context/readiness 원본을 검토한 Codex와, Codex 수정의 승인자는 구분한다. 운영 로그인/계정·Workspace·전체 객체/DB/Node 복원은 별도다.
- Gemini: 관측/unknown/미설정 상태와 실제 kernel 결과·인증/hash 다운로드·PTY/drain 계약을 연결한다. CLI null을 UI 성공으로 바꾸지 않는다. 물리 원격·브라우저 인수 대기.
- Orca/운영자: CI 계정, 운영 IdP/모델/권한/허용 폴더/추가 장비 입력, PR21→22→19 검토 순서를 추적한다. 실제 외부 메시지 전송·Agent 자동 실행 기록이 아니다.

전체 추정 **57.29% 완료 /42.71% 잔여(기존 표시55%/45%) 유지**. 이번 backend는 하위 구현·격리 시험을 충족했지만 원래48개 과제의 추가 인수 단계나 외부 연결을 충족한 것으로 점수를 올리지 않는다. CI·독립 검토·운영 인수 미완료 때문에 공식 done도 추가하지 않는다.

## 전달 상태

최종 문서 검사·push·Obsidian check/apply/check 결과는 전달 영수증으로 이어서 기록한다.

- 2026-09-12T01:13 KST: check_docs.py exit0(24 원본hash/284 versioned docs/48tasks), check_ontology.py exit0, git diff --check exit0. Obsidian 사전check461개/변경13개/충돌0, exit0.

- 실제 전달 2026-09-12T01:13:56+09:00: source `ed2a1e485e7604956891c19e8b2e2ce3844ca183` commit/push exit0. sync_obsidian.py --check → --apply → --check 모두 exit0, 변경13개 export, 관리461개 hash 일치, pending0/conflict0. 로컬 Obsidian 범위이며 OneDrive 클라우드 동기화는 미확인. PR19 제목/본문에 최종 backend·Context/readiness와 검증/차단을 반영했다. 이 영수증·정본 conformance 인계 갱신도 같은 절차로 export한다.
