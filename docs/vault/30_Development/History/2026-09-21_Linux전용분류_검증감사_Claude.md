---
doc_id: "LINUX-GATE-AUDIT-CLAUDE-001"
title: "Linux 전용 분류 검증 감사 — 왜 Linux인가, 소스 근거인가 추정인가. 3부류"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T17:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["verification-boundary", "linux-gate", "skipif", "audit", "measure-not-guess", "node-runtime"]
---

# Linux 전용 분류 검증 감사

내가 "Linux 필요"로 남긴 항목들이 **실제로 검증된 것인지(소스 근거) 아니면 안 돌아가서 그렇게 넣은 것인지(추정)**를 항목별로 확인했다. 오늘 이미 "Linux 필요"라던 5파일 88건이 실은 PG-only였고 exit 4는 오타였으니, 이 분류 자체를 의심해야 한다. **방법**: 각 시험의 skip 메커니즘·사유를 소스로 읽고, PG-only로 보이는 후보는 **일회용 PG를 띄우고 platform marker를 임시 우회해 Windows에서 실제로 돌려** 진짜 게이트를 드러냈다(추측 아니라 측정). 끝나고 내 라벨 PG 철거·baseline 48/79/11 복원·git 원복. `.venv`, 종료코드는 파이프 없이.

## 게이팅 메커니즘 (소스)
두 종류의 실제 게이트:
1. **POSIX 권한 모델** — `path.chmod(0o600/0o400)` 후 "private file은 소유자만 읽힘"을 단언. Windows에서 `chmod`는 **no-op**이라 그 보안 속성을 검증할 수 없다. `LinuxFileCredentials`(Linux 전용 자격 backend)도 같은 계열.
2. **Linux Node-agent Docker 런타임** — 공유 fixture `node_runtime`(`tests/integration/test_node_runtime.py:47`):
   ```
   if os.getenv("INV_RUN_NODE_TESTS") != "1": pytest.skip("Real Linux Docker runtime explicitly enabled only in isolated CI")
   binary = os.environ["INV_NODE_BINARY"]; image = os.environ["INV_NODE_IMAGE"]
   assert Path(binary).is_file() and image.startswith("sha256:")
   ```
   즉 `INV_RUN_NODE_TESTS=1` + 실제 node-agent **binary** + 컨테이너 **image**(sha256)를 요구하는 CI 전용 opt-in. `sys.platform != linux` marker는 이 위에 얹혀 있다.

## 측정 (추측 뒤집기)
PG-only로 보이던 후보(resume_input_readiness·business_handoff·output_ingestion — 대부분 `conn.execute`뿐)에 대해 일회용 PG를 띄우고 platform marker를 `False`로 임시 우회해 Windows에서 실행:
- 셋 다 **여전히 skip** — marker가 유일 게이트가 아니었다. `-rs`로 사유 확인: **"Real Linux Docker runtime explicitly enabled only in isolated CI"**(위 `node_runtime` fixture, 셋 다 `from test_node_runtime import node_runtime`).
- `test_workspace_checkout`은 marker 우회 시 **fixture 내부 `if sys.platform != "linux"`**에서 걸려 5 error.
- **결론: PG-only 가설은 틀렸다.** 이들은 PG가 아니라 **node-runtime Docker opt-in**이 진짜 전제다. (오늘 funnel과 반대 결과 — 억지로 Bucket 3에 넣지 않았다.)

## 3부류 (항목별)

### ① Linux 필요 · 소스 근거 있음 (concrete Linux primitive)
| 파일 | 무엇이 Linux인가 | 근거(소스) |
|---|---|---|
| test_snapshots | POSIX private-dir 권한 | `chmod(0o600/0o400)` ×3 — Windows no-op |
| test_results | POSIX private storage 권한 | `chmod` ×2 |
| test_credential_backend | Linux 파일 자격 backend + POSIX 권한 | `LinuxFileCredentials` import ×3, `chmod` ×5 |
| test_credential_provision | POSIX 권한 | `chmod` ×3 |
| test_backup_publication | private Linux 파일 권한 | docstring "Actual private Linux files", `chmod` ×3 |
| test_workspace_recovery | POSIX 권한(scoped handles) | `chmod` ×4 |
| test_lan_storage_install | POSIX 권한 + `INV_STORAGE_SOURCE_ROOT` env | `chmod` ×2, env 전제 |

이들은 **권한 모델 자체가 검증 대상**이라 Windows에서 의미가 없다 — 추정이 아니라 소스에 박힌 Linux 의존.

### ② Linux Node-agent Docker 런타임 필요 (전제는 소스로 확정, 그러나 "Linux 호스트 강제"는 추정)
| 파일 | 게이트 | 비고 |
|---|---|---|
| test_workspace_terminal | `node_runtime` (+"Linux PTY") | PTY는 node 컨테이너 내부 |
| test_workspace_start / _api / _resume | `node_runtime` | Workspace 실행 |
| test_model_node | `node_runtime` | "Real Linux Node model execution" |
| test_business_handoff | `node_runtime` | restricted Node |
| test_resume_input_readiness | `node_runtime` | recovery runtime |
| test_output_ingestion | `node_runtime` | private provider |
| test_developer_workloads | `node_runtime`(+chmod ×1) | Python Node 실행 |
| test_results | `node_runtime`(+chmod ×2) | ①·② 혼재 |
| test_workspace_checkout | fixture `sys.platform != linux` | 구체 primitive 미확인(추정) |
| test_recovery_drill | Docker `/var/lib/postgresql/data:rw` + "Linux private backup path" | Docker+Linux 경로 |

**구분(사용자 질문의 핵심)**: 이들의 **확정된 전제는 "Linux Node-agent Docker 런타임 opt-in"**(`INV_RUN_NODE_TESTS`+node binary+image)이다 — 소스(fixture)로 확정. 그러나 그 위의 **`sys.platform == linux` 호스트 강제**가 독립적으로 필요한지(예: Windows+Docker Desktop에서 Linux node-agent 이미지로 가능한지)는 **확인되지 않은 추정**이다. node-agent는 Go/Linux 컨테이너라 Linux일 가능성이 높으나, 나는 그것을 별도로 입증하지 않았다. 즉 "Docker node-runtime 필요"는 검증됨, "Linux 호스트 아니면 절대 불가"는 미검증.

### ③ 다시 보니 Linux 불필요 (지금 처리 가능)
**없음.** PG-only로 보이던 후보는 측정 결과 모두 `node_runtime` Docker 게이트를 갖고 있었다. 오늘 funnel처럼 억지로 채우지 않는다 — "없으면 없다고 보고".

## v1.1.0 보강 — CI가 열리면 무엇이 자동 강제되나 (CI-fail 분기. 내가 v1.0.0에서 놓친 것)
`node_runtime` fixture에는 **CI 분기**가 있다(놓쳤다): `INV_RUN_NODE_TESTS != "1"`일 때 로컬이면 `pytest.skip`이지만 **CI면 `pytest.fail("CI must enable real Node execution tests")`**. 즉 이 항목들은 CI에서 조용히 건너뛰어지지 않고 **강제된다**. 우리가 오늘 여러 곳에 만든 "전제 불충족 vs 실제 결함" 구분층이 여기엔 **원래부터** 있었다.

**전수 확인 — CI-fail(skip 아닌 fail) 분기를 가진 게이트는 정확히 셋뿐**:
| 게이트 | 위치 | CI에서 강제하는 전제 |
|---|---|---|
| PG (combined) | `tests/conftest.py:64` | `INV_TEST_ADMIN_DSN` |
| PG (integration) | `tests/integration/conftest.py:29` | `INV_TEST_ADMIN_DSN` |
| node-runtime | `tests/integration/test_node_runtime.py:50` | `INV_RUN_NODE_TESTS`(+binary+image) |

그 외 게이트 — `sys.platform != linux` marker, browser opt-in(`INV_BROWSER_TEST`), image opt-in(`INV_WEB_IMAGE`/`INV_UPGRADE_AGENT_IMAGE`), `INV_STORAGE_SOURCE_ROOT` — 에는 **CI-fail이 없다**(CI에서도 그냥 skip). 이 차이가 사용자에게 의미 있다.

**핵심 변수: CI 러너의 OS.** `sys.platform != linux` marker는 collection 시점에 평가되고 **skip일 뿐 fail하지 않는다**(marker가 skip하면 fixture는 실행조차 안 됨 → node-runtime의 CI-fail도 안 터진다). 그래서:

### CI가 **Linux 러너**로 열리면
- **① chmod/POSIX 계열 → 자동 실행·검증.** `sys.platform==linux`라 marker 통과 + PG는 위 CI-fail이 강제 → 별도 opt-in 없이 **돈다**. (즉 이 Linux 항목들은 영원히 미검증이 아니라 **Linux CI가 열리는 순간 자동 검증된다**.)
- **② node-runtime 계열 → 강제(RED unless opt-in).** marker 통과 → fixture 실행 → `INV_RUN_NODE_TESTS=1`+node binary+image 없으면 **pytest.fail(빨간불)**. 조용히 skip 불가 — CI가 node-agent 런타임을 반드시 제공해야 한다.
- **browser/image/lan_storage → 여전히 skip.** opt-in skipif(CI-fail 없음)라 env 없으면 CI에서도 skip, 빨간불 아님 → **열려도 미검증으로 남는다**(누가 env를 켜야 검증).

### CI가 **비-Linux 러너**(예: Windows)로 열리면
- Linux 계열 전부 `sys.platform != linux` marker로 **조용히 skip**(fail 없음). node-runtime CI-fail도 collection 전 skip이라 **안 터진다**. 즉 **아무것도 자동 검증 안 되고 빨간불도 없다** — 오늘 우리가 경계한 "초록이나 미커버" 형태. **CI 러너가 Linux여야** 이 항목들이 실제로 강제된다.

**요약(사용자용) — CI 결제 해결 후 (Linux CI 가정)**:
- **자동 검증**: ① chmod/POSIX 계열(PG만 있으면, PG는 CI-fail로 강제됨).
- **강제(빨간불로 눈에 띔)**: ② node-runtime 계열 — CI가 node-agent opt-in을 안 켜면 실패하므로 잊힐 수 없다.
- **여전히 남음(수동 opt-in 필요, 조용히 skip)**: browser·web image·upgrade image·lan_storage(`INV_STORAGE_SOURCE_ROOT`).
- **전제**: 러너가 Linux여야 함. Windows CI면 전부 조용히 skip.

## v1.2.0 정정 — 러너는 ubuntu-latest 확정, 그리고 enforcement는 워크플로도 한다 (내 v1.1.0 오류 정정. 전부 소스-읽기)
**[소스-읽기, 미실행]** `.github/workflows` 다섯(backend·core·desktop-browser·docs·frontend) **전부 `runs-on: ubuntu-latest`** — 러너 OS가 Linux로 확정됐다. 그러니 v1.1.0의 "Linux CI 경우"가 조건이 아니라 **실제**다.

그런데 v1.1.0에서 나는 **test-side 게이트(fixture CI-fail)만 보고 워크플로가 opt-in env를 켜는 것을 놓쳐** 두 가지를 틀리게 적었다. 정정한다(조용히 지우지 않는다):
- **틀림①: "node-runtime 계열 → RED unless opt-in".** 실은 **`core.yml`이 node-agent를 빌드하고 opt-in을 켠다**: `go build … inv-node`(L60) → `docker build … inv-node-test`(L66) → `INV_NODE_IMAGE`/`INV_NODE_BINARY`/`INV_RUN_NODE_TESTS=1`(L67-69). 즉 node-runtime 계열은 **CI에서 실제로 실행·검증된다**(빨간불 아님).
- **틀림②: "browser → 여전히 skip, 미검증".** 실은 **`desktop-browser.yml`이 실행·강제한다**: `VF_BROWSER_TEST=1` → `run_vf_security_tests.py`가 `INV_BROWSER_TEST=1`을 시험 subprocess에 전달(L153) → desktop/approval/studio browser 3파일 실행, 그리고 **"6 passed / 0 skipped / container removed"를 단언**하는 검증 스텝이 있어 하나라도 skip이면 빨간불. **browser 인수는 CI에서 검증된다.**

**교훈(오늘 반복된 것)**: enforcement 층이 둘이다 — **test-side**(fixture `pytest.fail` on CI: PG·node-runtime)와 **workflow-side**(워크플로가 env를 켜고 결과를 단언: node-image build, browser 6-passed assert). 내가 test-side만 보고 "미검증"이라 단정한 것은 오늘 우리가 계속 경계한 "신호가 무엇에 대한 것인지 못 박기 전에 결론" 그대로다. 워크플로까지 읽어야 실제 커버리지가 보인다.

## CI를 열면 무엇이 검증되고 무엇이 남나 (확정)
**[소스-읽기]** 러너 ubuntu-latest 확정 하에:

**자동 검증됨(워크플로가 제공)**:
- PG 스위트 — 워크플로가 `INV_TEST_ADMIN_DSN` 설정 + fixture CI-fail.
- ① chmod/POSIX 계열 — Linux 러너 + PG.
- ② node-runtime 계열 — `core.yml`이 node-agent build + `INV_RUN_NODE_TESTS=1`.
- **browser 인수**(desktop/approval/studio) — `desktop-browser.yml`이 실행 + "6 passed/0 skipped" 단언.

**여전히 미검증 (어느 워크플로도 opt-in을 안 켬)** — 오직 **이미지/설치 acceptance 셋**:
| 파일 | 무엇을 검증 | 필요한 opt-in |
|---|---|---|
| test_web_container | 빌드된 **frontend 컨테이너 이미지** + TLS + 실 proxy 소켓 | `INV_WEB_IMAGE`(빌드된 web 이미지) |
| test_workspace_upgrade | 실 **Docker 설치 프로그램** upgrade/rollback | `INV_UPGRADE_AGENT_IMAGE` + Linux |
| test_lan_storage_install | 패키징된 **LAN storage 설치**(Bash+Docker+Go receipt) | `INV_STORAGE_SOURCE_ROOT` + Linux |

**의도 vs 누락 판정: 의도.** 근거: (a) 사유가 "Explicit built image opt-in required"/"Opt-in … acceptance"로 명시적 opt-in을 표방, (b) `core.yml`은 node/backend 이미지를 빌드하면서 **web-container/installer 이미지는 의도적으로 안 빌드**한다(선택적 누락이 아니라 범위 밖), (c) 검증상태지도가 이미지/물리 acceptance를 **"운영 인수(별도 트랙) … 원격 설치/운영 결정 선행"**으로 분류([[2026-09-19_Claude영역_검증상태지도]]). 즉 이 셋은 **비싼 빌드 산출물/설치 프로그램 acceptance라 CI 기본이 아니라 운영 트랙으로 의도적으로 분리**된 것이다.

**CI-fail을 추가하는 것이 맞나: 아니다.** node-runtime엔 fixture CI-fail이 있지만 **동시에 `core.yml`이 제공**하기에 유효하다. 이미지 셋에 test-side CI-fail만 추가하면 **제공 워크플로가 없어 CI가 그냥 빨간불**이 된다(비싼 이미지 빌드를 강제). 올바른 선택지는 둘: ⓐ 의도된 수동 opt-in으로 두되 무엇이 남는지 문서화(현재), 또는 ⓑ web-container/installer 이미지를 빌드해 env를 켜는 워크플로를 추가(빌드 비용·시간·안정성 비용을 감수하는 운영 결정). **판단 근거**: 검증상태지도가 이미 이를 별도 운영 트랙으로 두었으므로 ⓐ가 현 설계와 정합하고, ⓑ는 사용자가 그 acceptance를 CI에 상시 포함하기로 결정할 때의 비용 트레이드다.

**남는 것을 검증하려면**: 각 이미지/설치 산출물을 빌드(frontend 컨테이너 이미지 / installer 이미지 / storage source 트리)하고 해당 env를 워크플로나 수동 실행에서 설정. 이는 browser처럼 전용 워크플로(예: `web-container.yml`)로 만들면 CI에 편입된다 — 비용 결정.

## 다음 사람에게 (환경 준비 기준)
- **①은 격리 Linux 호스트**가 실제로 필요하다(POSIX 권한/파일 backend).
- **②의 실제 준비물은 "Linux 박스"가 아니라 node-agent 런타임**이다: node-agent binary 빌드(services/node-agent, Go) + 컨테이너 image + `INV_RUN_NODE_TESTS=1`·`INV_NODE_BINARY`·`INV_NODE_IMAGE`. "Linux 필요"라고만 적으면 이 opt-in을 놓친다. 가능하면 Windows+Docker Desktop(Linux 컨테이너)에서 node-runtime을 켜 ②의 `sys.platform` 강제가 실제로 필요한지 한 파일로 측정해 볼 가치가 있다(오늘 180초 한도가 실은 처음부터 부족했던 것처럼, marker가 실제 전제가 아닐 수 있다).
- recovery_drill·workspace_checkout은 구체 primitive를 더 좁혀야 ①/② 사이가 확정된다(현재 ②로 잠정).

## 제약·인계
일회용 PG(`svcx01-linuxaudit`, 라벨)만 사용·`docker rm -f -v` 철거·baseline 48/79/11 복원, 보호 `saintvision-lan-db*`·`saintview-orthanc*`(4) 미접촉, 익명 볼륨 69 보존. platform-marker 임시 우회는 `git checkout`으로 전부 원복(변경 잔여 0). apps/web 미접촉. reviewer: Codex — ②의 host-Linux 강제 필요성(Windows+Docker 가능성)과 recovery_drill/workspace_checkout 구체 primitive 경계 검토.
