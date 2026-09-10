---
doc_id: "HIST-SHARD-RECOVERY-VERIFY-001"
title: "2026-09-10_13-05-06_KST_SHARD-RECOVERY_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:05:06+09:00"
source_of_truth: "Git"
---

# 샤드 재승인·대체 Node 실행 검증

Task SHARD-RECOVERY, owner Codex, independent reviewer Claude pending. base `a70aff43262b7457098d68c0d5b8a662aad4742a`, branch `agent/codex/shard-recovery`, draft PR [#15](https://github.com/egparadise/SaintVision-Invion/pull/15), base PR #13. GUIDE-001·GOV-AGENT-001·GOV-GIT-001·각 Backend/DB/Storage 계획·agent-delivery/core-reliability v1.0.0, ADR-INDEX-001 v1.14.0과 [[Codex 샤드 재승인과 대체 Node 복구 계약]]을 따른다.

## 결과와 범위

검증한 구현 SHA는 `3835b198884970840ce11ec92493bbadf60744b2`이다. 실패·취소된 독립 샤드 계획에서 모든 원본의 물리적 종료를 확인하고, 동일한 작업에 새 Run과 서로 다른 2명의 승인을 만든다. 승인 소비·예약·fence·claim·queue·부모·계보를 원자 확정한다. 대체 Node에서 실행한 실제 출력의 검증과 Evidence·새 부모 완료를 연결했다. 원본 terminal 기록은 유지한다. 같은 원본에서 하나의 후속 실행만 허용하며 최초 포함 총 3세대로 제한한다. 실행하지 못한 승인 준비는 세대 수에 포함하지 않는다.

서비스는 operator가 구성한 Node runtime을 사용한다. 공개 recovery HTTP route는 이번 범위에 포함되지 않는다. 브라우저가 NodePrincipal·key·policy/capability를 제출하는 경로는 없다. 서로 다른 Node key를 지원하며 하나의 제한 profile을 사용한다. migration 0020은 기존 양쪽 migration history가 합쳐진 0019 뒤에 추가했다. DB source/generation unique·CHECK·RLS·불변 레코드 및 runtime 그룹 권한을 실제 PostgreSQL에서 확인했다.

## 실제 합격 증거

- Core push [34435221408](https://github.com/egparadise/SaintVision-Invion/actions/runs/34435221408)와 Docs push [34435221374](https://github.com/egparadise/SaintVision-Invion/actions/runs/34435221374)는 같은 코드 SHA에서 success다. raw artifact에서 test count와 실패/누락을 다시 확인했다.
- 전체 Python **941 passed**, failure **0**, error **0**, skip **0**. 샤드 복구 전용 **19개**, Workspace 전용 **20개**는 전체 suite에 포함되며 중복 합산하지 않는다.
- Go race **40 top-level / 94 leaf cases**가 통과했다. Go/TS/Pydantic 계약 생성·컴파일, Node 빌드, production image 비root 및 설정 누락 시작 거부도 검증했다.
- Backend Python 3.12·3.14 CI, 빈 DB migration·반복 upgrade 및 기존 0018·0010·0019 head에서 새 head로 upgrade를 수행한다. CI artifact와 PR의 같은 SHA workflow 결과를 함께 읽는다.
- 실제 두 Go Node 프로세스는 서로 다른 mTLS 인증서·서명 키·저널을 사용한다. 두 Node 병렬 실행과 Node B로 전체 교체를 확인했다. 실제 Docker stdout/stderr → 저장 hash → child Evidence → parent aggregate가 연결된다.

전용 19개 시나리오는 정상 두 Node 완료, 물리 종료 미확인 차단, 두 번째 승인 누락 rollback/재요청, 작업 digest 변경 거부, 관측 중 requester/voter/Node membership 철회 3건, 서로 다른 준비 요청 경합, 3세대 상한, 두 번째 queue 삽입 후 합성 장애 rollback, 만료한 준비 대신 새 승인, 개별 dispatch/reserve 우회 차단, epoch/project 범위 차단, 준비한 자식 취소, 동일 key 동시 요청과 권한 재확인, 실패 부모의 전체 Node 교체다. 이 중 중간 장애는 서비스 예외 주입으로 트랜잭션 rollback을 확인하며 OS 전원 차단 실측으로 주장하지 않는다.

artifact ID `10136077501`, archive SHA-256 `aed08af60f8ef2001e290d72a56dd0b82e102d7ce390c33561e6ae741f1a79b4`, 확인 `2026-09-10T13:04:45+09:00`. 원본 JUnit/Go JSONL 및 provenance는 다음 파일이다.

- `Evidence/recoverycode-3835b19-tests.xml`
- `Evidence/recoverycode-3835b19-workspace-tests.xml`
- `Evidence/recoverycode-3835b19-shard-recovery-tests.xml`
- `Evidence/recoverycode-3835b19-unit.jsonl`
- `Evidence/recoverycode-3835b19-provenance.json`

## 명령·실패·동기화

2026-09-10 12:37 KST `git fetch origin`, 별도 worktree 준비 exit 0. 로컬 `python -m pytest tests/core -q --junitxml=.work/local-core.xml`는 198 passed, exit 0. `tools/generate_contracts.py`, `tools/check_docs.py`, `tools/check_ontology.py`, `git diff --check` 재검사 exit 0. Windows에서 실행하지 않은 Linux 통합 시험을 로컬 합격으로 세지 않았다.

초기 `abf9549` push/PR Core CI는 복구 SQL의 `old` 별칭이 PL/pgSQL `OLD`와 충돌하여 첫 복구 시험에서 실패했다. Workspace 20개는 통과했지만 전체 suite는 미실행이었다. `f312546`에서 source_member로 정정하고 target parent/샤드 수 가드도 보강했다. 이어 f312546 PR CI의 동시 heartbeat 역전은 `3835b19`에서 새 nonce 관측 총 3회 제한으로 수정했다. 실제 mTLS 응답 역전을 결정론적으로 만드는 성공/상한 2건과 scope·epoch 403 재시도 금지 1건을 추가했다. 실패를 숨기거나 기대값을 약화하지 않았다. [[SHARD-RECOVERY 통합 검증 오류]], [[SHARD-RECOVERY 통합 검증 해결]]에 남겼다.

Obsidian 최초 check는 Gemini가 추가한 index 두 행 때문에 exit 1, 쓰기 0이었다. Git `92c43b1`의 두 보고서를 읽고 원본 bytes/hash와 source SHA를 `Evidence/shard-recovery-sync-proposals.json`에 보존했다. 작성자 보고로 수용하며 그 UI/배포 합격 주장은 이번 Codex 검증에 포함하지 않는다. 수용 후 check는 248 files, pending 10, conflict 0이었다. 보고서 commit 후 `--check → --apply → --check` 및 전체 해시 대조를 수행하고 최종 SHA·실제 sync 시각/파일 수·최종 CI/artifact를 PR #15에 기록한다. OneDrive cloud 업로드 여부는 별도다.

## 실제 남은 항목과 다음 담당자

작업 중 PR14의 `44756e1` 업무 연결을 확인했다. [[PR14 업무 연결과 실행 커널 통합 선행 검토]]에 migration/DB 역할, kernel 증거 기반 binding, 현재 project/lock 권한의 통합 선행 사항을 기록했다. 다음 Codex 최우선은 이 통합이다. PR14 코드의 존재와 실제 실행 커널 연결 검증 완료를 구분한다.

| 담당 | 남은 작업 |
|---|---|
| Codex | PR14 업무 연결과 migration/권한/실제 Evidence 통합, kill switch/drain·주기 reconciliation, PTY/원격 Git·대용량 및 Workspace Node 이전, Windows/GPU/BuildKit 격리, Context/RO와 5대 PC 부하·장애·복구 검증 |
| Claude | 독립 검토, 공개 recovery route/운영 설정·준비 기록 보존, public 업무/데이터와 kernel 연결, 실행 운영 기록 |
| Gemini | 실제 project API 기반 복구 준비·새 승인·세대별 부모/자식·대체 Node·종료 미확인/상한 표시 및 브라우저 검증 |

두 Node는 한 CI 호스트의 별도 프로세스다. 운영 5대 PC, MPI/NCCL collective, Workspace 파일의 다른 Node 전달, 자동 무승인 재실행 또는 배포 인수 완료를 의미하지 않는다. Git main merge/운영 배포 및 다른 Agent 독립 검토는 수행하지 않았다. baseline registry의 선행·인수 조건을 충족하지 않은 task는 done으로 올리지 않는다.
