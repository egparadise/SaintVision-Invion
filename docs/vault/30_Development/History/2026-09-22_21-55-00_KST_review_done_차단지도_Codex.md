---
doc_id: "HIST-CODEX-2026-09-22-REVIEW-DONE-BLOCKER-MAP"
title: "review→done 차단 지도 — review 18건·in_progress 2건"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T21:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "80d4e748f53bc11a83ea5c26aebe33694bef6848"
tags: ["review", "done-blocker", "task-registry", "owner-proposal", "user-input", "physical-lab"]
---

# review→done 차단 지도

## 판독 기준

정본 registry `80d4e748`은 `planned 26 · review 18 · in_progress 2 · done 2`다. 아래 표는 `review` 18건과 `in_progress` 2건을 모두 다룬다. **모든 S02~S12 카드는 직전 스프린트의 FE/BE/DB/ST 네 base 카드가 먼저 `done`이어야 한다.** 따라서 표의 자체 차단 조건을 채워도 선행 카드가 열리지 않으면 자동으로 `done`이 되지 않는다. planned 26건은 이 20개 base 카드의 연쇄 의존 때문에 지금 착수 가능한 카드로 따로 세지 않는다.

`우리 몫`은 사용자 비밀·물리 장비 없이 지금 만들 수 있는 시험·문서·도구·제품 결속과 제안 owner다. `사용자 입력`은 [[S02_선행입력_체크리스트_2026-09-22]]의 U1~U6이며, `물리 자원`은 값이 아니라 실제 실행 Evidence가 필요한 환경이다. 이 지도는 배정 제안이며 registry 상태·owner를 바꾸지 않는다.

## 카드별 차단 조건

| 카드·현재 상태 | (a) 우리 몫 — 지금 가능한 일 / owner 제안 | (b) 사용자 입력 U1~U6 | (c) 물리 자원·실운영 Evidence | History 근거 |
|---|---|---|---|---|
| S01-BE `in_progress` | IdP/CA/DNS preflight와 `/readyz`·`/v1/session` 200/401·오류 Evidence 수집 도구/절차 고정 — **Codex** | **U2 IdP, U3 CA, U4 DNS** | 실제 issuer/JWKS와 Node 인증서로 mTLS·권한 경계 실측 | [[2026-09-22_21-31-00_KST_S01_증거기록갱신_Codex]] |
| S01-ST `in_progress` | 인벤토리 값 lint, Storage SHA-256 왕복 verifier, retention/GC 실행 Evidence 절차 보강 — **Codex** | **U1 토폴로지, U5 장비·허용 자원/폴더, U6 Storage** | 5노드 실제 값·NTP와 선택 Storage endpoint/bucket 실제 왕복·정리 | [[2026-09-22_21-31-00_KST_S01_증거기록갱신_Codex]] |
| S02-FE `review` | 로컬 실제 API에 붙는 로그인·Node 목록/상세·401/403 Chrome 시나리오와 결과 수집 — **Gemini** | **U2~U5**, U1은 대상 topology 확정 | 실제 IdP 로그인, 5노드 heartbeat/mTLS, 배포 브라우저 여정 | [[2026-09-09_23-20-00_KST_S02-FE_Gemini_노드관측_여정_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S02-DB `review` | 고정 SHA API↔PG token replay/RLS/tenant 격리 acceptance runner와 redacted Evidence 묶음 — **Claude** | **U2 IdP, U3 CA, U4 DNS, U5 Node** | 실제 IdP·물리 Node mTLS/heartbeat와 browser acceptance의 남은 red 해소 | [[2026-09-22_18-27-37_KST_S02-DB_S03-DB_Codex_독립검토]] |
| S03-FE `review` | 허용/거부 실행·exit code·Evidence ID를 실제 HTTP로 표출하는 browser scenario — **Gemini** | **U1~U6 간접**(S01/S02 선행) | 실제 sandbox/ToolGateway Node, 금지 명령·실출력·자원 회수 | [[2026-09-09_23-40-00_KST_S03-FE_Gemini_격리실행_결과_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S03-DB `review` | 컨테이너 출력 bytes/hash·금지 명령·lease 회수·Evidence ID 수집 runner — **Claude** | **U1~U6 간접** | 실제 Linux 제한 컨테이너·ToolGateway와 제품 Storage 출력 | [[2026-09-22_18-27-37_KST_S02-DB_S03-DB_Codex_독립검토]] |
| S04-FE `review` | 만료·취소·중복 클릭·SSE 단절/재연결·전송 재개 UI/Chrome matrix — **Gemini** | **U2~U5 간접** | 실제 Node 전달 중단·재개와 DB 상태/SSE 시간축 | [[2026-09-09_23-55-00_KST_S04-FE_Gemini_승인센터_SSE타임라인_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S04-DB `review` | HTTP+PG 만료 승인·cancel·idempotency·outbox crash/retry 통합 runner — **Codex** | **U1~U5 간접** | 물리 Node 전송 재개와 로컬 WSL2/Node 경계 인수 | [[2026-09-22_19-45-00_KST_S04-DB_S05-DB_S07-DB_Codex_owner판정]] |
| S05-FE `review` | snapshot/weight/policy version·후보 제외·Explain 일관성 Chrome 검증 — **Gemini** | **U1 토폴로지, U5 실제 자원** | 5노드 실제 snapshot으로 50동시/P95 결과를 화면과 대조 | [[2026-09-10_00-10-00_KST_S05-FE_Gemini_자원배치_토폴로지_Explain_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S05-DB `review` | 50동시 예약·동일 입력 반복·P95·fencing을 한 번에 산출하는 benchmark/JUnit 보고 도구 — **Codex** | **U1, U5** | 5노드 실측 locality/capacity에서 초과 0·P95 2초 측정 | [[2026-09-22_19-45-00_KST_S04-DB_S05-DB_S07-DB_Codex_owner판정]] |
| S06-FE `review` | WS/PTY 오류·재연결, editor diff, restart/restore 상태의 browser harness — **Gemini** | **U1, U5 간접** | 실제 원격 WS/PTY·remote Git·CP/Node 재시작 여정 | [[2026-09-10_00-25-00_KST_S06-FE_Gemini_개발작업공간_Monaco_Diff_Session_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S06-DB `review` | `WorkspaceRecovery` snapshot reader/checkout writer 제품 결속과 restart·restore hash Evidence 수집 — **Codex** | **U1, U5, U6** | 원격 Node에서 WS/PTY/Git·CP 재시작·Storage 복원을 한 여정으로 인수 | [[2026-09-22_21-13-00_KST_S06-DB_S08-DB_Codex_owner판정]] |
| S07-FE `review` | offline/recovering/stale·late result·fencing 상태를 구분하는 Chrome 장애 여정 — **Gemini** | **U1, U5 간접** | 5노드 중단·네트워크 분할·late write/cache 경합 | [[2026-09-10_00-45-00_KST_S07-FE_Gemini_분산복구_Stale_Fencing_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S07-DB `review` | 이탈 60초·복구 성공률 95%·late write/cache 경합 반복 측정 도구와 CX01 19건 실행 전환 — **Codex** | **U1, U5, U6** | 5노드 장애/분할 반복과 실제 시간·성공률 통계 | [[2026-09-22_19-45-00_KST_S04-DB_S05-DB_S07-DB_Codex_owner판정]] |
| S08-FE `review` | 권한 오류·Docker socket 차단·kill switch·복원 상태 admin Chrome matrix — **Gemini** | **U2, U3, U5, U6 간접** | 실제 GPU workload, 제한 컨테이너, backup/restore·승인 우회 0 | [[2026-09-10_01-10-00_KST_S08-FE_Gemini_보안감사_격리_관리자콘솔_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S08-DB `review` | hosted recovery 19 skip 해소용 opt-in, 독립 역할 restore/PITR·보존 Evidence runner — **Codex** | **U5 장비/GPU, U6 backup Storage** | 물리 GPU, off-device backup, 독립 역할 복원과 실제 보존 GC | [[2026-09-22_21-13-00_KST_S06-DB_S08-DB_Codex_owner판정]] |
| S09-FE `review` | 고정 SHA·원본 입력/출력·skip 0인 100 prompt/30 coding eval과 누출·금지행동 변이 도구 — **Gemini** | U1~U6 직접 입력 없음; 운영 모델/허용 도구 결정은 별도 | 실제 모델·도구 adapter 실행 환경; 합성 eval을 제품 인수로 세지 않음 | [[2026-09-10_01-30-00_KST_S09-FE_Gemini_자연어요청_예산_Diff_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S10-FE `review` | adapter conformance·실패 분류·lineage query·deployment digest 검증 harness — **Gemini** | U6은 artifact/model 저장소 선택 시 간접; 배포 정책은 별도 | 실제 lineage 저장소/query와 모델 artifact·승인된 배포 target 왕복 | [[2026-09-10_01-45-00_KST_S10-FE_Gemini_AI도구_모델계보_배포_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S11-FE `review` | 같은 SHA의 WCAG·시각 회귀·E2E matrix와 부하/복원/보안 결과 집계 도구 — **Gemini** | **U1~U6 간접** | 5노드 부하·장애복원·보안 환경과 실제 배포 후보 브라우저 | [[2026-09-10_02-00-00_KST_S11-FE_Gemini_접근성_시각회귀_배포후보_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |
| S12-FE `review` | release manifest 일관성 검사, 로컬 HTTPS smoke, UAT·복구 Evidence 템플릿 — **Gemini** | **U1~U6 전체** | 5노드 내부망 TLS/Nginx 배포·사용자 인수·실제 복구 | [[2026-09-10_02-15-00_KST_S12-FE_Gemini_내부망HTTPS_웹배포_운영인수_개발과정]] · [[2026-09-22_Codex_FE_review_map_S02-S12]] |

## 다음 배정 후보 — 사용자 입력 없이 시작 가능

1. **Codex:** S05-DB benchmark/JUnit 보고 도구(50동시·결정성·P95)와 S07-DB 장애 반복 측정기(60초·95%)를 먼저 고정한다. 실제 5노드 값은 나중에 같은 도구에 주입한다.
2. **Claude:** S02-DB API↔PG 인증/격리 Evidence collector와 S03-DB 제한 컨테이너 출력·거부·lease 회수 묶음을 고정한다.
3. **Gemini:** S09-FE 고정 입력 eval runner를 우선 만들고, 이어 S02-FE 실제 API 기반 Chrome 시나리오와 S04-FE SSE/중복/만료 matrix를 확장한다.
4. **Codex 후속:** S06-DB 제품 snapshot reader 결속과 S08-DB recovery/PITR 실행 전환은 코드 영향이 크므로 위 측정 도구 다음 카드로 분리한다.

어느 항목도 이 지도 작성만으로 `done`이 되지 않는다. U1~U6 또는 물리 자원이 필요한 행은 성공 신호와 고정 SHA Evidence가 들어온 뒤 owner/reviewer가 다시 판정한다.

## 검증·착지

Registry와 ontology는 변경하지 않았다. 초안에서 `check_docs.py` **813 documents / exit 0**, `check_ontology.py` **48 task mappings / exit 0**, `check_ontology_generation.py` **4 artifacts graph-equivalent / exit 0**, `check_doc_single_source.py --ratchet` **18 pairs / exit 0**, `git diff --check` **exit 0**을 확인했다. 표의 task 행은 **20개**, planned는 **26/26 모두 non-done dependency 보유**로 기계 대조했다.

Orca worktree의 `sync_obsidian.py --check`는 두 진행판이 `both-diverged`라 **2 conflicts / exit 3**이었다. 이 checkout에서는 `--apply`하지 않고, integration 착지 뒤 코디네이터가 정본 checkout에서 sync한다. 정확한 R1 candidate의 게이트와 landing SHA는 receipt에 기록한다.
