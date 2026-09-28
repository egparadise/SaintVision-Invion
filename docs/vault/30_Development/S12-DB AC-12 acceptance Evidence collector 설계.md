---
doc_id: "CLAUDE-S12-DB-AC12-EVIDENCE-COLLECTOR-DESIGN-001"
title: "S12-DB AC-12 acceptance Evidence collector 설계 — operational_readiness(--acceptance-evidence)·pitr_readiness·pitr_opt_in_dry_run·desktop-browser proof의 출력을 고정 SHA에서 읽어 AC-12 항목별 PASS·FAIL·NOT_OBSERVED·BLOCKED_EXTERNAL로 나누는 collector (판정 논리 복제 없음, #127·#131과 같은 형식, 카드 aq)"
version: "1.2.0"
status: "proposed-review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:23:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-DB"]
tags: ["S12-DB", "AC-12", "evidence", "collector", "operational-readiness", "pitr", "claude", "design"]
---

# S12-DB AC-12 acceptance Evidence collector 설계 (1쪽)

> [!warning] 설계 + PG-free 구현 단계
> task-registry S12-DB: scope "복원·권한·운영 인수", evidence "Release manifest·사용자 인수·웹 smoke·복구 Evidence", AC-12 "5노드 전체 여정·정량 목표·알려진 제한·인수 확인 모두 기록". 이 collector는 **AC-12 판정 논리를 복제하지 않는다** — [[Codex 권한 관측과 운영 인수 집계 계약]](ADR-082/083)의 `catalogComplete`·`acceptanceAssessed`·`blockers`를 만드는 `tools/operational_readiness.py --acceptance-evidence`(내부 `pilot_readiness`), `tools/pitr_readiness.py`, `tools/pitr_opt_in_dry_run.py`, desktop-browser CI proof(`vf-desktop-browser-ci.json`)의 **출력을 고정 SHA와 함께 읽어** 항목별로 나눈다. 공개 계약·registry·ontology·migration 변경 0. `acceptanceClaim=false`(S12-DB `planned` 유지).

## 1. 항목표 (AC-12 ↔ 입력 도구 ↔ 판정 규칙)

| 항목 id | 그룹 | 입력(도구 출력 필드) | PASS | FAIL | NOT_OBSERVED | BLOCKED_EXTERNAL |
|---|---|---|---|---|---|---|
| `release-manifest-recorded` | release | `acceptanceEvidence.version`·`manifestSha256` | 둘 다 존재 | assessed인데 누락 | 도구 미실행/미출력 | `--release` 없음(`acceptanceAssessed=false`) — release cut은 사용자 입력 |
| `user-acceptance-record-ac12` | release | `blockers` 중 "no acceptance record for AC-12"·"a rejected acceptance"·"an acceptance refers to a different manifest" | 해당 blocker 0 | 하나라도 | 도구 미출력 | `--release` 없음 |
| `known-limitations-recorded` | release | `knownLimitations` | 1건 이상 | — | 0건("없음"과 "미기록"을 구분 못 함) | `--release` 없음 |
| `database-recovery-drill-passed-with-targets` | recovery | `blockers` "no passing database recovery drill"·"no database recovery drill meeting …" | 해당 blocker 0 | 하나라도(+`drillsMissingTargets` 수) | 도구 미출력 | — |
| `verified-backup-in-retention` | recovery | `blockers` "no verified backup" | 0 | 있음 | 미출력 | — |
| `verified-off-site-backup` | recovery | `blockers` "no verified off-site backup" | 0 | 있음 | 미출력 | — |
| `contributed-folders-checked` | recovery | `blockers` "… contributed folder(s) need attention" | 0(+`contributionsNeedingAttention` 수) | 있음 | 미출력 | — |
| `operational-inputs-present` | permissions | `absent[]` | 비어 있음 | 이름 목록 | 필드 없음 | — |
| `offer-agreement` | permissions | `offerAgreement.disagreeing[]` | 비어 있음 | 개수 | 필드 없음 | — |
| `admission-gates-observed-open` | permissions | `admission.observedGatesOpen`·`closed[]`(scope diagnostic) | true | closed 목록 | 필드 없음 | — |
| `pitr-configuration-possible` | recovery | `pitr_readiness.verdict` | possible(`pitrVerified=false` 병기) | absent(+reasons) | inconclusive/미실행 | — |
| `pitr-rehearsal-dry-run-observed` | recovery | `harnessVerdict`·`mutations` | observed & mutation 전부 false | mutation true / 하네스 refused(argparse exit 2, label 시각 fail-closed) | inconclusive / `--pitr-archive`·`--pitr-backups` 없음 | — |
| `web-smoke-journeys` | web | proof `tests{passed,failure,error,skipped}`·`exitCode`·`evidenceStatus` | passed>0, 나머지 0, exit 0, complete | 그 외 | proof 미지정/부재/깨짐(Gemini lane) | — |
| `five-node-full-journey` | external | — | — | — | — | 물리 PC 5대(등록 3·겸임 BLOCKED, ADR-100) |
| `operational-rpo-rto-measured` | external | — | — | — | — | Tier-A PITR 유예(결정 B) |
| `real-pitr-target-time-recovery` | external | — | — | — | — | 실 WAL archive·운영자 복구 |
| `authenticated-browser-acceptance-on-physical-node` | external | — | — | — | — | 물리 fleet 사용자 인수 |

원칙: 관측하지 않은 값은 **0도 PASS도 아니다**(NOT_OBSERVED + reason, `value` 없음). 외부/사용자 입력 항목은 BLOCKED_EXTERNAL + reason, `value=null`. 도구가 `{"error": …}`나 JSON 아님을 출력하면 그 도구의 항목 전부 NOT_OBSERVED(FAIL 아님). 하네스의 fail-closed 거부(exit 2, #150)는 FAIL.

## 1b. Codex 검토(#153, head 30f5ca83) 4건 반영 — fail-closed 경계

| # | 지적 | 규칙 |
|---|---|---|
| F1 | serialize 뒤 raw 값 `.replace` → JSON escape된 값(`secret\"quote`) 잔존 | **구조화 값 단계에서 먼저 치환**(`redact_value`: dict 키·리스트·중첩) → serialize → 텍스트 치환 → `assert_redacted`가 raw·JSON-escaped·ASCII-escaped 세 표현을 모두 검사(잔존 시 거부). quote·backslash·개행·탭·U+2028 부정 시험 |
| F2 | 미분류 blocker·`catalogComplete=false`가 PASS | `KNOWN_BLOCKER_PREFIXES`(pilot_readiness가 오늘 내는 blocker 전부, 시험이 소스로 고정) 밖의 blocker가 하나라도 있으면 blocker 파생 5항목의 PASS를 전부 **NOT_OBSERVED**(사유에 blocker 원문); `acceptanceAssessed=true`인데 `catalogComplete≠true`이고 blocker 0이면 **FAIL**(도구 자기모순). release 없는 경우의 `catalogComplete=false`는 BLOCKED_EXTERNAL 사례라 recovery 항목 판정에 쓰지 않음 |
| F3 | `browserOptIn` 미검사·proof에 codeSha 결속 없음 | `browserOptIn is True` 필수(아니면 NOT_OBSERVED); proof의 `codeSha`/`gitSha` 또는 `--web-smoke-sha`(run head)가 이 bundle의 `codeSha`와 접두 일치해야 PASS 가능, 미결속·불일치는 NOT_OBSERVED |
| F4 | clean만 검사, remote 도달성 미검사 | `remote_reachability`: `--reachable-ref`가 있으면 `git merge-base --is-ancestor`, 없으면 `git branch -r --contains`(`->` alias 제외)에 하나라도 있어야 함. 아니면 exit 2, `--allow-unpushed-head`는 `provenance.unpushedHeadAllowed`로 기록되는 opt-out. `remoteReachable`·`remoteRefCount` 기록 |

## 1c. Codex 재검토(head 663aad65) 잔여 우회 2건

| # | 우회 | 규칙 |
|---|---|---|
| F3' | 상호 `startswith([:12])` 비교가 1글자 `proof_sha`도 결속으로 인정 | `sha_binding`: proof sha와 번들 codeSha 모두 **소문자 hex 12~40자**(`^[0-9a-f]{12,40}$`, 대문자는 소문자로 정규화, full 40 권장)여야 하고 짧은 쪽이 긴 쪽의 접두여야 PASS. 1자·11자·비hex·41자·다른 40자 → NOT_OBSERVED(사유 명시) |
| F4' | `--reachable-ref HEAD`가 raw 문자열로 `merge-base` 실행되어 항상 통과 | `resolve_remote_tracking_ref`: `refs/remotes/<remote>/<branch>` 또는 `<remote>/<branch>`(`git remote`에 있는 remote만)이고 `rev-parse --verify`로 commit에 풀려야 함. `HEAD`·local branch·tag·`refs/heads/*`·미설정 remote → `invalid-ref`(exit 2, opt-out으로도 통과 불가). stale 구분: `ls-remote --heads <remote> <branch>`의 live tip과 remote-tracking tip 비교 → `fresh`/`stale`/`unknown`(오프라인); **stale이면 도달 아님**, unknown은 기록. `provenance.remoteRefFreshness` |

## 2. 판정·산출·provenance

- verdict: 어느 항목이든 FAIL → **FAIL**; PASS 0건 → **NOT_OBSERVED**(exit 3); 그 외 NOT_OBSERVED/BLOCKED_EXTERNAL이 남으면 **PASS_MEASURED_PARTIAL**(exit 0, 외부 4건이 항상 남으므로 이 collector가 PASS를 낼 수 없음). `scope` = 4 상태별 항목 id 목록.
- 산출 `Evidence/s12-db-acceptance/s12-acceptance-<sha12>-<UTC %Y%m%dT%H%M%SZ>.{json,md}`: schema `s12-db-acceptance-evidence:1`, provenance(+collector sha256·`dirtyTreeAllowed`), `inputs`(각 도구 status/reason/exit/elapsed + 계약 필드 `acceptanceAssessed`·`catalogComplete`·`scope`·`operationalAcceptanceAssessed`·`evidenceComplete`·`unverified`·`blockers` 그대로), `items`, `scope`, `verdict`, `acceptanceClaim=false`.
- provenance: `tools.provenance.collect`를 repo 루트 cwd로, dirty tree 기본 거부(`--allow-dirty-tree` 기록), 기존 산출물 거부, 경로는 `<outside-repo>/<name>` placeholder.
- 도구 실행: subprocess(`PYTHONPATH`에 `src`·`services/control-plane/src` 주입), DSN은 환경변수 이름만 전달(`--readiness-dsn-env`·`--pitr-dsn-env`), 값 미기록.

## 3. redaction (prefix 비의존)

쓰기 전 전체 텍스트를 치환한 뒤 다시 검사(잔존 시 거부): (a) `--tenant`·`--release`로 받은 **정확한 값**(모양 무관, `<value:redacted>`), (b) UUID, (c) `<2~16 소문자>_<Crockford 26>` 전부(`<id:redacted>`; core `PREFIXES` 전수 + 커널 prefix + `backup_`/`release_` 같은 긴 prefix로 부정 시험), (d) disposable DB 이름, (e) `IPv4:port`. 비밀: 이 실행이 쓴 DSN env 2개 + 표준 5개의 DSN 값·비밀번호가 텍스트에 있으면 거부.

## 4. 부정 시험 목록 (PG-free, `tests/test_collect_s12_acceptance_evidence.py` **147 passed**)

- 항목표 17 유일·전부 평가·상태 4종; collector가 SQL·`archive_mode`·`met_targets` 등 판정 논리를 갖지 않음(소스 검사).
- 완전 관측 → 측정 항목 13 PASS·외부 4 BLOCKED·PASS_MEASURED_PARTIAL; `--release` 없음 → release 3항목 BLOCKED_EXTERNAL(FAIL도 PASS도 아님); catalog blocker 8종 각각 **정확히 그 항목만** FAIL; knownLimitations 0 → NOT_OBSERVED; absent/disagreeing/closed → 각 항목 FAIL; readiness unavailable → 관련 10항목 전부 NOT_OBSERVED+reason, `acceptanceCatalog=null`; pitr verdict 3종 매핑(재해석 없음); 리허설 6경우(refused → FAIL, inconclusive/not_run/unavailable → NOT_OBSERVED, mutation → FAIL); web proof 8경우(skipped 1이어도 FAIL, 미지정 → NOT_OBSERVED); 아무것도 관측 못 함 → NOT_OBSERVED exit 3, 값 0 없음; FAIL 우선; 외부 항목은 완벽한 catalog에서도 PASS 불가.
- 러너: DSN env 미설정 → unavailable/not_run; `{"error":…}` → unavailable(FAIL 아님); argparse 거부 → refused → FAIL; proof 부재/깨짐 → unavailable.
- redaction 부정 시험 = 5 부류 + prefix 전수(core ∪ kernel ∪ 긴 prefix); 명령행 값(모양 무관) 치환; sha/count/항목 id 보존; DSN env 비밀 guard(이 실행의 env 포함); `evidence_ref` placeholder; 기존 산출물 거부·미삭제; dirty 기본 거부·opt-out 기록; DSN 전무 → exit 2 미기록; label 시각 형식; repo 루트 provenance; stub end-to-end(tenant·release·id·host:port 전부 치환, stdout 경로 placeholder).
- postgres 마커 1(hosted Backend): 마이그레이션된 disposable DB의 새 tenant에 대해 실제 세 도구를 subprocess로 실행 — readiness `complete`, backup·drill 항목 FAIL(기록 없음), release 그룹 BLOCKED_EXTERNAL, 리허설·web NOT_OBSERVED, verdict FAIL, DSN·tenant 미포함. 로컬 실 PG·Docker·전체 suite 없음.

## 5. 경계·인계

owner Claude / reviewer Codex / 병합 금지. worktree `.worktrees/claude-test-hygiene` 재사용(새 worktree 없음), branch `agent/claude/s12-db-evidence-collector`, base `1e8baf04`. 실 evidence 파일은 사용자가 파일럿 tenant·release·PITR 경로·browser proof를 지정해 실행할 때 생긴다(이 PR에는 없음). 다음 첫 행동: Codex 설계·코드 검토 → hosted Backend run id → 파일럿 실행 여부는 코디네이터.
