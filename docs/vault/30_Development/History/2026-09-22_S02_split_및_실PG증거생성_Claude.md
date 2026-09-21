---
doc_id: "CLAUDE-S02-SPLIT-AND-REALPG-EVIDENCE-001"
title: "S02 (BE/DB/ST) 갈래 + 진행 가능분 실 PostgreSQL 증거 생성 (owner Claude)"
status: "in_progress-evidence-added"
version: "1.0.0"
author: "Claude (owner)"
reviewer: "Codex"
verified_at_sha: "a8c979d0 (origin/integration; 측정 중 tip 이동 가능)"
working_tree_clean: "YES"
db_method: "disposable pgvector/pgvector:pg16 via Docker 20.10.22, per-test DB, 제거 후"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S02", "split", "real-pg", "evidence", "owner", "wiring"]
---

# S02 갈래 + 진행 가능분 실PG 증거

S02-BE/DB/ST는 **owner Claude·reviewer Codex·planned·depends_on S01(전부)**. 요구 증거 = **실제 API·브라우저 여정·인증 실패 기록**. S01 방법으로 갈랐다(①없음/②있으나 미기록/③범위 미덮음, ③은 사용자 필요/불필요로 재분).

## 갈래 (assess: 코드+배선 상태)
S02 scope는 **①없음이 없다 — 전부 이미 built**(planned-but-exists). users/nodes/node_capabilities/**snapshot** 테이블(0001_s02_baseline), OIDC(`identity/oidc.py`), 노드 enroll+mTLS(`certificate_fingerprint`)+heartbeat 라우트, contributions+DataLocation 카탈로그(`/storage/locations`) 모두 존재.
- **S02-BE (OIDC·mTLS 등록·Heartbeat)**: ② 코드 built. **③ 사용자**: OIDC는 실 issuer/audience/jwks 필요(oidc.py가 그 settings 요구) → **실 IdP 인수 대기**; mTLS/heartbeat **실 물리 노드 인수 대기**. 소프트웨어+test-verifier+인증실패 증거는 진행 가능.
- **S02-DB (User·Node·Capability·Snapshot)**: ② 전부 built. **③ 없음 — 물리 의존 없음.** S01-DB처럼 **사용자 입력 없이 진행 가능**(실PG 증거는 일회용 컨테이너로).
- **S02-ST (제공 폴더·DataLocation 카탈로그)**: ② 코드 built. **③ 사용자**: 실 제공 폴더/장비 인수 대기. 카탈로그/계약 소프트웨어는 진행 가능.

## 진행 가능분 실행 — 실 PostgreSQL 증거 생성 (밤새 not_run이던 것)
이 호스트는 PG 부재라 S02의 실제-API/인증실패 시험이 **밤새 skip(not_run)**이었다. Codex 방법(일회용 pgvector/pgvector:pg16 컨테이너, per-test DB)을 읽어 그대로 써서 **실 PostgreSQL로 실행**했다. 내 소유 라벨(`ai.saintvision.owner=claude`)·전용 포트로 띄우고 **끝나고 제거**했다. Codex의 `codex-s05-pools-pg`와 보호 컨테이너(orthanc·lan-db)는 **미접촉**.

**provenance**: SHA `a8c979d0`, working_tree_clean=YES, `.venv` python 3.14.6, Docker 20.10.22.
- **`tests/test_api.py` → 28 passed / 0 skip** (실PG). = **S02-BE/DB AC-02**: 노드 등록→읽기, **인증 실패 기록**(부트스트랩 토큰 재사용 403·미지 토큰 거부·토큰 테넌트 결속 위반 거부), 프로젝트 간 테넌트 격리.
- **focused 세트 → 63 passed / 0 skip** (실PG): `test_storage_api`·`test_storage_catalog`·`core/test_storage_list_response_contract`·`core/test_storage_observation_contract`(**S02-ST 제공폴더+DataLocation 카탈로그**) · `test_node_auth`(**S02-BE 노드 auth**) · `core/test_node_page_detail_response_contract`(**S02-DB Node/Capability**).
- **합계 91 passed 실PG.** 실행이 **API→실DB 경로를 관통**하므로(노드가 API로 등록되어 실DB에서 읽힘·기여가 등록되어 카탈로그에 뜸) **"만든 게 제품 경로에서 실제로 불리는지"가 실측으로 확인**됨(오늘 밤 lesson 적용) — 죽은 코드 아님.

## 못 한 것 (not_run — 검증했다고 안 적음)
- **전체 CI-스코프 실PG 스위트**: 시도했으나 per-test DB 생성이 느려 **2분 초과로 미완**. S02 focused 91만 완료. 전체(1008 skip 깨우기)는 **CI 첫 실행/Codex 실PG 작업** 몫(사용자 입력 아님, 시간/러너 문제).
- **실 IdP**(OIDC 실 issuer/jwks 검증) = ③ 사용자. **실 물리 노드**(mTLS/heartbeat 실장비 인수) = ③ 사용자. **실 브라우저 여정**(Gemini) = 별도 레인/사용자.
- discovery 자격증명 auth-failure(`core/test_discovery_*`)는 focused 세트 밖(경로 tests/core, PG-marked) — 전체 CI-스코프 실PG에서 커버.

## 상태·인계
- S02 소프트웨어는 built + 위 91건 **실PG 실측**으로 실제-API/인증실패 증거가 섰다(S02-DB는 사용자 입력 없이). **브라우저 여정·실IdP·실장비는 미충족.** depends_on S01(in_progress)도 done을 gate.
- **나는 owner지만 self-close 안 함** — 증거를 기록하고 reviewer(Codex)에게 인계(next_handoff Codex). closing은 잔여 증거가 서고 절차대로.
- 사용자 입력 필요분(BE 실IdP·ST 실장비)은 브리프의 기존 물리장비/IdP/Storage callout에 붙였다.

관련: [[2026-09-22_S01_기반셋_왜안닫혔나_검토_Claude]] · [[사용자_결정대기_브리프_2026-09-22]] · [[Codex 잔여 개발 작업과 합격 증거]] · [[검증규칙과_세축_canon]].
