---
doc_id: "HIST-CREDENTIAL-CONFORMANCE-START-20260912"
title: "2026-09-12 CREDENTIAL-CONFORMANCE Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T00:43:33+09:00"
source_of_truth: "Git"
---

# CREDENTIAL-CONFORMANCE 착수

CX-02 / S01-BE·S08-ST / owner Codex / reviewer Claude pending. base34d457c8921e2c99d6f1cee2b94a46127211bb26, branch agent/codex/workspace-bridge, PR19. 공통 진행판1.0.19 / Codex1.0.5 / ADR075·076·운영계약1.0.0 / agent-delivery1.1.0 / core-reliability1.0.0을 따른다.

공통 typed interface와 backend-independent pytest 보안 conformance를 구현한다. 정상 사용·scope 거부·해석 후 회수·파일 경계·오류 비밀 비노출·정확한 버전·자동 재실행 금지를 시험한다. 검증용 모델과 의도적으로 잘못된 구현에 시험군을 적용해 검출력을 확인한다. 모델 결과는 실제 Linux backend/DB/외부 Provider 합격이 아니다. Claude가 같은 suite에 실제 harness를 연결하도록 인계한다.
