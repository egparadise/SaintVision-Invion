---
doc_id: "ERR-BACKUP-OPEN-GUARD-20260914"
title: "2026-09-14 BACKUP-OPEN-GUARD Codex 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T19:47:26+09:00"
source_of_truth: "Git"
---

# CLI 패키지 경로 누락

첫 복원 명령은 saintvision 패키지 경로가 없는 환경에서 실행돼 ModuleNotFoundError/exit1로 DB 접속 전에 중단됐다. PowerShell 세션의 PYTHONPATH에 현재 checkout의 src 및 services/control-plane/src를 지정한 뒤 동일 clean3eced3b로 다시 실행해 실제 복원/검증 exit0을 확인했다. 테스트 환경에서 자동 제공되는 경로를 standalone CLI에서도 명시한다. 비밀 DSN은 출력하지 않았다. CI 실패는 별개 계정 billing 제한이다.
