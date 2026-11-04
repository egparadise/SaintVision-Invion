---
doc_id: "HISTORY-20261104-DOCKER-API152-BROWSER-CODEX"
title: "2026-11-04 Docker API152 브라우저 검증기 수정 Codex"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-04T13:06:28+09:00"
source_of_truth: "Git"
---

# 2026-11-04 Docker API152 브라우저 검증기 수정 Codex

- 카드 `BROWSER-HARNESS-API152`, 부모 `SUPERVISION-20261104`; owner Codex, reviewer Claude(요청 전/판정 대기).
- checkout `D:/Project/SaintVisionI-Invion/supervision-integration-20261104`; branch `agent/codex/supervision-integration-20261104`; 직접 base `925dd669ba87f3067fe8f17f102eb5a804c4b1d9`.
- 이 base는 원격 train 78 `03e17c31cf535008d39534aaa80d3ae274bd75cc`와 supervisor `81a9982f8fbdac18428f57be628cfd49bdf7f391`의 로컬 통합 후보다. 두 진행판 충돌에서 더 높은 frontmatter와 양쪽 History 본문을 모두 보존했다. 원격 integration은 이 로컬 merge로 바꾸지 않았다.
- 읽은 계획/Skill 버전은 [[2026-11-04_전체개발_자동감독_착수_Codex]]와 동일하며, 새 수정은 canonical browser CI를 다시 실행 가능하게 만드는 검증기 범위다.

## 실제 실패와 원인

PR #404의 Desktop Browser run `41769889826`, job `126376855159`가 pytest 실행 전에 `KeyError: IPAddress`로 실패했다. PR #403 run `41759608209`도 같은 지점이다. 검증기는 `NetworkSettings.IPAddress`를 읽었지만 Docker API v1.52는 그 deprecated 필드를 제거했다. [Docker 공식 API 이력](https://docs.docker.com/reference/api/engine/version-history/#v152-api-changes)과 실제 job traceback을 대조했다. 이는 제품 브라우저 assertion 실패가 아니라 도구가 시험을 시작하지 못한 실패다.

로컬 변이 형태의 재현은 bridge 주소 `172.17.0.12`와 낡은 container-wide 주소 `10.20.30.98`을 다르게 주었다. 기존 검증기가 후자를 pytest 환경에 넘겨 `1 failed`, 직접 exit 1을 확인했다. API v1.52 형태처럼 legacy 주소가 없는 사례도 후속 회귀 집합에 포함했다.

## 변경과 실제 검증

- 소유 disposable PostgreSQL을 명시적으로 `bridge` network에 연결하고 그 network의 IPv4 endpoint만 사용한다. 관계없는 network나 legacy 주소로 fallback하지 않는다.
- endpoint 부재·형식 오류·미지정/멀티캐스트 주소는 pytest 실행 전에 exit 125 / `evidenceStatus=not-run` / `subprocessExitCode=null`로 기록한다. 소유 컨테이너 정리와 비밀 없는 proof 기록은 그대로 수행한다.
- 검사 입력을 echo하지 않으며 `operationalAcceptance=false`는 그대로다.
- Windows PowerShell, CPython 3.14.7, interpreter `D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/.venv/Scripts/python.exe`.
- 13:05:20 KST 시작 재현: `python -m pytest -q tests/test_vf_evidence.py::test_runner_reads_the_declared_bridge_endpoint_from_modern_inspect`, 직접 exit 1. 원 로그 `.work/browser-harness-repair/before.log`.
- 수정 후 `python -m pytest -q tests/test_vf_evidence.py tests/test_docker_diag.py --junitxml=.work/browser-harness-repair/after.xml`: **48 passed, 0 failed, 0 errors, 0 skipped**, 직접 exit 0, 13:06:28 KST 종료. 원 로그/JUnit은 같은 `.work/browser-harness-repair`에 남겼다. XML은 synthetic external boundaries이며 실제 Docker/PG/browser 인수가 아니다.
- `git diff --check`: 직접 exit 0. code commit과 최종 같은-SHA hosted CI는 후속 report/CI로 결속하며 이 문서가 자기 SHA를 참조하도록 반복 커밋하지 않는다.

## 감독 결과와 다음 담당

Claude는 #402의 Linux symlink fixture와 실패 receipt/latch를 changes requested, #401의 제품 caller 미연결·unknown 표시를 changes requested로 판정했다. Codex worker는 #400의 Node-leaf-only 변경을 accepted, #403의 현재 착지 상태 산문을 수정 대상으로 보고했다. 각 수정은 원 owner에게 실제 전달했으며 독립 검토 완료나 전체 인수로 대신 표시하지 않는다.

현재 r4의 CP/두 Node leaf 만료, listener 부재, 실제 2개 Node와 빈 resource 상태는 Codex worker의 read-only 관측 결과이며 이 검증기 수정으로 회복되지 않는다. 다음 담당 Codex coordinator는 수정 코드의 Claude 독립 검토와 정확한 후보 SHA의 hosted Browser/Backend/Core 결과를 확인한다. 통합 후보가 검토·CI를 통과한 뒤 최신 공통 문서를 Obsidian에 check/apply/check한다. 현재 운영 인수·전체 완료는 미달이다.

오류/해결: [[ERR-20261104-Docker_API152_브라우저_검증기]] → [[RES-20261104-Docker_API152_브라우저_검증기]].
