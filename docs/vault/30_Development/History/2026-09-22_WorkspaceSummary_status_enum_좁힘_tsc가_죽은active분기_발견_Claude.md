---
doc_id: "CLAUDE-WS-SUMMARY-STATUS-ENUM-001"
title: "WorkspaceSummaryResponse status/allowedNext enum 좁힘 — 검증 완료·착지 보류(프런트 죽은 'active' 분기 노출, Gemini 레인 커플링)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
measured_at_tip: "b3a14db6"
finding_current_at_tip: "3ebbe960"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["contract", "workspace", "enum-tightening", "cross-lane-coupling", "green-vs-reached", "handoff"]
---

# WorkspaceSummaryResponse status/allowedNext 좁힘 — 검증 완료, 착지 보류

## 무엇을 했나 (내 레인: 백엔드 계약)
[[2026-09-22_set_workspace_status_후속확인_잔여와레인_Claude]]가 권고로 남긴 잔여 1건을 착수했다. §0(이어가기)의 "다음 첫 행동"이며, 그 문서가 미착수로 둔 유일한 사유(`vw`에 `json-schema-to-typescript` 부재)를 이 세션에서 해소했다 — 메인 트리 `apps/web/node_modules`를 vw의 `apps/web/node_modules`로 **junction** 걸어 TS 생성·tsc·vitest 툴체인을 vw(clean tip)에서 사용 가능하게 만들었다.

- `src/saintvision/api/schemas.py`: `WorkspaceStatusName = Literal["provisioning","ready","suspended","deleting","deleted"]` 정의를 `WorkspaceSummaryResponse` **위로 이동**(class 정의 시 forward-ref 문제 회피), 그리고 두 필드 좁힘:
  - `status: str` → `status: WorkspaceStatusName`
  - `allowed_next: list[str]` → `allowed_next: list[WorkspaceStatusName]`
- 형제 `WorkspaceStatusResponse`는 이미 `WorkspaceStatusName` 사용 중 → **비대칭 해소**(같은 의미 필드가 한 응답엔 엄격, 다른 응답엔 느슨이던 것).
- 재생성: `tools/export_schemas.py`(스키마 JSON) + `apps/web` `contracts:generate`(TS). 변경 파일 정확히 **5개**:
  - `src/saintvision/api/schemas.py`
  - `contracts/workspace-summary-response.schema.json` (status·allowedNext.items에 enum 추가)
  - `contracts/project-workspaces-response.schema.json` ($defs 임베드 동일)
  - `apps/web/src/contracts/workspace-summary-response.ts` (`Status`/`Allowednext`가 union)
  - `apps/web/src/contracts/project-workspaces-response.ts` (동일)
  - 나머지 스키마·TS는 결정론적 재생성으로 바이트 동일 → git 무변경.

**도메인 안전**: DB CHECK `status IN ('provisioning','ready','suspended','deleting','deleted')`(migration 0002)로 백엔드가 낼 수 있는 값이 정확히 그 5개 → 좁혀도 500 위험 없음.

## 검증 (전부 vw clean 고정-tip `b3a14db6`, working_tree=내 5파일만; node 툴체인=junction)
- `python tools/export_schemas.py --check` → **PASS** (47 schemas)
- `apps/web` `contracts:check` → **PASS** (16 types)
- `pytest tests/core/test_workspace_response_contract.py` → **23 passed**
- `python tools/check_contract_bindings.py`(게이트) → **PASS** (38 fixtures / 12 bound responses)
- `vitest run developer-studio workspace` → **60 passed / 7 files**
- `tsc -b` → **RED 2건** (아래) — 그 외 오류 없음.

인터프리터 주의: vw 자체 `.venv/Scripts/python.exe`는 **실행 불가(깨진 링크)**라 메인 트리 `.venv` python으로 vw 스크립트를 돌렸다(`saintvision`은 메인 venv에 미설치 → 순수 sys.path, export_schemas의 `sys.path.insert(0, ROOT/src)`가 vw/src를 import함을 직접 확인).

## 발견 — 좁힘이 프런트의 도달 불가 분기를 드러냄 ("있다 ≠ 작동한다")
`tsc -b` 유일 RED = `apps/web/src/features/studio/DeveloperStudio.tsx` (tip에서 줄 1091-1092, vw에서 1096-1097):

```
backgroundColor: wsp.status === 'active' ? 'rgba(46,160,67,0.2)' : 'rgba(139,148,158,0.2)',
color:           wsp.status === 'active' ? '#3fb950' : 'var(--color-text-muted)',
```
`wsp`는 계약 타입 `WorkspaceSummaryResponse`. 좁힌 `Status` union에 `'active'`가 **없다**(계약은 provisioning/ready/suspended/deleting/deleted만). TS2367 "no overlap" = 이 초록 하이라이트 분기는 **절대 참이 되지 않는 죽은 코드**. 실제 UX 결함: **ready(정상 가동) 작업공간이 초록이 아니라 회색으로 표시된다.** 느슨한 `string` 타입이 이 결함을 가리고 있었다.

### 상태 어휘 불일치 (체계적, Gemini 판단 필요)
`'active'`는 백엔드 계약에 없고 프런트·레거시 어휘다:
- `apps/web/src/contracts/types.ts` 손수 타입 `WorkspaceItem.status`가 `'active' | 'terminating' | 'reclaimed' | ... | string` — 백엔드 5상태와 다른, 더 풍부한(그러나 계약과 어긋난) 라이프사이클을 상상.
- `apps/web/tests/developer-studio.test.ts:389` detail 문자열 "the workspace status is 'active'"(타입 아님, 무해하나 어휘 반영).
- `tests/fixtures/legacy_control.py`가 `status == "active"`로 판정(레거시 dict, 계약 모델 아님 → 내 변경 무영향).
백엔드 healthy 상태 = **`ready`**. 최소 수정은 `'active'`→`'ready'`이나, 어휘 정합(매핑/표시 규칙)은 화면 소유자 결정.

## 왜 착지 보류인가 (크로스레인 커플링 + 화면 소유권)
- 백엔드/계약 좁힘(내 레인)은 옳고 검증됐으나 **단독 착지 시 integration `tsc`가 RED**가 된다(위 2줄).
- 그 수정은 `DeveloperStudio.tsx` = **Gemini 레인**이며 CLAUDE.md는 "Frontend는 Gemini 책임, 배정되지 않은 화면을 임의로 대체하지 않는다"고 명시 → 내가 화면을 고치지 않는다.
- 메인 트리에서 이 파일은 **현재 Gemini가 dirty로 편집 중**(X-Content-SHA256 다운로드 무결성 작업)이나 그 변경은 이 status-coloring 영역이 아니다(줄 다름, diff 무관) → 내가 이 파일을 만지면 R5 소유 흐려짐/클로버 위험.
- 결론: **미검증/차단을 done으로 바꾸지 않는다**(§6 규율). integration RED를 만들지 않고, 화면도 만지지 않는다.

## 인계 (Gemini, 화면 소유자) + 착지 순서
1. **Gemini**: `DeveloperStudio.tsx`의 `wsp.status === 'active'`(2곳)를 `wsp.status === 'ready'`로 교정(또는 계약 5상태에 맞는 healthy 표시 규칙). 필요 시 `types.ts`의 `WorkspaceItem.status`·`developer-studio.test.ts:389` 어휘도 정합.
2. **그 후** 내 백엔드/계약 5파일 좁힘을 착지 → `tsc` GREEN. 순서 뒤집으면(내 것 먼저) integration RED.
   - 대안: Gemini의 화면 수정과 내 5파일을 **한 묶음(같은 tip)** 으로 함께 착지 — reviewer(Codex)가 병합 시점에 조율.
3. 내 5파일 변경은 patch로 durable 캡처: 세션 scratchpad `workspace-summary-status-enum.patch`(137줄). vw에도 적용된 상태로 보유(재검증 즉시 가능). 재적용: 임의 clean tip 체크아웃 → `git apply` → export_schemas + contracts:generate + tsc.

## 현재 유효성
tip `3ebbe960`(측정 후 이동한 origin/integration)에서도 두 전제 확인: WorkspaceSummaryResponse 여전히 느슨 · DeveloperStudio 여전히 `'active'` 비교 → 발견·patch·인계 **최신**.

관련: [[2026-09-22_set_workspace_status_후속확인_잔여와레인_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]] · [[공유워크트리_개인index_커밋규칙]] · [[검증규칙과_세축_canon]]
