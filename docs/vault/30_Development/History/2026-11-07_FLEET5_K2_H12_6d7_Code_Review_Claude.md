---
doc_id: "HISTORY-FLEET5-20261107-K2-H12-6D7-CODE-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 K2 H12 서명 수학 후보 6d7ee3d 독립 코드 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T11:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "6d7ee3d85bd0e47eb7b787234c10d5dbfdb3a9e8"
task_ids: ["FLEET5-K2-H12-SIGNATURE-6D7-INDEPENDENT-CODE-REVIEW-20261107"]
tags: ["fleet5", "independent-review", "k2", "h12", "signature", "code", "claude"]
---

# K2 H12 서명 수학 후보 6d7ee3d 독립 코드 검토

Orca `task_7cf5765e1538` / dispatch `ctx_5cdc22d019b8`에서 한 실제 독립 CODE 검토다. 검토자는 Claude 하나다. helper·subagent·두 번째 검토자는 쓰지 않았다. 대상은 Codex `task_a95ef3d8ccce/ctx_ed23b4a777d0`가 만든 네 개 소스 파일이다. H1–H7 재설계, 실제 권한 설치, binding은 이 검토에 들어 있지 않다.

- 시작 11:43:14 KST. 직전 B 코드 검토 `task_1e856e06e90a/ctx_fe0931cf5bde`는 succeeded/settled/exited/released 상태였다(Root `.work/h12-6d7-reviewer-predecessor-lifecycle.json`).
- 새 branch `agent/claude/fleet5-k2-h12-6d7-code-review-20261107`을 정확히 `6d7ee3d8`에서 만들었다.
- Root 보드: fleet-five-orchestration HEAD `2a9eae0f`, Index 1.0.499, Codex 1.0.460, Claude 1.2.130. 후보 branch 안의 옛 보드는 이력으로만 봤다.

## 대상과 사전 확인

- 후보 `6d7ee3d8`, 직접 부모 `0bf852a6`. 원격 author ref가 정확히 `6d7ee3d8`이다.
- 266개 경로 = A264/M2. docs 밖 경로는 네 파일뿐이다. 나머지는 후보 Evidence 259개와 Codex 자기 History 3개다. post-CI 보고서는 tree에 없다.
- 네 pin은 git blob과 worktree 모두 일치했다: helper `f9e3e808…`, test `94f9bd56…`, effect `d34eecc2…`, source `0ad2989b…`. `wip02/*.current.raw` blob도 같다.
- `pureExternalObjects` 블록은 0bf8과 6d7에서 바이트가 같다(`64805959…`, 786 B). 새 세 객체는 그 안에 없다. `pl_r1a_test.go`(`9ea789e3…`)와 `p02_evaluate_internal.go`는 바뀌지 않았다.
- author 최종 보고서 `b944af89…`(101998 B)는 author worktree에 추적되지 않은(`??`) 로컬 post-CI 증거다. 6d7 CI tree에는 들어 있지 않다.
- 먼저 읽은 것: Root `.work`의 code grant `h12-signature-code-r1-root-cut.txt`, 수정 grant `h12-signature-r1-actual-failure-root-fix.txt`, publication `h12-signature-wip02-root-publication-step.txt`, WIP02·Go·회귀·CI Root 검증 JSON. 각 SHA256은 [static result](../Evidence/fleet5-k2-h12-6d7-code-review-20261107-claude/reviewer-h12-6d7-static-result.json)에 있다.

## 판정: ACCEPT_NARROW_PRIVATE_MATH_AND_SCOPED_GUARD_CODE_KEEP_HOLD

필수 수정은 0건이다. HIGH 0, MEDIUM 0, LOW 1(비필수), INFO 4. 상세는 [review.json](../Evidence/fleet5-k2-h12-6d7-code-review-20261107-claude/review.json)에 있다.

**수학 helper (`h12_signature_internal.go`).** 검사 순서는 다음과 같다.

1. 크기·형식을 먼저 본다: 레코드 1 B 이상 `p02EnvelopeLimit`(2 MiB) 이하, DER 1 B 이상 4096 B 이하, 기대 hash는 정확히 64자 소문자 hex.
2. 그다음에 raw와 DER을 복사한다.
3. 기존 `p02Decode(c2=false)` canonical roundtrip, `p02EnvelopeSchema`, `p02ReadEnvelope`를 돈다.
4. format·purpose를 확인하고, signer hash와 전체 DER의 SHA256이 둘 다 공급된 기대 hash와 같은지 본다. 원시 32 B 키 hash가 아니다.
5. `p02Unhex`로 64 B를 얻는다.
6. ParsePKIX → 구체 `ed25519.PublicKey`, 길이 32 → MarshalPKIX roundtrip이 전체 DER과 바이트가 같은지 본다.
7. 기존 `p02Context{envelopeValue: v}.signingInput()`을 쓴다. 이것은 `p02Domain`||NUL||canonical {body,signer} 전체다.
8. 마지막으로 stdlib `ed25519.Verify`.

실패 출구는 9개이고 모두 `p02SignatureTuple{}, false`다. 성공 출구는 1개이고 선언된 13개 필드를 정확히 채운다. 새 codec·domain·JSON callback·caller·port·factory는 없다. 결과는 공급된 키 가설 아래의 수학 DATA일 뿐이다.

**입력 소유권.** bounds 검사 뒤, parse·hash 전에 복사한다. 출력의 signingInput은 append로 새로 할당되고, sig는 `hex.DecodeString`의 새 slice다. 동시성·적대 isolation은 주장하지 않는다.

**시험.** 서명 oracle은 공개 결정적 seed와 stdlib JSON으로 만든다. 고정 domain 상수 + NUL + body/signer 전체이며, helper나 `signingInput`을 부르지 않는다. 표의 complete input은 32개다(fingerprint로 중복 금지).

- 수학 true 2개
- 수학 false 7개: 각 행이 canonical·schema·hash·DER 전제가 성립하는지 먼저 확인한다.
- 앞 층 거부 23개

DER 행은 decode·schema·hash가 성립함을 먼저 확인한다. 따라서 거부는 parse·type·roundtrip 층에서 온다. 소유권 행은 반환 뒤 원본을 바꿔 출력 alias가 없음을 확인한다. oversize 레코드는 AllocsPerRun 0이다. 같은 입력을 2번 평가하며, 새 unique 입력은 아니다.

**guard (`effect_gate_test.go`, `source_gate_test.go`).** 제거된 줄은 4개다. 두 조건에 `h12.references`/`h12.calls`를 덧붙였고, loop 변수를 추가했고, t.Fatal 하나를 위치 검사로 바꿨다. 새 예외가 성립하는 조건은 다음과 같다.

- 실제 `*types.Func` 객체
- 조정하지 않은 FileSet 위치가 H12 파일(`//line`은 무시)
- receiver 없는 패키지 함수 `h12CheckRegistrySignature`가 owner(중첩 FuncLit은 owner 없음)
- 직접 `call.Fun`

새 type 제한은 `file == h12SignatureSource`에만 걸린다. 이것이 WIP01 RED의 원인을 고친 부분이다. 실제 compile을 거친 fixture 12개(허용 2, 거부 10)와 resolver 대조 2개가 원인 문자열까지 확인한다. 거부 fixture는 함수값, 비호출 참조, 인자 전달, wrapper, 중첩 literal, 외부 파일, alias import, line directive, 다른 method, PrivateKey를 다룬다. Signer/PrivateKey/Sign 권한은 넓어지지 않았다. Sign과 NewKeyFromSeed는 test fixture에만 있다.

- **H12C-L1 (LOW, 비필수).** DER 0 B/4096 B 초과 거부는 구현이 맞다. 다만 empty-/oversize-DER 행은 `base.expected`를 그대로 둔다. 그래서 거짓 결과가 hash 불일치만으로도 이미 정해지고, 이 bound를 지워도 현재 시험은 모두 통과한다. 나중에 Root가 허가하는 시험 카드에서, hash를 다시 묶은 oversize DER 행과 AllocsPerRun 0 측정을 넣기를 제안한다(`h12_signature_test.go:220-225`, helper `:15`).
- **H12C-I1.** 일부 분기는 defense-in-depth라서 bool 결과만으로는 원인을 귀속할 수 없다. 예: schema가 signatureHex를 128 hex로 고정하므로 63/65 B 서명 행은 helper의 `len(sig)` 검사 전에 schema에서 거부된다(라벨이 그렇게 정직하게 적혀 있다). `len(key)` 검사와 roundtrip 불일치는 stdlib 입력으로는 아마 도달하지 않는다. 이는 실행하지 않은 수동 추론이다.
- **H12C-I2.** call 예외 key는 `call.Pos()`만 쓴다. 세 객체의 반환값은 호출할 수 없으므로 지금은 안전하다.
- **H12C-I3.** 공개 거부 단언은 표 뒤 한 번의 무조건 호출이다. 연결이 없다는 증거이고, 특정 행의 인과 성질은 아니다. ReadHistory/null/unregistered 거부는 기존 시험이 계속 맡는다.
- **H12C-I4.** 파일 식별은 bare FileSet 이름이다. 실제 소스로 돈 real-closure 대조가 이 결합이 실재함을 보여준다. dot import로 Verify를 직접 부르면 같은 객체라서 허용되며, 우회가 아니다. 이를 다루는 fixture는 없다.

## 증거 귀속

- **Root unit 실행(Root 사실, 내가 다시 돌리지 않음).** WIP01 `f320083d…`는 phase 4에서 실패 event 9개(leaf 5 + parent 3 + package 1)를 냈다. 실패 시험 9개가 아니다. WIP02 `f4e1532a…`는 PC3 pinned Go1.27.1 격리 환경, 10:22:54–10:25:28 KST, 4 phase 모두 direct exit 0, 28 top/274 sub pass, 0 fail, 0 skip, OOM false, 373 소스 불변이었다. 옛 PLR 다섯 leaf의 원래 원인과 S1/S2 LIMIT가 복원됐다. 원래 RED는 지우지 않았다.
- **Hosted CI(Root 검증).** Docs `42324844830` 19/19 SUCCESS. Core `42324848063` main 42 success + 선언된 optional skip 6, S01 16 success. primary JUnit 9358 = 9312 pass + 46 skip. Go race 146 top + 550 sub. live Docker 호환 1 top + 4 sub(CI runner이며 사용자 5대 수용이 아니다). 새 H12 행 32+12. P02 92행/90 unique. 공식 artifact digest 4개 일치.
- **검토자 static.** [reviewer_h12_6d7_static_check.py.txt](../Evidence/fleet5-k2-h12-6d7-code-review-20261107-claude/reviewer_h12_6d7_static_check.py.txt)를 `-I -B`로 돌렸다. attempt 1은 exit 1이었다. 원인은 검토자 regex 결함 두 개다(계산된 `signature-bytes-` 이름을 중복으로 셌고, 허용 행 패턴이 틀렸다). attempt 2는 exit 0, 검사 48개 통과다. git·blob·파일 구조 사실일 뿐이고 compiler 증명이 아니다.
- **검토자 수동 추론.** 실제 소스를 놓고 한 go/types·AST 추론이다. type 증명을 지어내지 않았다.
- **내가 실행하지 않은 것.** Go, compiler, test, crypto, keygen, 서명, X509, 앱, Node, browser, 전체 Core, SSH, Docker, PG, process. author·Root gate도 다시 돌리지 않았다.

## 남은 것과 다음 담당

이 통과로 닫히지 않는 것: 실제 H1–H7/H3EA, verdict custody, RD NULL_HOLD, raw7 UNREGISTERED, A01–A40 NOT_RUN, 실제 Root binding(없음), authority(없음), 공개 TrustUnknown, K1 13 types/73, 28 pins, 5대 전체 프로그램(미완료). 원래 B19 HOLD와 runtime B0에는 영향이 없다. N10–N14 binding 선택은 FUTURE 입력으로 남는다. trust·current·port·producer·effect·positive factory·register·deploy·merge 권한은 주지 않았다.

다음 첫 행동은 Root/Codex 집계자가 이 판정을 받고 다음 범위를 정하는 것이다. H12C-L1은 선택 사항이며, 나중에 Root가 허가하는 시험 카드로 간다. 로컬 문서 gate와 sync CHECK는 [local-doc-gates.txt](../Evidence/fleet5-k2-h12-6d7-code-review-20261107-claude/local-doc-gates.txt), 명령 이력은 [commands.json](../Evidence/fleet5-k2-h12-6d7-code-review-20261107-claude/commands.json)에 있다. 검토 SHA와 Docs run은 push 뒤 Orca worker_done으로 Root에 보고한다.
