---
doc_id: "HIST-IMAGE-POST-CLEANUP-001"
title: "Docker 정리 후 고정 이미지 보안 재검증"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T11:47:55+09:00"
source_of_truth: "Git"
---

# Docker 정리 후 고정 이미지 보안 재검증

- owner Codex/reviewer Claude, base90c07c6, branch agent/codex/image-post-cleanup, 착수2026-09-18T11:47:55+09:00. 공통/개인판·agent-delivery1.1.0/core-reliability1.0.0 확인. 범위는 동일 image 재실행/증거 판정이다. VF-CL-R-001 시험 구현(사전 prune/best-effort cleanup/진단)은 Claude owner이며 수정하지 않는다.
- 사용자 독립 검증 수신: a591f4f DSN CLI exit2, 해당 시험5 passed/1 skipped, tip90c07c6 전체 비-integration1074 passed/489 skipped/0 failed. MIGRATION-PREREQUISITE-001 수정에 대한 사용자 검증 완료이며 Claude 검토를 대신 수행했다고 쓰지 않는다.
- 사용자 정리 보고: kernel-test exited130개/bridge-test7개 표적 제거, 전체187→54, build cache3.624GB 회수, running/이미지/볼륨 보존. 제거137와 순감소133의 차이는 동시 생성 등 확인되지 않았으므로 합산 재구성하지 않는다. Codex가 광역 삭제를 재실행하지 않는다.
- Codex 읽기 전용 확인: 운영DB 및 Orthanc h1/h2 모두 Up3days. image sha256:b93b5ef1f94469bc4b18c1214354249ec9f55974aef30898287f5feac13c1d7e 존재, Config.User65532:65532.
- 동일 runner/시험소스, `VF_EVIDENCE_PREFIX=cx01-image-post-cleanup VF_TEST_IMAGE=<위digest> python tools/run_vf_security_tests.py tests/integration/test_server_container.py`: exit1, pytest 이전 disposable PG inspect에서 daemon i/o timeout. 시험0건, own PG 컨테이너 제거 확인. Evidence/cx01-image-post-cleanup/attempt1.json.
- Docker version20.10.22 응답 정상. 일시성 여부를 확인하는 동일 조건 재시도1회 진행 중(prefix cx01-image-post-cleanup-retry). prior image1pass/7fail 증거는 그대로 보존한다.
- 다음 Codex: case별 실패 위치/보안 단언 도달 여부를 판정하고 정본 갱신. CI billing/원격 mTLS 인수는 별도 대기다.

## 재실행 결과와 판정

- 두 번째 동일 digest 실행: **4 passed/4 failed/0 skipped, exit1**, own PG 제거 완료. healthy/workspace/unreadable/business 통과. healthy/workspace/business는 uid65532·401 Bearer·실제 JWT 읽기·설정 readonly 단언까지 통과했다. unreadable은 설정 읽기 거부 기동 종료를 확인했다.
- writable: 본문 이후 volume rm에서 daemon i/o timeout. public-signing-key: finally의 소유 label inspect에서 daemon i/o timeout. 두 건은 정리 실패이며 pytest 합격으로 승격하지 않는다.
- business-workspace: workspace 소유권 준비용 docker run이 `unable to upgrade to tcp, received 500`으로 실패했다. 이어 working volume in-use 정리가 원래 오류를 가렸다. Workspace persistence 보안/재시작 단언에 도달하지 못했다.
- business-kernel-role: startup state docker inspect가90초 timeout. 잘못된 DB role 거부 보안 단언은 이번에도 미검증이다.
- 이전7실패 중4건이 합격,3건은 미완. 이전에 통과했던 writable도 이번에는 정리 실패했다. 정리 효과로 일부 진행은 확보했지만 자원 고갈이 유일 원인이었다고 확정할 수 없다. 제품 보안 단언 실패는 이번 traceback에서 관측되지 않았으며, 제품 전체 무결함이나 image8/8합격을 뜻하지 않는다.
- 비교가능성: image digest 동일, test_server_container.py와 run_vf_security_tests.py는 기존8e9f8c8과 byte동일. comparability.json. 첫 시도0시험·두 번째4/4·기존1/7을 모두 보존하고 cx01-landing/image-tests.json은 최신 결과/이전 evidence 링크를 기록한다.
- 안전 정리: 이번 실패ID·label·image·initializer command·mount로 소유 확인한 종료/created 컨테이너2개와 임시volume3개만 제거(exit0). 광역 prune, 운영 컨테이너/이미지/다른 볼륨 변경 없음. cleanup.json. 운영 DB/Orthanc3개 실행 상태 확인.

## 인계

- Claude VF-CL-R-001: 위 startup-inspect90초/daemon I/O/initializer HTTP500/원래 예외를 가리는 cleanup 오류를 입력으로 진단·정리 개선을 진행한다. Codex가 시험 구현을 중복 수정하지 않았다.
- 다음 Codex: Claude 변경 수신 후 동일 digest 재검증. CI billing 사용자 대기, 실제 운영mTLS/5대인수 미완. 단순 반복 실행으로 실패를 숨기지 않는다.
