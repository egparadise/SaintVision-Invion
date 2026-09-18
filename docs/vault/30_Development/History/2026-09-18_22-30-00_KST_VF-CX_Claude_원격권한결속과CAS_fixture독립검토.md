---
doc_id: "HIST-VF-MODEL-AUTHORITY-REVIEW-001"
title: "원격 모델 권한 결속(8c347b7)과 channel CAS fixture(e89a415) 독립 검토 (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-18T22:30:00+09:00"
branch: "agent/claude/vf-cl-cx01"
task: "VF-CX (model registry binding)"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "model-remote", "cas", "concurrency", "security", "codex-authored"]
---

# 원격 모델 권한 결속(8c347b7)과 channel CAS fixture(e89a415) 독립 검토 (Claude)

CLAUDE.md 핵심 역할로 Codex의 `8c347b7`(원격 모델 channel 권한을 frozen input·admission에 결속)와 `e89a415`(실 PostgreSQL 권한 검증 + channel CAS fixture 수정)를 독립 검토했다. **판정: sound — 실제 결함 없음.** e89a415의 CAS fixture 수정은 제품 결함이 아니라 시험 준비 결함의 교정이며, 그 전까지 무엇이 미검증이었는지를 아래에 짚는다. 실제 수행한 검증만 기록한다.

## 변경 표면과 성격

- `model_remote.py`: **docstring만** 변경("not wired into ModelRuntimeStore" → "ModelRuntimeStore가 capture/recheck orchestration 공급; reader는 여전히 독립적으로 실행 권한 발급 불가"). 로직 무변경 — 내 앞선 sound 검토(HIST-VF-MODEL-REMOTE-REVIEW-001) 유효, 배선 맥락만 갱신.
- `model_runtime.py`(+59/-14): remote reader를 verifier로 허용, channel 캡처·결속·재검증 추가.
- `model_source.py`(신규 74): 원격 channel provenance를 frozen 바이트에 결속(호출자 권한 아님).
- `e89a415`: **test/docs/evidence만** 변경 — `test_model_remote_runtime.py` 6줄(CAS fixture) + 증거 JSON + ERR 문서. **src/migration 무변경 확인**(제품/제약 무완화).

## 결속 구조 (sound)

- **캡처(잠금 하)**: `model_source.capture_channels`가 `SELECT * FROM inv.node_channels ... FOR SHARE`로 노드별 channel을 잠그고 tenant/epoch·`assert_channel`(enabled/만료 등 admission) 검증 후 frozen `ChannelProof`(version 포함) 반환.
- **읽기는 트랜잭션 밖**: `prepare`가 scope 트랜잭션을 닫은 뒤 `remote.read(...)`(네트워크). 반환된 `remote.locations/channels != captured`면 `rejected()` — model_remote가 계약상 호출자에게 미룬 recheck를 여기서 수행. 시험이 "Network read under DB transaction"을 **부정 단언**하고 `scopes==2`(재scope)를 단언.
- **freeze 쓰기 CAS**: 쓰기 트랜잭션에서 `self._scope(...) != captured`면 `rejected()` — 네트워크 읽기 중 channel이 바뀌면(정상 변경은 version 증가) 재캡처가 달라져 커밋 거부. TOCTOU 폐쇄.
- **claim admission CAS**: `approved_model`이 Node 잠금 후 `capture_channels(...) != saved_channels`면 `rejected()`(version-CAS), approval-생성 단계(node_id None)는 `assert_channel`만(문서화된 계층). 
- **provenance 결속·무downgrade**: frozen snapshot에 `SOURCE_FILE`(=`source_content` 해시) 기록, `frozen_sources`가 `files[SOURCE_FILE]==source_content(records)` 검증, 로컬 snapshot이 SOURCE_FILE을 가지거나 원격이 결여하면 `rejected()`(부분 remote 마커가 로컬로 조용히 downgrade 불가). private channel 메타데이터는 해시로만 결속(엔드포인트/경로 원문 미노출).
- **provider-swap replay 차단**: remote verifier면 idempotency ledger payload에 `sourceMode="node-mtls-v1"` 포함 — 같은 key로 로컬 commitment을 원격 검증으로 재생 불가.

`test_model_source.py`(217줄)는 vacuous하지 않다: no-downgrade/rebind, changed-version, foreign-tenant/epoch → DomainError; `scopes==2`; 네트워크-트랜잭션-밖 부정 단언; admission rotated/revoked 재검사. 500 누출 경로 없음(`frozen_sources`가 구조 오류를 `rejected()`로 수렴).

## CAS fixture 버그 — 그 전까지 무엇이 미검증이었나 (사용자 질문)

**제약은 실재·작동**: `inv.channel_monotonic`(migration 0005) 트리거를 실측 확인 —
```
IF TG_OP='DELETE' OR NEW.tenant_id<>OLD.tenant_id OR NEW.node_id<>OLD.node_id
   OR NEW.version<>OLD.version+1 THEN RAISE EXCEPTION ... ERRCODE='23514';
```
즉 node_channels의 모든 UPDATE는 `version=OLD.version+1`(정확히 +1, forward CAS)을 강제하고 DELETE·tenant/node 변경을 금지한다.

**fixture 버그**: 수정 전 `test_model_remote_runtime.py`는 `UPDATE inv.node_channels SET enabled=false`(또는 `certificate_not_after=과거`)를 **version 증가 없이** 주입했다. 실 PG에서 이는 `channel_monotonic`을 위반해 **CheckViolation(23514)**을 일으킨다. 그 예외는 `pytest.raises(DomainError)` 밖(또는 그것이 잡지 않는 종류)에서 터지므로, **제품 보안 단언(무커밋 / claim 거부)에 도달하기 전에 시험이 에러**한다. DSN 부재 시엔 6건 전부 skip(8c347b7 착지가 보류된 이유).

**따라서 미검증이었던 것**: `enabled=false`·`certificate expired` 시나리오의 **end-to-end CAS/admission 거부**. 즉 "정상적으로(version 증가와 함께) 비활성화되거나 인증서가 만료된 channel이 freeze 재scope 및 claim CAS에서 커밋/claim을 막는가"가 실제로 실행된 적이 없었다. 오직 순수 `version=version+1` 케이스만 CAS 경로에 도달했다. 첫 PG 실행 3 passed/3 failed가 이를 드러냈다(순수 version 케이스 통과, 나머지는 fixture setup에서 CheckViolation).

**수정**: 각 UPDATE에 `version=version+1`을 함께 넣어(트리거 요건과 정확히 일치) **정상적이고 실제적인** channel 변경을 주입 → `capture_channels` CAS가 version 차이를 감지해 거부. 이제 disable+bump·expiry+bump 시나리오가 진짜로 검증된다. **제품 코드/제약 무완화**(제약은 오히려 위반을 잡아 정상 작동을 입증). e89a415가 test/docs/evidence만 건드린 것과 정합.

## 방법과 한계

- origin/integration/all-agents-unified의 두 커밋 diff, `model_runtime.py`/`model_source.py` 전문, `test_model_remote_runtime.py`(수정본)·`test_model_source.py`, 그리고 `migrations/0005_node_channels.sql`의 `channel_monotonic` 정의를 정독·상호 대조. e89a415가 src/migration을 건드리지 않음을 `--name-only`로 확인.
- 이 스위트는 `pytest.mark.postgres`이며 실 PG16+무거운 의존이 있어야 하므로 **내 환경에서 실행하지 않았다**(정직 기록). 사용자가 clean worktree에서 e89a415를 실 PG로 75 passed 실측(Codex 작성자 79 passed와 미합산), DSN 부재로 미실행이던 영역이 실제 PostgreSQL에서 통과함을 확인했다. 나는 코드 경로·계약·제약으로 검증했다.

## 결론·인계

원격 권한 결속은 캡처(FOR SHARE)→네트워크(트랜잭션 밖)→freeze 재scope-CAS→claim capture_channels-CAS의 계층과 provenance 해시 결속·무downgrade·provider-swap 차단이 일관되며, 500 누출·바이트 우회·조용한 downgrade가 없다. CAS fixture 수정은 그 전까지 미도달(skip/setup-error)이던 disable/expiry 시나리오의 CAS/admission 거부를 실제로 실행하게 만든 **시험 교정**이지 제품 완화가 아니다. **finding 없음.** Codex에 sound 판정을 인계한다. 실 PG 실행 확인은 사용자/CI가 수행했다.
