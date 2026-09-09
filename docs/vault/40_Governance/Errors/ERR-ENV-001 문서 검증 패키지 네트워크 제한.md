---
doc_id: "ERR-ENV-001"
title: "ERR-ENV-001 문서 검증 패키지 네트워크 제한"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T15:33:26+09:00"
source_of_truth: "Git"
---

# ERR-ENV-001 문서 검증 패키지 네트워크 제한

종류: environment. 제품 오류 아님.

pip install에서 pypi.org 연결 WinError 10013, exit 1. 네트워크 차단을 패키지 미존재로 단정하지 않았다.

해결: [[RES-ENV-001 문서 검증 패키지 네트워크 제한 대응]].
