---
doc_id: "HIST-STORAGE-NODE-TRANSPORT-ERROR-20260912"
title: "2026-09-12 STORAGE-NODE-TRANSPORT 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T12:57:44+09:00"
source_of_truth: "Git"
---

# 실행 오류와 해결

[[2026-09-12_STORAGE-NODE-TRANSPORT_Codex_검증보고]]에 최종 증거를 연결했다.

- 루트에서 go test를 실행해 go.mod를 찾지 못했다(exit1). 실제 services/node-agent module cwd로 실행했다. 저장소를 새로 init하지 않았다. 일부 존재하지 않는 source/test 경로 조회도 rg 목록으로 정정했다.
- TestStorageSlotDoesNotConsumeHeartbeatCapacity 초기 실패: 새 fake sampler가 아니라 기존 fixture Node profile 빈 값 때문에 heartbeat contract가503. 이 시험 fixture에 유효 profile을 설정한 후 Windows/Linux 최종 transport22 pass events를 확인했다.
- Python dataclass asdict의 tuple은 JSON Schema array의 Python list와 다르다. 전송 전에 canonical JSON을 strict parse하여 실제 wire 값으로 검증하게 했다. 최종 Go/Python Unicode 포함 통합 성공.
- Obsidian 인계 목록 외부 편집 감지→동기화 쓰기0 중단→원문/hash 보존→검증된 동일 bytes 인수 절차를 수행한다. 타 Agent의 보고를 운영 인수로 바꾸지 않는다.
- CI6개 job은 계정 결제/한도로 미시작. 로컬 테스트와 분리 기록. 실제 운영자 계정 조치 후 같은 SHA CI가 필요하다.
