---
doc_id: "HIST-CLAUDE-REVIEW-CODEX-CARD3-URI-RESOLVER-001"
title: "Codex 카드 3 독립 검토 — b06fc199 inv URI resolver↔strict 실행 Manifest 결속(VF-CL-02d): 실 PG·권한 경계·되살림 2건(1 KILLED·1 SURVIVED) → 조건부 승인(시험 무게 1건 후속)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T21:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "codex", "vf-cl-02", "model-resolver", "model-manifest", "permission-boundary", "mutation", "real-postgres"]
---

# Codex 카드 3 독립 검토 (reviewer Claude)

대상: integration `b06fc199`(feat(core): bind inv model URI resolver to kernel manifest) + 보고 `6706fbde`. 검토 트리 `.worktrees/claude-rev3`(detached tip `0de0f650` ⊇ b06fc199, clean). 실 PostgreSQL = `.env` DSN(127.0.0.1) 일회용 Alembic-head DB, PowerShell 분리 실행 1레인(메모리 경보: 단일 파일만). **실제 수행한 것만** 기록. 앞 카드 검토: [[2026-09-22_Codex_카드2_실행Manifest관측_model-retry_F1_독립검토_Claude]].

## 판정: **조건부 승인** — 제품 코드 결함 0, **시험 무게 결함 1(F1)**, 관찰 3

## 1. 실측 표

| # | 범위 | 검증 | 결과 |
|---|---|---|---|
| 1 | 계약 앵커 | `tests/core/test_model_execution_manifest_contract.py`(+2 시험: `ModelUriResolver.__module__` 결속, `_checked`가 `executionAuthorized=true` 오염 투영을 거부) + `check_contract_bindings.py` serving 파일에 `model_uri_resolver.py` 추가 | PG-free 45 passed(route_coverage 시험 포함); `check_contract_bindings` PASS 52 fixture / 17 응답 타입. **새 fixture 없음** — 1.9.0 fixture 재사용이 맞다(응답 계약이 동일 `ModelExecutionManifestObservation`, 새 완화 envelope 없음) |
| 2 | replay guard | HTTP 시험 `…rechecks_both_roles_and_never_replays_authority` 실 PG | **1 passed** — ready 200 / replica stale → readyNodes [] / 미존재 404 `MODEL-0004` / 타 project 403 `AUTH-0030` / `project_members` 삭제 후 같은 GET 403 `AUTH-0030` |
| 3 | 권한 경계 | 같은 시험이 `inv_app` 멤버 별도 login으로 직접 검증 | `SELECT count(*) FROM public.models` = **0**(tenant GUC 미설정 → RLS 0행), `SELECT … FROM inv.model_manifests` → **InsufficientPrivilege**. 코드 순서도 문서 주장과 일치: `_authorized_user`(kernel `_grant` + business `permission(linked=True)`) → 그 다음에만 `resolve_model`이 `(tenant, project, name, version)` 조회 → 타 project는 존재 조회 전 403 |
| 4 | 라우트 커버리지 | `route_coverage --served src --served services/control-plane/src --client apps/web/src` | clientPaths 44 / unserved 0(새 라우트는 화면 미호출 — 정상) |
| 5 | 신선도 | `check_response_freshness` | MISSING 0(응답 타입 신설 없음) |
| 6 | 문서 | `check_docs`(tip) | PASS 805 |

## 2. 되살림 (mutation) — 2건, 적용은 `git diff --stat`으로 확인

| 변이 | 대상(`model_uri_resolver.py`) | Codex 시험 | 결과 |
|---|---|---|---|
| M1 | 교집합 재검증 2줄 제거(`item["readyNodes"] = checked.ready_nodes` / `materialisable`) → kernel 관측 그대로 통과 | `…never_replays_authority` | **SURVIVED — 1 passed** |
| M2 | `_authorized_user`가 재검증 없이 `principal.subject_id` 반환 | 같은 시험 | **KILLED** — `ready` 케이스에서 `readyNodes []`(reader 범위가 business userId가 아니라 subject로 잡혀 location 누락) |

**M1이 살아남은 이유(확인)**: 시험의 "stale" 케이스는 `public.data_replicas.state='stale'`인데, 커널 관측(0046 `public.model_location_readiness`)도 같은 `data_replicas`를 `state='ready'`로 필터하므로 커널이 이미 `readyNodes []`를 준다. 즉 현 시험은 **business 경계가 kernel 관측에서 node를 빼는 유일한 경로(reader scope: `storage_contributions.registered_by_user_id`·`status='active'`)를 한 번도 밟지 않는다**. 카드의 핵심 주장("최종 readyNodes는 두 관측의 교집합")에 시험 무게가 없다.

**판별 시험(내가 작성, 실 PG)**: ready 이후 `UPDATE public.storage_contributions SET status='revoked', revoked_at=now()`(멤버십은 유지) → 커널 라우트 `/execution-manifest`는 여전히 `readyNodes [node]`(200), 리졸버 `/models/resolve`는 `readyNodes []`·`materialisable=false`(200). 원본에서 **1 passed**, M1 적용 시 **FAIL**(`assert ['nod_…'] == []`). 이 케이스가 들어가야 M1이 죽는다.

## 3. 발견
- **F1 시험 무게(후속 필수, 비차단)** — `test_model_uri_resolver_http.py`에 위 판별 케이스(contribution `revoked` 뒤 kernel ready ↔ resolver 강등 비교)를 추가. 검토용 시험 본문은 아래 §5. 제품 코드 변경 불필요.

## 4. 관찰 (finding 아님)
- **오류 매핑 합성**: `_check_observation_shape`의 `ValueError`(커널 관측 형태 불일치 = 서버측 불변식 위반)가 `parse_uri`의 `ValueError`와 같은 422 `VAL-0002 "Invalid immutable model URI"`로 나간다. 커널 투영이 깨진 경우는 409 `MODEL-0001`(이미 `resolved.locations is None`에 쓰는 코드) 쪽이 정직하다. 현재 도달 경로는 커널 view 자체가 계약 검증을 거치므로 실질 노출은 없다.
- **replay guard 이중화**: M2에서 403이 아니라 reader-scope 강등으로 죽은 것은 커널 `ModelExecutionManifestObservation.get`이 매 호출 `_grant`+`permission`을 다시 하기 때문 — 리졸버 층의 재검증은 방어 심층(중복)이며 폐기 후 403은 두 층 모두에서 성립한다. 문제 없음, 기록만.
- `ApprovalStore._grant` 비공개 메서드 호출은 `model_view.py`와 같은 기존 패턴(잠금 순서 동일). 별도 카드로 공개 helper화 가능.

## 5. 판별 시험 본문(Codex 반영용, `stale` GET 직후·멤버 삭제 전에 삽입)
```python
with psycopg.connect(a.e.owner) as conn:
    conn.execute("UPDATE public.data_replicas SET state='ready' WHERE location_id=%s", (location[0],))
    conn.execute("UPDATE public.storage_contributions SET status='revoked',revoked_at=now() "
                 "WHERE contribution_id=%s", (a.contribution,))
kernel_after_revoke = client.get(
    f"/v1/projects/{a.e.project}/models/{a.body['modelId']}/versions/{a.body['version']}/execution-manifest",
    headers=_auth())
business_after_revoke = client.get(url, params={"uri": model_uri}, headers=_auth())
# …assert 블록에:
assert kernel_after_revoke.status_code == 200
assert kernel_after_revoke.json()["shardLocations"][0]["readyNodes"] == [a.e.node]
assert business_after_revoke.status_code == 200
validate_contract("ModelExecutionManifestObservation", business_after_revoke.json())
assert business_after_revoke.json()["shardLocations"][0]["readyNodes"] == []
assert business_after_revoke.json()["materialisable"] is False
```

## 6. 부수 조치
- `.work/dev/orch/codex-worker-status.md`에 `CLAUDE-REVIEW:` 줄 기입. 코드 변경 없음(docs-only PR).
