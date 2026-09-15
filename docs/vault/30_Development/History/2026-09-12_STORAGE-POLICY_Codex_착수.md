---
doc_id: "HIST-STORAGE-POLICY-START-20260912"
title: "2026-09-12 STORAGE-POLICY Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T15:20:07+09:00"
source_of_truth: "Git"
---

# 설정 설치·교체의 영속 경계

Base0c1a4cf3d698130b0ca3803f10f19aea7e310ea5 / agent/codex/workspace-bridge / CX-02 Codex owner, Claude reviewer pending. agent-delivery1.1.0/core-reliability1.0.0, Storage계약1.4.0/ADR-091/진행판1.0.36 확인. 운영 설치 전 선행 결함은 재시작 뒤 storage-policy의 버전 역행을 막을 journal floor가 없다는 것이다.

기존 Node identity/epoch journal에 contribution별 root/channel 두 버전과 hash를 보존하고 같은 버전의 변경·한 축만 올려 다른 축을 되돌리는 교체를 거부한다. 실제 로컬 policy/root/현재 인증서를 검증한 뒤 영속화하고 보호 정보가 없는 시작 확인 기록을 출력한다. 이 로컬 기록은 서버 mTLS 운영 인수와 별도다. 운영 PC/키/volume 변경이나 실제 설치 완료를 주장하지 않는다. 검증 후 설치/교체 운영 절차와 남은 원격 작업을 기록한다.
