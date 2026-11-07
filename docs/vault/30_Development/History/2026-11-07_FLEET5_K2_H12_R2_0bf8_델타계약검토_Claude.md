---
doc_id: "HISTORY-FLEET5-20261107-K2-H12-R2-0BF8-DELTA-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 K2 H1/H2 권한 계약 R2 0bf852 좁은 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T09:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "0bf852a66b2eb01f95da65ebbad0360a04ea6fed"
task_ids: ["FLEET5-K2-H1-H2-AUTHORITY-DESIGN-R2-20261107"]
tags: ["fleet5", "independent-review", "k2", "h1", "h2", "authority", "r2", "claude"]
---

# K2 H1/H2 권한 계약 R2 0bf852 좁은 delta 독립 검토

Orca `task_638219a79555` / dispatch `ctx_2e3e33bdc879`에서 한 실제 독립 검토다. 검토자는 Claude 하나이고, helper와 두 번째 검토자는 쓰지 않았다. 대상은 R1 검토 [8141a49b](2026-11-07_FLEET5_K2_H12_382f_계약독립검토_Claude.md)의 M1/L1/L2를 고친 계약 DESIGN delta뿐이다. 실제 binding, crypto, 코드, 등록, runtime 수용은 이 검토에 들어 있지 않다.

- 시작 전 확인: 직전 B mode 검토 `task_696b2783bc0b/ctx_6b18bf1ef5b4`가 succeeded/settled/exited/released였다. 이 task는 그 의존성 아래 ready였다(Root `.work/b-mode-reviewer-before-h12-r2-start.json`, `h12-r2-delta-review-ready-before-start.json`).
- owner: Codex `task_a95ef3d8ccce/ctx_ed23b4a777d0`, pending `msg_16c9f2a0ec9b`, Root 수정 허가 `msg_e41b206771c3`.
- 관리 worktree에서 새 branch `agent/claude/fleet5-k2-h12-r2-0bf8-review-20261107`을 정확히 `0bf852a6`에서 만들었다.

## 대상과 사전 확인

- 대상 `0bf852a6`, 직접 부모 `382fe3d8`. 원격 author ref가 정확히 `0bf852a6`이다.
- 382fe3 이후 추가 10개(Evidence 9, History 1)이고, 모두 100644다. 수정·삭제는 0이다. f2c1에서 docs 밖 변경도 0이다.
- 네 pin을 다시 계산했고 모두 일치했다: contract `b02ee1c7…`, matrix `6a8c67a3…`, cases `35f63a91…`, response `b53d6eca…`.
- R1 next-code `f8b3f6d7…`는 382fe3과 0bf852에서 같다.
- 공개 입력 pin 14개를 f2c1 blob에서 다시 계산했고 14/14 일치했다. 8141 원본 11개 파일의 OID/크기/SHA256도 11/11 일치했다. manifest 9개 항목도 대상 blob과 같았다.
- 먼저 읽은 것: 8141 History·review.json·commands.json과 권위 있는 static attempt2 결과(OID `f23490e9…`), 그다음 Root `.work/h12-r2-design-fix-root-cut.txt`.
- Root 보드: fleet-five-orchestration HEAD `c23ae5d1`, Index 1.0.493, Claude board 1.2.130.
- author gate는 다시 돌리지 않았다. B author 작업 코드와 추적되지 않은 post-CI receipt는 보지 않았다.

## 판정: CONTRACT_DESIGN_ACCEPT_M1_L1_L2_CLOSED_KEEP_ACTUAL_HOLD

세 건 모두 CLOSED다. 개수·필드 이름이 맞는다는 선언 검사와 의미 닫힘은 따로 봤다. 의미 닫힘이란 issuer, 원천, subject, version, 현재성 검증, readback이 각각 정의되어 있고, 독립 값에 묶여 있으며, 자기 검증이 아니라는 뜻이다. 또 각 변형이 앞 단계를 모두 통과한 뒤 자기 원인 층에서 거부된다는 뜻이다. 상세는 [review.json](../Evidence/fleet5-k2-h12-r2-0bf8-review-20261107-claude/review.json)에 있다.

**H12R-M1 (MEDIUM) — CLOSED.**

- issuer: `RD_CAPTURE_DELIVERY`가 별도 origin이다. issuer는 G00_BINDING 아래에서 Root custody가 따로 허가한다. assertion 자기 내용에서 고르거나 H1_INSTALL provisioner 권한을 물려받을 수 없다.
- 원천·subject:
  - 원본 불변 assertion이 capture/publication 신원·순서·시각과 RD ID/version을 묶는다.
  - raw registration SHA256은 바뀌지 않은 `sourceConstants.designRegistrationSHA256`과 같아야 한다.
  - project/purpose/source/contract subject는 독립 등록 정책과 같아야 하고, destination registry generation은 설치된 `capsule.generation`과 같아야 한다.
  - subjectFields는 12개, join은 4개다. H2 slot `registrationDeliverySubject`는 이 값을 전부 담고, H1 deliveryID/version과 다르다고 명시한다. 이름표만 있는 slot이 아니다.
- version: vector 28-29번에 `registrationDeliveryID/Version`을 추가했고, H1 쌍과 분리했다. checkpoint 행이 이 쌍을 전체 RD subject/raw assertion에 묶는다. 같은 ID/version에 다른 bytes는 equivocation으로 금지한다.
- 현재성: G08은 RD subject와 RD issuer grant의 현재 nonrevocation을 요구한다. RD issuer는 원본 assertion만 서명한다. subject 현재성은 독립 현재 등록 권한이 판정하고, grant 현재성은 G00만 판정한다. 순환이 없다.
- readback: G10이 최종 전체 RD subject/raw identity와 29개 vector를 비교한다.
- 인과 변형(모두 PROPOSED_NOT_RUN):
  - C07: RD assertion 누락 또는 잘못된 issuer(H1 issuer나 후보 key, 서명은 수학적으로 유효) → G04 REGISTRATION_ORIGIN.
  - C05: RD subject REVOKED → G08 REVOKED.
  - C08: RD version만 RV+1이고 기존 27개는 같음 → 시간 술어 전에 G10 READBACK.

**H12R-L1 (LOW) — CLOSED.**

- `G00_BINDING`이 별도 origin이다. 값은 provisioner/status/clock/RD 권한자 진술이나 후보 bytes에서 배우지 않는다. `bootstrapBindingIdentityVersion` origin이 H1_INSTALL에서 G00_BINDING으로 바뀌었다. 기존 H2 행 중 바뀐 것은 이것 하나다.
- G08 행과 `currentStatusSubjects`(11개)가 네 권한자 grant를 현재 G00 mapping 아래에서 명시한다. H1 delivery, capsule, H2 grant/key, registry, record, RD subject도 함께 든다.
- G04는 참조·신원 인증, G08은 현재성, G10은 현재 G00과 vector(`trustBindingIdentity/Version` 포함)의 반복 비교다. R1에서 수용한 G04 진위 / G08 ACTIVE 분할과 같다.
- C05 변형: 현재 G00 mapping이 한 권한자 grant를 해제하고 그 권한자는 여전히 ACTIVE를 서명한다. 이 경우 G00..G07을 통과한 뒤 G08 AUTHORITY_NOT_CURRENT로 거부된다.

**H12R-L2 (LOW) — CLOSED.**

- C09가 늦은 G10 경로가 되었다. G00..G09를 통과하고, 처음 [L,U]는 모든 경계 안에 엄격히 있다.
- G10에서는 origin/subject, 29개 vector, 같은 clock mechanism/epoch, bracket이 시간 술어보다 먼저 통과한다.
- `U_final == ticket.expiresAt` 하나만 경계에 닿는다. record.validUntil, status.expiresAt, H5.expiresAt, keyNotAfter는 모두 엄격히 뒤다.
- 기대 결과는 G10 EXPIRED이고 "ticket 또는 response" 선택지가 없다. 정적으로 구성 가능하다. 예: ticket 끝 = record.issuedAt+60초, 나머지 끝 ≥ +100초, 나이 ≤120초.

## 보존 확인

- stage 목록은 R1과 같다. 표 행 G00/G01/G02/G03/G05/G06/G07/G09는 byte 단위로 같다.
- 전체 시간 공식 블록과 D04 handoff 앞부분도 byte 단위로 같다.
- capsule 26, nested 선언 7그룹/항목 11, tuple 13, token 9가 R1과 같다.
- 원래 origin 5행과 나머지 H2 22행, vector 앞 27개가 같다. case C01/C02/C03/C04/C06/C10도 같다. 공개 거부 `TRUST_UNKNOWN_OR_PIN_MISMATCH`도 그대로다.
- 인접 정밀화 N1/N2/N3/N7/N8/N9가 권한·시간과 모순되지 않는지 확인했고, 모순은 없다.

## 비차단 정밀화 노트 N10-N14

판정 조건이 아니다. 나중에 Root가 따로 binding/코드를 허가할 때 N4와 함께 입력으로 쓴다.

- N10: `currentRegistrationSubject` join은 R1 문구 그대로라 RD와 grant를 적지 않는다. 기준은 G08 행과 11개 목록이다. RD subject 현재성의 원천이 H4_STATUS라는 점도 명시하면 좋다.
- N11: 유한 TCB binding 문장과 bootstrap slot join에 RD issuer 신원이 빠져 있다. mapping에 없는 issuer는 G04에서 실패하므로 fail-closed다.
- N12: C05 권한자 변형의 fixture는 그 신원을 mapping에 남겨 두고 grant 현재성만 바꿔야 한다. 신원을 빼면 G01/G04에서 걸린다.
- N13: C09 fixture는 다른 독립 경계(RD/grant 상태 만료 포함)도 엄격히 뒤에 둬야 한다.
- N14: G08 행의 "bounds remain unchanged"는 문구 문제다. RD destination generation이 capsule generation과 같아야 하므로 H1 generation마다 RD를 다시 전달해야 한다. 이 점은 Root가 확인한다.

## 검증 증거

- `reviewer_h12r2_static_check.py.txt`: stdlib만 쓰고 git blob을 읽는다. crypto, Go, network는 없다.
  - 한 번 실행했다. 09:16:23.188-09:16:30.145 KST, exit 0.
  - 결과 `reviewer-h12r2-static-result.json`(sha256 `d07ed9b6…`). 로그는 PowerShell이 잡은 같은 stdout이다(BOM+CRLF, sha256 `80595be2…`).
- 구조·참조·문자열 사실일 뿐이고, 인증 증명이 아니다. crypto/runtime 증명이 필요한 새 우려는 없어서 Root에 probe를 요청하지 않았다.
- 로컬 문서 gate 11개와 canonical sync CHECK의 직전/직후 state hash는 [local-doc-gates.txt](../Evidence/fleet5-k2-h12-r2-0bf8-review-20261107-claude/local-doc-gates.txt)에 있다. CHECK만 했고 apply/adopt/resolve/state write/export는 하지 않았다.

## 유지되는 HOLD

- 실제 binding은 모두 NULL/HOLD다. G00_BINDING과 RD_CAPTURE_DELIVERY의 실제 값도 UNBOUND_HOLD다.
- H1-H7/H3EA/expectedVerdict custody/RD는 NULL_HOLD이고 raw7은 UNREGISTERED다. public은 TrustUnknown이다.
- A01-A40은 NOT_RUN이고, H12-C01..C10은 PROPOSED_NOT_RUN이다.
- K1의 13 types/73 fields와 28 pin은 바뀌지 않는다. 전체 K2와 fleet 100은 미완이다.
- 다음 math helper는 R1 DATA ONLY 그대로다. 이 수용은 그 helper나 어떤 코드도 허가하지 않는다.

## 다음 첫 행동

Root가 이 검토를 검증한다. 그다음 별도 binding/코드 허가를 낼지, 언제 낼지 정한다(입력: N4, N10-N14). 이 검토로 코드·binding·후속 작업이 생기거나 시작되지 않는다.
