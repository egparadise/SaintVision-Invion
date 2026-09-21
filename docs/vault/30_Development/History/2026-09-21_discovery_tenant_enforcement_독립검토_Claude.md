---
doc_id: "CLAUDE-INDEP-REVIEW-DISCOVERY-TENANT-001"
title: "독립 검토 — discovery X-Inv-Tenant enforcement (fb2ba31): 가드 무게 + 부트스트랩 갭"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
updated: "2026-09-21T20:06:00+09:00"
source_of_truth: "Git"
tags: ["independent-review", "security-posture", "discovery", "bootstrap", "fixed-sha"]
---

# 독립 검토 — discovery 안내 tenant enforcement (fb2ba31)

**성격**: 결함 수정이 아니라 **문서화된 설계 결정을 뒤집는 보안 태세 변경**. 원래는 "미등록 기계가 부를 수 있는 유일·최약 엔드포인트"(principal 없이 후보 row만). fb2ba31이 인증 principal을 요구하고 X-Inv-Tenant≠principal.tenant면 DB 전 403.

## 검토 트리 못 박기
- origin/integration = **`e69f2b8`**. 피검토 커밋 **`fb2ba31`**("fix: bind discovery announcements to authenticated tenant"), **integration에 병합됨**(ancestor 확인). 로컬 워킹트리 HEAD=e69f2b8, pools.py clean.
- 인터프리터 `.venv/Scripts/python.exe`(3.14.6). 백엔드는 e69f2b8 워킹트리에서 실행. **Go(node-agent)는 컴파일러 부재 → 소스 읽기만, 빌드 미검증**.

## 직접 확인 (내 손)
### ① 가드가 무게를 지는가 — 예 (실행 + 되살림)
- `src/saintvision/api/v1/pools.py announce()`: `principal: Principal = Depends(get_principal)` 추가(미인증→401), `if tenant_id != principal.tenant_id: raise InvError(AUTH_TENANT_SCOPE, 403)`를 **`make_session_factory` 전에** 배치. 옛 `request.state.actor_type="node"`/tenantless 경로 제거.
- **시험 직접 실행**: `tests/core/test_discovery_announcement_tenant_boundary.py` **2 passed** — 교차테넌트 403+`AUTH-TENANT-SCOPE`+`writes==[]`(record_announcement·make_session_factory 둘 다 호출 시 AssertionError로 몽키패치 → **DB 작업 전 거부** 증명), 미인증 401+`AUTH-MISSING-CREDENTIAL`.
- **가드 제거 되살림(내 손, 보고 아님)**: pools.py의 4줄 가드를 임시 제거 후 재실행 → 교차테넌트 시험이 `assert 500==403`으로 **실패**(403 사라지고 요청이 DB 경로까지 진행, 테스트 stub의 AssertionError로 500). 즉 **가드가 정확히 403·DB-쓰기 차단을 만든다.** 이후 `git checkout`으로 복원·clean 확인. (401은 get_principal 의존성이라 가드와 독립.)

### ② 부트스트랩 경로 독립 추적 — **보안↑/기능정지 확정** (이번 검토 핵심)
- **토큰 없는 새 기계는 이제 공지 불가**: `inv-discover`(main.go)가 `INV_DISCOVERY_BEARER_TOKEN` 없으면 실행 거부("tenant discovery credential unavailable"), 보내더라도 서버가 principal 요구(401)+tenant 대조(403).
- **그 토큰은 어디서 오나 — 코드·배포 자료에 발급/설정 전무(실측)**:
  - 프로덕션 principal 검증 = `OidcPrincipalVerifier`(oidc.py는 **검증만, 발급 안 함**). ⇒ discovery bearer = **외부 IdP가 발급하는 OIDC principal 토큰**(이 저장소가 mint하지 않음).
  - `identity/tokens.py:56 issue_bootstrap_token`은 존재하나 **node 등록 bootstrap 토큰**으로, 문서가 "bootstrap token·인증서·Node role은 이 공지의 결과가 아니다"라 명시 분리 — discovery bearer 아님.
  - `deploy/`·compose·`*.ps1`·`*.env`에서 `INV_DISCOVERY_BEARER_TOKEN` **설정 0건**. 도구/배포가 주입하지 않는다.
  - Codex 문서 다수가 일치: "secret manager/service environment로 주입", "운영 등록 토큰과 CA 발급 경로는 Claude와 연결 필요(=미정)", "operator token provisioning remains pending".
- **결론**: 순환은 아니다(OIDC principal 토큰은 node 등록 없이 IdP에서 발급 가능). 그러나 **운영자가 대상 tenant의 OIDC 서비스 자격증명을 발급받아 각 새 기계 env에 주입하는 절차가 코드·자동화·배포 어디에도 없다**(문서상 pending). ⇒ **그 절차가 생기기 전엔 새 노드를 붙일 수 없다.** 사용자 우려 그대로: 상태를 명시 안 하면 나중에 "노드가 안 붙음"의 원인을 못 찾는다. **다음 할 일**: 토큰 발급·배포 절차(운영 OIDC 서비스 credential/tenant + 주입 runbook) 신설 — 보안/발급 경계라 Codex+운영자.

### ③ Go 변경 — 소스 읽기만 (빌드 미검증, 컴파일러 부재)
- main.go: env에서 bearer 읽고 빈 값·CR/LF 거부, `"Bearer "+bearer`를 Send에 전달. announce.go: Send에 `authorization` 인자 추가, `Bearer ` 접두·비공백·CR/LF 금지 검증 후 `Authorization`+`X-Inv-Tenant` 헤더 설정. **소스상 방어적·정합**(헤더 주입·빈 토큰 차단). **컴파일·테스트는 실행 못 함 — 소스 검토로만. 빌드 검증 없음.**

## 보고로 수용 (직접 재현 안 함)
- 옛 위험 근거 "타 tenant 후보 주입 + 후보 500 한도 소진 가능"(Codex 문서): 코드상 개연적이나 옛 상태를 독립 재현하진 않음 [추정].
- Codex의 되돌림 대조 주장: **내가 독립으로 되살려 확인**(위 ①)했으므로 수용이 아니라 직접 확인.

## 판정
- **가드: sound, 무게 짐(직접 확증).** 401/403/DB-쓰기 없음 모두 실행+되살림으로 확인.
- **부트스트랩: 기능 정지 갭 확정** — 토큰 발급/주입 절차 부재(코드·배포 실측). 보안↑는 타당하나 이 갭을 **명시적으로 남겨야** 한다(이 문서가 그 기록). 결함이라기보다 **미완의 운영 선행작업**이며, 완료 전 새 노드 온보딩 불가.
- **Go: 소스상 타당, 빌드 미검증(명시).**

관련: [[2026-09-21_계약이_못잡는_가짜값_목록_Claude]](이 변경을 촉발한 최고위험 finding) · [[2026-09-21_Codex계약결속_독립검토_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
