---
doc_id: "RES-ENV-002"
title: "RES-ENV-002 Windows 샌드박스 및 Git 소유자 차이 대응"
version: "1.0.0"
status: "workaround"
author: "Codex"
updated: "2026-09-09T15:33:26+09:00"
source_of_truth: "Git"
---

# RES-ENV-002 Windows 샌드박스 및 Git 소유자 차이 대응

오류: [[ERR-ENV-002 Windows 샌드박스 및 Git 소유자 차이]].

일반 환경 승인 후 git -c safe.directory=C:/Project/SaintVision-Invion 으로 저장소 범위만 신뢰했다. git status exit 0. 전역 설정은 변경하지 않았다. 내부 원인은 미확정이며 샌드박스 자체를 복구했다고 주장하지 않는다.

resolution_scope: environment. 후속 실제 결과: [[개발 과정 인덱스]].
