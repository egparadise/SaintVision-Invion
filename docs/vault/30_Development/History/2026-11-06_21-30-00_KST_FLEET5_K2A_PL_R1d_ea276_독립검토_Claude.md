---
doc_id: "HISTORY-FLEET5-20261106-K2A-PL-R1D-EA276-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 K2A PL-R1d test-only delta ea276 독립 좁은 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T21:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b47d5dd6cd23873c62602e02e85a8f82c9843dc5"
task_ids: ["FLEET5-K2A-PL-R1D-20261106"]
tags: ["fleet5", "independent-review", "k2a", "pl-r1d", "source-gate", "claude"]
---

# K2A PL-R1d test-only delta ea276 독립 좁은 검토

Orca `task_41987ea5739d`, dispatch `ctx_fb6fdb3cd301`다. owner는 Codex `task_a95ef3d8ccce / ctx_ed23b4a777d0`이고, 질문 `msg_4b416731f99d`는 이 판정과 Root의 Core 선택을 기다린다. 선행 UI854 검토 `task_599e55626b4a / ctx_15e621fbe050`는 succeeded/settled/exited/released 상태다(Root `.work/ui854-reviewer-before-plr1d-start.json`, 읽기만 함).

- **대상:** 최종 `ea276c97`, source `3311f453`(불변 base `b47d5dd6`의 직접 자식)이고, branch는 `agent/codex/fleet5-k2a-pl-r1d-20261106`(동결)이다. 검토 branch `agent/claude/fleet5-k2a-pl-r1d-ea276-review-20261106`은 정확히 ea276에서 만들었다.
- **Git 확인:** origin == ea276이다. b47→ea276 non-docs는 정확히 3개 수정(`effect_gate_test.go`, `pl_r1a_test.go`, README)이고, 3311→ea276 non-docs는 0 path다.
  - `effect_gate_test.go`: `conversionPointerElements` 추가와 변환 loop 한 줄 교체뿐이다.
  - `pl_r1a_test.go`: 397행 뒤에 순수 추가만 있어 옛 75건 prefix는 손대지 않았다.
  - README: PL-R1d 한정 7줄 추가와 R1c→R1d 한 단어 교체다.
  - Root `.work/plr1d-source-root-verified.json`(5495 unchanged rows, 43 own docs, Docs `42211618094`/`42212250558` all19 SUCCESS)은 읽기만 했다. owner CI와 202/19354 byte 검사는 다시 돌리지 않았다.
- **읽은 근거:** 내 이전 검토 `cfec7b81`의 review.json·sketch·probe·real G1, owner History v1.0.1과 Evidence `fleet5-k2a-pl-r1d-20261106-codex`, Root `msg_049b87bd98ba`.
- **기계 판독 결과:** `docs/vault/30_Development/Evidence/fleet5-k2a-pl-r1d-ea276-review-20261106-claude/review.json`
- **명령·exit·log hash:** 같은 폴더의 `commands.json`, `reviewer-results.txt`, `local-doc-gates.txt`, 그리고 probe 원문 `reviewer_plr1d_probe_test.go.txt`

## 판정

**CODE_AXIS_ACCEPT_FOR_BOUNDED_PL_R1D_TEST_DELTA.** 새 blocking finding은 없고 Info 3건만 있다. **G1–G6과 pointer 변환 class는 약속한 fence 안에서 닫혔다.** full Core·runtime·K2 완료가 아니다.

### 닫힘 근거

- **G1–G6:** 검토자의 깨끗한 ea276 FULL에서 6건 모두 build/typecheck 0이고 `pointee-changing pointer conversion forbidden: P`로 거부됐다. G1–G4가 옛 gate에서 통과(우회)한 것은 내 cfec 관측이다(e93 gate bytes == b47). G5/G6의 옛 b47 red는 owner 증거이고 다시 돌리지 않았다.
- **변환 class 논증:**
  - 변환이 pointee를 바꿀 수 있는 경우는 대상이 pointer 타입을 가리킬 때뿐이다. non-generic 대상은 b47이 이미 underlying pointer로 검사한다.
  - `*types.TypeParam` 대상은 Go 규칙상 피연산자가 P type set의 **모든** 타입으로 변환 가능해야 한다. 그 타입들은 constraint → (alias/named) interface → embedded 원소 → union term → interface 타입 term(재귀)으로 모두 도달 가능하다.
  - pointer base는 type parameter일 수 없으므로 수집된 element는 모두 구체 타입이다. named/alias pointer term은 `pointerElement`의 Unalias+Underlying이 처리한다.
  - 각 element에 기존 untyped nil / `types.Identical(src,dst)` 검사가 그대로 적용된다. slice 피연산자는 element가 없어 거부된다.
  - own non-test import는 allowlist라 `unsafe`/`reflect`가 없다(`source_gate_test.go:568-591`). 따라서 검토 closure 안에 다른 세탁 변환 형태는 없다.
- **owner 표에 없는 적대 probe:** ea276에서 exit 0, 13/13 build 0 / typecheck 0이다.
  - 음성 8건은 모두 `...forbidden: P`로 거부됐다. X1 인스턴스화된 generic constraint `C[L]`, X3 generic 타입 method의 receiver type parameter, X4 interface 타입 term이 있는 union, X5 method+pointer constraint, X6 `comparable` embedding, X7 generic body 안 closure의 변환, X8 type parameter 피연산자→type parameter 대상, X10 두 pointer term union을 통한 slice→array view다.
  - 같은 파일을 **옛 b47**에서 관측 모드로 돌리면 X1·X3·X4·X5·X6·X8·X10은 통과한다(우회). X7은 함수값 호출 규칙으로만 거부된다. 즉 이 delta가 실제로 막는 형태다.
  - 양성 Y1 인스턴스 constraint identity, Y2 receiver type parameter identity, Y3 interface term/named pointer union identity, Y4 non-pointer type parameter 값 변환은 ea276에서 허용된다.
- **수용한 control:** C1–C5·C7·C8은 의도한 변환 사유로 거부되고, C6은 쓰기 규칙으로 거부된다. P7–P10과 Q1–Q6(embedded, named pointer union, alias constraint, named pointer term, core pointer term, nil pointer term)은 허용된다. 모두 검토자 FULL 실행에서 확인했다.
- **실제 non-test G1:** cfec 파일(sha256 `2d65b939…287a`, 사용 안 함, 실행 안 함)을 완전한 공개 ea276 archive에 넣었다. `go build -p 1 -buildvcs=false ./...` exit 0, `TestResolvedObjectEffectBoundary` exit 1, 사유 `effect_gate_test.go:485: pointee-changing pointer conversion forbidden: P`다.
- **수치:** 깨끗한 ea276 FULL은 2차 시도에서 exit 0이었다. 20 top / 171 sub PASS, FAIL 0, 실제 build 99건 exit 0(본문 실행 없음), REASON 99줄 = 거부 69 / 허용 30, OWNER_PLR1C 21줄 + OWNER_PLR1D 24줄로 owner 주장과 같다. `go vet -p 1 ./internal/migrationcontext ./migrationverify`는 exit 0이다.
- **README:** PL-R1d 문단은 pointer-term 한정(constraint, embedded, alias/named pointer, union term, EACH element, slice 피연산자 거부)을 정확히 적는다. heap/type-set effect 증명이나 generic/storage 감사가 아니라는 점도 적는다. PL-R1b-I1 slice/map/backing storage, PL-I4 Marshal dispatch·인자 소유권, PL-I1 factory-before-K1, PL-I2 archive op-set, S2 info는 그대로 남아 있다. accept한다.

### Info

- **PL-R1d-I1:** 수집이 교집합 type set이 아니라 모든 embedded/union term을 문법적으로 따라간다. 상위 집합이므로 과거부만 가능하다. X11 `interface{~*L|~*time.Location; ~*time.Location}`(실제 집합은 identity)가 ea276에서 거부된다. 방어 gate로는 문제없고 변경을 요구하지 않는다.
- **PL-R1d-I2:** type parameter **피연산자**는 pointer로 보지 않는다(C3, X8). 그래서 pointer-term 대상으로의 변환은 항상 거부된다. 보수적이며 b47과 같다.
- **PL-R1d-I3 (독립성):** ea276 helper/loop bytes는 내 cfec sketch와 같다. owner 표 밖의 음성 8 + 양성 4, 옛 b47 대조 실행, 위 논증으로 보완했다. Root가 가중치를 판단한다.
- **PL-R1c-I1:** 옛 75건 prefix를 byte 동결했기 때문에 짝 잃은 주석이 남아 있다. 외형만의 문제이고 blocker가 아니다.

## 축 분리

1. **code:** ACCEPT(bounded PL-R1d test delta). source 판정일 뿐이다.
2. **local:** 검토자가 직렬로 재현했다. probe 13건(ea276 assert, b47 observe), 깨끗한 FULL 20/171, vet 0, 실제 G1 build 0 → gate 1.
3. **NOT RUN:** owner CI, Stage2 129, standalone 37, owner byte 검사, owner 옛 b47 FULL·G5/G6 red, generic type alias 형태(module이 `go 1.23`이라 실행 전 제외, 결과 주장 없음), local race(CGO 0), provisioned LAN, hosted race/LAN/main pytest/build/final Go/full Core.
4. **hosted:** owner Docs `42211618094`·`42212250558`은 Root가 검증했다. 재dispatch하지 않았다. 이 검토의 own Docs만 실행한다.
5. **runtime:** NONE이다. 옛 Core `42164071724`/Stage1 `42170068364` 실패와 원래 de71 field UNKNOWN은 유지한다. auth/clock/current/effects/entrypoint/self-measurement/install은 NULL/HOLD/ABSENT, A01–A40은 NOT_RUN, 5PC는 미완료다.

## 시도 기록

- **probe 1차:** exit 1이었다. 내가 처음 쓴 X10(두 core union에서 `(*P(k))[0]++`)이 Go로 유효하지 않아 go build가 실패했다. gate 결과가 아니다. 반환형 view로 고친 2차 실행은 exit 0이다.
- **FULL 1차:** exit 1이었다. archive에 `.git`이 없어 git을 쓰는 4개 top test가 exit 128로 실패한 setup 실패다. owner가 문서화한 읽기 전용 GIT_DIR/GIT_WORK_TREE(이 worktree, HEAD ea276, status 비어 있음)로 다시 돌린 2차는 exit 0이다.
- OOM은 없었다. 삭제 명령은 실행하지 않았고 scratch fixture는 남겨 두었다.

## 다음 행동

- **Root:** 판정을 기록하고, ea276c97에 fresh full Core + Docs를 한 번 돌릴지 정확히 결정한다. 이 결정은 검토자가 하지 않는다.
- **Codex:** `msg_4b416731f99d`에 대한 Root 답을 기다린다. 이 검토는 수정을 요구하지 않는다.
- **Claude:** 추가 배정이 없으면 대기한다.

검토자는 Core와 owner CI를 dispatch하지 않았다. 공유 진행판·registry·ADR·pins·K1·modules·workflow·product·owner Evidence는 수정하지 않았다. Obsidian은 `--check`만 했다(`local-doc-gates.txt`).
