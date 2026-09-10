---
doc_id: "RES-NODE-001"
title: "RES-NODE-001 중첩 제한과 삭제 후 정지 확인"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:16:02+09:00"
source_of_truth: "Git"
---

# RES-NODE-001 중첩 제한과 삭제 후 정지 확인

StrictJSON은 root depth 1부터 64 제한을 적용한다. admittedAt+budget deadline에 fsync/create/start 시간을 포함하고, stopped 상태 및 force=false 삭제 성공 뒤에만 durable receipt를 저장한다. PID 1 supervisor는 private PID namespace에서 별도 monotonic timer와 출력 폐기로 Node-agent 사망 후에도 종료를 집행한다.

수정 구현 98d02be8528c3a09c5d38239fd8fcce93affa39e의 Core CI #34373543925 success. Go race detector 14개 top-level/37개 leaf case 통과. Python 194 tests/0 failures/0 errors/0 skipped 안에 실제 Node Docker 16건과 signer 6건을 포함한다. 원본 [[node-98d02be-tests.xml]], [[node-98d02be-unit.jsonl]], [[node-98d02be-provenance.json]]. Linux 합성 환경 검증이며 운영 장비/Windows/GPU 시험은 아니다.

Go JSON 집계 시 테스트가 없는 4개 command/helper 패키지의 package-level skip은 실제 Test skip과 구분했다. 테스트 case skip은 0이며 해당 명령은 CI에서 빌드되고 실제 컨테이너 통합 시험에서 실행됐다. [[ERR-NODE-001 JSON 중첩 경계와 실행 종료 경쟁 검토]]의 대응이다.
