---
doc_id: "PUBLIC-DSN-EXPOSURE-VERIFY-CLAUDE-001"
title: "공개 저장소 평문 DSN 마스킹 — Codex 착지분 독립 검증(통합 tip 기준). 값 미노출·변형 확인"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T23:30:00+09:00"
integration_tip_verified: "8197897"
source_of_truth: "Git"
tags: ["security", "secret-exposure", "dsn", "independent-review", "mutation-testing", "value-safe"]
---

# 공개 평문 DSN 마스킹 — 독립 검증 (통합 tip 8197897)

Codex가 공개 저장소의 평문 PostgreSQL DSN을 마스킹하고 통합에 착지시켰다(merge `5c7ce9d`, 마스킹 `5b6bfca`·`bd4af9c`, 이후 `b569318`/`8197897` 검증 receipt). 브랜치에서는 별표로 가렸으나 **통합에서는 평문이라 공개=노출** 상태였다. 내가 통합 기준으로 독립 검증했다. **원칙: 값을 어디에도 옮기지 않았다 — SHA-256 비교와 형상 signature만 사용, 성격·개수·경로만 기록.** 그리고 **브랜치가 아니라 현재 통합 tip에서** 확인했다(내가 오늘 정정당한 "diverged 시점을 현재로 읽는" 함정 회피 — 검증 중 통합이 `b569318`→`8197897`로 또 이동해 매번 최신 tip으로 재실행했다).

## 노출 규모 (정합)
착지 전(`0b2d7d0`) 실측: **`proposal-3.txt` 14파일이 고유 비밀 1종을 28회** 보유 — 사용자 "14"·Codex "14개/28회"와 정확히 일치. (내 앞선 잠정 "16파일/32회"는 느슨한 `://user:pass@` 정규식의 과대계수였고, postgres-DSN + 노출값 해시로 좁히면 14/28/1이 정확하다 — 내 수치를 정정.)

## ①+② 평문 0 · 마스킹 원복 안 됨 — PASS (해시, 값 미노출)
가장 강한 형태로 통합: 노출 비밀의 SHA-256을 착지 전 `proposal-3.txt`에서 얻어, **통합 tip 추적 파일 전체**에서 그 해시를 가진 DSN(마스킹이든 평문이든)을 스캔.
- 결과: **0건.** 유출 자격은 통합 어디에도 없다. `proposal-3.txt` 14개 전부 masked 버킷으로 이동, 평문 버킷에서 소멸.
- 이 스캔이 ②도 겸한다: 병합에서 통합 평문 측이 이겼다면 그 해시가 재등장했을 텐데 0 → **마스킹이 병합에서 뒤집히지 않았다.** `proposal-3.txt`만이 아니라 전 파일을 훑었다.

## ③ guard 존재·실행·실제 포착 — PASS (변형)
- **존재**: 통합 `tools/check_docs.py`에 `PASSWORD_BEARING_POSTGRES_DSN` 정규식(L8)과 거부 오류(L50). 스캔 대상 확장자에 **`.txt` 포함**(노출 파일 형식), 마스킹 토큰 `***`(3+)/`<redacted>`/`[redacted]`/`redacted`만 제외, scope는 `docs/vault`.
- **실행**: `.github/workflows/docs.yml:24 python tools/check_docs.py`가 통합에서 호출.
- **실제 포착(변형)**: 변형 전 DSN 오류 0 → vault에 평문 DSN `.txt`를 심으니 `ValueError: Password-bearing PostgreSQL DSN must be redacted (1 occurrence(s)): <path>`로 **exit 1**(오류에 경로만, 값 미노출) → 원복 후 0. **"통과하는 검사"가 아니라 실제로 잡는 검사**임을 확증.
- **부수 발견(DSN 무관, 인계)**: 현재 `check_docs.py`는 통합에서 **broken wiki link 때문에 exit 1**이다 — 두 index 문서(`전체 개발 진행 현황.md`, `Codex 작업 현황.md`)의 **line 13이 mojibake로 깨진 중복 항목**이라 링크 대상 `2026-09-21_????DSN_???_Codex`가 부재(실 문서 `2026-09-21_공개제안DSN_마스킹_Codex.md`는 line 15에서 정상 링크). **DSN 마스킹 자체는 clean**(DSN 오류 0)이나, 문서 게이트가 이 깨진 링크로 red다. Codex/Gemini가 손상 항목을 고쳐야 게이트가 green이 된다.

## ④ 남은 24(통합 23) DSN 독립 분류 — Codex 판정 확인 (값 미노출)
착지 후 통합 잔여 평문 DSN을 독립 분류(해시 비교 + 형상 signature):
- **노출값과 일치: 0.** 24곳(통합 스캔상 23) 전부 유출 비밀과 다른 해시.
- **성격**: `.env.example`(user=invowner, **host=localhost**, 예시 dev — 노출값과 다름), CI(`backend.yml`/`core.yml`, 전부 localhost 임시 DB, `offline:offline` 류), tests(합성 fake host `*.invalid`/`private-host`/`db.internal`/`h`/`database`, 파싱·거부 시험 입력), `check_kernel_docker.py`(host=`{database}` = **format 템플릿**, 실 DSN 아님), `test_check_docs_secret_guard.py`(guard 시험용 의도적 평문 fixture, localhost). **어느 것도 실 외부 비밀 아님.** → Codex 분류(.env.example/임시 CI DB/시험 입력/로컬 기본값, 노출값과 불일치) **독립 확인**. 특히 `.env.example`은 이름과 달리 실 값을 담지 않고 localhost 예시다.

## 계약 사슬 — 통합 기준 재확인 (브랜치 `675a6e1`는 stale이므로 재검증) — 끊긴 고리 없음
계약 브랜치가 함께 착지했다. 통합 tip에서 소스+변형으로 재확인:
- **소스**: 프런트 fixture가 공유 JSON을 `readFileSync`(복사 아님), 공유 fixture/schema/생성 TS타입/생성 스크립트 존재, CI 게이트 2종(`backend.yml:75 export_schemas --check`, `frontend.yml:43 contracts:check`).
- **변형**: 공유 fixture 숫자 필드→문자열 → 계약 시험 **FAIL**(Ajv, 프런트가 통합 fixture에 묶임); schema 속성 type number→string → `contracts:check` **exit 1**("generated type is stale"). 둘 다 원복, baseline PASS/exit 0 복귀.
- 판정: **통합에서도 사슬 온전, 끊긴 고리 없음.** 브랜치 판정을 현재 tip에서 재확증(stale 함정 회피).

## 종합·인계
공개 평문 DSN 노출은 통합에서 **해소**됐다(유출값 전 파일 0, 마스킹 미원복). guard는 **실재·실행·실포착**(변형 확증). 잔여 24는 전부 노출값과 다른 benign 형태. 계약 사슬은 통합에서 온전.
- **열린 항목(DSN 무관)**: 두 index 문서 line 13 mojibake 손상 → broken wiki link 4건으로 `check_docs.py`/docs 게이트 red. **Codex/Gemini** 수정 대상(vault는 내 읽기전용).
- **범위**: 값 미기록, 시험/문서 미수정, 모든 변형 원복, 검증 worktree 제거. reviewer: Codex.
- **후속(내 소관 아님, 기록)**: 과거 public Git 이력의 원문 노출은 마스킹으로 사라지지 않는다 — **DB 소유자의 자격증명 유효성 판단·회전**이 별도 필요(Codex 노트와 동일 결론).
