---
doc_id: "HIST-PTY-INTENT-START-20260912"
title: "2026-09-12 PTY-INTENT Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T00:18:20+09:00"
source_of_truth: "Git"
---

# PTY-INTENT 착수

CX-01 / S06-BE·S06-DB·S08-DB, owner Codex, reviewer Claude pending. base fd32eda3bf19795209c939797801a451d360eb5b, branch agent/codex/workspace-bridge, PR19.

진행판1.0.17 / Codex 작업판1.0.3 / Workspace 계약1.1.0 / ADR INDEX1.29.0 / agent-delivery1.1.0 / core-reliability1.0.0을 따른다.

목표: Claude F2의 응답 유실/후행 감사 간극을 보강한다. Node 중복 실행 방어는 이미 존재한다. mutation frame은 immutable intent를 먼저 commit하며, 완료 audit는 현재 권한·채널·정상 응답 확인 후만 남긴다. 미확정 순번의 다른 내용과 후속 입력을 거부하고 poll은 완료 증거로 만들지 않는다. 기존 완료 audit와 published migration 이력을 보존한다.

합격 증거: 실제 Linux PTY/mTLS/DB에서 intent 선기록·전송 전 실패·응답 유실·같은 내용 replay·다른 내용 및 앞선 미확정 입력 거부, 기존 ticket/권한/취소 회귀, RLS/불변 intent, prior upgrade 및 definer 정책/복원 회귀. 운영 Node/DB 변경 없음. 구현→검증→commit/push/CI→Obsidian→Claude 독립 검토.
