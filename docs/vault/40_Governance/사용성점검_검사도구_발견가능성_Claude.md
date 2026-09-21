---
doc_id: "GOV-CHECK-USABILITY-AUDIT-001"
title: "사용성 점검 — 검사 도구 발견가능성·실패 대응·규칙 내구성; 빠진 링크 채움 + 트레이스 시험"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["governance", "usability", "onboarding", "discoverability"]
---

# 사용성 점검 — 오늘 만든 것이 내일 손에 잡히는가

새 것이 많다(검사 5·규칙 6·축 3·ratchet). 내일 다른 사람 손에서 쓰이는지 셋을 점검하고 빠진 것을 채웠다.

## ① 발견가능성 — 새 사람이 검사들을 어떻게 아는가
- **문제**: CLAUDE.md는 도구를 하나도 안 적음. AGENTS.md `## 검증`은 **옛 3개만**(check_docs·ontology·sync). 신규 5개는 날짜 박힌 History 문서에만 흩어져 있어 **진입 경로에서 안 보임** = 없는 것과 같음.
- **채움**: 거버넌스 카탈로그 [[검증검사도구_목록]] 신설(옛3+신규5, 각 무엇을·등급·실행법·실패 시 대응). **AGENTS.md `## 검증`에 링크 한 줄** 추가 → 진입 경로가 카탈로그에 닿는다.

## ② 실패 시 대응 — 출력이 어떻게 고치는지 말하는가
전수 확인. 대부분 대응을 말함; **한 건(freshness) 약함 — 그 파일을 Codex가 능동 편집 중이라 수정은 권고로 넘김.**
| 검사 | 실패 출력 대응성 |
|---|---|
| check_docs / check_ontology | 어느 문서·필드·링크·query인지 지목 — 대응 명확 |
| check_contract_bindings | "fixture X 무-시험"→그 fixture 참조 시험; "응답 X 무-앵커시험: X 명명 + inv.Y import한 시험 없음"→그런 시험 추가. 명확 |
| check_frontend_integrity | 위반 파일·지문 목록(Gemini) — 명확 |
| test_serving_anchors | pytest 단언 + 시험명/docstring이 어느 앵커인지 — 명확 |
| check_doc_single_source --ratchet | "통합 or baseline에 명명 줄 추가 / stale 삭제" — 명확(앞서 수정됨) |
| **check_response_freshness** | MISSING 메시지가 "화면이 진실시각 못 봄"(영향만) — **약함**. 내가 손봤으나 Codex가 같은 파일을 `f1d95466`(durable run time 노출)로 능동 편집 중이라 **클로버 방지로 내 수정 철회**; 방법-명시 개선을 **Codex에 권고**(그 파일 소관). |

## ③ 규칙 내구성 — 6규칙이 참조 가능한가
- **문제**: 6규칙이 이어가기(**날짜 박힌** 문서) §2에만. 내일이면 어제 문서 → 묻힌다.
- **채움**: 정본 [[검증규칙과_세축_canon]] 거버넌스 신설(6규칙+3축+6층+축별도구). 이어가기 §2는 그것을 **가리키는 요약**으로(규칙5 자기적용). AGENTS.md에도 정본 링크.

## 직접 트레이스 시험 (새 컨텍스트 흉내)
CLAUDE.md → AGENTS.md → 카탈로그 → 검사 실행, 4홉 전부 성립 확인:
1. CLAUDE.md가 AGENTS.md를 읽으라 함 ✓
2. AGENTS.md `## 검증`이 [[검증검사도구_목록]] 링크 ✓
3. 카탈로그가 `check_response_freshness`를 명령·대응과 함께 목록 ✓
4. 그 명령 실행 → 동작(현재 5/9 present, 4 pending은 Codex 노출 진행 중) ✓
→ 이전엔 이 경로가 신규 검사에 대해 **끊겨 있었다**(AGENTS엔 옛 3개뿐). 이제 이어진다.

## 남은 한계
- 발견가능성은 **AGENTS.md 링크 유지**에 의존 — 카탈로그가 새 검사를 계속 담으려면 검사 신설 시 카탈로그 갱신을 해야 한다(또 사람 몫; 검사-신설 습관에 묶을 것). 검사 카탈로그 자체의 최신성은 자동 검증 안 됨(향후 후보: tools/의 check_*가 카탈로그에 다 있는지 대조하는 메타 검사).

관련: [[검증검사도구_목록]] · [[검증규칙과_세축_canon]] · [[검사_게이트승격_기준과_5검사_분류_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
