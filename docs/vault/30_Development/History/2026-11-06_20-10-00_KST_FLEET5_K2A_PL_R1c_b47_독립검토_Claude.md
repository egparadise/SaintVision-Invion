---
doc_id: "HISTORY-FLEET5-20261106-K2A-PL-R1C-B47-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 K2A PL-R1c test-only delta b47 독립 좁은 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T20:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "084bd9471673f7f4f41dc547c76a2411c066109b"
task_ids: ["FLEET5-K2A-PL-R1C-20261106"]
tags: ["fleet5", "independent-review", "k2a", "pl-r1c", "source-gate", "claude"]
---

# K2A PL-R1c test-only delta b47 독립 좁은 검토

Orca `task_26dd9ebd51dd`, dispatch `ctx_63ce6b6612b7`다. owner는 Codex `task_a95ef3d8ccce / ctx_ed23b4a777d0`이고, 질문 `msg_7215f61639b2`는 이 판정과 Root의 CI 선택을 기다린다. 선행 `ctx_94f4cd146419`는 Root가 19:40에 settled/released로 확인했다.

- **대상:** 최종 `b47d5dd6`, source `e93ceb3b`(불변 base `084bd947`의 직접 자식)다.
- **Git 확인:** 084→b47은 3개 수정(`effect_gate_test.go`, `pl_r1a_test.go`, README)과 own Docs 41개 추가뿐이다. 삭제·mode 변경은 0이고, e93→b47 non-docs는 0 path다. Root의 `.work/plr1c-source-root-verified.json`(5454 unchanged rows, 두 Docs run)은 읽기만 했고, owner CI와 202 byte 검사는 다시 돌리지 않았다.
- **읽은 근거:** 내 이전 검토 `5a3c77f6`의 review.json·sketch·probe(sha256이 owner `review-inputs.json`과 같다), owner History v1.0.1과 Evidence `fleet5-k2a-pl-r1c-20261106-codex`.
- **기계 판독 결과:** `docs/vault/30_Development/Evidence/fleet5-k2a-pl-r1c-b47-review-20261106-claude/review.json`
- **명령·exit·log hash:** 같은 폴더의 `commands.json`, `reviewer-results.txt`, `local-doc-gates.txt`

## 판정

**REVISION_REQUIRED (좁음).** 변환 범위 안의 새 LOW 1건(PL-R1d)과 Info 1건이다. 그 밖의 PL-R1c delta는 accept한다. **N1–N6은 닫혔다. 그러나 type parameter 대상 변환이 규칙을 우회하므로 변환 class와 class (b)는 닫히지 않았다.**

### accept한 부분

- **N1–N6:** 검토자의 깨끗한 e93 FULL 실행에서 6건 모두 build/typecheck 0이고 `pointee-changing pointer conversion forbidden: *OWN.<type>`로 거부됐다.
- **non-generic 대상 규칙:** 대상 underlying이 pointer이면 피연산자는 untyped nil이거나 element가 `types.Identical`인 pointer여야 한다. 검토자 control로 확인했다.
  - C1 identity 후 세탁 연쇄, C2 own→foreign 역변환(보수적 거부), C3 type parameter **피연산자**, C4 호출 안 된 closure, C5 helper method 안의 함수 지역 이름 타입, C7 package 변수 initializer, C8 own pointer alias 대상: 모두 변환 사유로 거부됐다.
  - C6 foreign named pointer identity 변환 뒤의 쓰기는 쓰기 규칙(`foreign pointee write forbidden: time.Location`)이 거부한다.
  - P7 foreign pointer alias identity, P8 alias element identity, P9 foreign **값** 변환 복사, P10 typed nil은 허용된다.
- **수치:** 깨끗한 e93 FULL은 exit 0, 19 top / 147 sub PASS다. OWNER_PLR1C 21줄(변환 거부 6, R 거부 7, 양성 6, 한계 2)은 owner 기록과 같다. vet은 0이다.
- **README:** PL-R1b-I1 문장은 slice/map 원소 저장소와 append backing array가 일반적으로 검사되지 않는다는 점(복사된 header, slice parameter)과, SliceExpr root walk가 storage 소유가 아니라는 점을 명시한다. bounded fence와 맞는다. 자체 이름 pointee가 실제 heap 소유를 뜻하지 않는다는 점도 유지된다. 변환 문장만 아래 PL-R1d 한정이 필요하다.

### PL-R1d (LOW, 제품 동작은 막지 않음): type parameter 대상 변환이 검사를 우회

- **원인:** `effect_gate_test.go:375`의 `pointerElement(tv.Type)`는 대상 underlying이 pointer일 때만 동작한다. type parameter P의 underlying은 constraint interface라서 false가 되고, 변환은 검사 없이 통과한다.
- **반례:** compile-valid 4건이다. 모두 build exit 0, re-typecheck 0이고, 현재 e93 gate가 nil을 반환한다.
  1. G1 `func launder[P interface{*L}](x *clock.Location) P {return P(x)}; *launder[*L](clock.UTC)=L{}`
  2. G2 `func set[P ~*L](x *clock.Location){*P(x)=L{}}`
  3. G3 `func bump[P ~*C](c *x509.Certificate){(*P(c)).Version++}`
  4. G4 `func bump[P ~*a](k ed25519.PrivateKey){(*P(k))[0]++}`(P를 통한 slice→own array pointer)
- **end-to-end:** G1을 실제 non-test 파일(사용 안 함, 실행 안 함)로 완전한 공개 e93 archive에 넣었다. `go build -p 1 -buildvcs=false ./...` exit 0, production source gate `TestResolvedObjectEffectBoundary` exit 0이다. 즉 우회다.
- **영향:** README의 "own defined pointee name cannot launder a foreign pointer; slice-to-array-pointer conversions are refused by this rule"가 generic 대상에서는 거짓이다. N1과 같은 process-global `utcLoc`이다.
- **현재 도달 여부:** production에는 generic pointer 변환도, 외부 타입 위의 자체 타입도 없다(generic은 `copyMap[V any]`뿐).
- **검토자 자기 정정:** `5a3c` sketch와 계약("target underlying POINTER")이 같은 누락을 갖고 있었다. owner는 지정한 대로 구현했다.
- **수정안 (test-only, 범위 한정, alias/heap 분석 없음):**
  - 변환 대상의 pointer element 집합을 계산한다. 대상 자신이 pointer이면 그 element, `*types.TypeParam`이면 constraint type set의 모든 pointer term(embedded interface와 `*types.Union`을 재귀)이다.
  - 각 element에 기존 untyped nil / `types.Identical` 검사를 적용한다.
  - G1–G4를 변환 음성(`pointee-changing pointer conversion forbidden:`, type string P)으로 추가하고, README 변환 문장에 pointer-term type parameter 대상을 포함한다고 적는다.
- **sketch 검증:** scratch에서만 했고 commit하지 않았다(`reviewer_plr1c_fix_sketch.py.txt`).
  - 1차 FULL은 host OOM(`runtime: cannot allocate memory`)으로 exit 1이었다. gate 결과가 아니다.
  - 2차 FULL은 exit 0, 20 top / 163 sub PASS, FAIL 0이다. G1–G4는 `...forbidden: P`로 거부되고, owner 75건과 C1–C8·P7–P10은 그대로다. vet 0이다.
  - 실제 G1 파일은 sketch 아래에서 `TestResolvedObjectEffectBoundary` exit 1, 의도한 사유다. production source는 그대로 통과한다.

### PL-R1c-I1 (INFO)

`pl_r1a_test.go` 새 case table 주석에 짝 잃은 줄 `// otherwise the intended refusal prefix.`가 남아 있다. 외형만의 문제다.

### 유지되는 것

PL-R1b-I1 slice/map/backing storage는 선언된 미검사 한계로 남는다(여기서 요구하지 않음). PL-I1 factory-before-K1, PL-I2 archive operation-set 인증, PL-I4 Marshal 암묵 dispatch·인자 소유권, S2 info는 추적만 한다. merge/pin/diagnostics/public refusal/product/Stage2와 PL-R1b 쓰기 형태는 다시 열지 않았다. 변환 fence를 넘는 generics·소유권 감사로 넓히지 않았다.

## 축 분리

1. **code:** REVISION_REQUIRED(PL-R1d LOW). source 판정일 뿐이고, full Core·runtime·K2 완료가 아니다.
2. **local:** 검토자가 직렬로 재현했다. 깨끗한 e93 FULL 19/147, vet 0, 검토자 probe 16건 build 0, 실제 G1 build 0 + gate 0(우회).
3. **NOT RUN:** owner CI, Stage2 129, standalone 37, owner 202 byte 검사, 실제 G1 FULL suite(메모리 압박으로 production source gate test로 한정), local race(CGO 0), provisioned LAN, hosted race/LAN/main pytest/build/final Go/full Core.
4. **hosted:** owner Docs `42203278140`·`42204126607`은 Root가 검증했다. 재dispatch하지 않았다. 이 검토의 own Docs만 실행한다.
5. **runtime:** NONE이다. 옛 Core `42164071724`/Stage1 `42170068364` 실패와 원래 de71 field UNKNOWN은 유지한다. auth/clock/current/effects/entrypoint/self-measurement/install은 NULL/HOLD/ABSENT, A01–A40은 NOT_RUN, 5PC는 미완료다.

## 시도 기록

- sketch 1차 FULL: host OOM으로 exit 1(위 참조). 재시도 전 free RAM 346 MB를 관측했고 OS/pagefile/env는 바꾸지 않았다.
- 실제 G1 정리 1차: scratch 파일을 지우는 `rm -f $S/$F/...` 명령이 Claude Code 내장 위험 rm 검사에 걸려 **NOT_EXECUTED**였다. 아무것도 실행되지 않았다. 검사가 제안한 `${S:?}/${F:?}` 형식으로 바꾼 2차 명령이 실행됐다. 지운 것은 scratch fixture의 `pl_review_real_g1.go`와 scratch sketch probe test 파일뿐이다. 이 2차는 Root `msg_7c72c36dc9c2` 지침이 도착하기 전에 실행됐고, 그 뒤로 추가 삭제는 없다.

## 다음 행동

- **Root:** 판정을 기록하고 둘 중 하나를 고른다.
  - **권장:** owner가 PL-R1c branch에 test-only commit 1건을 더한다(2 test + README: type parameter pointer-term 규칙 + G1–G4 + README 한정 + 선택적 주석 정리). Claude가 그 delta만 검토한다. 그다음 그 SHA로 full Core + Docs를 한 번만 돌린다.
  - **대안:** PL-R1d를 tracked LOW로 이월하고 b47로 Core + Docs를 돌린다. 이 경우 변환 class/class (b)를 CLOSED로 인용하지 않는다.
- **Codex:** Root 지시가 있을 때만 수정한다.
- **Claude:** 배정되면 그 delta만 검토한다.

검토자는 Core를 dispatch하지 않았다. 공유 진행판·registry·ADR·Card150·pins·K1·modules·workflow·product·owner Evidence는 수정하지 않았다. Obsidian은 `--check`만 했다(`local-doc-gates.txt`).
