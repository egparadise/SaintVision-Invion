---
doc_id: "CLAUDE-G11-CLI-PROVISION-DESIGN-001"
title: "G-11 hosted CLI provision 설계 v1.0 — 4개 CLI(claude-code·codex-cli·gemini-cli·antigravity)의 hosted 실행 가치/비용, 배포 채널·버전 고정 실측, 격리(opt-in label lane), credential 없는 적합성 범위, 결론 '지금 하지 않음'과 재평가 조건 (카드 78, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:49:07+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-ST"]
tags: ["G-11", "cli", "adapters", "hosted", "ci", "design", "claude"]
---

# G-11 hosted CLI provision 설계 v1.0 (2026-09-28, 카드 78)

> [!note] 범위
> PR #179 §3-5의 G-11: `tests/test_cli_adapters.py:378` `test_the_tool_definitions_match_what_the_tools_actually_offer`의 parametrize 4건이 hosted에서 `shutil.which` 부재로 skip(`'<executable> is not installed on this machine': 1` × 4, `backend.yml:163-166`·`core.yml:174-177`). 이 문서는 **hosted runner에 CLI를 provision해 skip 4 → 실행으로 바꾸는 안**의 가치/비용을 실측으로 판정한다. docs-only, migration 없음(#179 §4 확정). 코드·workflow 변경 없음.

## 0. 결론 먼저

**지금 하지 않는다.** 근거는 §5, 재평가 조건은 §6. 요지: (1) 4건 중 **antigravity는 provision으로 닫을 수 없다**(Linux CLI가 없고 headless 호출도 정의돼 있지 않음 — §1-4) 그래서 상한은 3/4; (2) 세 npm CLI는 릴리스 속도가 매우 빠르고(§1) 우리가 통제하지 않는 postinstall·플랫폼 패키지를 runner에 들여온다; (3) 시험이 증명하는 것은 "`--version`이 답하고 status 명령의 **출력 모양**이 정의와 맞다"까지이며(§3), credential 없이 얻는 정보는 그 이상이 아니다; (4) 안전한 형태(별 opt-in label lane + 잠금 파일 핀)로 만들어도 매달 핀을 올리는 사람이 필요하다. #179가 "1~4순위 뒤 재판단"이라 한 판단을 실측이 뒤집지 않는다.

## 1. 배포 채널·설치 명령·버전 고정 — 실제 조회 출력만

조회 방법: `curl https://registry.npmjs.org/<pkg>`(2026-09-28 17:4x KST), GitHub `actions/runner-images` README(raw), 이 PC(Windows)의 설치본 실행. **조회하지 않은 것은 NOT_OBSERVED**로 적는다.

### 1-1. claude-code

| 항목 | 관측값 |
|---|---|
| npm 패키지 | `@anthropic-ai/claude-code` — `dist-tags`: `stable 2.1.274`, `latest 2.1.283`, `next 2.1.283`; 버전 수 **525**; latest 게시 `2026-09-25T18:46:11Z` |
| bin / engines / license | `bin: {"claude": "bin/claude.exe"}`(npm 메타데이터 그대로), `engines: {"node": ">=22.0.0"}`, `license: SEE LICENSE IN README.md`(OSS 아님), `repository: None` |
| 설치 명령 | `npm install -g @anthropic-ai/claude-code@2.1.283` (버전 핀은 §1-5) |
| 이 PC 실행 | `claude --version` → `2.1.283 (Claude Code)`; `claude auth status --json` → exit 0, JSON 키 `analyticsDisabled, apiProvider, authMethod, configDirectory, email, loggedIn, orgId, orgName, projectsDirectory, subscriptionType` (로그인 상태에서; 값은 기록하지 않음) |
| 로그아웃 상태의 `auth status --json` 출력 | **NOT_OBSERVED**(이 PC는 로그인돼 있고 로그아웃 시험은 사용자의 세션을 끊으므로 하지 않음) — 시험 통과 조건(§3)의 미확인 지점 |
| postinstall 스크립트 유무 | **NOT_OBSERVED** |

### 1-2. codex-cli

| 항목 | 관측값 |
|---|---|
| npm 패키지 | `@openai/codex` — `latest 0.158.0`(게시 `2026-09-28T05:12:20Z`, 조회 당일), 버전 수 **5044**; `dist-tags`에 `win32-x64`, `alpha-darwin-x64`, `alpha-linux-x64` 등 **플랫폼별 태그** 존재 |
| bin / engines / license | `bin: {"codex": "bin/codex.js"}`, `engines: {"node": ">=16"}`, `license: Apache-2.0`, `repository: github.com/openai/codex` |
| 설치 명령 | `npm install -g @openai/codex@0.158.0` — linux-x64 네이티브 바이너리가 어떻게 끌려오는지(optionalDependencies/postinstall)와 runner에서 실제 설치 성공 여부는 **NOT_OBSERVED** |
| 이 PC 실행 | `codex --version` → `codex-cli 0.150.1`(npm이 아니라 `AppData/Local/Programs/OpenAI/Codex/bin/codex` 네이티브 설치본); `codex login status` → exit 0, `Logged in using ChatGPT` |
| 로그아웃 상태의 `login status` 출력·exit code | **NOT_OBSERVED** |

### 1-3. gemini-cli

| 항목 | 관측값 |
|---|---|
| npm 패키지 | `@google/gemini-cli` — `latest 0.61.0`(게시 `2026-09-24T00:04:53Z`), `preview 0.62.0-preview.0`, `nightly 0.63.0-nightly.20260928…`, 버전 수 **763** |
| bin / engines / license | `bin: {"gemini": "bundle/gemini.js"}`, `engines: {"node": ">=20"}`, `license: Apache-2.0`, `repository: github.com/google-gemini/gemini-cli` |
| 설치 명령 | `npm install -g @google/gemini-cli@0.61.0` |
| 이 PC 실행 | `gemini --version` → stderr에 설정 디렉터리 ACL 경고("Security Warning: Skipping system settings file …") 뒤 stdout `0.60.0`. 정의는 `login_args=None`, credential 파일 `.gemini/google_accounts.json`만 신호 → runner에서는 언제나 `LOGGED_OUT`(시험은 이 경우 state를 단언하지 않음, §3) |

### 1-4. antigravity

| 항목 | 관측값 |
|---|---|
| 정의(`agents.py:79-94`) | `executable="antigravity"`, `login_args=None`, `install_paths`는 **Windows(`…/Programs/antigravity/Antigravity.exe`)·macOS(`/Applications/Antigravity.app`)만**, `prompt_args=None`("A desktop application with no documented headless invocation") |
| 배포 채널 | npm `antigravity`는 무관한 placeholder 패키지(`description: placeholder for the haters`, `0.0.0`) — **CLI 배포 채널은 조회로 찾지 못함: NOT_OBSERVED** |
| Linux runner | 정의된 설치 경로가 Linux에 없고 headless 호출이 없으므로 **provision해도 이 케이스는 닫히지 않는다.** G-11의 실효 상한은 **3/4** |

### 1-5. 버전 고정 방법(설계, 미실행)

- `tools/cli-conformance/package.json`에 세 패키지를 **정확 버전**(`"@anthropic-ai/claude-code": "2.1.283"` 등, 범위 지정 금지)으로 두고 **`package-lock.json`을 커밋** → lane은 `npm ci --prefix tools/cli-conformance`로만 설치. lock의 `integrity`(sha512)가 tarball을 고정하므로 "같은 버전 이름의 다른 바이트"도 막힌다. `npm install -g pkg@x`는 lock이 없어 transitive 의존이 흔들리므로 쓰지 않는다.
- 핀 갱신은 사람이 PR로(Renovate 등 자동 갱신 도입은 별 결정). 핀이 오래되면 시험은 "예전 CLI의 모양"을 증명하게 되므로 §6의 재평가 조건에 갱신 주기를 둔다.
- **pinned 이미지 여부**: 세 CLI 모두 우리가 통제하는 컨테이너 이미지가 없다. Core lane의 `postgres:16`·`python:3.12-slim`처럼 digest로 고정할 대상이 아니며, 만들려면 `Dockerfile`로 우리 이미지를 빌드·digest 고정해야 한다(비용은 §5).
- runner 전제: `ubuntu-latest` = Ubuntu 24.04 이미지 `20260920.314.1`, **Node.js 22.23.2 preinstalled**(runner-images README 실측) → claude-code의 `node>=22`를 만족. Backend job은 `setup-node`가 없고 Core job은 `node-version: '22'`(`core.yml:63-65`).

## 2. 설치 실패가 CI 실패면으로 들어오는 위험과 격리

| 위험 | 내용 | 격리 |
|---|---|---|
| 외부 릴리스 흔들림 | 세 패키지는 하루~며칠 단위로 릴리스(§1). 핀 없이 설치하면 CI가 상류 릴리스마다 흔들린다 | 정확 버전 + lock(§1-5) |
| 설치 실패 = 시험 실패 | npm 레지스트리 장애·플랫폼 패키지 누락·postinstall 실패가 Backend/Core red로 보인다 | **본 lane(Backend 3.12/3.14·Core)에는 넣지 않는다.** #176의 `mlflow-live`(`backend.yml` `if: contains(labels, 'run-mlflow')`)와 같은 **별 opt-in job `cli-conformance`(label `run-cli`)**. 설치 단계가 실패하면 그 job만 red이고 exact map은 본 lane과 분리 |
| 서드파티 코드 실행 | postinstall·바이너리는 우리가 검토하지 않은 코드다 | lane은 `permissions: contents: read`, secrets 0, 네트워크는 npm 레지스트리 외 불필요. `--ignore-scripts`는 CLI가 postinstall에 의존하면 깨지므로 **관측 뒤 결정**(§6) |
| 비용·시간 | 세 패키지 설치 시간·용량은 **NOT_OBSERVED** | 캐시(`actions/cache`로 npm cache) 가능하나 첫 실측 뒤 판단 |
| exact skip map | 본 lane 4건은 그대로 두고(변경 0), 새 lane은 자기 map `{'antigravity is not installed on this machine': 1}` + 실행 3을 단언 | skip이 "증거"로 남는 규칙 유지 |

## 3. credential 없이 실행 가능한 적합성 시험 범위 (credential 금지)

시험 `test_the_tool_definitions_match_what_the_tools_actually_offer`가 하는 일(코드 실측):
1. `shutil.which(tool.executable)` 부재 → skip.
2. `adapter.probe()` = `<exe> --version` 실행, `reachable(exit 0)`·`api_version(첫 줄)` 단언. **credential 불필요.**
3. `login_args`가 있는 도구(claude·codex)만 `login_state()`가 `UNKNOWN`이 아님을 단언. `login_state`(`cli.py:295-343`)는 status 명령을 **실행하되 프롬프트를 보내지 않는다**(무료 경로). claude: `auth status --json`이 **답하고(JSON) `loggedIn` 키가 있으면** LOGGED_IN/LOGGED_OUT → UNKNOWN 아님. codex: `login status`가 **답하면**(exit code 무관) marker `logged in` 유무로 LOGGED_IN/LOGGED_OUT → UNKNOWN 아님. gemini·antigravity는 credential 파일 유무만 보고, 시험은 state를 단언하지 않는다.

따라서 **credential 없는 runner에서 통과 가능한 범위** = "`--version`이 답한다" + "claude/codex의 status 명령이 **정의된 모양으로 답한다**(로그아웃 상태여도)". 이것이 G-11이 닫으려는 공백의 전부다: **상류 rename 감지**(정의 드리프트). 실행·프롬프트·결과 attestation은 범위 밖이며 credential을 두면 안 된다(runner에 사람의 세션을 심는 것이고 `cli.py` 계약이 "install and login are observed, never performed"라 명시). 다만 로그아웃 상태에서 claude `auth status --json`이 JSON을 내는지, codex `login status`가 답하는지(exit·출력)는 **NOT_OBSERVED**(§1) — 첫 실측 전에는 "통과한다"고 적을 수 없다.

## 4. skip map 변경량

| 안 | Backend map | Core map | 새 lane |
|---|---|---|---|
| A. 본 lane에 설치 | 4건 −3(antigravity 1 잔존) × 3.12/3.14 | −3 | 없음 |
| **B. opt-in lane(권고 형태)** | **변경 0** | **변경 0** | 자기 map `antigravity 1` + 실행 3 단언 |

A는 §2의 위험을 본 lane에 그대로 들여온다. B만 검토 대상이며, B도 지금은 하지 않는다(§5).

## 5. 가치/비용 판정

- 가치: 상류 rename 감지 3건(claude·codex·gemini). 이 회귀는 지금까지 hosted에서 한 번도 관측된 적이 없고(NOT_OBSERVED), 잡히더라도 대응은 `agents.py` 정의 한 줄 수정이다.
- 비용: 잠금 파일·package.json·새 job·자기 exact map·핀 갱신 PR(월 단위 이상; codex는 하루에도 릴리스) + 첫 실측 2회(§6) + 서드파티 코드 실행 표면. antigravity 1건은 어떤 비용을 들여도 닫히지 않는다.
- #179 §3-5의 "가치/비용이 가장 나쁘다"는 실측으로 **강화**됐다(4/4가 아니라 3/4, 로그아웃 출력 미관측, codex linux 설치 미관측).

## 6. 재평가 조건(모두 충족 시 B안으로 카드 재개)

1. G-01~G-05(#179 §3-1~3-4) 구현 카드가 닫힘.
2. `workflow_dispatch` 1회 실측: runner에서 `npm ci`(lock 핀)로 세 패키지 설치 성공, `--version` 3건 exit 0, 로그아웃 상태 `claude auth status --json`이 JSON(`loggedIn` 키 포함)을 내고 `codex login status`가 답함 — 결과를 Evidence JSON으로 남김.
3. 핀 갱신 담당·주기 결정(예: 월 1회, 담당 Claude).
4. antigravity는 정의 변경(Linux headless 호출 존재 확인) 전까지 **G-11 범위에서 제외**하고 map에 skip 1로 명시.

## 7. 검증 방법(실제 수행한 것만)

- `git grep -n -F "is not installed on this machine"`(base `1e8baf04`): `backend.yml:163-166`, `core.yml:174-177`, `tests/test_cli_adapters.py:382`.
- `tests/test_cli_adapters.py:378-395`, `src/saintvision/adapters/agents.py:47-94`, `src/saintvision/adapters/cli.py:1-60·264-343` 정독.
- npm 레지스트리 `curl` 3건 + `antigravity` 1건, `actions/runner-images` Ubuntu2404 README `curl`.
- 이 PC에서 `which`·`claude --version`·`claude auth status --json`(키만 기록)·`codex --version`·`codex login status`·`gemini --version` 실행. 로그아웃 상태·runner 설치는 실행하지 않음(NOT_OBSERVED로 표기).
- workflow·코드 변경 없음, npm 설치 없음.
