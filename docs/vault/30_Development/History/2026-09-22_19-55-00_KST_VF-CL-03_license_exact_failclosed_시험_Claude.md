---
doc_id: "CLAUDE-VF-CL-03-LICENSE-EXACT-FAILCLOSED-001"
title: "카드 9 — VF-CL-03 licensePolicy/classification exact-비교 fail-closed 시험 착지 (커널 정책 allowlist + Claude 소유 import adapter, 37 passed, 계약 무변경) — 매치는 법적 허가·실행 승인이 아니다"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T19:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c75201af"
impl_sha: "(착지 커밋 — Claude 작업 현황 항목 참조)"
tags: ["vf-cl-03", "license", "classification", "fail-closed", "import-adapter", "claude"]
---

# 카드 9 — VF-CL-03 exact-비교 fail-closed 시험 (2026-09-22, 19:55 KST)

**Codex 판정(코디네이터 전달)**: immutable manifest 선언(`licensePolicy`·`classification`)과 import 제안을 **exact 비교**, mismatch는 **fail-closed**, 매치는 **법적 허가·실행 승인을 뜻하지 않는다.** 카드 8 대기 중 준비한 골격(현 코드 19 passed)을 정식 경로로 옮기고 판정의 두 번째 절반(import 제안 ↔ 선언)을 Claude 소유 adapter로 채웠다. 계약 파일·생성 타입·커널 코드 무변경.

## 1. 두 층 (둘 다 DB 불필요, 단일 파일)

| 층 | 소유 | 비교 대상 | 코드 |
|---|---|---|---|
| 1 커널 정책 allowlist | Codex(시험만 Claude) | `(body.licensePolicy, body.classification) ∈ RegistryBindingPolicy.allowed`(커널 binding이 그대로 쓰는 술어) + `configured_registry_policy`(유일한 builder) | 기존 `inv/model_registry_binding.py`·`model_registry_config.py`, 변경 없음 |
| 2 import adapter | **Claude** | import 제안 dict ↔ manifest 선언: `compare_declaration(manifest, proposal) -> [reason]`, `require_exact_declaration(...)` → `InvError(VAL-MODEL-IMPORT-DECLARATION, 409, extra.mismatches=[…])` | 신규 `src/saintvision/adapters/model_import.py` |

adapter 규칙(각각 이유 문자열로 명명, 값은 절대 echo하지 않음): `missing:<field>`(제안에 없음) · `differs:<field>`(문자열 `==` 실패 — 대소문자·공백·prefix·비문자열 전부) · `extra:<field>`(선언에 없는 필드 — 제안이 선언보다 넓을 수 없음) · `undeclared:<field>`(**선언 자체가 불완전하면 매치 불가 = 거부**, 통과 아님). 순수 함수, 입력 불변.

## 2. 시험 `tests/core/test_registry_policy_exact_match.py` — **37 passed**(1.3s, DB 없음)

- 층 1(19): exact pair 허용 2 · 근접값 거부 10(대소문자·앞뒤 공백·classification 대소문자·prefix 확장·허용 license+타 classification·두 허용 쌍의 교차·순서 바꿈·빈 값) · 정책 빈집합/3-튜플/길이 초과/빈 version 거부 · 설정이 선언한 쌍만 만들고 넓히지 않음 · 필드 누락/추가/비문자열/와일드카드-모양 설정 거부-또는-미확장 · 중복 쌍 거부(합치지 않음).
- 층 2(18): 동일 제안 매치(그리고 그 이상 아무 의미 없음) · **모든 편차가 이름 붙어 거부됨**(누락 3형·대소문자·공백·완화 시도 public·강화 시도 restricted·prefix·비문자열·추가 필드·공백 붙은 유사 키) — 각 케이스에서 `code`·`status 409`·`extra.mismatches` 정확 일치 + 메시지에 제안 값 미노출 확인 · 선언 불완전 3형(`undeclared`) 거부 · 순수성(입력 미변조).
- docstring에 **"매치 = 값이 같다는 것뿐, 법적 허가·실행 승인 아님(운영자·커널 배포 admission이 결정)"** 명시.

## 3. 하지 않은 것
- import adapter를 실제 import 경로(MLflow/lineage import 호출자)에 배선하는 것 — VF-CL-03 import adapter 본체는 계약 결속 방식(Codex (a)/(b)/(c), 카드 8 §3) 회신 후. 이 카드는 비교 규칙과 그 시험만 고정한다.
- 실 PG 불필요(순수 함수)라 DSN 미사용. 이웃 `tests/core/test_model_registry_config.py`는 무변경.

## 다음 첫 행동 / 담당
- Codex: (a)/(b)/(c) 회신 → Claude가 manifest reader + import 경로 배선 카드.
- Claude: S02-DB/S03-DB finding 보완(도착 시).
