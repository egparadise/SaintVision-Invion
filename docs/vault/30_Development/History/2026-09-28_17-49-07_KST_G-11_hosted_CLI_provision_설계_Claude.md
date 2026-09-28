---
title: "G-11 hosted CLI provision 설계 v1.0 (카드 78, docs-only)"
version: "1.0"
status: "review"
author: "Claude"
updated: "2026-09-28T17:49:07+09:00"
---

# G-11 hosted CLI provision 설계 v1.0 (카드 78, docs-only)

branch `agent/claude/g11-cli-provision-design`, base `1e8baf04`(integration). 문서: [[G-11 hosted CLI provision 설계 v1.0]]. 코드·workflow 변경 0, migration 없음.

## 무엇을 판정했나

#179 §3-5의 G-11 — `tests/test_cli_adapters.py:378` 실바이너리 적합성 4건(claude·codex·gemini·antigravity)이 hosted에서 skip. provision으로 실행으로 바꿀 가치/비용을 **실측**으로 판정했다.

## 실측(요지)

- npm: `@anthropic-ai/claude-code` latest 2.1.283(525 버전, node>=22, 비OSS 라이선스), `@openai/codex` latest 0.158.0(5044 버전, 조회 당일 게시, 플랫폼별 dist-tag), `@google/gemini-cli` latest 0.61.0(763 버전). npm `antigravity`는 무관 placeholder — Antigravity는 데스크톱 앱이고 정의(`agents.py:79-94`)에 Linux 경로·headless 호출이 없다 → **provision해도 1건은 닫히지 않음(상한 3/4)**.
- runner: `ubuntu-latest` = Ubuntu 24.04 `20260920.314.1`, Node.js 22.23.2 preinstalled.
- 이 PC: `claude --version` 2.1.283, `claude auth status --json` JSON(`loggedIn` 키 포함, 값 미기록); `codex --version` 0.150.1, `login status` exit 0; `gemini --version` 0.60.0(stderr ACL 경고). 로그아웃 상태 출력·runner 설치 성공 여부는 NOT_OBSERVED.
- 시험이 credential 없이 증명 가능한 범위: `--version` 응답 + claude/codex status 명령의 **출력 모양**(로그아웃이어도 UNKNOWN 아님) — 즉 상류 rename 감지뿐.

## 결론

**지금 하지 않음.** 하더라도 본 lane이 아닌 opt-in label lane(`run-cli`, #176 `mlflow-live` 형식) + `package.json` 정확 버전 + 커밋된 `package-lock.json`으로 `npm ci`(integrity 핀); 본 lane exact map 변경 0, 새 lane 자기 map(antigravity skip 1 + 실행 3). 재평가 조건: G-01~05 종료, `workflow_dispatch` 1회 실측(설치·`--version`·로그아웃 status 출력)을 Evidence로, 핀 갱신 담당·주기, antigravity는 정의 변경 전 제외.

## 검증 방법(실제 수행한 것만)

`git grep -n -F`로 skip map·시험·정의 라인 확인, `curl`로 npm 레지스트리·runner-images README 조회, 이 PC의 CLI 실행(계정 값 비기록). npm 설치·workflow 실행 없음. 검토자 Codex.
