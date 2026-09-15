---
doc_id: "ERR-STORAGE-CHECK-20260912"
title: "2026-09-12 STORAGE-CHECK 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T11:11:46+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-CHECK 오류와해결

1. 원본71cf2c0은 caller가 준 --node와 DB row를 비교한 뒤 운영 건강 기록을 바로 썼다. 실기계 증명은 없다. 실제 격리 DB 재현에서 기록0이어야 하는데1개가 만들어졌다. 수정본은 명시적 root 아래 local sample만 반환하고 PostgreSQL read-only를 강제한다.
2. 기준 checksum이 없어 sampled=0인데도 원본 service가 healthy=true를 기록했다. byte_size 불일치도 원본 collector가 비교하지 않아 healthy=true였다. 원본3개 actual test가 기대대로 실패했고 안전한 판정을 보완했다. [원본 재현](../Evidence/storage-check-original-71cf2c0.json).
3. 과거 zero-sample healthy/동시각의 실패/미래 시각을 집계에서 숨길 수 있어 서비스/주의 대상 집계를 보강했다. 과거 row를 소거하지 않았다.
4. 초기 private 재현은 tests 밖에서 실행해 conftest fixture3개 setup error였다. pytest -p conftest로 실제 fixture를 로드한 뒤 위3개 assertion failure를 확인했다. setup error는 제품 오류 재현/검증 수에 세지 않는다.
5. Linux source image allowlist에 새 CLI가 없음을 실행 전 확인했다. a7d0f5e에서 tools/storage_check.py를 명시적으로 포함하고 새 clean image를 만들었다. 이전 준비 image는 최종 검증으로 세지 않는다.
6. Obsidian 공통 진행판/Gemini 작업판 외부 편집으로 check exit1·쓰기0. [원문/hash 보존](../Evidence/obsidian-proposals-20260912-storage-check/manifest.json) 후 작성자 제안을 최신 정본에 수신 요약으로 병합한다. CI는 계정 결제/한도 때문에 job 미시작이며 로컬 검증과 구분한다.

