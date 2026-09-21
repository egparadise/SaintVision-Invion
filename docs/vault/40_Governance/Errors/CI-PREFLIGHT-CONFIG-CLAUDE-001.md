---
doc_id: "CI-PREFLIGHT-CONFIG-CLAUDE-001"
title: "CI 사전 점검 — 결제 열기 전 설정-원인 빨간불 제거. 발견·인계(워크플로는 Codex)"
version: "1.3.1"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T21:50:00+09:00"
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

### ② [철회 — v1.1.0 정정] go-version 1.27.1은 빨간불 아님
**철회한다.** 아래 v1.1.0 정정 참조. Go 1.27.1은 출시된 최신 stable이라 `core.yml:39`은 정상이다. Codex 인계 목록에서 제외.

## 취약(현재는 맞으나 드리프트 시 빨간불 — definer 9-vs-10 형태)

### ③ 하드코딩된 개수 — 파일에서 세지 않고 박아둠
- `desktop-browser.yml`: `assert proof['tests'] == {failure:0, error:0, skipped:0, passed:6}` — **6은 워크플로에 박힌 리터럴**. 현재 실측 **6 tests collected**로 일치하나, browser 여정이 하나 추가/삭제되면 어긋나 **비-결함 RED**. 오늘 definer에서 9-vs-10으로 겪은 형태.
- `core.yml`: `assert len(host.findall('.//testcase')) == 2` — docker-host hygiene 케이스 **2도 리터럴**. 현재 **2 collected**로 일치하나 동일 취약.
- **수정안**: 아래 「## ③ [v1.3.0 정정]」 참조(유도 방식 — 이름 집합 대조). ~~최소 변경 `passed>0`~~ 안은 철회됨(삭제 탐지력 상실). *(이 취약 항목의 진단은 유효; 유효 수정안은 v1.3.0 섹션 한 곳.)*

## 비-문제 (한 층 더 확인해 걸러낸 것 — 나의 near-slip 포함)
사용자 교훈("불일치로 보이면 한 층 더: 워킹디렉터리·env 변환·래퍼·조건 분기") 그대로, 아래는 처음엔 의심했으나 다음 층에서 무해로 확정:
- **참조 경로**: 전부 존재. `core.yml`의 `./cmd/inv-node` 등은 `working-directory: services/node-agent` 문맥으로 해석돼 정상(사용자가 먼저 확인).
- **env 이름 A(INV_TEST_EVIDENCE_DIR)**: `test_subject_tenant_boundary`가 hard-access하는 듯 보였으나 **`if os.getenv("INV_TEST_EVIDENCE_DIR"):` 가드 안**이라 미설정 시 그냥 건너뜀 — KeyError 없음. (내가 위험이라 할 뻔함.)
- **env 이름 B(INV_TEST_SERVER_IMAGE)**: `test_server_container`가 쓰지 **browser 3파일은 안 씀**. desktop-browser.yml의 기본값은 browser 시험이 소비 안 함. (내가 위험이라 할 뻔함.)
- **env 소비처 전수**: 워크플로가 SET하는 INV_* 전부 코드 소비처 있음(오타 없음).
- **버전**: playwright 1.62.0(파이썬, apps/web은 playwright 미사용 → 충돌 없음), typescript 5.9.3(npx standalone, apps/web `^5.7.3`와 독립).

## 오늘의 형태 (기록)
경계·귀속 미끄러짐이 **셋 모두에게** 나왔다. 사용자는 오늘 세 번(변수명→변환층, 엉뚱한 워크트리→뒤처짐, 경로→working-directory) 불일치를 의심했다가 문맥 확인 후 정정했다 — 틀린 의심이 워크플로 구조 확인으로 이어진 경우다(옳았던 것으로 적지 않는다). 나도 강제층을 한쪽만 보고 단정했다가 정정했고, 이번 A·B도 한 층 더 안 봤으면 오탐할 뻔했다. **교훈: 불일치로 보이면 한 층 더(working-dir/변환/래퍼/조건 가드/정책 파일)를 확인한 뒤 결론.** 이번 ①은 반대로 여러 층을 확인하고도 남은 **진짜 설정 불일치**다 — 오탐과 진탐을 가르는 것이 바로 그 "한 층 더".

**그리고 나의 ② 슬립은 다른 급이다(구별해 기록).** 지금까지의 미끄러짐은 전부 **대리 신호를 목표로 착각**(초록≠도달, 배선≠통과, tip/트리/인터프리터 못 박기)하는 형태였고, 공통 처방은 "저장소·아티팩트를 한 층 더 본다"였다. 그런데 ②는 **내 지식 경계를 세계의 경계로 착각**한 것이라, **저장소를 아무리 읽어도 못 잡는다.** 처방이 다르다 — 안이 아니라 **밖(go.dev)을 조회**해야 한다. 그래서 위 v1.1.0에 3-갈래 규칙([측정]/[외부조회]/[미확인추정])을 별도로 세웠다. 사용자의 세 슬립과 같은 급의 사례로 나란히 남긴다.

**v1.3.0 추가 — 사용자의 5번째, 그리고 워크플로 자체의 미끄러짐.** ③를 다듬다 사용자가 browser 파일의 `def test`를 세어 **5**라 보고 단언의 `6`과 안 맞는다고 의심했다 — **틀렸다**(실 수집 6, 내 실측이 옳았다: 한 함수가 `invalid_token`으로 2항목). **함수 정의라는 대리 지표를 수집 항목이라는 목표로 센 것** — 오늘 우리가 남에게 계속 지적한 형태를 사용자가 다섯 번째로 한 것이다. 그런데 그 오류가 **진짜**를 드러냈다: 6은 여정 수가 아니라 항목 수이고, **단계명 "six journeys"는 여정을 말하나 실제로는 항목을 센다** — 이름-vs-세는대상 미끄러짐이 워크플로에 박혀 있었다. 그리고 나도 여기서 미끄러졌다: ③ 문안을 "숫자 폐기(`passed>0`)"로 냈는데, 그건 **삭제 탐지력을 버리고** 내가 인용한 definer 선례(숫자를 **유도**로 바꿈)와 반대였다. 셋 다 같은 축이다 — **대리(함수정의/개수/`passed>0`)를 목표(여정 집합/유도된 진실)로 착각**. 처방도 하나 — 진실의 원천(여정 이름 집합)에서 유도한다.

## v1.1.0 정정 — ②는 빨간불 아님, 그리고 외부 사실 3-갈래 규칙
**②를 철회한다.** 사용자가 go.dev 배포 목록을 조회하니 **`go1.27.1`·`go1.27.0`이 stable**로 있고 `1.27rc1~rc3`도 있다. 오늘은 2026-09-21이고 Go는 반년 주기라 1.27은 이미 나왔다. 그러니 `core.yml:39 go-version: '1.27.1'`은 정상이고 setup-go가 받아온다. **② 삭제.**

**왜 틀렸나(중요)**: 나는 "Jan 2026 지식 기준 미출시"라고 적었다. 그건 **저장소를 읽은 게 아니라 내 지식 시점을 세계의 상태로 놓은 것**이다. "소스-읽기 유력"으로 정직하게 표시했지만, **표시만으로는 부족하다 — 저장소 밖의 사실은 소스-읽기로 확인되지 않는다.** 그리고 이건 다른 것들과 달리 **저장소를 아무리 읽어도 스스로 못 잡는다. 반드시 바깥을 조회**해야 한다.

**규칙(앞으로) — 외부 사실에 기대는 판단은 3-갈래로 분리해 적는다:**
1. **[측정]** 저장소에서 실측한 것(예: junit 22/22 skip). 근거로 쓴다.
2. **[외부조회]** go.dev·PyPI·릴리스 목록 등 바깥을 조회해 확인한 것(예: go1.27.1 stable — 사용자 go.dev 조회). 근거로 쓴다.
3. **[미확인추정]** 내 지식에서 나온 것. **근거로 쓰지 말고 조회 대상으로만 남긴다.** 외부 버전/가용성/현재-세계-상태 판단은 전부 여기서 시작해 (2)로 승격돼야 근거가 된다.

즉 "go 1.27.1 미출시"는 (3)이었는데 내가 (1)처럼 근거로 썼다. 올바른 행동은 `go-version` 같은 항목을 만나면 **먼저 go.dev/dl을 조회**(2)한 뒤 판정하는 것이다. (버전 pin·외부 이미지 태그·패키지 가용성이 이 부류다.)

**규칙 보강 (4) — 빈 결과는 사실이 아니다 (측정 도구가 조용히 실패한다):** 아무것도 안 나왔다는 것은 "없다"일 수도, "명령이 실패했다"일 수도 있다. 사용자가 방금 워크플로의 node_dependent 사용 여부를 훑다가 **빈 결과를 얻었는데**, 원인은 Git Bash 경로 변환이 `origin/branch:path` 인자를 역슬래시·세미콜론으로 망가뜨려 `git show`가 전부 실패했고 stderr를 버려 조용히 빈 결과가 된 것이었다(`MSYS2_ARG_CONV_EXCL='*'`로 다시 하니 backend.yml이 그 목록을 쓴다는 판정이 맞았다). 오늘 파이프 뒤 종료코드로 한 번, 경로 변환으로 또 한 번 — **뿌리가 같다: 측정 도구 자체가 조용히 실패**. 그래서 빈 결과를 사실로 읽기 전에 **① 반드시 무언가를 찾아야 하는 대조군에서 같은 명령이 도는지, ② 종료코드·stderr가 성공인지**를 확인한다. (측정으로 확정하기 전 계측을 확정한다 — `memory:empty-output-is-not-evidence`.)

**규칙 보강 (5) — 정정은 결론이 읽히는 모든 자리를 고쳐야 끝난다 (문서 층위의 배선≠통과):** 정정문을 쓰는 것으로 끝내지 말고, 그 결론이 **인용·요약된 자리를 전부 찾아 함께 고친다**. 문서 안에서 결론이 두 번 이상 적히면 갱신 안 된 사본이 남고, **행동하는 쪽은 대개 요약(인계 목록)을 읽는다** — 그러면 정정을 기록해도 행동 대상은 정정 이전을 지시한다("고쳤는데 고친 것이 읽히는 자리에 없음"). 오늘 하루 쫓은 "초록≠도달, 배선≠통과"가 문서 층위로 한 번 더 나온 형태다(이 문서 자체가 v1.3.0에서 그랬다 — 정정은 별도 섹션에, 인계 목록엔 철회된 `passed>0`이 남아 Codex가 그것을 집어갈 뻔했다; 사용자가 문안을 직접 열어 잡았다). **처방: 유효 지시는 한 곳에만 두고 나머지는 그곳을 가리키게 한다.** 인계 문서는 "유효 수정안 = 한 섹션" 원칙으로 쓴다.

## v1.2.0 — ① 배선→통과 실증 (before-red / after-green) + Codex 적용 패치문안
①은 "junit 22/22 skip"까지만 [측정]했었다 — 그건 배선(skip이 있다)이지 **통과 실패(워크플로가 실제로 RED)**를 보인 게 아니다. 오늘의 배선≠통과 구별대로, 워크플로의 **단언 단계 코드를 그대로 그 junit에 먹여** 실패까지 보이고, 수정 후 통과까지 보였다.

**실증 (workflow의 실제 단언 코드로, .venv 실행):**
| | junit | `backend.yml` 단언(`assert not findall('.//skipped')`) | `core.yml` 단언(`testcase 있음 + failure/error/skipped 없음`) |
|---|---|---|---|
| **BEFORE**(통과대역 `test_model_execution_registry` 7 + 3 image 파일) | testcases=29, skipped=22 | `AssertionError` **exit 1 (RED)** | `AssertionError` **exit 1 (RED)** |
| **AFTER**(3 image 파일 수집 제외) | testcases=7, skipped=0 | **exit 0 (GREEN)** | **exit 0 (GREEN)** |

기계 증명: `pytest tests/integration --collect-only --ignore=<3 image 파일>` → 그 3파일 항목 **22→0**(기본 비명시 수집에서 제거됨, browser가 이미 그렇게 제외되는 것과 동일). 즉 **수정안(수집 제외)이 그 RED의 원인을 실제로 없앤다** — 고치기 전 빨강·고친 뒤 초록 양쪽 확인.

**수정 조합 판단(근거와 함께 — Codex 최종 결정)**: browser 3파일은 이미 backend·core **양쪽에서 typed `--ignore`**로 제외돼 있다. image 3파일도 **같은 패턴으로 양쪽에 `--ignore` 추가**가 최소·정합(ⓐ). 주의: `core.yml`은 `node_dependent_tests.py` 목록을 **안 쓰므로**(browser만 하드코딩 --ignore) core는 반드시 명시 --ignore가 필요하다 — 즉 ⓑ(computed)만으로는 core를 못 덮는다. computed 순정 경로(ⓑ)를 원하면: `node_dependent_tests.py`는 "test_node_runtime 도달"만 계산하므로 image-env(`INV_WEB_IMAGE`/`INV_UPGRADE_AGENT_IMAGE`/`INV_STORAGE_SOURCE_ROOT`) skipif를 계산하는 **분류를 내가(Claude) 추가**하고 **core.yml도 그 목록을 채택**해야 완결된다(더 큰 변경). **내 권고: ⓐ(양쪽 --ignore, browser와 동일 패턴)** — 최소 변경이고 이미 존재하는 browser 처리와 정확히 같은 형태다. 도구의 "computed, not typed" 선호가 걸리나, browser가 이미 typed --ignore이므로 새 안티패턴을 들이는 게 아니라 기존 제외를 확장하는 것뿐이다.

**Codex 적용 패치문안 ⓐ (양쪽 --ignore 추가):**
- `backend.yml` Tests 스텝의 pytest 줄 끝에 추가:
  ```
  --ignore=tests/integration/test_web_container.py --ignore=tests/integration/test_workspace_upgrade.py --ignore=tests/integration/test_lan_storage_install.py
  ```
- `core.yml` 최종 `python -m pytest --junitxml=dist/core-tests.xml …` 줄 끝에 **같은 3개 --ignore** 추가.
(둘 다 이미 browser 3개 --ignore가 붙어 있는 그 자리에 나란히.)

## ③ [v1.3.0 정정] 유도로 간다 — 숫자를 버리지 말고 진실의 원천에서 유도
**내 v1.2.0 문안(`passed>0`)을 철회한다.** 그건 조용한 skip은 막지만 **삭제 탐지력을 잃는다**: 누가 여정을 하나 지우면 항목이 6→5, `skipped==0`, `passed>0`이라 그대로 초록 — 삭제가 안 보인다. 그리고 definer 선례와 어긋난다. definer에서 한 것은 **숫자를 버린 게 아니라 박은 숫자를 수집 결과·정책 파일이라는 진실의 원천에서 유도**하도록 바꾼 것이다. 내 문안은 유도가 아니라 폐기였다 — 선례를 인용하고 선례와 다른 짓을 했다.

**그 과정에서 드러난 진짜(이름 vs 세는 대상)**: browser는 **여정 5개**인데 **수집 항목 6개**다(`test_full_studio_login_project_approval_and_logout`가 `invalid_token` 두 값으로 parametrize돼 2항목). 그런데 단계명은 "**Require all six browser journeys to execute**" — **여정 여섯을 요구한다고 적혔으나 실제 세는 것은 여정이 아니라 수집 항목**이다. 이름이 주장하는 것과 세는 대상이 다르다 — 워크플로 자체의 경계·귀속 미끄러짐.

**택: (b) 여정 이름 집합을 진실의 원천으로.** (a)수집수==passed는 마법 숫자를 없애나 삭제 시 양쪽이 같이 줄어 못 잡는다. (b)는 **삭제·이름변경·skip을 다 잡고** 단계명의 "여정"과도 맞는다(parametrize로 항목이 갈라져도 여정 수 불변). definer의 정책-파일 = 진실의 원천과 같은 형태다. 여정 이름(구분 함수명)이 그 원천이다.

**Codex 적용 문안 — desktop-browser.yml "Require … browser journeys" 스텝** (단계명도 함께 고침: "six"는 틀림 → 숫자 대신 정본 집합):
```python
import json, re
from pathlib import Path
proof = json.loads(Path('.work/vf-desktop-browser-ci.json').read_text())
assert proof['browserOptIn'] and proof['exitCode'] == 0
assert proof['subprocessExitCode'] == 0 and proof['evidenceStatus'] == 'complete'
assert proof['isolatedContainerRemoved']
t = proof['tests']
assert t['failure'] == 0 and t['error'] == 0 and t['skipped'] == 0, t
# journey = 구분되는 test 함수(파라미터 접미사 제거). 6은 항목 수, 여정은 5.
cases = json.loads(Path(proof['xmlPath']).with_name('case-identities-private.json').read_text())
journeys = {re.sub(r'\[.*\]$', '', c['name']) for c in cases}
EXPECTED_JOURNEYS = {
    'test_actual_browser_quorum_snapshot_and_no_duplicate_vote',
    'test_actual_browser_stale_run_and_revoked_review_are_rejected',
    'test_browser_real_catalogue_owner_scope_and_revocation',
    'test_browser_real_committed_model_and_current_permission',
    'test_full_studio_login_project_approval_and_logout',
}
assert journeys == EXPECTED_JOURNEYS, f'browser journeys drifted: {journeys ^ EXPECTED_JOURNEYS}'
```
단계명: `Require all six browser journeys to execute` → `Require every canonical browser journey to execute`(또는 `all five …`). 이제 여정 삭제(집합 부족)·추가(집합 초과)·이름변경(불일치)·skip(`skipped==0`)이 전부 RED. (harness가 `case-identities-private.json`을 junit 옆에 쓰고 proof에 `xmlPath`가 있어 워크플로가 읽을 수 있다; `evidenceStatus=='complete'`면 그 파일이 존재.)

**Codex 적용 문안 — core.yml docker-host 줄** (같은 유도):
- OLD: `assert len(host.findall('.//testcase')) == 2, 'Both Docker host hygiene cases must execute'`
- NEW:
  ```python
  host_cases = {c.get('name') for c in host.findall('.//testcase')}
  assert host_cases == {
      'test_prune_never_force_removes_a_running_concurrent_container',
      'test_prune_removes_old_exited_residue_but_spares_a_recent_one',
  }, f'docker-host cases drifted: {host_cases}'
  ```
  (바로 다음의 `assert not any(... failure/error/skipped)` 유지 — 돌고 통과·skip 없음을 함께 보장.)

**주(선택)**: 두 `EXPECTED_*` 집합은 워크플로 인라인이지만 definer식으로 작은 정책 파일(예: `tools/definer-policy.json` 계열)로 빼면 단일 원천이 된다 — 인라인은 최소 변경, Codex 판단.

## 인계
워크플로 YAML(`.github/workflows/*`)은 CI 인프라로 Codex가 저자였다(DSN 마스킹·node-runtime). **②는 철회. ①③만 인계**(위 패치문안·판단 재료 첨부):
- **①(image-opt-in skip → no-skipped RED)** — [측정]된 사실. **재현법 함께 인계**: `.venv python -m pytest tests/integration/test_web_container.py tests/integration/test_workspace_upgrade.py tests/integration/test_lan_storage_install.py --junitxml=<path>` → junit `testcases=22, skipped=22, failure=0, error=0`; 이 3파일은 node_dependent 목록에 없어 backend(`$IGNORES`+browser)·core(browser만) collect에 포함됨. **수정안 2개**: ⓐ 워크플로에서 browser처럼 제외(`--ignore=…`) — **Codex 소관**; ⓑ `node_dependent_tests.py`(**Claude 소관**)에 이 opt-in-이미지 부류를 추가해 backend에서 자동 제외 — 단 core.yml은 그 목록을 안 쓰므로 core는 별도 제외 필요. Codex가 어느 쪽이 정합적인지 판단하고, ⓑ면 내가 확장한다.
- **③(하드코딩 개수)** — **유효 지시는 위 「## ③ [v1.3.0 정정]」 섹션 하나뿐이다**(browser 여정 이름 집합 대조 + docker-host 케이스 이름 집합 대조, 실제 정본 이름 박음). 이전에 여기 있던 `passed>0` 안은 **철회됨**(삭제 탐지력 상실 — 그 섹션 참조). Codex는 그 섹션의 문안을 적용한다.

reviewer: Codex. apps/web 미접촉, tests 미수정(전부 소스-읽기/실측, img_probe.xml 삭제).
