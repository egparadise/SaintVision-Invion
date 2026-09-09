---
doc_id: "ERR-NODE-001"
title: "ERR-NODE-001 JSON 중첩 경계와 실행 종료 경쟁 검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:16:02+09:00"
source_of_truth: "Git"
---

# ERR-NODE-001 JSON 중첩 경계와 실행 종료 경쟁 검토

개발 중 첫 Go TestByteBindingAndStrictJSON에서 65중 빈 array가 허용되어 실패했다(해당 go test exit 1). root를 depth 0으로 세어 문서의 64수준 경계보다 하나 더 허용한 것이 원인이다. 운영 장애 기록이 아니다.

별도 코드 검토에서 intent fsync 뒤 새 timer를 시작하면 승인 잔여 시간이 늘어날 수 있고, stopped 관찰만으로 ACK하면 지연된 Docker start와 경쟁할 수 있음을 확인했다. Node process 자체의 timer만으로는 Node SIGKILL 뒤 workload 정지를 보장할 수 없어 독립 PID 1 supervisor를 추가했다. 실제 장애 주입은 수정 후 CI에서 검증했으며 수정 전 물리 사고를 재현했다고 주장하지 않는다.

[[RES-NODE-001 중첩 제한과 삭제 후 정지 확인]]을 따른다.
