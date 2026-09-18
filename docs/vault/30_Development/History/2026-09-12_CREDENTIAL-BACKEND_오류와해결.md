---
doc_id: "ERR-CREDENTIAL-BACKEND-20260912"
title: "2026-09-12 CREDENTIAL-BACKEND 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:12:51+09:00"
source_of_truth: "Git"
---

# 2026-09-12 CREDENTIAL-BACKEND 오류와해결

검증 기준0f5f4e8, owner Codex / reviewer Claude pending. [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]].

1. Claude dcad652 Context는 오류 message와 causeRef에 입력 item_id를 넣었다. 본문만 검사하여 metadata에 같은 비밀을 넣는 경우도 막지 못했다. ordinal·고정 field/label만 노출하고 content/item_id/source_uri를 저장 전 검사했다. 실제 PostgreSQL에서 세 위치 모두 snapshot 수가 늘지 않음을 확인했다. 알려진 패턴의 경계이며 DLP 전면 해결은 아니다.
2. Claude5995b8b readiness는 일부 관측만으로 wouldAdmit=true를 반환하고 DSN을 argv로 받았다. ADR-078에 따라 unknown/null과 관측 결과를 분리하고 보호 환경 입력·고정 오류·읽기 전용 일관 snapshot으로 바꿨다. 이 변경은 kernel 실행 권한 API의 대체물이 아니다.
3. Linux runner에 tests/core/test_readiness_cli_boundary.py를 전달한 첫 명령이 허용 경로 검사에서 exit1로 거부됐다. runner는 tests/integration/test_* 및 tests/test_*만 허용한다. guard를 우회하지 않고 core3개는 같은 SHA Windows에서 수행했으며 Linux의 허용154개는 exit0으로 완료했다.
4. 같은 SHA CI6개는 job 시작 전 계정 제한으로 실패했다. 로컬 성공으로 CI 성공을 대체하지 않는다. 운영자 계정 제한 해소 후 동일 SHA를 다시 실행한다. [CI 증거](../Evidence/credential-backend-0f5f4e8-ci.json).

운영 secret/DB/Node는 바꾸지 않았고 시험 소유 자원만 정리했다. 원격 profile/IdP/실제 Provider·장비는 별도 미완료다.
