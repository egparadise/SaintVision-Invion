---
doc_id: "HIST-STORAGE-SIGNED-SAMPLE-ERROR-20260912"
title: "2026-09-12 STORAGE-SIGNED-SAMPLE 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T12:19:39+09:00"
source_of_truth: "Git"
---

# 검증과 전달 경계

[[2026-09-12_STORAGE-SIGNED-SAMPLE_Codex_검증보고]]의 실제 기록이다.

- 저장소 구조 확인 중 존재하지 않는 src/saintvision/kernel 및 20_Plans 경로를 조회했다(exit1). rg --files로 실제 services/control-plane/src/inv 및30_Development 경로를 확인해 계속했다. 제품 오류로 기록하지 않는다.
- Black 정렬 후 ConfiguredSampler 변경 patch의 예상 줄이 달라 적용 도구가 거부했다. 현재 파일을 읽고 정확한 구간에 불변 dataclass 변경을 적용했다. 검증 결과는 최종124fe97의 Windows124/Linux129다.
- Obsidian 외부2개 수정으로 sync --check exit1/쓰기0. 원문/hash를 보존하고 검증된 동일 bytes 인수 후 정본을 export한다. 타 Agent 완료 주장을 독립 승인으로 승격하지 않는다.
- 같은 SHA CI6개는 계정 결제/한도 때문에 job이 시작되지 않았다. 로컬 시험을 CI 통과로 표시하지 않는다. 운영 책임자 계정 조치 후 동일 제품 SHA CI가 필요하다.
- 구조적으로 남은 것: 서명 검증만으로 nonce 중복 방지/현재 DB 권한/원자 Evidence 기록을 충족하지 않는다. 현재 모듈은 기록하지 않으며 Go adapter와 durable commit이 다음 작업이다.
