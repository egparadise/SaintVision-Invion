---
doc_id: "HIST-VF-MODEL-REMOTE-REVIEW-001"
title: "model_remote.py 독립 검토 (Claude, Codex 산출물)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-18T20:10:00+09:00"
branch: "agent/claude/vf-cl-cx01"
task: "VF-CX (model registry binding)"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "model-remote", "security", "codex-authored"]
---

# model_remote.py 독립 검토 (Claude, Codex 산출물)

CLAUDE.md 핵심 역할(고난도 보안 산출물의 독립 검토)에 따라 Codex 작성 `services/control-plane/src/inv/model_remote.py`(origin/integration/all-agents-unified, codex 브랜치 `5e4d6ae`와 동일 blob)를 독립 검토했다. **판정: sound — 실제 결함 없음.** 아래는 실제 수행한 검증만 기록한다.

## 대상과 계약

`ConfiguredRemoteModelReader.read(manifest, locations, channels, *, tenant_id, recovery_epoch)` — pinned Node로 ≤32 KiB 비암호 모델의 ≤8 replica 바이트를 읽어 불변 receipt(`RemoteModelBytes`)를 반환. 의존: `model_manifest.manifest_copy/canonical/LocationSnapshot/rejected`, `node_channels.ChannelProof/endpoint_parts`, `node_chunk.verified_chunk`, `node_transport.NodeTLSClient`.

## 검증한 것 (실측)

- **500 경로 없음(내 최초 우려 반증)**: `body["shards"][shardIndex]`(IndexError)·`chunks[i]`(KeyError) 가능성을 의심했으나, reader 최상단의 `manifest_copy`가 `{r["shardIndex"]} == set(range(len(shards)))`(전 shard 커버리지)와 `shardIndex < len(shards)`를 강제하므로 둘 다 발생 불가. `by_location[locationId]`·`by_node[node_id]`도 preflight의 집합 동등성과 replica 루프의 `location.node_id == replica.nodeId` 검증으로 항상 존재. 모든 실패 경로가 `rejected()`(DomainError) 또는 `verified_chunk`의 DomainError로 수렴 — 비-DomainError 누출 없음.
- **바이트 무결성 3중 결속**: preflight가 `location.sha256/byte_size == shard.sha256/byteLength` 결속 → `verified_chunk`가 request 전 필드 echo·정확 길이·`sha256(chunk)==chunkSha256`·canonical base64 검증 → reader가 다시 `sha256(chunk)==location.sha256`(신뢰 manifest) → 마지막에 `sha256(join(shards))==contentHash`. self-consistent forgery(data/chunkSha256 동시 위조)가 `verified_chunk`는 통과해도 `location.sha256` 대조에서 거부됨을 시험이 실증.
- **반재생·범위**: 요청마다 `secrets.token_hex(32)`, `verified_chunk`가 nonce·offset·sizeBytes echo를 강제(불일치 403). offset 0 단일 chunk, `min(256KiB, size)` 길이 정확 일치. `byte_size < 1` 거부로 0바이트 읽기 차단(offset>=size 이중 가드).
- **preflight가 네트워크 이전**: 잘못된 channel(tenant/epoch/node/version=0/version=True/http/URL 내 자격증명/잘못된 cert hash)·늦은 location 불일치가 **첫 shard 요청 전에** 거부됨을 시험이 `assert not calls`로 실증. `type(version) is not int`가 `True`(bool)를 거부.
- **모든 replica 검사(조기 종료 없음)**: 같은 shard의 두 번째 replica가 나쁜 바이트를 줘도 검사되어 거부됨을 시험이 실증. `setdefault`는 중복 shard의 첫 chunk만 보존하나, 모든 replica는 읽고 검증하므로 각 사본의 정직성이 확인됨(sha256 결속으로 어느 사본을 보존하든 동일).
- **인가와 분리**: receipt는 frozen(`FrozenInstanceError`)이고 `executionAuthorized` 같은 플래그 없음(시험 확인). relative_path는 remote 경로에서 미사용(content-addressed sha256 읽기) — 경로 traversal 표면 없음.
- **배선 없음**: integration 전체에서 `model_remote`/`ConfiguredRemoteModelReader`는 자기 시험만 참조. docstring의 "deliberately not wired into ModelRuntimeStore"가 사실 — 실행/인가 경로 조기 결합 없음.

## 설계 의존(결함 아님, 명시)

- reader의 pin/redirect/retry 금지는 `NodeTLSClient`가 전송 계층에서 강제(TLS1.3+, `VERIFY_X509_STRICT`, 명시 CA, `OneConnection` 재연결 금지, ≤40s, "no proxy, redirect or retry"). 루프백 mTLS 시험이 pin 불일치=0요청·redirect(302)=DomainError로 실증. reader는 frozen `ChannelProof`를 그대로 넘기고 단일 호출만 하므로 이 결속을 유지.
- **TOCTOU는 계약상 호출자 책임**: DB 잠금 없음, 네트워크 I/O는 트랜잭션 밖. reader는 사용한 channels/locations를 receipt에 담아 반환하므로, 신뢰 호출자가 commit 트랜잭션 안에서 재검증할 수 있다. docstring이 이를 명시하며 reader는 인가를 부여하지 않는다 — 올바른 경계.

## 방법과 한계

- origin/integration/all-agents-unified의 소스·시험·의존 4모듈(`model_manifest`, `node_chunk`, `node_channels`, `node_transport`)을 정독하고 계약을 상호 대조. 엣지(빈 shard, 0바이트 shard, 중복/누락 replica, version=bool, URL 자격증명, self-consistent forgery)를 코드 경로로 추적.
- pytest 스위트는 **본 worktree pytest 미설치**로 이 환경에서 미실행 — 시험이 주장하는 동작은 코드 경로로 검증했고, 실행 확인은 pytest 가능 환경(CI/Codex) 몫으로 남긴다. 정직하게 기록한다.

## 결론·인계

`model_remote.py`는 계층 방어(manifest 전수 검증 → snapshot 결속 → chunk 검증 → manifest/whole-hash 대조 → frozen 무권한 receipt)가 견고하고 500 누출·바이트 우회·조기 배선이 없다. **finding 없음.** Codex에 sound 판정을 인계한다. pytest 실행 확인만 남는다.
