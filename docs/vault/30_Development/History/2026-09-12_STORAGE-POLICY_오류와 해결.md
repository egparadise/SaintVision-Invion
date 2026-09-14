---
doc_id: "ERR-STORAGE-POLICY-20260912"
title: "2026-09-12 STORAGE-POLICY 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:25:11+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-POLICY 오류와 해결

선행 결함: Go --storage-policy hash pin은 프로세스 내부 값이라 재시작 후 옛 설정 수락을 막지 못했다. 기존 journal에 contribution별 root/channel 독립 최소 버전을 영속화하고 same-version equivocation을 거부했다. 신규7개 실제 재시작 시험을 포함한 Linux85개 통과(exit0). Windows Go runtime/transport 시험 exit0이며 Linux root 시험으로 대체하지 않는다.

CI6개는 account payment/spending limit 때문에 시작 전 실패다. 로컬 성공과 구분하고 운영 계정 조치 뒤 같은 SHA 확인을 기다린다. 운영 설치 bundle/원격 PC 변경은 미수행이며 Node journal/키 초기화로 우회하지 않았다.
