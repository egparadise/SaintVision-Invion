---
doc_id: "HIST-STORAGE-REPLACE-PREFLIGHT-START-20260912"
title: "2026-09-12 STORAGE-REPLACE-PREFLIGHT Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:45:15+09:00"
source_of_truth: "Git"
---

# 교체 사전 점검 착수

CX-02 / S12-ST, Codex owner, Claude reviewer pending. base c9dcb09a61a4fdcc59cf16211b0c9debcec0a05f, agent/codex/workspace-bridge. GUIDE-001/GOV-AGENT-001/GOV-GIT-001 1.1.0, ADR-093, agent-delivery1.1.0/core-reliability1.0.0.

이번 범위는 기존 정지된 관측 Node를 교체하기 전 읽기 전용 점검과 stale 재검사다. 기존 컨테이너/볼륨 독점 사용·정체성·전체 상태 파일 내용 및 권한을 확인하고 실제 Docker 시험으로 비변경을 검증한다. 삭제/재생성 executor와 실패 후 forward 재개는 이 선행 경계 위의 후속 단계다. 키/journal 원문을 증거에 출력하지 않는다. 운영 Node를 정지하거나 교체하지 않는다.
