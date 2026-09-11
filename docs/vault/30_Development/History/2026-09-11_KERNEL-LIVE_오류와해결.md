---
doc_id: "ERR-KERNEL-LIVE-20260911"
title: "KERNEL-LIVE 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T10:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["error", "kernel", "integration"]
---

# KERNEL-LIVE 오류와 해결

| 실제 문제 | 원인과 수정 | 검증 |
|---|---|---|
| Python Node 이미지 COPY에서 `/lib` non-directory 오류 | scratch용 Git root 사본을 Debian의 `/lib → /usr/lib` 구조에 덮어쓰려 했음 | 해당 Python 배포판에 Git을 설치하도록 변경. 다른 glibc/loader 복사 제거 |
| 첫 전용 시험 exit 1, `FileNotFoundError: docker` | Debian의 `docker.io` 패키지는 이 버전에서 CLI를 포함하지 않음 | test runner에 `docker-cli` 명시 설치. 기존 DB/Node 초기화 없음 |
| 기존 CI probe 이미지에는 Python이 없음 | Python 전용 시험을 scratch 이미지로 실행하면 실패 | 별도 Python 이미지의 실제 content ID를 `INV_PYTHON_NODE_IMAGE`로 고정하고 시험에서 새 Node allowlist/profile 적용 |
| 일부 로컬 경로/검색식 오기 | PowerShell 경로 glob과 rg 정규식 중괄호 사용 오류 | 실제 경로 확인 후 재조회. 구현 파일이나 기존 사용자 자료 변경 없음 |

첫 실패의 private pytest 로그와 JUnit은 `.work/sv-kernel-c4e334e6f563/runs/bb1d3f5af5a8`에 보존했다. DB 비밀번호·JWT가 포함될 수 있는 원문 로그는 공개 Git 보고서에 복사하지 않는다. 수정 후 10:02 KST 전용 4개 시험 exit 0을 확인했다. [[2026-09-11_KERNEL-LIVE_Codex_검증보고]]에서 확정 코드 SHA와 후속 통합 결과를 분리한다.
