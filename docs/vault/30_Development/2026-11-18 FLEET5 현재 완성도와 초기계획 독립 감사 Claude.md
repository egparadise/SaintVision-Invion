---
doc_id: "AUDIT-FLEET5-COMPLETION-INITIALPLAN-20261118-CLAUDE"
title: "2026-11-18 FLEET5 현재 완성도와 초기계획 독립 감사"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-18T21:40:00+09:00"
source_of_truth: "Git"
---

# 2026-11-18 FLEET5 현재 완성도와 초기계획 독립 감사

Task `FLEET5-CURRENT-COMPLETION-AND-INITIALPLAN-AUDIT-20261118`(Orca task_121355869af1, dispatch ctx_a23798cf4e04)의 감사 보고서다. 착수 시각은 2026-11-18 20:59 KST이고 기준은 Root544 `d81d40f8`(Docs 44298774163 성공)이다.

- **역할**: 나는 이 감사의 작성자다. Root 운영 스크립트와 제품 코드의 작성자는 아니다.
- **범위**: Git 객체, 커밋된 문서, Root Evidence를 정적으로 읽었다. 기존 hosted CI는 gh API로 조회만 했다.
- **실행하지 않은 것**: 제품 실행, SSH, DB, 재부팅, APPLY는 하지 않았다.
- **기계 판독 원본**: `30_Development/Evidence/fleet5-completion-initialplan-audit-20261118-claude/` 아래에 있다.
  - `audit.json`: 요약
  - `trace-48.json`: 48행 추적표
  - `expanded-vf-matrix.json`: 확장 범위 행렬
  - `transport-verdict.json`: 연결 통로 판정
  - `connection-table.json`: 현재 연결표
  - `read-sources.json`: 읽은 자료 54개의 blob과 실행 명령·exit

## 1. 결론 (사용자 질문에 대한 답)

| 질문 | 답 | 분모와 근거 |
|---|---|---|
| 정식 완료 카드 비율 | **4.17%** (2/48) | registry 1.0.1 기준 done 2(S01-FE `b0313282`, S01-DB `8b20d3e6`), blocked 4, planned 42. 12개 outcome은 전부 planned다 |
| 마지막 기록된 코드 성숙도 (11-04) | 착지 C **71.35%**, 후보 Z **72.40%** | [[2026-09-28 48 task 진행률 재채점]] v1.21.1. 같은 4,800 분모와 0/25/50/75/100 rubric을 쓴다 |
| **이번 감사의 원래 48 task 성숙도 (11-18)** | **확정 하한 72.40%** (3,475/4,800). 미통합 고정 source 사슬을 포함하면 **72.40~72.92%** | 하한 tree는 착지 integration tip `59f0a3c2`다. Z를 포함하고 hosted run 13/13이 성공했다. 상한 +25는 S12-BE 한 행의 미해결 범위다 |
| 지금 구조적으로 올라갈 수 있는 최대치 | **76.04%** (3,650) | S01-BE·S01-ST가 사용자 결정 U1~U6에 막혀 있고 필수 운영 인수가 없다. 그래서 나머지 46행은 75를 넘을 수 없다 |
| 확장 범위 전체 (Web Desktop·Storage/Model·VF) | **단일 %를 낼 수 없다.** 운영 인수는 카드 0/16, outcome 0/7이다 | §3 참조 |
| 전체 제품 | **100%가 아니다** | 신뢰된 Node 0대(CA_TERMINAL), Main의 DB·IdP 정지, 실제 사용자 작업 실행 0건, 5대 인수 0 |

- **72.40%의 성격이 바뀌었다.** 11-04에는 "Z가 착지하면"이라는 조건부 수치였다. 이제는 착지 tree의 값이다. Z(`03e17c31`)는 `59f0a3c2`의 조상이다. `59f0a3c2`에서는 post-landing-verify 8개를 포함한 hosted run 13개가 모두 성공했다.
- 다만 이 값은 v1.21의 행별 판정을 승계한 것이다. 이번에 확인한 것은 다음 세 가지다.
  - 행 점수에서 합계를 다시 계산했다: 2,800 / 3,400 / 3,425 / 3,475가 모두 재현된다.
  - §3의 결속 경로 88개가 `59f0a3c2`와 `d47630d7`에 모두 있는지 `git ls-tree`로 확인했다.
  - 11-04 이후의 운영 증거를 행별로 대조했다.
- 시험 case 수준의 재감사는 하지 않았다.
- **시험·커밋·PR·파일 수는 점수에 넣지 않았다.**

## 2. 48행 추적 — 무엇이 바뀌었고 무엇이 안 바뀌었나

전체 행은 `trace-48.json`에 있다. 각 행에는 다음이 들어 있다.
- 원래 task ID, owner, reviewer, registry 상태, scope
- baseline, `95a59b24`, C, Z, 제안 현재값
- 결속 경로가 두 tree에 있는지 여부, hosted 근거, 11-04 이후 운영 증거
- 남은 단계, 신뢰도, 날짜, 다음 담당

| 구분 | 행 | 설명 |
|---|---|---|
| 100 | S01-FE, S01-DB | closure commit 둘 다 integration tip 안에 있다. `origin/main` `f9be6b61`에는 없다 |
| 50 → 75 (11-04까지의 문서 판정) | S11-BE (v1.5), S12-FE (v1.9), S08-BE (v1.15) | 결속: `tests/test_import_ac11_composite_long_soak.py`, `apps/web/tests/s12-release-manifest-server-binding.test.tsx`, `tests/integration/test_build_product_runtime_real_pg.py`(Core 37072629027, 13/13) |
| 50 유지 | S03-ST, S05-ST, S07-ST, S08-ST, S12-BE, S12-DB, S12-ST | S03-ST의 사슬 delta는 5줄이고 행 고유 시험이 없다 |
| **미해결 범위** | **S12-BE 50~75** | 미통합 사슬에 설치·upgrade·rollback scope의 코드와 시험이 추가됐다(`worker_plain_rotation.py`, `worker_peer_floor.py`, `test_fleet5_setup_packet.py`, `test_lan_leaf_rotation_*`). 통합 tree에서의 행 결속 검토가 없어서 점수를 주지 않았다 |
| 75 유지 (39행) | 나머지 | 100까지 남은 것은 실 IdP 여정, 5노드 인수, PITR, GPU 실장비 같은 운영 인수다. 그리고 선행 사슬이 열려 있다 |

**11-05~11-18의 운영 성과는 어느 행도 100으로 올리지 않는다.** 그래도 실제 성과이므로 행별로 적는다.
- 3 Node가 실제 mTLS로 등록됐다.
- capacity를 실측으로 읽었다: Node당 500m CPU / 64MiB, 합계 1,500m / 192MiB.
- 실제 관리자 PKCE 로그인과 자원 화면을 확인했다.
- 승인 2인 gate가 지켜졌다: 승인 전 실행 0건.

올리지 않는 이유는 두 가지다. 선행 S01-BE/ST가 blocked이고, 그 신뢰가 지금 CA_TERMINAL이라 유효한 운영 인수가 아니다.

**확인한 문제 하나**: 현재 배포된 코드(Node `1efea494`, API `96afd799`, UI `abb7074e`)와 수락된 `d47630d7`은 **integration branch에도 main에도 없다.** `59f0a3c2`의 후손인 고정 branch다. 행 점수를 올리려면 통합 tree가 필요하다. 그러므로 이 사슬을 integration에 병합하고 full CI를 돌리는 일이 S12-BE 재판정의 선행 조건이다.

## 3. 확장 범위 — 초기 의도와 현재 상태

로드맵 [[57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵]]에는 outcome 7개와 카드 **16개**가 있다(VF-CX 5, VF-CL 5, VF-GM 6). brief가 말한 15개가 아니다. 기계 registry가 있는 것은 CX와 CL 10개뿐이다.

| outcome | 초기 의도 (로드맵 Outcome 표) | 수락된 코드·런타임 증거 | 빠진 인수 |
|---|---|---|---|
| VF-01 | 하나의 canonical 보안 control plane | VF-CX-01 `partial`. PC3 API96에서 실제 OIDC 로그인을 했다(11-08) | Main의 IdP:8443과 DB:55461에 listener가 없다(11-18) |
| VF-02 | Web Desktop 단일 PC 경험 | abb707 배포, 실제 로그인, 자원 frame | AC-11 접근성이 MEASURED_FAIL이다(수동 인수 1). 세션 복원 인수가 없다 |
| VF-03 | 통합 `inv://` | VF-CL-01/02: 구현·CI·검토 완료 | 실제 Node에서 왕복한 적이 없다 |
| VF-04 | ModelManifest·shard/replica | VF-CX-02, VF-CL-03: 구현·CI·검토 완료 | 실제 import·repair를 하지 않았다 |
| VF-05 | 지역성 기반 분산 실행 | VF-CX-03/04 구현. capacity 실측 | **실제 작업 실행 0건.** run이 승인 대기 상태로 만료됐다 |
| VF-06 | 5대 실제 PC 인수 | 3 Node를 7일짜리 pilot CA로 등록했다 | VF-CX-05 blocked. CA_TERMINAL. PC1 key가 거부된다. Main은 Node가 아니다. GPU를 제공하지 않는다 |
| VF-07 | Cell/Federation 준비 | 로드맵상 Later | 카드·증거가 없다 |

- **수치**: 구현 true 8, partial 1, CI true 8, 운영 인수 0/16. VF-GM 6개는 Gemini 작업판의 자기 보고(승인·100%)뿐이다. registry와 독립 운영 인수가 없다.
- **단일 %를 낼 수 없는 이유**:
  - 설계 인덱스는 새 범위의 분모를 "카드와 합격 증거가 등록된 뒤 별도로" 고정한다고 정한다. 아직 고정되지 않았다.
  - VF 카드와 outcome에는 가중치나 rubric이 없다.
  - VF-GM에는 registry가 없고 VF-07에는 카드가 없다.
  - 지금 존재하는 수락 비율은 0뿐이다.
- **100%가 되는 유한 조건**:
  1. VF-GM을 registry에 넣고 독립 reviewer를 지정한다.
  2. 확장 분모와 가중치를 ADR로 고정한다.
  3. DB·IdP를 복구하고 새 authority를 세운 뒤 Node를 재등록한다.
  4. 실제 승인 작업, `inv://` 왕복, 모델 import를 실행한다.
  5. 5대 인수(VF-06)를 받는다: 이탈·재접속, 저장, GPU, 터미널, 복구.
  6. VF-07의 증거를 내거나, ADR로 100 범위에서 제외한다.

## 4. Root 연결 통로 독립 검토 (Keep-SaintVisionTransport)

**판정**: 현재 사용자의 대화형 통로로는 건전하다. **상시 연결로는 M1~M4가 닫힐 때까지 수락하지 않는다.** 필수 4, LOW 6, INFO 4건이다. 구현 담당은 Root다.

- **건전한 것**:
  - known_hosts를 hash로 pin했고 StrictHostKeyChecking=yes를 쓴다.
  - BatchMode와 IdentitiesOnly를 쓴다.
  - forward 양끝이 모두 loopback이다.
  - ExitOnForwardFailure를 켰고 keepalive는 15초×3이다.
  - 다른 프로세스를 kill하지 않는 HOLD가 있다.
  - mutex의 abandoned 상태를 처리한다.
  - state 파일을 원자적으로 교체한다.
  - log를 2MiB 단위로 회전한다.
  - 비밀을 출력하지 않는다.
  - 검증 스크립트는 소유가 확인된 child만 종료했다.
- **6.561초 재접속**은 Root의 운영 증거다. 시각 산술(20:49:27.470 − 20:49:20.910)과 event 순서가 내부적으로 일치함을 확인했다. 나는 재실행하지 않았다.
- **manifest**: 16/16이 일치한다. 3개는 원본 바이트로, 13개는 CRLF 변환 뒤에 일치한다. manifest는 CRLF 바이트로 hash를 냈고 Git은 LF로 보관하기 때문이다.

| ID | 분류 | 내용 |
|---|---|---|
| M1 | 필수 | catch 블록 안의 state/event 쓰기가 예외를 던지면 supervisor가 종료된다. 예: state.json을 읽는 중에 Move-Item이 실패하거나 디스크가 가득 찬 경우. 그 뒤로는 다음 로그인까지 아무것도 재시작하지 않는다 |
| M2 | 필수 | supervisor를 감시하는 것이 없다. HKCU Run은 대화형 로그인 때만 실행된다. crash·logoff·로그인 없는 재부팅에서는 통로가 없다. 재부팅·로그인 시험은 NOT_RUN이고, S4U 등록은 이전에 0x80070005로 실패했다 |
| M3 | 필수 | state.json은 상태가 바뀔 때만 기록된다. 그래서 supervisor가 죽었거나 PC3 서비스가 내려가도 `SSH_PROCESS_STARTED`가 그대로 남는다. heartbeat, end-to-end probe, alert가 없다 |
| M4 | 필수 | Run 값의 실제 명령줄과 그 hash가 증거에 없다. 그래서 시작 경로를 검증할 수 없다 |
| L1 | LOW | 상시 통로가 shell 권한이 있는 fleet 관리 key를 재사용한다. PC3 authorized_keys에 `restrict,port-forwarding,permitopen` 제한이 있다는 증거가 없다 |
| L2 | LOW | `-F none`을 쓰지 않는다. GlobalKnownHostsFile을 pin하지 않았다 |
| L3 | LOW | exit code가 null로 기록된다(events.jsonl에서 관측). handle을 cache하지 않아서다 |
| L4 | LOW | ssh child가 job object 밖에 있다. supervisor가 죽으면 고아 child가 port를 점유한다 |
| L5 | LOW | 고정 간격으로 무한 재시도하고 backoff나 escalation이 없다. HOLD_KEY_UNAVAILABLE은 event를 남기지 않는다 |
| L6 | LOW | `Local\` mutex는 로그인 세션 단위다 |
| I1 | INFO | state.json과 events.jsonl 첫 줄에 UTF-8 BOM이 있다 |
| I2 | INFO | **이 통로는 portal과 API만 다룬다.** 실 IdP(Main:8443)와 CP DB(Main:55461)의 PC3 역방향 bridge는 범위 밖이다. 그래서 로그인과 DB 호출은 지금 동작할 수 없다 |
| I3 | INFO | Main의 모든 로컬 프로세스가 loopback으로 PC3 API에 접근할 수 있다. API 인증은 그대로 적용된다 |
| I4 | INFO | healthz 200은 liveness일 뿐이다. Root도 그렇게 바르게 적었다 |

## 5. 현재 연결표 (Root 영수증 기준, 내가 접속하지 않음)

| 장비 | SSH | 서비스·Node | 신뢰 | 실제 제공 |
|---|---|---|---|---|
| PC1 .13 | **255, 공개키 거부**(20:51, 사용자 등록 응답 이후) | 미관측 | — | 없음 |
| PC2 .143 | 0 | ssh·docker active/enabled, Node unless-stopped 실행 중 | **CA_TERMINAL** | 500m / 64MiB, GPU 미제공 |
| PC3 .222 | 0 | 위와 같음. API96·portal·observer 실행 중, healthz 200(liveness) | **CA_TERMINAL** | 500m / 64MiB |
| PC4 .210 | 0 | 위와 같음 | **CA_TERMINAL** | 500m / 64MiB |
| Main (CP) | client | **Docker daemon 불가.** DB:55461·IdP:8443 listener 없음. 사용자 통로만 복구됐다 | CA_TERMINAL | Node 아님 |

- **관측된 하드웨어는 메타데이터다.** 12 thread, 약 15GiB, T600 4GiB가 3대 있다. 이것은 묶인(pooled) 자원도 아니고 제공된 자원도 아니다. 5대 정상이 아니다.
- **만료 시각**: 원래 CA는 2026-11-14 16:15 KST에, CP leaf는 11-09 16:15 KST에 만료됐다. 같은 CA로 갱신하거나, 만료된 신뢰를 우회하거나, reset·restart로 정상처럼 보이게 하지 않는다.

**상시 연결의 최종 상태 지도** (`connection-table.json`):

| 계층 | 지금 | 남은 것 | 담당 |
|---|---|---|---|
| Linux 프로세스 지속 | 3대 enabled/unless-stopped | 만료된 신뢰 아래에서 재부팅하면 정책상 종료한다. PC1 | Root·사용자 |
| 통로 자동 감시 | 재접속 6.561초 | M1~M4. IdP·DB bridge | Root |
| DB·IdP 지속성 | **Main daemon 꺼짐. 마지막 백업은 schema-only**(11-07, 데이터·globals·복원 시험 없음) | 최신 데이터 보존과 복원 시험 | Root(운영) / Claude(runbook·도구) |
| authority 교체와 사전 갱신 | CA_TERMINAL | **검토된 교체 workflow가 없다.** CA 7일, leaf 2일 수명 | Codex 계약·코드, Claude 검토 |
| 신선한 상태·경보 | 일회성 영수증뿐 | redacted collector | Claude 도구 + Root 배포 |
| 실제 전원·네트워크 복구 | NOT_RUN | 장비별 시간 영수증 | Root·사용자 |

## 6. 원래 방향 평가 (구체 증거가 있는 것만)

- **맞음**:
  - 만료를 fail-closed로 처리한다. d476은 CA·leaf 만료를 typed 종단으로 거부하고 일반 경로를 완화하지 않는다([[Proposed expired-policy non-serving custody candidate ADR R1]] 17행).
  - capacity API는 측정한 500m/64MiB만 보고하고 "공유 RAM이 아니다"라고 적는다. 최종 지침의 "물리 RAM/VRAM을 하나로 표시하지 않는다"와 맞다.
  - 승인 gate가 실제로 지켜졌다: `enqueueEligible=false`, 투표 0, 실행 0.
- **어긋남**:
  - **운영 수명**: pilot CA는 7일, CP leaf는 2일로 발급됐다. 자동 갱신은 11-05에 비활성화됐다. 회전 도구 PR이 여섯 번 넘게 전진했지만 적용되지 않았다(r4는 11-02, 1efea는 11-09·11-14에 만료). 그 결과 신뢰가 두 번 소멸했다. OUT-12("5대에서 개발부터 장애 복구까지")와 반대 방향이다.
  - **단일 장애점**: CP DB와 IdP가 Main에 있다. Main은 가장 자원이 빠듯한 장비이고(RAM 89~99% 관측) 지금 Docker daemon이 꺼져 있다.
- **부분**:
  - Web Desktop과 UI는 실제로 배포되고 로그인까지 됐다. 지금은 IdP가 꺼져 있다.
  - GPU(OUT-08)는 합성 실행조차 없다. GPU false.
  - Workspace 실행(OUT-03)은 실제 실행이 0건이다.

## 7. 우선순위와 다음 카드 (구현을 전진시키는 것)

1. **[Root 운영, 지금] FLEET5-MAIN-DB-IDP-DURABILITY-R1**
   - Main Docker, CP DB, IdP를 읽기 전용으로 관측한다.
   - 데이터와 globals 전체를 dump하고 SHA-256을 기록한다.
   - 일회용 컨테이너에 복원해 행 수를 확인한다.
   - 백업 전에는 아무것도 쓰지 않는다.
   - *합격*: 위 영수증. 이것이 없으면 아래 2번의 live 단계를 시작할 수 없다(재등록이 DB에 쓴다).
2. **[다음 ready 카드, Codex owner, Claude 실제 검토] FLEET5-AUTHORITY-REPLACEMENT-AND-ADVANCE-RENEWAL-R1**
   - 근거:
     - [[Current three-Node pilot renewal preflight and recovery plan R1]] 67행은 "now ≥ CA 만료면 같은 CA 복구가 불가능하고 교체 workflow는 범위 밖"이라고 적는다.
     - 수락된 `d47630d7`은 유효한 CA를 전제한다.
     - 그래서 이 카드 없이는 OUT-02~12와 VF-05/06이 하나도 전진하지 않는다.
   - 범위:
     - 새 CA custody와 수명 정책: CA 수명을 leaf보다 충분히 길게 하고 사전 갱신 창을 둔다.
     - 기존 NodeID 세 개를 보존할지 retire할지 계약으로 결정한다.
     - PC2~PC4를 재등록한다.
     - 대화형 세션에 의존하지 않는 무인 사전 갱신과 경보를 만든다.
     - DB와 journal floor를 reset하지 않는다.
   - *합격*:
     - 정확한 SHA의 hosted Core/Backend/Docs 성공
     - 음성 시험: 만료 CA 거부, 같은 CA 갱신 없음, 옛 leaf 재사용 불가
     - Claude의 실제 검토 수락
     - Root live 재등록과 fresh capacity readback
     - 짧은 수명 예행에서 만료 전 자동 갱신
3. **[Root] 통로 M1~M4 수정**
   - IdP·DB bridge를 같은 감독 아래 둘지 결정한다.
   - 실제 logoff/logon과 재부팅 시험을 한다.
4. **[사용자]**
   - PC1의 비밀 아닌 정보(계정, IP, authorized_keys 권한, 지문)
   - 요청자가 아닌 실제 승인자 2명
   - 결정 U1~U6
5. **[Codex] 고정 사슬 `1efea494..d47630d7`를 integration에 병합하고 full CI를 돌린다.**
   - 그다음 S12-BE 행을 결속 검토하고 Claude가 검토한다.
6. **[Root+사용자]** 새 authority 아래에서 첫 실제 승인 작업을 실행한다.
   - 기존 `run_01M6VXSMM9SV8MAB7K4B1YCRX8`은 승인 기한이 지났다. 실제 승인자 2명으로 새 제안을 낸다.
   - 그 뒤 5대 인수로 간다.
7. **[Claude, 병행 가능] FLEET5-REDACTED-STATUS-COLLECTOR-R1**
   - 읽기 전용 collector: 통로 M3, Node·DB·IdP liveness, observedAt 신선도
   - 시험과 hosted CI를 붙이고 Codex가 검토한다.

**이어지는 HOLD**: Original19HOLD, discharges0, runtimeB0, A1–A16, H1–H7, H3EA, RDNULL_HOLD, raw7UNREGISTERED, A01–A40 NOT_RUN. 실제 run은 미실행이고 실제 승인자 2명은 없다. 관련 실제 증거가 생길 때까지 유지한다. 승인자나 투표를 만들어 내지 않는다.

## 8. 이 감사가 하지 않은 것

- 시험 case 수준의 행 재감사를 하지 않았다. 손대지 않은 행은 v1.21의 판정을 승계했다.
- 제품, 시험, Docker, SSH, DB, 재부팅을 실행하지 않았다. 통로의 동작은 정적 분석이고, 6.561초는 Root의 증거다.
- 진행 중인 Codex의 F1~F6 수정 코드는 읽지 않았고 세지 않았다.
- task 상태, registry, rubric, Root 공통 진행판, 제품 코드를 바꾸지 않았다. APPLY나 export도 하지 않았다.

기록: [[2026-11-18_FLEET5_Completion_InitialPlan_Audit_Claude]]
