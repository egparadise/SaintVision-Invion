---
doc_id: "HIST-STUDIO-AUTH-ENTRY-ERROR-20260915"
title: "2026-09-15 STUDIO-AUTH-ENTRY Codex 오류해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:54:21+09:00"
source_of_truth: "Git"
---

# 2026-09-15 STUDIO-AUTH-ENTRY Codex 오류해결

최초 전체 App 시험은 2실패/36통과였다. 로그인은 성공했으나 시험이 실제 `/decision` 대신 `/decisions`를 기다려 timeout이 났다. 실패 로그인 시험은 전체 DB 투표를 세어 이전 component 시험의 투표를 오인했다. URL을 정정하고 approval_id로 DB 검증을 한정한 뒤 38개 통과, 화면 보완 후 재검증도 38개 통과했다. 이들은 시험 결함이며 서버 권한 우회로 기록하지 않는다.

실제 프로젝트 진입은 UI가 business `projects`만 기대하고 kernel `items`를 거부하던 계약 불일치를 수정해 통과했다. 임의 로그인 코드와 JSON token 교환·redirect URI 누락도 제거했다. 인증 프로토콜 참고: https://www.rfc-editor.org/rfc/rfc6749#section-4.1.3 및 https://www.rfc-editor.org/rfc/rfc7636#section-4.5.

한 번의 apply_patch가 같은 Login 파일의 삭제·추가를 동시에 지정해 거부됐으며 파일 변경 없이 중단됐다. 별도 파일 쓰기로 적용했다. 존재하지 않는 시험 경로는 수정 후 실제 approval 계약 10개 통과를 따로 기록했다.

동기화는 외부 3파일 변경으로 쓰기 전 중단됐다. 원문 보존·diff 검토·동일 bytes 기준 adoption 후 정상 export를 수행한다. 최신 원문이 다시 바뀌면 재확인 없이 덮어쓰지 않는다.
