# 2026-09-22 Codex hosted CI wiring and first-run forecast

## 기준

- 통합 tip: `92c138fd83eecd26cdf05c6d2d1fe84c0b6dd131`에서 워크플로를 읽었고, 이후 이 기록을 추가하는 별도 착지에서 재검증한다.
- 조사자: Codex
- 범위: `.github/workflows/{backend,core,desktop-browser,docs,frontend}.yml`, 새 도구 배선, trigger/path 조건
- hosted GitHub Actions 실행 결과는 아직 없다. 아래는 YAML과 소스의 정적 판정이다.

## 다섯 workflow의 trigger와 실제 명령

| workflow | push trigger | pull request | 주요 실행 | 새 PC 주의 |
|---|---|---|---|---|
| `backend.yml` | `main`, `integration/all-agents-unified` | path 제한 없음 | schema export, offline/DB migration, full pytest, PostgreSQL no-skip gate | 다른 브랜치 push만으로는 안 뜸 |
| `core.yml` | `main`, `integration/all-agents-unified` | path 제한 없음 | Go race/build, Docker image/API, PG integration, core pytest, LAN/image lane, Go/TS checks | Docker·Go·PG를 실제로 처음 사용 |
| `desktop-browser.yml` | `main`, `integration/all-agents-unified` | path 제한 없음 | Playwright Chromium, Vite/proxy, Uvicorn/PG VF runner, web-container test | 실제 브라우저와 HTTP가 처음 실행 |
| `docs.yml` | `main`, `integration/all-agents-unified` | path 제한 없음 | docs/contract/frontend scanners, ontology semantic check, ontology, bundle | 이번 새 semantic check가 여기서 실행 |
| `frontend.yml` | 위 브랜치이면서 `apps/web/**`, `contracts/**`, workflow 자체 변경 | 같은 path 조건 | `npm ci`, Vitest, `contracts:check`, build | docs/ontology-only push에서는 실행되지 않음 |

다섯 파일 모두 `workflow_dispatch`와 schedule은 없다. 수동 실행을 전제로 한 버튼은 현재 없다.

새 PC에서 브랜치를 `integration/all-agents-unified`로 유지하면 push workflow가 시작된다. 다른 이름의 작업 브랜치에 push하면 push workflow는 시작되지 않으며, PR을 열어야 PR workflow가 시작된다. 단 frontend PR도 `apps/web`, `contracts`, 또는 frontend workflow 변경이 없으면 path filter에서 제외된다.

## 새 도구의 배선 상태

- `tools/check_ontology_generation.py`: `docs.yml`에 **게이트로 배선됨**. 임시 복제본 생성 후 RDF graph 비교.
- `tools/check_anchor_weight.py`: workflow에 직접 배선되지 않음. 거버넌스상 정적 proxy **report-only/온디맨드**이며 `--strict`는 사람의 별도 선택이다. 자기시험 파일은 full pytest 수집 대상이지만 도구 CLI 실행과는 다르다.
- `tools/run_real_browser_acceptance.py`: workflow에 직접 배선되지 않음. 공식 **온디맨드 실측 도구**다. CI의 `desktop-browser.yml`은 별도 `run_vf_security_tests.py`와 실제 browser test 모음을 실행한다. 두 실행을 같은 증거로 세지 않는다.
- `tools/check_contract_bindings.py`, `tools/check_frontend_integrity.py`: `docs.yml`에 배선됨.

## 첫 hosted CI에서 예상할 위험

예측은 실패 확정이 아니라 첫 실행에서 처음 드러날 환경·실행 경계다.

1. **docs**: 현재 로컬 tip에서 docs/ontology/semantic graph가 통과했으므로 상대적으로 GREEN 예상. 다만 hosted Python 3.12 의 dependency 설치와 문서 encoding이 첫 환경 차이다.
2. **backend**: Python 3.12·3.14 matrix와 실제 PostgreSQL에서 PG 테스트가 skip 대신 실행된다. `CREATE ROLE`/`GRANT` 권한, migration 전체 실행시간(현재 도구는 revision마다 새 DB를 재생), 3.12 호환성이 첫 RED 후보다. 실패하면 제품 결함과 CI DB 권한/시간 제한을 먼저 분리해야 한다.
3. **core**: Go race/build, Docker build/pull, PostgreSQL 통합, LAN/image lane이 이 호스트에서 한 번도 함께 돌지 않았다. Go 1.27.1 toolchain 제공, Docker pull/network, 25분 job timeout, no-skip JUnit gate가 가장 큰 위험이다.
4. **desktop-browser**: 실제 Chromium, Uvicorn TCP, Vite proxy, disposable PostgreSQL과 exact journey-set gate가 처음이다. browser dependency, auth/proxy/port, journey 누락·skip이 첫 RED 후보다. `run_real_browser_acceptance.py` 자체가 CI에서 돈다고 예측하지 않는다.
5. **frontend**: 올바른 path가 포함된 SHA/PR에서만 실행된다. npm registry 설치, Vitest, shared contract check, TypeScript/Vite build가 범위다. ontology-only SHA에서는 아예 실행되지 않는 것이 정상이며, 이를 전체 CI green으로 세면 안 된다.

## 종료 판단에 필요한 증거

CI가 열리면 같은 SHA에 대해 다음을 확인해야 한다.

- 다섯 workflow의 run URL, workflow/job conclusion, commit SHA
- 각 job의 실제 collected/passed/skipped/error/failure 수와 JUnit/proof artifact
- backend/core의 PostgreSQL no-skip 및 core LAN/browser opt-in gate 결과
- desktop browser의 `evidenceStatus=complete`, exact journey 집합, skipped/error/failure 0
- docs의 semantic ontology check 출력과 구체적 diff 없음
- frontend가 path filter 때문에 실제로 실행됐는지 여부

workflow가 존재하거나 queued 된 것만으로 실행 증거를 만들지 않는다. 이 문서는 hosted CI 실행 전 예측이며, 실제 결과가 나오면 예측과 관측을 분리해 갱신해야 한다.
