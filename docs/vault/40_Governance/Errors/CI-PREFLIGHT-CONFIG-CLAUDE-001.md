---
doc_id: "CI-PREFLIGHT-CONFIG-CLAUDE-001"
title: "CI 사전 점검 — 결제 열기 전 설정-원인 빨간불 제거. 발견·인계(워크플로는 Codex)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T19:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["ci", "preflight", "config", "workflows", "boundary-attribution", "handoff-codex"]
---

# CI 사전 점검 — 설정-원인 빨간불 제거

목적: 사용자가 CI 결제를 열었을 때 **실제 결함이 아니라 설정 문제(경로·버전·env·하드코딩 개수)로 빨간불이 뜨는 것**을 미리 없앤다. 실제 결함으로 인한 빨간불은 CI의 목적이니 그대로 둔다. 러너는 5개 워크플로 전부 `ubuntu-latest`(확정).

**실행 vs 읽기**: 개수/collect/junit-skip은 이 호스트에서 **실 pytest 실행**(artifact 기반). 버전/경로/env 이름 대조는 **소스-읽기**. 이 라운드 Docker는 안 띄웠다(image 게이트는 PG 독립).

## 확정된 설정-원인 빨간불 (첫 CI 실행에서 뜸)

### ① [최우선·artifact 확증] image-opt-in 시험이 no-skipped 단언을 깬다
- `backend.yml`("No PostgreSQL test was skipped": `assert not root.findall('.//skipped')`)과 `core.yml`("Every collected test must run and pass": `assert not any(... 'skipped')`) 둘 다 **skip 0을 단언**한다.
- 그런데 세 image-opt-in 파일 — `test_web_container`(`INV_WEB_IMAGE`), `test_workspace_upgrade`(`INV_UPGRADE_AGENT_IMAGE`), `test_lan_storage_install`(`INV_STORAGE_SOURCE_ROOT`) — 은 **어느 워크플로도 그 env를 안 켠다**(전수 grep 0). 그리고 `node_dependent_tests.py` 목록에 **없어** backend에서도, browser-only 제외인 core에서도 **collect된다**.
- **artifact 실측**: 세 파일 `--junitxml` → **testcases=22, skipped=22, failure=0, error=0** (postgres 마커 없음 → PG와 무관하게 image 게이트로 전부 skip). CI엔 PG가 있어도 이 skip은 그대로다.
- **결과**: 첫 CI 실행에서 backend·core 둘 다 이 22 skip으로 **no-skipped 단언 실패 → RED**. 실제 결함이 아니라 설정 불일치(image 시험이 추가/게이트됐으나 워크플로의 collect·단언이 그에 맞춰 안 됨; CI가 한 번도 안 돌아 미노출).
- **수정안(Codex)**: 이 셋은 의도된 별도 opt-in 트랙(이미지/설치 acceptance)이므로 **browser처럼 backend·core collect에서 제외**하는 것이 정합(`--ignore=tests/integration/test_web_container.py …`), 또는 `node_dependent_tests.py`류 제외 목록에 추가(그 도구는 Claude 소관 — 원하면 내가 확장), 또는 워크플로가 해당 이미지를 빌드해 env를 켠다(더 큰 변경·비용). 별도 트랙 설계상 **제외**가 최소·정합.

### ② [소스-읽기] go-version 1.27.1이 floor를 초과·미출시
- `core.yml` `setup-go go-version: '1.27.1'`. `services/node-agent/go.mod`·`packages/contracts-go/go.mod`는 **`go 1.23`**만 요구(하위호환이라 상위 toolchain은 무방). 그러나 **1.27.1은 Jan 2026 지식 기준 미출시** 버전이라, CI 실행 시 setup-go가 못 받으면 **core.yml이 setup에서 RED**.
- **수정안(Codex)**: floor를 넘는 특정 미래 패치 고정은 취약 — 출시된 버전(예: `'1.23'`/`'1.24.x'`/`'stable'`)으로. (주의: CI가 1.27.1 출시 이후 돈다면 무해 — 그러나 특정 미래 패치 고정 자체가 취약.)

## 취약(현재는 맞으나 드리프트 시 빨간불 — definer 9-vs-10 형태)

### ③ 하드코딩된 개수 — 파일에서 세지 않고 박아둠
- `desktop-browser.yml`: `assert proof['tests'] == {failure:0, error:0, skipped:0, passed:6}` — **6은 워크플로에 박힌 리터럴**. 현재 실측 **6 tests collected**로 일치하나, browser 여정이 하나 추가/삭제되면 어긋나 **비-결함 RED**. 오늘 definer에서 9-vs-10으로 겪은 형태.
- `core.yml`: `assert len(host.findall('.//testcase')) == 2` — docker-host hygiene 케이스 **2도 리터럴**. 현재 **2 collected**로 일치하나 동일 취약.
- **수정안(Codex, definer식)**: 리터럴 대신 **수집 결과/정책과 대조**. 최소 변경은 `skipped==0 and failure==0 and error==0 and passed>0`(마법 숫자 제거 — `skipped==0`이 이미 "조용한 skip 없음"을 보장하므로 개수 고정의 이득이 작다). 또는 collect-only 개수와 대조. (browser의 `browserOptIn`·`exitCode==0`·`isolatedContainerRemoved`·junit-파싱 비공허성은 유지 — 6만 완화.)

## 비-문제 (한 층 더 확인해 걸러낸 것 — 나의 near-slip 포함)
사용자 교훈("불일치로 보이면 한 층 더: 워킹디렉터리·env 변환·래퍼·조건 분기") 그대로, 아래는 처음엔 의심했으나 다음 층에서 무해로 확정:
- **참조 경로**: 전부 존재. `core.yml`의 `./cmd/inv-node` 등은 `working-directory: services/node-agent` 문맥으로 해석돼 정상(사용자가 먼저 확인).
- **env 이름 A(INV_TEST_EVIDENCE_DIR)**: `test_subject_tenant_boundary`가 hard-access하는 듯 보였으나 **`if os.getenv("INV_TEST_EVIDENCE_DIR"):` 가드 안**이라 미설정 시 그냥 건너뜀 — KeyError 없음. (내가 위험이라 할 뻔함.)
- **env 이름 B(INV_TEST_SERVER_IMAGE)**: `test_server_container`가 쓰지 **browser 3파일은 안 씀**. desktop-browser.yml의 기본값은 browser 시험이 소비 안 함. (내가 위험이라 할 뻔함.)
- **env 소비처 전수**: 워크플로가 SET하는 INV_* 전부 코드 소비처 있음(오타 없음).
- **버전**: playwright 1.62.0(파이썬, apps/web은 playwright 미사용 → 충돌 없음), typescript 5.9.3(npx standalone, apps/web `^5.7.3`와 독립).

## 오늘의 형태 (기록)
경계·귀속 미끄러짐이 **셋 모두에게** 나왔다. 사용자는 오늘 세 번(변수명→변환층, 엉뚱한 워크트리→뒤처짐, 경로→working-directory) 불일치를 의심했다가 문맥 확인 후 정정했다 — 틀린 의심이 워크플로 구조 확인으로 이어진 경우다(옳았던 것으로 적지 않는다). 나도 강제층을 한쪽만 보고 단정했다가 정정했고, 이번 A·B도 한 층 더 안 봤으면 오탐할 뻔했다. **교훈: 불일치로 보이면 한 층 더(working-dir/변환/래퍼/조건 가드/정책 파일)를 확인한 뒤 결론.** 이번 ①은 반대로 여러 층을 확인하고도 남은 **진짜 설정 불일치**다 — 오탐과 진탐을 가르는 것이 바로 그 "한 층 더".

## 인계
워크플로 YAML(`.github/workflows/*`)은 CI 인프라로 Codex가 저자였다(DSN 마스킹·node-runtime). **①②③ 수정은 Codex 소관으로 인계** — 위 수정안 참조. `node_dependent_tests.py`(Claude 소관)로 ①을 처리하는 선택지면 내가 확장 가능. reviewer: Codex. apps/web 미접촉, tests 미수정(전부 소스-읽기/실측, img_probe.xml 삭제).
