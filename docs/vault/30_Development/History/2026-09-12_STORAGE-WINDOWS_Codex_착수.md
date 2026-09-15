---
doc_id: "HIST-STORAGE-WINDOWS-START-20260912"
title: "2026-09-12 STORAGE-WINDOWS Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:35:24+09:00"
source_of_truth: "Git"
---

# Windows/WSL 저장소 교체 진입점

CX-02/S12-ST, Codex owner/Claude reviewer pending, base773e3e6d343c1ee316ebb400cad1f38529cc8f4a, agent/codex/workspace-bridge. GUIDE/GOV-AGENT/GOV-GIT1.1.0, ADR-095, agent-delivery1.1.0/core-reliability1.0.0.

범위: Windows 특정 허용 폴더·policy hash 입력 검증, Ubuntu WSL Python bridge의 기존 identity 검사·고정 private 준비 기록·그 hash를 지정한 apply/resume, 최소 결과 검증. 기존 키/journal/정책 파일 덮어쓰기 방지. Node 자동 정지/방화벽 변경/원격 운영 변경 없음. 실제 Linux Docker bridge 시험과 Windows launcher 모사 시험을 구분한다.
