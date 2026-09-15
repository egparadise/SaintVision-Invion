---
doc_id: "HIST-PTY-INTENT-ERRORS-20260912"
title: "2026-09-12 PTY-INTENT 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T00:24:11+09:00"
source_of_truth: "Git"
---

# 2026-09-12 PTY-INTENT 오류와해결

## 응답 유실의 감사 공백

기존 흐름은 Node 응답을 받은 뒤에만 frame audit를 썼다. Node는 중복 입력을 이미 방어하지만, 응답이 유실되면 서버에 시도 기록이 남지 않았다. 0034 intent 표와 전송 전 transaction으로 보완하고, 성공 audit는 기존 후행 확인 시점을 유지했다. 의도 기록 자체를 실행 성공으로 바꾸지 않는다.

전송 전 오류/실행 뒤 응답 유실/scope 위조/DB intent transaction 실패는 의도적으로 주입한 시험이며 현재 발견된 운영 장애가 아니다. 실패 시 raw 입력·키·nonce·출력을 예외/감사에 붙이지 않는다. 부분 write/종료한 PTY는 자동 재실행하지 않는다.

## 검증 범위 기록

21개 upgrade가 실행되는 동안 문서 Evidence만 추가되어 harness 종료 dirty=true가 기록됐다. 제품/시험/migration은1460634 동일임을 git status로 확인했다. 이 실행을 clean으로 표기하지 않았다. 별도 Linux61은 clean1460634이다.

## CI 외부 차단

1460634의6개 workflow가 계정 결제/사용 한도 때문에 시작 전 실패했다. 로컬 통합 성공은 CI 합격이 아니다. 운영자 조치 후 같은 SHA 재실행과 독립 reviewer 검토가 필요하다.
