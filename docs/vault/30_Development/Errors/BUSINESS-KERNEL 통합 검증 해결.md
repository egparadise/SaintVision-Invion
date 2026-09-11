---
doc_id: "FIX-BUSINESS-KERNEL-001"
title: "BUSINESS-KERNEL 통합 검증 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:57:52+09:00"
source_of_truth: "Git"
---

# BUSINESS-KERNEL 해결 기록

[[BUSINESS-KERNEL 통합 검증 오류]]의 실패를 그대로 보존한다. `255b29e`에서 다음을 보완했다. 최종 전체 CI·Artifact 결과는 연결한 History 보고서가 정본이며 이 페이지의 구현 설명만으로 통과를 선언하지 않는다.

- 최초 전송 전 권한·승인·fence가 더 이상 유효하지 않으면 Run을 failed로 전이하고 같은 signed permit의 Node cancel 경로를 사용한다. 실행을 새로 시작하거나 Lease를 즉시 반환하지 않는다. Node가 stop receipt 또는 미수신 취소 tombstone을 기록한 뒤 정확한 예약 집합을 반환한다. 불확실한 취소의 다음 시도도 cancel이며 새 execute로 돌아가지 않는다. 이미 전송을 예약한 일반 crash 복구는 기존 observe 경로를 유지한다.
- queued 이후 requester 철회 시험은 실제 processStarted=false 영수증·Run failed·Lease 0·자동 lock 해제를 요구한다. 기존 grant 철회 시험도 observe 기대값을 cancel로 바꾸고 Run failed를 추가 검증한다. 승인 우회나 assertion 삭제로 통과시키지 않는다.
- 인증된 Node의 heartbeat/snapshot 429만 NODE-0050 retryable 503으로 분류한다. restricted Workspace 관측은 10/20ms 간격과 매번 새 nonce로 총 3회만 시도한다. epoch/인증 403과 실행 POST의 429는 자동 재시도하지 않는다. 실제 TLS 서버의 관측/실행 429 분리 3건, busy/superseded의 fresh nonce·3회 상한을 검증한다.
- 로컬 `pytest tests/core/test_node_tls.py tests/core/test_workspace_api_boundary.py tests/test_migrations.py -q --disable-warnings`: 51 passed, exit 0. 실제 PostgreSQL·Go·Docker 경로는 동일 SHA CI에서 추가 확인한다.

[[Codex 업무 binding과 실행 커널 연결 계약]]의 ADR-050/051/052에 반영했다. peer reviewer Claude의 독립 검토와 운영 실장비 검증은 pending이다.

수정 구현 `255b29e2b74a61bb8ef3dd798cacee10e7faecec`의 Core/Backend/Documentation push·PR 검사 6개가 모두 성공했다. 실제 Artifact에서 전체 Python 962개, 업무 16개·샤드 21개·Workspace 20개 부분집합과 Go race를 확인했다. 명령·CI ID·hash·다음 담당자는 [[2026-09-10_13-57-52_KST_BUSINESS-KERNEL_Codex_검증보고]]를 따른다.
