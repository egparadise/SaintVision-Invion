---
doc_id: "HIST-STUDIO-TLS-PROXY-ERROR-20260915"
title: "2026-09-15 STUDIO-TLS-PROXY Codex 오류해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T01:07:48+09:00"
source_of_truth: "Git"
---

# 2026-09-15 STUDIO-TLS-PROXY Codex 오류해결

첫 fixture는 Docker --internal network를 사용하여 이 환경에서 publish한 호스트 포트가 inspect에 없었다. 처음에는 Nginx 종료로 추정했으나 stderr까지 확인해 startup fatal 오류가 없음을 확인했다. 전용 bridge network와 localhost-only publish로 바꾸고 Running/port를 확인하여 해결했다. 운영 네트워크를 바꾸지 않았다.

그 뒤5통과/1실패는 중단된 backend 연결이 기본 timeout으로 대기해 발생했다. Nginx 연결 제한2초와 502/504 거부 검증을 적용한 뒤6개 통과했다. 실제 Edge HTTPS 렌더링/캐시 검증을 추가한 최종은7개 통과다.

Compose 최초10통과/1실패는 normalized JSON이 false인 create_host_path 필드를 생략하는데 시험이 반드시 키가 있다고 가정해서 발생했다. 생략된 false를 처리한 뒤11개 통과했다. 제품 mount는 명시 create_host_path=false를 유지한다.

이전33d63d5 Nginx 설정으로 헤더/SSE/로그3실패를 따로 재현했다. 최종수정 통과와 구분하여 기록했다. build warning2 moderate 의존성과 deprecated http2 설정은 이번 실패 원인이 아니며 미해소로 인계했다.

Obsidian3파일 외부 변경은 쓰기 전 감지하여 obsidian-proposals-20260915-studio-tls에 원문/해시를 보존했다. Gemini6b32c5a의 새 EvidenceViewer 및137시험/26route 보고를 읽었고, project→flat→ResultView 합성 fallback은 신규 검토 대상으로 남겼다. 보존 원문과 destination hash가 동일할 때만 adoption/export한다.
