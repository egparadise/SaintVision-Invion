---
doc_id: "HIST-CLAUDE-NEWPC-DAY1-CI-TRIAGE-001"
title: "새 PC 첫날 — CI 첫 실행 triage 지도(원인 6·Claude 레인 0) + 이전 후 전수 검증(절차서 §5) 결과"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["ci", "first-run", "triage", "migration", "verification", "go", "handoff"]
---

# 새 PC 첫날 — CI 첫 실행 triage + 이전 후 전수 검증

[[CI_첫실행_분류귀속조율_규율]]의 「첫 산출물 = 지도」를 따른다. 낱개 수정이 아니라 **원인 × 분류(A/B1/B2) × 레인 × 딸린 실패 수**다. 이어서 [[개발환경_이전_절차서]] §5(규칙 8 전수 검증)를 새 PC에서 돌려 기준선과 대조했다.

## 0. Provenance

- 측정 SHA **`d01c931a`** = origin/integration tip(측정 시작·종료 시 동일, fetch로 확인). 트리: `.worktrees/claude-newpc`(detached, `git status --porcelain` **0줄**, working_tree_clean=YES). 메인 워킹트리는 Codex가 dirty(워크플로·provision_credentials·contracts 등 11파일)라 측정에 쓰지 않았다.
- 인터프리터 `.venv/Scripts/python.exe` = **Python 3.14.7**(절차서 §2-1은 3.14.6 — patch 차이, 아래 대조에서 이상 없음), pytest 9.1.1. Node **v24.10.0**, npm 11.6.1. Docker Desktop 동작. gh **인증됨**(egparadise). **Go 없음**(이 PC에도 미설치 — Go 증거는 hosted CI에서, §3).
- 실 PostgreSQL: 로컬 일회용 컨테이너 `saintvision-invion-dev-pg`(postgres:16-alpine, 127.0.0.1:55432), DSN은 메인 트리 `.env`(값 미기재). 보호 컨테이너 4개(CX01 등)는 옛 기계 — `CX01_CONTAINER` 미설정, 관련 시험은 정직히 skip.
- **2차 실행(이 문서 작성 중 착지)**: Codex가 C1~C4 수정을 `881f2911`·`51d53b7f`로 착지(+ 계약 결정 #2/#5 채택 `eceac8cf`, fixture reachability `dcf2b947`, EvidenceEnvelope 5자리 PG 무게 `1312e295`). 51d53b7f에서 docs·frontend(workflow_dispatch)·browser 완료, backend 진행 중(작성 시점). 원인 지도의 상태 열은 이 2차 관측까지 반영.
- CI 1차 실행: docs `35688813795`(success) · backend `35688813798`(failure, 3.12·3.14 둘 다) · core `35688813794`(failure) · desktop-browser `35688813838`(failure). **frontend는 미실행** — 이 push(`d01c931a`)가 문서·AGENTS.md만 바꿔 경로 필터 밖(규율의 「all-5-same-SHA」대로, 구멍 아님).

## 1. CI 첫 실행 관측 (SHA d01c931a)

| workflow | 결론 | 실패 지점 | 그 앞까지 |
|---|---|---|---|
| docs | **success** | — | check_docs·contract_bindings·frontend_integrity·ontology·semantic check 전부 통과(hosted Linux, UTF-8) |
| backend ×2 (3.12/3.14) | failure | 3단계 `export_schemas.py --check` — **schema 2파일 stale** | pip 설치까지. **full pytest는 안 돎**(cascade: PG no-skip 결과 미관측) |
| core | failure | 22단계 full pytest: **2964 수집 / 6 실패 / 58 skip** | 10~21단계 **전부 success**: Go race/build, Node·Python·LAN 이미지 build, workspace 22·containment 28·business handoff 17·shard recovery 21·LAN installer 15 = **0 실패** |
| desktop-browser | failure | VF runner: **3 실패 / 3 통과 / 0 skip**, `evidenceStatus=partial` | Chromium·Uvicorn·tmpfs PG·후보 이미지 기동 성공 |

## 2. triage 지도 — 원인 6개 (1차 실패 9건 + 2차 신규 2건, 원인으로 셈)

분류 판별자 = 옛 PC 로컬 baseline `0b7d51ed`(CI-스코프 1622 passed / PG·Go·브라우저 not_run)의 ran-passed ↔ not_run 집합과 `git diff 0b7d51ed d01c931a -- <파일>`.

| # | 원인(뿌리 하나) | 분류 | 레인/소유 | 딸린 실패 | 근거·상태 |
|---|---|---|---|---|---|
| C1 | `contracts/pool-list-response.schema.json`·`pool-list-item-response.schema.json`이 모델과 stale — `9425062c`(canonical pool inventory endpoint, Codex)가 모델을 바꾸고 `export_schemas.py` 재생성을 안 착지 | **B1 회귀**(baseline에서 `export --check` PASS였고 그 뒤 변경) | Codex(계약 소유·해당 커밋 작성자) | backend 2 job + **backend pytest 전체 미실행(cascade)** | 새 PC clean 트리에서도 `export_schemas.py --check` **exit 1 재현**(환경 아님). **착지 `881f2911`**(재생성) → 2차 backend 실행 결과 대기 |
| C2 | core job이 `requirements-test.txt`만 설치 → `tools/check_ontology_generation.py`가 spawn될 때 `ModuleNotFoundError: rdflib` | **B2 환경/machinery** | Codex(core.yml machinery; 시험 `92c138fd`도 Codex) | core 2 (`test_ontology_generation_check` ×2) | 새 PC(rdflib 있음)에선 도구 **exit 0 PASS** → 코드 아닌 설치 목록. **착지 `881f2911`**(core.yml에 requirements-docs) |
| C3 | `test_credential_backend[wrong_owner]`가 `docker exec --user 1:1 $HOSTNAME`로 uid-1 파일을 만드는데 hosted runner는 이름 있는 컨테이너가 아님(`No such container`) | **A 새로 드러남**(Linux+PG 전용, 옛 PC not_run) | Codex(자격증명 백엔드 시험) | core 1 | **착지 `881f2911`**(`docker run --rm --volume`로 교체) |
| C4 | `tools/provision_credentials.py` 오류 매핑: malformed manifest → `JSONDecodeError`가 internal(exit 4)로 새고, 잘못된 rotation → `InternalError`(Denied여야) | **A**(PG 필요, 옛 PC skip) | Codex(도구·시험 작성자) | core 3 (`test_credential_provision` ×3) | **착지 `51d53b7f`**(Denied 매핑) |
| C5 | 브라우저 여정 3건 실패 — 1차는 safe evidence가 클래스명을 숨김. **2차(51d53b7f, run 35700169728)에서 노출**: `tests.integration.test_desktop_browser`·`tests.integration.test_studio_browser`(3 실패/3 통과, 재발) | **A**(실 브라우저 옛 PC not_run) | **Gemini**(화면·브라우저 인수 시험 `7c55fea7`·`325554cb` feat(web) 계열) / runner=Codex | desktop-browser 1 step(3 case) ×2회 | 다음: Gemini가 hosted Chromium에서 그 두 파일의 실패 케이스를 봄(케이스명은 safe evidence 밖 — proof.json/tests.xml은 runner 내부) |
| C6 | **frontend vitest 1파일 2케이스** `tests/freshness-and-staleness-wiring.test.tsx`(Priority 11·12): 기대값을 `testTimestamp.toLocaleTimeString()`(**러너 기본 locale**)로 만들고 화면은 `toLocaleTimeString('ko-KR')`로 고정 → hosted(en-US)에선 `12:30:00 AM` ≠ `AM 12:30:00`. 옛/새 PC(ko-KR)에선 우연히 일치해 655 통과 | **B2 환경차**(로컬 ran-passed, 파일 미변경, locale만 다름) | **Gemini**(`597ef148`) | frontend 1 job(2 case), 51d53b7f·39d8c238 둘 다 | 고침: 시험 기대값도 `'ko-KR'`로 고정(화면이 이미 고정) — 「시험이 러너 환경에 기댐」 부류, C3·`.work` 선존재와 같은 모양 |

- **Claude 레인 원인: 0** (C1~C6 전부). `src/saintvision`·`tests/core`(ontology 시험 제외)·`contracts`에서 난 것은 C1뿐이고 C1은 Codex 커밋의 재생성 누락이다.
- **1원인 1소유 확인**: 여섯 모두 단일 레인. Codex가 C1~C4(+C5 노출)를 착지했고(15:41 착수 → 16:33 push), C5·C6은 Gemini. 내가 같은 파일에 손대지 않는다.
- **멈출 선(규율 (4))**: 사용자 결정을 요구하는 원인 없음(계약 가정·우선순위 충돌 없음) → 자율 진행 가능. 사용자 몫은 그대로 [[사용자_결정대기_브리프_2026-09-22]].
- **cascade 주의**: C1이 backend pytest 전체를 가렸으므로 backend job의 PG no-skip 결과는 **아직 0 관측**이다. C1 착지 후 재실행이 backend의 진짜 첫 실행이다.
- **다섯 전부 같은 SHA**: 51d53b7f는 frontend가 dispatch로, Codex PR 브랜치 `agent/codex/continuation-20260922`(39d8c238)는 pull_request로 다섯 전부 떴다. 규율 종료 조건은 다섯이 **green**이어야 하므로 C5·C6 해소 후.

## 3. CI가 처음 검증한 것 (예측→관측; Go 지도 갱신)

[[2026-09-21_Go검증밀도지도_미검증표면_Claude]]가 "CI 열리면 해소"로 적은 항목이 **관측으로 바뀌었다**(core 10·11단계 success = `go test -race` + `go build` inv-node/inv-discover; 산출물 artifact에 `inv-discover`·`inv-node` 바이너리 존재).
- **해소됨(관측)**: main.go·announce.go **컴파일**; announce_test.go 실행(헤더 전송·빈 토큰 거부·TLS·redirect). 옛 PC "Go 0 컴파일"은 끝났다.
- **그대로 남음**: T1(CR/LF·공백·비-Bearer 주입 거부 분기 미시험) · T2(main.run env 로직) · T3(교차언어 e2e). 이 셋은 CI로도 안 잡힌다는 지도 판정 유지.
- **PG-in-CI**: 옛 PC 1039 skip 중 대부분이 깨어나 통과 — core 2964 수집·58 skip. 남은 58의 이유는 정직한 환경 게이트(CX01 19·명시 PG 이미지 13·Windows PowerShell 11·후보 이미지 10·브라우저 smoke 1·CLI 미설치 4).
- **node-dependent 레인**: 옛 PC `--ignore` 24파일 중 CI 레인이 돈 것(workspace·containment·business handoff·shard recovery·LAN installer) 전부 0 실패.

## 4. 이전 후 전수 검증 — 절차서 §5 (규칙 8), 새 PC clean 트리 `d01c931a`

| 항목 | 기준선(옛 PC, `47b0d2de`/`0b7d51ed`) | 새 PC (`d01c931a`) | 판정 |
|---|---|---|---|
| check_docs | PASS 758 | **PASS 760**(문서 +2, 그 사이 착지) | 같음 |
| check_contract_bindings | PASS 48 fixture·14 anchor·12 replay | **PASS 48·14·12** | 같음 |
| check_ontology | **RED**(S01 ontology 미재생성) | **PASS** | 기준선 RED 해소 — Codex `730b5ee0`(sync S01 done statuses) |
| check_doc_single_source --ratchet | PASS 18 | **PASS 18** | 같음 |
| check_response_freshness | PASS(report-only) | **PASS** | 같음 |
| check_frontend_integrity | PASS 0 위반 | **exit 1 → exit 0** (아래) | **환경 차이 발견** |
| export_schemas --check | (CI 배선; 로컬 baseline PASS) | **FAIL 2파일** | = C1 재현, 환경 아님 |
| contracts:check | PASS 16 | **PASS 16** | 같음 |
| tsc -b --force | exit 0 | **exit 0** | 같음 |
| vite build | exit 0 (99 modules) | **exit 0 (99 modules)** | 같음 |
| vitest | 655 / 75 files | **655 / 75 files** | 같음 |
| CI-스코프 pytest(실 PG, core.yml 22단계와 같은 `--ignore` 6) | 1650 passed / 1039 skip(PG 없음) | **2549 passed / 2 failed / 408 skip / 2 deselected** (34분 40초) | 아래 해석 |

**pytest 해석(예상 차이 vs 예상 밖)**:
- **skip 1039 → 408**은 예상된 것(로컬 PG가 붙어 PG 게이트 skip이 깨어남). 남은 408은 전부 정직한 환경 게이트 — Linux Docker 런타임 140·Linux 파일 백엔드 48·Linux Workspace 실행 26+17+11+11·Linux 저장소/자격증명 21+20+15·CX01 19·명시 PG 이미지 13·기타. **Windows 호스트라 Linux 전용이 skip이고, 이것들이 CI에서 도는 것**(core 2964 수집·58 skip)이다.
- **passed 1650 → 2549**: 깨어난 PG 시험이 통과. CI core의 6 실패(C2~C4)는 로컬에서 **안 난다**(rdflib 있음·docker exec 경로 Windows에선 skip·자격증명 시험은 Linux 게이트 skip) — 로컬 GREEN이 CI GREEN을 뜻하지 않는 사례 그대로.
- **로컬 failed 2 — 둘 다 새 트리·공유 자원 모양이고 단독 재실행 통과**:
  1. `tests/integration/test_vf_canonical.py::test_factory_route_measurement_is_not_fixture_union` — `root/.work/vf-route-gap.json`을 쓰는데 **fresh 워크트리에 `.work/`가 없어** `FileNotFoundError`. `.work` 만들고 재실행 → **1 passed**. 시험이 **pre-existing `.work/`에 기대는 잠복 가정**(옛 PC·메인 트리엔 있었고 CI는 앞 단계가 `.work/storage-source`를 만들어 통과). 소유 Codex(VF, `fc34f37c`). **Codex가 같은 결론으로 `51d53b7f`에 이미 고침**(`mkdir(parents=True, exist_ok=True)`) — 독립 도달·일치. 새 PC/clean clone에서만 드러나는 부류 = "있던 것에 기대던 시험".
  2. `tests/test_account_integration.py::test_published_migration_heads_upgrade_without_rewriting` — `tools/check_migration_upgrade.py` exit 1(진단 비공개). **단독 실행 → exit 0, 발행 head 전부 PASS.** 전체 run 중에만 실패 = 재현 안 됨. 같은 로컬 PG(55432)를 Codex가 메인 트리 시험으로 **동시에 쓰고 있어** 일회용 DB/lock 경합 가능성[미확인 추정]. CI core 9단계(같은 도구)는 success. 회귀 아님으로 두되, 측정 트리 1소유 원칙을 **PG 컨테이너에도** 적용해야 한다(R6-d의 DB판) — 다음 전수 측정은 내 전용 PG 컨테이너로.

**check_frontend_integrity — 새 PC 환경 차이(Gemini 도구, 짚어 넘김)**: 9규칙 0위반까지 다 돌고 **마지막 `print("✔ …")`에서 `UnicodeEncodeError: 'cp949' codec can't encode '✔'`로 exit 1**. 한국어 Windows 콘솔(cp949)에서 게이트가 **검사는 통과하고 출력에서 죽는** 거짓 RED. `PYTHONUTF8=1`이면 exit 0. hosted CI(UTF-8)는 영향 없음(docs run success). 옛 PC에선 왜 안 났나 — 그 세션의 콘솔 인코딩이 달랐거나 `PYTHONUTF8`이 켜져 있었을 가능성[미확인 추정]. **권고(Gemini)**: 도구가 자기 출력 인코딩에 의존하지 않게(ASCII 결과줄 또는 `sys.stdout.reconfigure(errors="replace")`). Codex가 docs.yml에 `PYTHONUTF8: '1'`을 넣는 것(dirty)과 같은 부류이나, 도구 쪽 고침이 뿌리다. 이 PC 규칙: 게이트는 `PYTHONUTF8=1`로 돌린다.

**절차서 §2·§4 상태**: §2-1 선행 설치 중 **Go만 없음**(나머지 충족). §2-3 venv·node_modules 생성됨. §3 경로 3곳은 `d01c931a`에 반영됨. §4 비밀은 `.env`에 로컬 PG용 5개(값 미기재·재발급). **완료 판정**: §5 core 수치가 기준선과 같으므로 이전은 완료로 본다(단 Go는 이 PC에 없어 §2-1 한 항목이 미충족 — Go 검증은 CI에 위임).

## 5. 인계 · 다음 첫 행동

- **Codex**: C1~C4 착지 완료. backend 2차(51d53b7f, run 35700169744) 결과가 PG no-skip의 첫 관측 — 나오면 내가 재triage해 이 표를 갱신.
- **Gemini**: (1) C6 vitest locale 고정(작음, 1파일) (2) C5 `test_desktop_browser`·`test_studio_browser` 3케이스 hosted Chromium 실측 (3) check_frontend_integrity 출력 인코딩 독립화.
- **사용자**: 새 결정 없음. 브리프 대기분 그대로.
- **나(Claude)**: (a) backend 2차 결과 재triage(51d53b7f), (b) Go 지도 T1~T3 잔여는 Codex/운영자 소관 유지, (c) 내 레인 무-블록(§0 (c)) 계속.

관련: [[2026-09-21_이어가기_상태와규칙_Claude]] §0 · [[2026-09-22_Codex_hosted_CI_wiring_and_first_run_forecast]](Codex 예측 — 1·3·4번 예측이 관측과 일치, 2번 backend는 PG 권한이 아니라 계약 drift가 먼저 막음) · [[검증규칙과_세축_canon]] 규칙 8.
