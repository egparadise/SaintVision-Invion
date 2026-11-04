---
doc_id: "RES-20261104-DOCKER-API152-BROWSER"
title: "Docker API152 브라우저 검증기 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-04T13:06:28+09:00"
source_of_truth: "Git"
---

# Docker API152 브라우저 검증기 해결

- error_id `ERR-20261104-DOCKER-API152-BROWSER`; resolution_scope `runtime_implementation`의 검증 도구; owner Codex; reviewer Claude pending.
- 소유 DB의 network를 `bridge`로 고정하고 `NetworkSettings.Networks.bridge.IPAddress`만 읽는다. legacy 필드·임의 첫 network는 권위가 아니다.
- 검증 가능한 IPv4 endpoint가 없으면 pytest를 시작하지 않고 exit 125 / not-run proof를 남긴다. secret-safe proof·소유 컨테이너 정리·실패 exit 보존을 유지한다.
- 재현 exit 1 → 수정 후 focused **48 passed**, exit 0. 원 명령·환경·KST·JUnit·source base는 [[2026-11-04_Docker_API152_브라우저_검증기_수정_Codex]]에 결속한다.
- `runtime_verified=false`: synthetic boundary 회귀는 통과했지만, 실제 Linux Docker/HTTP/브라우저 hosted lane 및 독립 review는 아직 수행/판정 대기다. 전체 프로그램이나 운영 인수 완료 근거로 쓰지 않는다.
- rollback은 원상 복구가 아니라 정상 Git 수정으로 수행하며 사용자 data·live Node·기존 volume은 변경하지 않았다. 다음 담당은 Claude 독립 reviewer와 exact-SHA CI를 결속할 Codex coordinator다.
