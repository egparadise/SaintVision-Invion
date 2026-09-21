---
doc_id: "CODEX-REVIEW-VITEST-MIGRATION-TIMEOUT-20260921"
title: "Vitest moderate audit와 migration-head timeout 독립 검토"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "pending"
updated: "2026-09-21T13:24:00+09:00"
source_of_truth: "Git"
tags: ["security-review", "npm-audit", "vitest", "migration", "timeout"]
---

# Vitest moderate audit와 migration-head timeout 독립 검토

## 범위와 고정점

- 저장소 checkout: `agent/codex/discovery-candidates-contract`, HEAD `eb4366d835081fb6e9c8f75d3e681106fc4a38b1`.
- Claude 수정은 고정 SHA `79487cb60bd85505b47a3c56557ecc7c365714e4`에서 `tests/test_account_integration.py`와 전용 오류 기록만 검토했다. 현재 Codex checkout에 이 수정이 포함됐다고 가정하지 않는다.
- 이 문서는 독립 소스 검토와 지정된 로컬 실행만 기록한다. Claude가 기록한 PostgreSQL 런타임 측정은 별도 표기하고 Codex 재실측처럼 취급하지 않는다.

## npm audit: 두 moderate 항목은 같은 Vitest 취약점의 중복 집계

`apps/web`에서 `npm audit --json`은 exit 1, `moderate=2`를 반환했다. 두 항목은 `vitest@3.2.7`(직접 devDependency)와 그 하위 `@vitest/mocker@3.2.7`(간접 devDependency)이며, 둘 다 GHSA-82fw-gwwq-j7x9 / CVE-2026-84373 하나를 가리킨다. 서로 다른 취약점 두 개가 아니다. 적용 범위는 `>=2.1.0 <4.1.11`; GitHub Advisory가 고친 최소 안정 버전으로 제시하는 것은 Vitest `4.1.11`이다.

취약점은 mock redirect 경로 검증이 없어 노출된 interceptor WebSocket에 redirect mock을 등록할 수 있을 때 개발 서버 프로세스가 임의 로컬 파일을 읽을 수 있는 경로 탐색/파일 읽기다. Advisory는 Vitest browser mode의 자체 RPC는 run token으로 인증되고 기본적으로 원격 공개 경로가 아니라고 구분한다. 저장소는 `vitest`와 `vi.mock` factory를 테스트에만 사용하고 `@vitest/mocker` API를 직접 호출하거나 redirect mock을 등록하는 소스는 발견되지 않았다. Vite 설정은 dev server host를 `0.0.0.0`으로 지정하지만, 일반 `npm run dev`와 Vitest mocker interceptor의 외부 노출 가능성은 같은 경로가 아니다. 현재 테스트 설정과 테스트 호출이 취약한 공개 interceptor 경로를 실제 사용하는지는 설치 코드 및 설정상 확인되지 않았다. 악의적 네트워크 클라이언트로 exploit을 시도하지 않았으므로 런타임 비도달의 동적 증명으로 과장하지 않는다.

`npm audit --omit=dev --json`은 exit 0, 취약점 0건이었다. `npm run build`는 exit 0으로 Vite production bundle을 만들었고, `dist` 산출물에서 `vitest`/`@vitest/mocker` 표식 검색 결과가 없었다. 따라서 현재 감사 항목은 운영 dependency나 배포 bundle에 포함된 취약점이 아니라 테스트 개발 도구의 취약점이다. `package.json`의 범위는 `^3.0.5`라 3.x 안에서의 재설치로는 수정 버전을 받을 수 없다.

### 조치 및 호환성 판단

- 수정이 필요하면 `vitest`를 최소 수정 안정판 `4.1.11` 이상으로 올린다. npm audit의 `fixAvailable=5.0.1`은 최신 제안이며, advisory의 최소 고정판 `4.1.11`과 구분한다.
- 이것은 3→4 메이저 업그레이드다. 현재 Node `v24.17.0`, Vite 해석 버전 `6.4.3`은 Vitest 4의 공식 최소조건(Node 20+, Vite 6+)을 만족한다. 현재 테스트는 `describe`/`it`/`expect`/`vi.mock` 같은 기본 API, Node 실행 및 `happy-dom`을 사용하고 Vitest browser mode, 커버리지 provider, 내부 `vite-node` API 사용은 발견하지 않았다. 따라서 검토한 소스에는 알려진 V4 제거 API와의 직접 충돌이 없다.
- 그럼에도 메이저 업그레이드의 동작 호환성을 실행으로 증명하지 않았다. 적용 전후 `npm test`, `npm run build`를 비교해야 한다. 이 검토에서는 dependency를 바꾸지 않았다.

### 후속 조치 — 패치 적용 및 로컬 검증

같은 날 이어서 `apps/web/package.json`을 `vitest: 4.1.11`로 고정하고 lockfile을 갱신했다. `npm ci` 재설치가 exit 0이었고 `@vitest/mocker`도 4.1.11로 설치됐다. 이후 `npm audit --json`은 exit 0 / vulnerabilities 0, `npm test -- --reporter=dot`은 34 files / 332 tests passed / exit 0, `npm run build`는 Vite 6.4.3 / 90 modules / exit 0이다. 따라서 확인한 테스트 API 및 빌드와의 호환성은 lockfile clean install 후 로컬에서 확인됐다. 운영 CI와 독립 검토는 별도다. 이 조치로 이 기록의 npm audit 로컬 잔여는 닫혔다.

## migration-head timeout SHA 79487cb

### 코드에서 확인한 동작

`tests/test_account_integration.py::test_published_migration_heads_upgrade_without_rewriting`는 `INV_MIGRATION_CHECK_TIMEOUT`(기본 600초)을 바깥 Python subprocess 제한으로 사용한다. 완료 후 자식 exit가 non-zero면 기존대로 assertion failure다. 바깥 제한에서 `subprocess.TimeoutExpired`가 나면 사유가 출력되는 pytest skip이다. Python 인터프리터는 테스트 실행자의 `sys.executable`을 상속한다. `pytest`는 기존 파일 상단에서 import되어 있다.

`tools/check_migration_upgrade.py`는 30개 시작 revision을 코드에 고정 목록으로 둔다. 각 prior마다 새 DB를 만들고 Alembic `upgrade prior`, `upgrade head`, `upgrade head`를 순서대로 subprocess 실행한 다음 최종 head·grant·데이터 보존·definer 정책을 검사하고, 정상적인 함수 흐름에서는 `finally`에서 disposable DB를 지운다. Alembic subprocess 자체에는 개별 timeout이 없다. 목록은 graph에서 자동 수집되지 않으므로 새 revision을 추가해도 prior 검사 케이스가 자동 증가하지 않는다.

### 600초 판정과 성장

600초는 현재 단계의 임시 예산으로는 합리적이다. Claude 커밋 설명/오류 문서는 idle 211초와 CPU 부하(4개 busy process) 324초를 기록했다. 이는 600초의 약 35%와 54%를 사용하며, 관측된 가장 느린 실행에는 276초 여유가 있다. 단, Codex는 PostgreSQL DSN 부재(`INV_TEST_ADMIN_DSN=unset`)로 이 시간을 재현하지 못했다. 두 수치는 Claude 기록이지 Codex 독립 실측이 아니며, 부하 표본도 한 번이다.

성장 설명에는 정정이 필요하다. 실행량은 단순히 현재 prior 개수에만 비례하지 않는다. 각 prior에서 head까지의 migration 적용 경로 길이도 현재 graph revision 수에 따라 커지므로, 현재처럼 30 prior 목록을 유지하면 대략 `O(P×R)`(P=30개 검사 시작점, R=revision 경로 길이)로 증가한다. 새 revision 하나는 각 해당 prior의 head upgrade에서 반복 적용된다. 반면 prior 목록은 고정 코드이므로 R이 증가한다고 P가 자동 증가하지 않는다. 목록까지 매 revision마다 늘리는 설계라면 비용은 더 가파르게 증가할 수 있다. 211/324초 단 두 측정만으로 “몇 개 revision 또는 언제 600초를 넘는지”를 신뢰성 있게 예측할 수 없다. elapsed time과 revision 수를 함께 누적 측정해야 한다.

### timeout-as-skip 안전성 판정

non-zero exit를 failure로 남기고 timeout을 완료되지 않은 검사로 분리한 방향은 맞다. 그러나 현재 설명의 “실제 migration 결함은 budget보다 훨씬 전에 non-zero로 끝난다”, “timeout은 migration defect가 아니다”는 보장되지 않는다. 잘못된 SQL·명시적 assertion 위반은 보통 빠른 non-zero가 되지만, migration이 기다리는 lock, 끝나지 않는 쿼리, 연결 대기, 외부 I/O 정체처럼 결함이 hang으로 나타나면 동일한 600초 timeout→skip 경로를 탄다. 따라서 skip은 “결함 아님” 판정이 아니라 “원인 미결·검증 미완”이어야 한다. 현재 skip 사유의 `not a migration defect` 문구와 커밋 문서의 `never reached its assertions`는 과도하다. 내부 prior 검사는 timeout 전에 일부 수행됐을 수도 있고, 완료되지 않은 것은 전체 외부 회귀 단언이다.

추가 경계: pytest가 `check_migration_upgrade.py` 프로세스를 timeout으로 종료하면 그 도구의 Python `finally` cleanup은 보장되지 않는다. 그 도구는 DB 생성 직후에 cleanup을 `finally`에 두지만, 외부에서 interpreter 자체를 중단하면 실행되지 않는다. 내부 Alembic 자식 프로세스에도 별도 timeout/종료·DB cleanup handoff가 없어 disposable DB나 child process가 남을 가능성이 있다. timeout 경로의 실제 잔여 정리는 Codex가 실측하지 않았다. 강제 timeout을 정상적으로 SKIP으로 확인했다는 Claude 기록만으로 이 위험이 해소됐다고 볼 수 없다.

### 증거 수준과 권고

- 소스 대조: 고정 SHA `79487cb`의 test wrapper와 migration tool을 읽어 확인. 기본 600초, 환경변수 조정, non-zero failure, timeout skip, 30 prior 및 DB-per-prior 구조를 확인했다.
- Claude가 해당 커밋에 기록한 실행: idle 211초 PASS, CPU load 324초 PASS, `INV_MIGRATION_CHECK_TIMEOUT=5` SKIP. 이 검토에서 재실행하지 못했다. 명령 원문/JUnit/DB 실행 산출물이 커밋에 포함되지는 않았다.
- Codex 환경: `.venv\Scripts\python.exe`가 존재하지만 `INV_TEST_ADMIN_DSN`이 설정되지 않아 실제 PostgreSQL 전체 회귀를 실행하지 않았다.
- 제안: 600초는 임시 한도로 허용하되 timeout은 “inconclusive/incomplete”로만 표현하고 migration defect가 아니라는 주장을 제거한다. 각 Alembic 단계에 명시적 timeout/진행 prior 기록/종료 후 소유 DB 회수를 보장하고, 비정상 중단 시 별도 cleanup backstop을 둔다. timeout이나 kill로 인한 cleanup이 검증되기 전에는 skip 경로가 안전하다고 승인하지 않는다.

증분화는 현실적으로 가능하지만 단순히 한 DB를 한 번만 앞으로 움직이는 변경은 아니다. 현 시험은 각 역사적 시작 상태에서 head upgrade, 재실행 idempotency, 과거 데이터 보존, 권한·definer 정책을 검사한다. 이를 유지하려면 prior 스냅샷 DB/template를 순차 구축해 checkpoint별 clone을 만들고 각 clone을 head로 승격하는 구조가 후보이며, branch/merge revision 및 특별 보존 데이터 fixture를 보전해야 한다. 대안은 전체 prior 대신 의미 있는 published branch head/보존 경계만 선정하는 검증 범위 변경이다. 어느 쪽이든 측정만으로 교체하지 말고 기존 30개 전수 경로와 새 방식의 결과 집합을 대조하는 전환 시험이 필요하다. 따라서 증분화는 현실적이나 작고 무위험한 patch는 아니다.

## 검증 명령 요약 (KST 2026-09-21, Codex)

| 명령/입력 | 결과 | 범위 |
|---|---|---|
| `cd apps/web; npm audit --json` (패치 전) | exit 1; moderate 2 | 두 이름은 동일 GHSA를 지칭 |
| `cd apps/web; npm audit --omit=dev --json` | exit 0; 0 vulnerabilities | production dependency set |
| `cd apps/web; npm ls vitest @vitest/mocker --all` (패치 전) | Vitest 3.2.7 / mocker 3.2.7 | dependency ancestry |
| `cd apps/web; npm run build` | exit 0; Vite 6.4.3, 90 modules | production build; dist search had no Vitest marker |
| `node --version`; `npm view vitest@4.1.11 peerDependencies engines` | Node 24.17.0; Vite ^6/^7/^8, Node 20/22/24+ | candidate compatibility metadata |
| `cd apps/web; npm audit --json` (패치 후) | exit 0; 0 vulnerabilities | lockfile including dev dependencies |
| `cd apps/web; npm ci` (패치 후) | exit 0; 128 packages audited, 0 vulnerabilities | lockfile clean install |
| `cd apps/web; npm test -- --reporter=dot` | exit 0; 34 files / 332 tests passed | Vitest 4.1.11 |
| `cd apps/web; npm run build` (패치 후) | exit 0; Vite 6.4.3, 90 modules | production build |
| `& .\\.venv\\Scripts\\python.exe -c "...migration_graph.chain()..."` | exit 0; 60 graph revisions, head `0044_model_registry_binding` | source graph only, no PostgreSQL |
| AST count of `check_migration_upgrade.py` `priors` tuple | exit 0; 30 selected prior starts | source only |

## 다음 담당

- Vitest 취약점 dependency remediation은 로컬로 수정·검증 완료; 동일 SHA 독립 검토와 CI 실행은 외부 대기다.
- migration timeout 문구/cleanup hardening 및 incremental prototype은 migration tool owner가 수행하고 Codex가 고정 SHA로 독립 검토한다. 실제 PostgreSQL proof에는 소유를 명시한 disposable DB만 사용한다.
