---
doc_id: "LINUX-GATE-AUDIT-CLAUDE-001"
title: "Linux 전용 분류 검증 감사 — 왜 Linux인가, 소스 근거인가 추정인가. 3부류"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T16:40:00+09:00"
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

## 다음 사람에게 (환경 준비 기준)
- **①은 격리 Linux 호스트**가 실제로 필요하다(POSIX 권한/파일 backend).
- **②의 실제 준비물은 "Linux 박스"가 아니라 node-agent 런타임**이다: node-agent binary 빌드(services/node-agent, Go) + 컨테이너 image + `INV_RUN_NODE_TESTS=1`·`INV_NODE_BINARY`·`INV_NODE_IMAGE`. "Linux 필요"라고만 적으면 이 opt-in을 놓친다. 가능하면 Windows+Docker Desktop(Linux 컨테이너)에서 node-runtime을 켜 ②의 `sys.platform` 강제가 실제로 필요한지 한 파일로 측정해 볼 가치가 있다(오늘 180초 한도가 실은 처음부터 부족했던 것처럼, marker가 실제 전제가 아닐 수 있다).
- recovery_drill·workspace_checkout은 구체 primitive를 더 좁혀야 ①/② 사이가 확정된다(현재 ②로 잠정).

## 제약·인계
일회용 PG(`svcx01-linuxaudit`, 라벨)만 사용·`docker rm -f -v` 철거·baseline 48/79/11 복원, 보호 `saintvision-lan-db*`·`saintview-orthanc*`(4) 미접촉, 익명 볼륨 69 보존. platform-marker 임시 우회는 `git checkout`으로 전부 원복(변경 잔여 0). apps/web 미접촉. reviewer: Codex — ②의 host-Linux 강제 필요성(Windows+Docker 가능성)과 recovery_drill/workspace_checkout 구체 primitive 경계 검토.
