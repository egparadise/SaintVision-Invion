---
doc_id: "HIST-LAUNCHER-EVIDENCE-AUDIT-001"
title: "Launcher와 운영 증거 경계 감사"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T15:03:06+09:00"
source_of_truth: "Git"
---

# Launcher와 운영 증거 경계 감사

base3a570a1, owner Codex(검증경계), reviewer Claude(미검토), branch agent/codex/model-registry-binding. 우선순위5 먼저,4는 evidence 경계 표본. agent-delivery1.1.0/core-reliability1.0.0 적용, 공통판1.0.97/Codex1.0.64/지도1.3.0 확인. 사용자 VB-FIX-01/02 Claude owner 전달 수신; 실제 수정/검토 완료로 대체하지 않는다.

## VB-LAUNCH-01 / P2 — 인증서 생성 실패 후 preflight 성공

`tools/deploy_intranet.ps1` 인증서 부재 분기의 `.venv\Scripts\python tools/generate_tls_cert.py` 바로 뒤에 LASTEXITCODE 검사가 없다. ErrorActionPreference Stop만으로 native nonzero가 종료 오류로 바뀌지 않는다. 뒤 npm/node/docker 성공이 종료코드를 갱신하고 마지막 ZERO Errors (All Exit Codes 0) 문구까지 실행된다.

Evidence/verification-boundary-audit/launcher-audit.py: 원본 PS1을 byte-identical하게 임시 폴더에 복사. python/npm/node/docker는 종료코드와 trace만 기록하는 native .cmd 대역이며 Invoke-WebRequest는 HTTP200 객체 대역이다. 인증서 파일은 없고 실제 key 생성/HTTP/npm/Docker/배포0. Windows PowerShell child를 pipeline 없이 subprocess로 실행하여 returncode를 직접 받았다.

| 주입 | native | 스크립트 exit | 성공 배너 |
|---|---:|---:|---|
| 인증서 생성 실패 |23|0|있음|
| npm test 실패 |23|1|없음|
| node smoke 실패 |23|1|없음|
| compose config 실패 |23|1|없음|
| 모든 대역 성공 |0|0|있음|

launcher-results.json에 실제 단계 trace·원본 hash·복사본 동일 여부를 보존했다. npm build 단독 실패 주입은 이번 표본에서 하지 않았고 즉시 LASTEXITCODE 검사만 소스 확인했다. 제품 TLS 인증 우회/실제 잘못된 배포가 발생했다는 주장이 아니다. preflight 결과의 거짓 성공이다.

수정 owner Gemini(해당 frontend/intranet script), 계약 reviewer Codex. 생성 직후 native exit 검사 및 nonzero 종료, 성공 시 기대 산출물 확인, 실패 후 후속 단계 미실행 회귀 시험이 필요하다. 기존 npm/node/compose 실패 대조도 유지. 실제 구성/서비스 검증과 API 응답 smoke 라벨을 분리하고, 누락 Docker/실패한 optional gateway probe를 전체검증 완료로 읽지 않도록 요약 scope를 정확히 한다. 이번에는 감사만 했으며 미수정이다.

## deploy 경로의 제한된 소스 대조

- LAN Prepare/Start/Repair/Enable-Workspace/Enable-ExecutionTests/Replace-Storage PS1은 WSL native 직후 nonzero throw를 갖는다. 실제 원격 실행은 하지 않았다.
- LAN sh4파일은 set -euo pipefail을 사용하며 주된 작업 명령은 직렬 실행한다. Bash 조건식/명령치환/프로세스치환의 모든 실패 조합을 감사했다는 의미가 아니다.
- worker_config/workspace/execution/storage/replace/storage_bridge Python subprocess 경계는 check=True 또는 returncode 검사를 확인했다. Python launcher 전체 의미/rollback의 완전성을 인증하지 않는다.
- studio/container_worker.py 자체는 JSON 결과를 출력하지만 tools/dev_studio.py는 result.exitCode와 reason으로 succeeded/failed를 판정한다. 외부 worker exit0만 보고 누락 전달로 판정하지 않았다.
- Start-LiveConsole.ps1의 docker start에는 즉시 exit 검사가 없다. 직접 launcher는 PID와 주소를 출력하고 상위 Start-Environment는 HTTP 건강검사를 한다. 해당 상위 검사의 실제 DB 연결 보증까지 재현하지 않았으므로 이번 신규 확정 finding에 합산하지 않는다. 별도 실패 주입 후보로 남긴다.
- Agent-Shell/Open-Tool은 사용자 대화형 도구 실행 경로이며 운영 인수 판정과 동일시하지 않는다. NoExit 세션 결과 전달은 잔여 감사 범위다.

## 우선순위4 — 생성/저장/조회 경계 표본

operational-evidence-audit.py는 원본 main/exit 판정 함수를 호출하며 리허설 실행만 대역으로 교체한다. CLI 실패와 산출물 상태를 별도로 기록했다.

1. rehearse_lan_upgrade: 기존 성공 JSON을 둔 경로로 현재 rehearsal 실패 주입 → exit2, 이전 JSON 불변. 현재 실패가 exit0으로 바뀌지 않는다. 과거 파일을 현재 성공으로 오독할 수 있는 산출물 재사용 위험 후보이며 실제 소비자의 오인수는 미재현. 고유 output/new-file 정책 또는 실패 run을 구분하는 별도 receipt가 후속 보강 후보다. 기존 성공 증거를 무조건 삭제하지 않는다.
2. rehearse_independent_restore: 기존 output 경로는 argparse exit2로 즉시 거부, rehearse 미호출. 새 report는 open(x)로 생성하며 일반 실패와 RehearsalFailure를 구분한다. finally cleanup 예외가 RehearsalFailure 보고서를 대체할 수 있는 경로는 별도 잔여 검토이며 이번에는 실제 장애를 주입하지 않았다.
3. storage_check: 원본 _check_one과 실제 temp ReadRoot에서 빈 locations → sampled0/sampleHealthy false. CLI는 nodeBindingVerified/recorded/operationalAcceptanceAssessed false를 명시하고 DB 쓰기 없이 관측한다. 빈집합 PASS 반례는 발견하지 못했다.
4. operational_readiness: acceptanceEvidence.evidenceComplete false → exit1, true와 나머지 관측 조건 충족 → exit0. 합성 record gate 검증이지 AC-12 물리 복구 검증이 아니다. 소스상 read-only repeatable-read 조회 및 snapshot transaction commit 뒤 receipt 노출을 확인했다. rollback/DB I/O 전 조합은 이번 실행 범위 밖이다.

PITR 코드·archive_command·운영 compose는 변경하지 않았고 Claude 수정 작업과 겹치는 구현을 하지 않았다.

## 실행과 다음 행동

두 감사 스크립트 각각 exit0, launcher5조건/운영증거5조건. 이는 감사 관측 수집 성공이지 배포/복구 합격이 아니다. `python -m pytest -q tests/test_operational_readiness.py tests/test_storage_check_integrity.py`: exit0,5passed/30skipped(DSN 미설정),0.84초. DB 저장/조회30건을 실행했다고 보고하지 않는다. 기존 제공 disposable DSN을 없다고 판정하는 것이 아니라 이번 오프라인 감사 명령에 넣지 않았다.

다음 Gemini: VB-LAUNCH-01 수정, Codex 검토. 다음 Codex: LAN 리허설 stale output·독립복원 cleanup 보고 보존·LiveConsole native 실패 후보를 필요 시 대조. Claude: 진행 중 PITR/fixture 수정 및 AGG 독립 검토. 전체 감사 완료 선언 없음, 운영인수0/5·business-kernel-role 미검증·CI 외부대기 유지.

## 전달 수령증

51563eb 작업branch/integration push exit0. check_docs542문서/ontology exit0. scoped Obsidian8파일 hash일치/pending0/conflict0. CI/운영배포 실행0. Gemini 실제 수신/검토 완료는 미확인이다.
