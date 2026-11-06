---
doc_id: "ERR-IDP-WINDOWS-TRUST-20261107"
title: "로컬 IdP 인증서 기본 Windows 신뢰 미반영"
version: "1.0.0"
status: "blocked"
author: "Codex"
updated: "2026-11-07T03:59:21+09:00"
source_of_truth: "Git"
---

공개CER의정확한CA를지정하면IdP discovery HTTPS200이지만,현재Windows기본SSL은self-signed verify18이고ROOT/CA/MY동일인증서0이다. 이미승인된CurrentUser/Root등록의한정1회시도는Import-Certificate의UI is not allowed in this operation/exit1로실패했고전후저장소동일0이다. key/password/machine trust/검증우회는사용하지않았다.

Windows computer-use SKILL이필수로읽게하는외부guidance는Windows보안설정변경과securitypermission입력을금지한다. 인증서확인GUI를다른경로로우회하거나입력하지않고,기존로컬수동등록의실제반영은미완료로남겼다. 추가사용자승인질문은반복하지않으며코드/검토는계속한다. 실제명령·exit·시간·전후store·CApin은Root Evidence의idp-existing-public-ca-current-user-import-attempt.json 및idp-existing-public-ca-trust-boundary-root-decision.json에있다. 다음담당은기존공개인증서로컬등록을확인할사용자/장비관리자와그결과를재측정할Root다. 실제브라우저/SSO성공을이HTTP검사로추정하지않는다.
