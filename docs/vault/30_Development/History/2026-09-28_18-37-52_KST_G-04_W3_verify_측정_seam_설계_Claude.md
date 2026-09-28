---
title: "G-04 W3 verify trusted-worker 측정 seam 설계 v1.0 (카드 83, docs-only)"
version: "1.0"
status: "review"
author: "Claude"
updated: "2026-09-28T18:37:52+09:00"
---

# G-04 W3 verify trusted-worker 측정 seam 설계 v1.0 (카드 83, docs-only)

branch `agent/claude/g04-w3-verify-seam-design`, base `1e8baf04`(integration). 문서: [[G-04 W3 verify trusted-worker 측정 seam 설계 v1.0]]. 코드·workflow·migration 변경 0(번호 0054는 **요청**만).

## 왜

G-04·G-05 설계 v1.2.1(#183)에서 W3 verify는 보류: `services/lineage.py:279`의 정본("trusted worker가 실제 weights를 해시")을 승인 사용자가 DB digest를 그대로 제출해 세울 수 있으면 거짓이 된다. 이 문서는 사용자 입력 digest를 route에서 **없애고**, 측정 정본(measurement)을 verify가 결속하도록 seam을 제안한다.

## 제안 요지

- **누가 읽는가**: model version의 bytes가 놓인 contribution의 enrolled node(mTLS `NodePrincipal`, `lock_current`로 tx 안 재확인). 읽기는 kernel의 challenge-bound signed sample(`storage_commit.accept`·`node_transport.storage_sample`·`storage_sampling.verify_sample`: nonce·만료·pinned leaf 인증서 서명 검증)과 같은 기계로 `model-measure` challenge를 발급·수집. 사용자는 측정을 요청만 한다.
- **무엇을 남기는가**: append-only `model_version_measurements`(model_version_id·uri·provider_id/locator·sha256·byte_size·observed_at·recorded_at·node_id·certificate_sha256·request_id·challenge/response digest·evidence_id·duration). saintvision `EvidenceEnvelope`는 run 종속·`inv://` output_ref 제약이라 정본으로 쓰지 않고 evidence_id로만 연결.
- **verify route**: body는 `{measurementId}`만(strict; digest 필드 존재 시 422). #183 §5-3 순서(IDEM-6 → live canApprove → `_locked_version` FOR UPDATE+populate_existing → 재확인) 뒤 measurement를 tenant·version·uri·sha256·byte_size·신선도·node 상태로 결속하고, `verify_model_version(content_sha256=measurement.sha256)`에 **측정값**을 넘긴다. 불일치·stale·node retired → `GRAPH-0002/409`(값 비노출), 다른 version/tenant/없음 → 404 동일 문구, lock timeout → `SYS-0001/503`.
- **migration**: 필요(measurement 테이블) → **0054 요청**. 소유는 kernel(권고; node transport가 kernel에 있고 business는 관측을 HTTP로 읽는 #167 패턴) 또는 business — Codex 확정.
- **시험**: 위조 evidence(서명·지문·만료)·다른 object·replay·node 신원 없음/retired 거부, RLS·불변 trigger, W3 route의 22 되살림(digest body 422 포함), release↔verify·verify↔pin 실 PG 경합(W4에서 NOT_OBSERVED였던 verify↔pin을 채움).
- **열린 질문**: 다중 파일 model의 `content_sha256` 정의(단일 object 우선), 기록 소유, 신선도 창.

## 검증 방법(실제 수행한 것만)

`git grep -n -F`로 인용 라인 확인(base 1e8baf04; `_locked_version`은 #167/#183/#196 인용), kernel `storage_commit.py`·`storage_sampling.py`·`node_transport.py` 정독. 실행한 시험 없음. 검토자 Codex(보안 경계).
