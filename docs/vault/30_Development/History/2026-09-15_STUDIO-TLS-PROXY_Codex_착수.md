---
doc_id: "HIST-STUDIO-TLS-PROXY-START-20260915"
title: "2026-09-15 STUDIO-TLS-PROXY Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:59:12+09:00"
source_of_truth: "Git"
---

# Studio TLS 배포 경계 검증

CX-01 후속. Owner Codex, reviewer Claude 대기, Gemini 화면/배포 인수 대기. agent-delivery1.1.0/core-reliability1.0.0. 코드 base33d63d5, agent/codex/approval-browser. 문서 base1d68a8b workspace-bridge. 공통 진행판·Codex 작업판·운영 절차를 읽었다.

실제 Nginx container의 TLS 인증서 검증, /studio·callback 정적 경로, 인증 설정 주입, 보안/cache header, query 로그 비노출, API 상태 전달과 중단을 확인한다. 우선 정본 Dockerfile build와 전용 transport fixture로 재현한다. Fixture는 proxy 계약 검증용이며 실제 커널/JWT/DB 인증 시험이라고 쓰지 않는다. 이전 실제커널/Edge 로그인 결과와 별도 증거로 관리한다. 운영 서비스·인증서·장비를 변경하지 않는다.
