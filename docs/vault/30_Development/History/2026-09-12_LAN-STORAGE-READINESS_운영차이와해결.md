---
doc_id: "HIST-LAN-STORAGE-READINESS-ERROR-20260912"
title: "2026-09-12 LAN-STORAGE-READINESS 운영차이와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:55:31+09:00"
source_of_truth: "Git"
---

# 확인된 차이와 해소 조건

[[2026-09-12_LAN-STORAGE-READINESS_Codex_검증보고]]의 live evidence를 기준으로 운영 테이블/공개 묶음이 최신 코드와 다름을 확인했다. 당장 파일 복사/권한 확대/kill switch 해제로 해결되는 문제는 아니다. 실제 서비스 역할·migration 이력·등록 owner/project를 검토한 후 의존 순서로 적용한다. Node 관측은 정상이며 workload 설치/실행 성공과 구분한다.

진단 중 Database.session을 호출하여 AttributeError(exit1)가 발생했다. 실제 API는 transaction이며 FOR SHARE가 있어 이번 순수 읽기 점검에서는 psycopg READ ONLY transaction에 tenant 설정과 명시적 scope 조건을 사용했다. 잘못 추정한 작업판 파일 경로도 실제 Agent별 작업 하위 경로로 정정했다. 이 실패들은 운영 변경을 발생시키지 않았다.

CI 6개 job은 결제 제한으로 미시작, 독립 검토와 실제 원격 Windows/WSL 경로·서명 Evidence·7개 workload 시험 미완료다.
