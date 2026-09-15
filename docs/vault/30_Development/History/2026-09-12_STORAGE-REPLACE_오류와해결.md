---
doc_id: "ERR-STORAGE-REPLACE-20260912"
title: "2026-09-12_STORAGE-REPLACE_오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:12:16+09:00"
source_of_truth: "Git"
---

# 교체 재개 시험 오류와 해결

첫 실제 시험: 설치3개 통과, 교체7개는 첫 교체 또는 중단 후 진행은 가능했으나 반복 재개에서 실패했다. 유지된 Docker volume의 CreatedAt 필드가 정책 쓰기 이후 달라졌다. preflight 원본 hash를 유지하고 교체 중에는 CreatedAt을 제외한 모든 metadata, 정확한 보존 컨테이너 ID/상태 mount, old/new만의 consumer 집합으로 검증했다. 이름/driver/label/mountpoint 변경은 계속 거부한다.

별도 시험 실패는 Linux에서 선택한 임시 port가 Windows의 TCP 예약 범위와 겹쳤기 때문이다. 호스트에서 사용 가능한 port를 선택하고 시험 컨테이너에 전달하도록 했다. 포트 예약을 없애거나 운영 방화벽을 바꾸지 않았다.

최종 f766146 실제 Docker11/경계111 exit0. CI6개는 결제 제한으로 job 시작 전 실패. 운영 장비 변경 없음. [[2026-09-12_STORAGE-REPLACE_Codex_검증보고]] 참조.

