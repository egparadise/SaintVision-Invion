---
doc_id: "ERR-20261104-DOCKER-API152-BROWSER"
title: "Docker API152 브라우저 검증기 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-04T13:06:28+09:00"
source_of_truth: "Git"
---

# Docker API152 브라우저 검증기 오류

- error_id `ERR-20261104-DOCKER-API152-BROWSER`; task `BROWSER-HARNESS-API152`; owner Codex; reviewer Claude pending; 종류 environment/runtime harness; P1 CI 차단.
- 실제 발생: Desktop Browser run `41769889826`, job `126376855159`, 2026-11-04 12:55 KST. `tools/run_vf_security_tests.py`가 `NetworkSettings.IPAddress`를 읽다가 pytest 전에 실패했다.
- 기대: 소유 disposable PostgreSQL의 bridge endpoint를 실제 pytest에 전달하고 실제 실행 결과를 기록한다. 실제: Docker API v1.52에서 제거된 legacy 필드에 의존해 실행 전 `KeyError`가 났다.
- 로컬 재현: bridge/legacy 주소가 다른 inspect를 주입하면 낡은 주소가 전달되어 assertion 실패(exit 1). 실제 Docker/제품 실패로 위장하거나 skip을 PASS로 바꾸지 않는다.
- 원인 확정: 실제 traceback, Docker 공식 API 이력, 실패 회귀 사례가 일치한다. 비밀이나 운영 DSN을 이 페이지에 보관하지 않는다.
- 상태: 수정·로컬 회귀 확인, hosted/독립 검토 대기. 해결: [[RES-20261104-Docker_API152_브라우저_검증기]]. 다음 담당 Codex coordinator/Claude reviewer.
