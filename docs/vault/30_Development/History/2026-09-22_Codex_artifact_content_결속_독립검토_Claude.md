---
doc_id: "CLAUDE-INDEP-REVIEW-ARTIFACT-CONTENT-001"
title: "독립 검토 — Codex artifact-content 결속(65aec0c): 원본 바이트라 envelope 계약, 무게 되살림, 화면이 그 경로를 씀"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
reviewed_at_tip: "83070a92"
code_commit: "65aec0c"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["independent-review", "artifact-content", "raw-bytes", "envelope-contract", "revival"]
---

# 독립 검토 — artifact-content 결속

Codex가 원본 아티팩트 바이트 응답을 결속(`65aec0c`, 기록 `83070a9`). 고정 tip **`83070a92`**. 성격이 다른 케이스 — 응답이 JSON이 아니라 **원본 바이트**라 response_model이 아닌 다른 방식.

## 무엇으로 걸려 있나 + 적절한가 — envelope validate_contract, 적절함
- 응답은 `application/octet-stream`(원본 바이트) → JSON 스키마로 바디를 못 검증. 그래서 **envelope(HTTP 헤더+메타)를 계약으로 건다.**
- `artifact_content_response(content: bytes, artifact: dict)`(app.py):
  1. **바이트를 메타와 대조**: `len(content)!=byteSize OR sha256(content)!=checksumSha256` → `DomainError VERIFY-0023`. 서빙 전 바이트가 커밋된 digest·크기와 일치해야 함.
  2. envelope 구성 `{statusCode, contentType, contentDisposition, artifact{path,checksumSha256,byteSize,verified,evidenceId}, contentTypeOptions:"nosniff"}`.
  3. **`validate_contract("ArtifactContentResponse", envelope)`** — envelope 형태를 계약으로 강제.
  4. `Response(content, headers=…validated envelope에서 파생)`: Content-Disposition·**X-Content-SHA256**·Content-Length·**X-Content-Type-Options:nosniff**.
- **판정**: 원본 바이트에 대한 올바른 방식. response_model보다 **강하다** — (a) 서빙된 체크섬 헤더가 바이트에 대해 **참임을 보장**(바이트-검증), (b) 보안 헤더(nosniff·attachment) 강제, (c) 메타 형태 고정. JSON response_model이면 바디-바이트 무결성은 못 잡았을 것.

## 무게 되살림 (내 손, PG-free)
`inv.app.artifact_content_response` + `inv.contracts.validate_contract`를 직접 호출(양쪽 src path):
- **VALID**: 13바이트 + 맞는 메타 → status 200, **`X-Content-SHA256 == sha256(bytes)`**, Content-Length 13, nosniff. 헤더가 검증된 envelope에서 파생됨 확인.
- **바이트 무결성 무게**: 체크섬 틀림 → **VERIFY-0023**; byteSize 틀림 → **VERIFY-0023**. 메타와 안 맞는 바이트는 서빙 거부 → 체크섬 헤더가 거짓말 못 함.
- **envelope 계약 무게**: artifact 누락 / 여분 필드 / statusCode 타입 오류 → 전부 `validate_contract` **거부**.
- → 결속이 무게를 진다(바이트-검증 + envelope-계약 양쪽). 반환이 스키마와 일치(VALID 검증·fixture 통과).
- **못 돌린 것**: `result_view.download`(스토리지에서 실 바이트 읽기)는 PG/스토리지 필요 → Codex integration 결과 수용(test_result_observation +12). 순수 envelope+바이트-검증 로직은 직접 확증.

## 화면이 이 계약/경로를 쓰는가 (Gemini 0f491b6) — 경로는 씀, 헤더는 미활용
- **경로 ✓**: `DeveloperStudio.tsx:611`이 `fetch('/v1/projects/{p}/runs/{r}/artifacts/content?path=…')` — **결속된 그 커널 경로.** 어댑터 `runArtifactObservation.ts:42`도 같은 URL 구성. **다른 경로를 쓰지 않는다** → 묶인 의미 있음(사용자 핵심 우려 해소).
- **그러나 계약 헤더 미활용**: 화면은 status + `blob()`만 쓰고 **`X-Content-SHA256`(수신 바이트 클라이언트 무결성 검증)·서버 `Content-Disposition`(파일명)을 무시**(자체 fileName 사용). 결속의 부가가치(클라 체크섬 검증)를 안 씀.
- **결함 아님**: 서버측 바이트-검증(VERIFY-0023)이 무결성을 이미 보장하고 nosniff도 서버가 세팅 → 화면이 무시해도 보호는 유지. 다만 **화면 권고(Gemini)**: 수신 바이트를 `X-Content-SHA256`과 대조(전송 손상 포착)하고 서버 Content-Disposition을 쓰면 계약이 주는 것을 온전히 활용. 선택.

## 판정
- **결속 sound·무게 있음**: 원본 바이트엔 envelope-계약이 옳고, 바이트-검증 + validate_contract 양쪽이 되살림으로 무게 확증. response_model보다 강함.
- **화면 경로 일치**: 결속된 커널 경로를 그대로 씀(우회 없음). 헤더 미활용은 화면 개선 여지(권고), 결속 결함 아님.

## 직접 확인 vs 보고 수용
- **직접(되살림·소스)**: artifact_content_response 바이트-검증(VERIFY-0023)·envelope validate_contract 거부·VALID 헤더 파생; 화면 fetch 경로·헤더 미활용 (전부 tip `83070a92`).
- **보고 수용(PG/스토리지 부재)**: `result_view.download` 실 바이트 읽기·DB-backed 다운로드 = Codex integration 결과.

관련: [[2026-09-22_미구현목록_백엔드대조_남은구현범위_Claude]] · [[2026-09-22_Codex_appliedToKernel_신선도시각_독립검토_Claude]] · [[2026-09-21_서빙앵커_감사_3갈래_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
