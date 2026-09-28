---
doc_id: "HIST-CLAUDE-2026-09-28-S10-BE-MLFLOW-DESIGN"
title: "S10-BE MLflow 연동 설계 v1.0 — 정본은 lineage(content_sha256·approval digest), MLflow는 미러(B 권고, A 미도입 선택지, C 정본 거부), TrackingSink 계약·strict config·fail-closed·부재 시 NOT_OBSERVED·시험 계획; 결정 요청 (카드 bd, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:21:22+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["S10-BE", "mlflow", "design", "claude", "docs-only"]
---

# S10-BE MLflow 연동 설계 v1.0 (2026-09-28, 카드 bd)

산출물: [[S10-BE MLflow 연동 설계 v1.0]]. #166 G1a(MLflow adapter·계약·설정·시험 부재) 해소안. 구현은 결정·승인 뒤.

## 1. 확인 방법(실제 수행한 것만)

`git grep -i mlflow`로 코드 0건·문서 8건(아키텍처 4·로드맵·자격증명 계약·점검 2)을 확인하고 아키텍처 문서의 MLflow 역할("실험과 model registry MVP, 배포 권한은 별도 정책", ML Worker 생태계, `inv mlflow RUN`), 자격증명 계약의 "MLflow-owned artifacts" namespace, `src/saintvision/adapters/contract.py`(Capability·ProbeResult·AuthResult·Attestation·ProviderAdapter 8 멤버), `src/saintvision/services/lineage.py`(register/record_lineage kind 5·REQUIRED_KINDS·release·record_deployment digest 결속), `evaluation.py`(start/finish eval run·score_report), `src/saintvision/config.py`(strict env 패턴), `errors.py` 코드 체계, 0003 `NEW_APPEND_ONLY`, #159의 `configurationReadiness.objectStore` 패턴을 읽었다. 가벼운 명령만.

## 2. 결과

- 결정 요청: A 미도입 / **B 미러(권고)** / C 정본(거부 — append-only·approval digest·활성 배포 1 원칙과 충돌).
- B 설계: 범위표(experiment·run·metric·artifact 참조만·model registry 메타 미러, 받는 것은 미러 id뿐), 정본 관계(lineage 불변·edge 추가 없음·`mlflow_mirrors` append-only 미러 참조 테이블·불일치 표면화), `TrackingSink` 계약(ProbeResult/AuthResult/Attestation 재사용, `mirror`·`redact`, conformance + in-memory ReferenceSink), strict config 4(URI https만·userinfo 거부·credential 참조만·timeout), 오류 코드 4(`TRACK-MLFLOW-*`)와 fail-closed(정본 커밋 뒤 outbox, 미러 실패는 성공 아님·정본 불변), 부재 시 NOT_OBSERVED, 시험 계획(PG-free·실PG·hosted pinned 컨테이너·운영 실측 G1b).

## 3. 게이트·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 코드 변경 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: 코디네이터/사용자 A·B 결정 → Codex 설계 검토 → 구현 카드.
