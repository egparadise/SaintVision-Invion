---
doc_id: "ERR-RECOVERY-INTEGRATION-20260911"
title: "2026-09-11 RECOVERY-INTEGRATION 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T18:53:13+09:00"
source_of_truth: "Git"
---

# 2026-09-11 RECOVERY-INTEGRATION 오류와해결

- **복원 판정/기록 계약**: Claude dee31e5의 _passed는 nonzero/음수/NaN 검증이 없고, 기록은 존재하지 않는 DrillMeasurement 인자를 사용했다. 5fc1116에서 공통 판정과 실제 서비스 기록으로 수정; core22/실PG12 및 관련 회귀로 확인.
- **측정/누락/보안**: target 목록에 없는 table, RTO의 조기 종료, source의 늦은 토큰, is_called 경계, 양쪽 schema RLS/owner/grant를 보강했다. 소스 참조/합격 증거는 [[2026-09-11_RECOVERY-INTEGRATION_Codex_검증보고]].
- **CI**: 5fc1116 6개 workflow 모두 billing/spending 제한으로 시작 전 실패. 로컬 성공과 별도로 미완료 기록. 운영 책임자가 해소 후 같은 code SHA CI를 실행한다.
- **Go 시험 호출**: PowerShell이 점이 있는 -test 옵션을 잘못 전달하여 시험 미실행 exit1. Python subprocess 인자 배열로 정확히 전달한 재실행은 3개 pass/exit0. 첫 오류를 제품 실패나 시험 성공으로 세지 않는다.
- **Obsidian**: check가 외부 편집 3개를 감지해 쓰기 없이 중단(exit1). 원문/hash/Git 대응을 보존하고 최신 owner 보고와 정본 판정을 합친 뒤 동일 byte만 baseline으로 인수한다. 현재 내용을 무시한 강제 덮어쓰기는 하지 않는다.
- **신규 인수 잔여**: Claude F1 제공량 경합 수정은 다음 CX-01. F2는 Node 중복 방어와 서버 감사 순서를 구분한다. Gemini local drain/만든 ticket/설정 검사 기반 배포·65% 보고는 정본 운영 인수로 승인하지 않는다.
