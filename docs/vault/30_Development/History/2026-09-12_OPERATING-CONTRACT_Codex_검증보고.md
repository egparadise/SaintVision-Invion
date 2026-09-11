---
doc_id: "HIST-OPERATING-CONTRACT-REPORT-20260912"
title: "2026-09-12 OPERATING-CONTRACT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T00:32:00+09:00"
source_of_truth: "Git"
---

# OPERATING-CONTRACT 검증보고

CX-02 / owner Codex / reviewer Claude pending. base f5c43a1040c213e56efb546a2849ccc4317850cd, branch agent/codex/workspace-bridge, PR19. [[2026-09-12_OPERATING-CONTRACT_Codex_착수]].

## 작업한 것

[[Codex 운영 자격증명과 Storage 계약]] ADR-075/076에 첫 Linux 보호 파일 backend 구현 기준, opaque immutable reference, tenant/project/purpose/destination/회수 검사, secret 로그·경로 경계를 정의했다. `contracts/credential-reference.schema.json`에 문법 정본을 추가했다. 기존 hosted adapter의 string authenticate 인자와 연결하되 resolver 구현/계정 등록은 완료했다고 쓰지 않았다.

Storage는 현재 `LocalObjects`의 Linux/64MiB 범위와 운영 S3/50GiB 목표를 분리했다. 기존90일/1년 pin/수동 보존/backup35일을 유지하고 GC·MLflow·KEK·객체/DB 합동 복원의 인수 조건과 owner를 명시했다. 운영 S3 제품은 선택 증거가 없어 미선정으로 유지하며 후보 선정/운영 입력 담당을 기록했다.

[[운영 환경 입력과 Agent 인계]]에 IdP/사용자/DNS·TLS/원격 profile/허용 폴더/추가3대/credential backend/Provider·모델/Git/저장 제품/backup·KEK/CI의12항목을 정리했다. 어떤 입력이 어떤 작업을 막으며 입력 전 가능한 일이 무엇인지 표시했다. 타 Agent 착수·동의·승인을 대신 기록하지 않았다.

## 확인한 것과 실제 한계

- 소스 대조: `workspace_config.py`, `node_transport.private_key`, `object_store.LocalObjects`, `identity.py`, `worker.py`, `adapters/contract.py`, `adapters/cli.py` 및 Storage 최초 계획/ADR. 제품 코드/DB/운영 설정은 변경하지 않았다.
- 기존 CLI 인증은 credential_ref를 무시하고 개인 로그인 상태를 확인하며, 파일 존재를 LOGGED_IN으로 표시하는 경로가 있다. 공통 hosted resolver 또는 verified 외부 인증과 동일하지 않으므로 Claude 구현 인계에 명시했다.
- `Draft202012Validator.check_schema`와 문법 예제 검사 exit0: 정상1개, latest/경로/URL/raw string/호출자 object/누락 version/unknown revision/newline/길이/null/bool/대문자12개 거부. [실제 검사 기록](../Evidence/operating-contract-schema-20260912.json). schema 검증은 권한 검사·실제 provider 호출 합격이 아니다.
- localhost pilot overview read-only 조회에서 worker `nod_01M25VZZFBYQVFGYB11G7HC10J` 1대 online, `lan-observe-v1` 보고. 직접 mTLS/원격 실행을 새로 수행하지 않았다. 나머지3대/허용 폴더/운영 계정은 입력 미확정.
- 제품 실행·복원 회귀를 새로 돌린 작업이 아니다. 직전 PTY1460634의61/25/21 결과를 이번 schema 계약의 시험 수로 합치지 않는다.

## 다음 첫 행동

Codex는 resolver scope/회수/경로의 보안 conformance와 Claude 독립 검토를 진행한다. Claude는 결정된 reference/backend 기준으로 resolver/adapter를 구현하고 기존 CLI 인증 증거를 구분한다. Gemini는 unknown/미등록/회수 상태와 수정 담당 안내를 연결한다. 운영자는 입력판의 비밀 없는 값과 실제 보호 registry 등록을 담당한다.

CX-02는 구현·독립 검토·실제 운영 값 수신이 남아 in_progress다. 전체48 task 추정 **57.29% 완료 /42.71% 잔여(표시55%/45%) 유지**. 문서 계약 작성으로 운영 인수 점수를 올리지 않는다.

## 전달 검사

문서/ontology·commit/push·같은 SHA CI·Obsidian 영수증은 아래에 기록한다.

- 2026-09-12T00:32:35+09:00: `python tools/check_docs.py` exit0(24 원본 hash/278 versioned docs/48tasks), `python tools/check_ontology.py` exit0, `git diff --check` exit0. Obsidian 사전 check exit0:449개/변경9개/충돌0.
