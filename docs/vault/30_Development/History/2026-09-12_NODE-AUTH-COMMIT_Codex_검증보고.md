---
doc_id: "HIST-NODE-AUTH-COMMIT-REPORT-20260912"
title: "2026-09-12 NODE-AUTH-COMMIT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T11:46:52+09:00"
source_of_truth: "Git"
---

# 2026-09-12 NODE-AUTH-COMMIT Codex 검증보고

CX-01/CX-02 · owner Codex / reviewer Claude pending. Base345cc1a → **28308870268b2d37b924d74e4305f129b5b9adb1**, agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_NODE-AUTH-COMMIT_Codex_착수]].

## 이번 범위와 발견

Node storage challenge/Evidence 연결의 선행 인증 경계를 검토했다. public inbound node_auth는 ASGI client_cert_error를 읽지 않았으며 heartbeat는 인증 session과 기록 transaction이 분리돼 있어 사이에 retirement/certificate rotation이 끝나도 옛 principal로 기록했다. 원본3개 actual DB 재현에서 검증 오류가 있는 등록 fingerprint를 인증했고, retirement/rotation 뒤 heartbeat가 applied=true였다.

ASGI는 인증서 검증이 실패해도 서버가 연결을 애플리케이션으로 전달할 수 있으며 client_cert_error로 실패를 알리도록 정의한다. 이 값이 None이 아니면 즉시 거부하고 proxy header로 재시도하지 않도록 고쳤다. [ASGI TLS Extension 공식 규약](https://asgi.readthedocs.io/en/latest/specs/tls.html).

잘못된 direct chain/빈 leaf도 proxy fallback을 허용하지 않는다. 표준이 허용하는 iterable chain의 첫 leaf를 처리한다. transport가 검증한 DER bytes 호환 입력은 유지한다. CA/TLS 검증 자체를 Python parser가 대신 구현한 것은 아니다.

NodePrincipal.lock_current는 tenant/node/certificate/status를 최신 row에서 확인하고 FOR UPDATE를 기록 transaction 끝까지 유지한다. heartbeat route가 모든 쓰기 전에 호출한다. 먼저 완료된 회수·교체·지문 제거는 AUTH-INVALID-CREDENTIAL/403, seq 변화0이다. 기록이 먼저 잠금을 얻으면 회수 UPDATE가 transaction 종료를 기다려 명확한 순서를 갖는다. 기존 sequence 원자 UPDATE·observations rollback 규칙을 유지한다. network I/O는 lock 밖에서 수행해야 한다. migration/Go Node 프로필 변경 없음.

## 실제 검증

| 명령/환경 | 실제 결과 | Evidence |
|---|---|---|
| cx01_local.py -p conftest .work/test_node_auth_original.py | 원본3개 assertion failure, exit1; 실제 격리 PostgreSQL, ASGI metadata/API 함수 입력 | [원본 재현](../Evidence/node-auth-commit-original.json) |
| cx01_local.py tests/test_node_auth_commit.py tests/test_node_auth.py tests/test_api.py tests/test_storage_check_integrity.py | **89 passed,0 skipped,exit0**, clean2830887 Windows/실제DB | [Windows cases](../Evidence/node-auth-commit-windows-2830887.json) |
| check_kernel_docker.py --prepared ... --tests 같은4개 | **89 passed,0 skipped,exit0**, clean2830887 Linux/실제DB | [Linux SHA/images/cases/cleanup](../Evidence/node-auth-commit-linux-2830887.json) |
| git push origin agent/codex/workspace-bridge |2830887 exit0|PR19|
| 동일 SHA Actions6개 |계정 결제/한도 때문에 job 미시작 failure|[CI ID/annotation](../Evidence/node-auth-commit-2830887-ci.json)|

89는 새 인증19+기존 인증19+API26+local Storage25. 두 환경의 공통 시험은 합산하지 않는다. 초기 API3개 실패는 서비스 실패가 아니라 시험에서 기존 AUTH403을401로 기대했던 오류다. 계약 확인 후403/정확한 code/DB heartbeat0을 검증했다. 초기 실패와59개 라이브러리/시험 warning을 숨기지 않으며 최종 실패0과 구분한다. [[2026-09-12_NODE-AUTH-COMMIT_오류와해결]].

ASGI scope와 allowlisted proxy를 사용하는 실제 API/DB 시험이다. 물리 TLS 연결·원격 .225·인증서 배포·실제 7개 실행 인수는 이번에 수행하지 않았다. 등록 지문을 선택하는 것과 OS/원격 위치를 증명하는 것은 다르다. inbound public binding 보강은 inv.node_channels recovery epoch의 대체물이 아니다.

## 다음 작업과 현재 한계

인증 선행 보강은 전달했지만 **storage challenge/서명 결과 수집·StorageCheck/Evidence 원자 기록은 아직 구현되지 않았다.** 다음 Codex는 기존 Go transport의 nonce/probe와 kernel ChannelProof/epoch 재검증을 확장하는 경로부터 진행한다. inv.evidence는 run-bound이며 public.evidence_envelopes와 중복 표현이 존재하므로 새 운영 원장을 만들거나 가짜 run ID를 넣지 않는다. 실행 kernel의 Run/기존 Evidence와 public StorageCheck를 연결하는 계약을 먼저 고정한다. local storage_check.py는 계속 read-only다.

Claude는2830887/ADR-087 독립 검토를 수행하고, 최신00b1159 알람 보고/partition 운영화는 별도 검토 대기다. 이번에00b1159의2파일 변경만 확인했고 작성자7개 시험·현재 배포 partition2027-01-01 주장은 독립 검증하지 않았다. 외부19:20 표기는 작성자 시각이며 이번11시대 관측으로 재해석하지 않는다. [외부 원문/hash](../Evidence/obsidian-proposals-20260912-node-auth/manifest.json). 과거 backup/permission 보완에 대한 검토 요청 기록을 삭제하지 않았다.

전체 개발 성숙도 추정 **57.81% 완료/42.19% 잔여 유지**. 이번은 기존 고위험 범위 안의 선행 수정이고 signed storage 관측 인수는 남아 점수를 더하지 않는다. CI·독립 검토·운영 인수 미완료, task done으로 승격하지 않는다. 문서 검사/push/Obsidian 결과는 전달 기록에 추가한다.


전달 준비: check_docs.py exit0(원문24·문서312·작업48), check_ontology.py exit0, git diff --check exit0. 변경 Python Black 적용. PR19 설명 갱신/draft 유지. Obsidian 외부2개를 원문/hash 보존했고 동일 bytes 인수 후 정본 동기화한다.
