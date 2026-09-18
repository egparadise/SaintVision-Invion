---
doc_id: "ERR-CREDENTIAL-PROVISION-20260912"
title: "2026-09-12 CREDENTIAL-PROVISION 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:26:09+09:00"
source_of_truth: "Git"
---

# 2026-09-12 CREDENTIAL-PROVISION 오류와해결

owner Codex / reviewer Claude pending. [[2026-09-12_CREDENTIAL-PROVISION_Codex_검증보고]].

c0397a3 Linux runner에서 tests/integration/test_credential_provision.py가 tools 디렉터리의 provision_credentials를 모듈명으로 import하여 ModuleNotFoundError가 발생했다. 수집 실패 exit2, 시험1 error이며 제품90개가 실행된 것으로 세지 않는다. private evidence는 .work/sv-kernel-9db2d0f2f3f6/runs/234deb6ec332에 보존한다. DB DSN/원문 로그는 공개하지 않는다.

76ba5ba에서 테스트가 저장소의 tools/provision_credentials.py를 명시적으로 로드하도록 수정했고 새 Linux 소스/이미지에서90개 실제 pass·0skip·exit0과 test 자원 정리를 확인했다. runtime/backend guard는 우회하지 않았다.

GitHub CI6개는76ba5ba에서도 account billing/spending 때문에 시작 전 실패했다. 로컬 성공으로 대체하지 않고 운영자 계정 조치 후 같은 코드 SHA CI를 재실행한다. 독립 검토·운영 인수 미완료라 PR19 draft와 공식 task in_progress를 유지한다.

Obsidian 사전check에서 공통 진행판/Gemini 작업판2개의 외부 편집을 검출해 exit1·쓰기0으로 중단했다. 외부원문/hash를 Evidence에 보존하고9532a35 실 Git 변경을 확인했다. 최신 canonical 이력·검토 finding을 유지하면서 작성자 수신 요약을 병합한다. 보존한 두 파일과 현재 대상의 byte 일치를 재검사하고 exporter의 adopt-identical로 같은 bytes만 수용한 뒤 정규 check/apply/check를 수행한다. state hash를 수동 변경하거나 미확인 외부 내용을 덮어쓰지 않는다.
