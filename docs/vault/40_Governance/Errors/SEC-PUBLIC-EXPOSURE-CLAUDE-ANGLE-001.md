---
doc_id: "SEC-PUBLIC-EXPOSURE-CLAUDE-ANGLE-001"
title: "공개 전환 노출 조사 — Claude 각도(마스킹/증거/테스트). 값 미기록"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-19T23:00:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "security", "public-exposure", "credentials", "masking", "no-values"]
---

# 공개 전환 노출 조사 — Claude 각도

저장소가 공개로 전환돼 tracked 파일이 인터넷에 노출됐다(사용자 확인: GitHub visibility=public, `deploy/certs/saintvision.key`가 익명 HTTP 200). Codex가 전체 노출 범위를 조사 중이라 중복하지 않고, **내 각도**(마스킹 코드·증거 파일·테스트/도구 하드코딩·임시 DSN 기록 여부)에서 확인했다. **값은 옮겨 적지 않고 경로·성격만 기록한다**(finding 문서에 비밀을 다시 남기지 않는다 — Codex와 동일 규율). **삭제·이력 재작성·설정 변경은 하지 않았다. 조사·기록까지.**

## 사용자 확인 맥락
`deploy/certs`의 인증서·키는 **개발 전용**이고 운영은 별도 인증서를 쓴다. 따라서 공개된 개인키의 위험은 **개발 환경 한정**이며 **운영 TLS 종단 위장은 해당 없음**. 단, 개인키가 dev용이라는 것이 다른 비밀까지 안전하다는 뜻은 아니므로 아래를 확인했다.

## A. 확인된 노출 (public tracked)
| 경로 | 성격 | 위험 |
|---|---|---|
| `deploy/certs/saintvision.key` (+ `.crt`) | TLS 개인키(PEM) | **dev 전용**(사용자 확인). 개발 환경 한정. Codex가 제거·구조정리 범위 |
| `.env.example:6-7` (`INV_DATABASE_URL`, `INV_TEST_DATABASE_URL`) | 비밀번호가 박힌 DSN(**dev/example** 자격증명, `invowner@localhost:55432`) | 값 미기록. **이 dev 비밀번호가 실제 어딘가 재사용되는지** 사용자 확인 필요. 임시 DSN과는 다름 |
| `docs/vault/30_Development/Evidence/*-tests.xml`, `Evidence/obsidian-proposals-*/**` | pytest junit·제안 텍스트에 **합성 test-role 비밀번호**(예: `CREATE ROLE ... LOGIN PASSWORD '<합성>'`) | 합성/dev test 자격증명. 낮음이나 public에 존재 |

## B. 확인된 안전 (비밀 미유출)
- **사용자 제공 임시 PostgreSQL DSN(:55432)**: **자격증명 미기록** — `Evidence/model-registry-binding/user-independent-e89a415.json`이 명시적으로 "credentials not recorded"(포트만); 여러 History 문서는 **포트 참조만**(비밀번호 없음); **내 PITR 리허설 증거(`Evidence/pitr-rehearsal/...txt`)에 PW/DSN 없음**(랜덤 probe 비밀번호가 출력에 안 남음). → 임시 DSN 비밀번호는 **유출되지 않았다.**
- **PRIVATE KEY 마커 파일**(`src/saintvision/adapters/conformance.py`, `tools/dev_studio.py`, `tests/core/test_dev_studio.py`, `tests/core/test_workspace_bridge.py`, `tests/test_adapters.py`): `-----BEGIN ... PRIVATE KEY-----` **마커 문자열 참조**만 있고 **base64 키 본문 0줄** → 임베드된 실제 키 아님(credential 검사·redaction·런타임 생성 코드). **유출 아님.**
- **`docker-compose.prod.yml`**: `POSTGRES_PASSWORD`/`MINIO_ROOT_PASSWORD`가 `${VAR:?...}` **placeholder만**, 리터럴 자격증명 없음.
- **내 PITR 리허설·docker_diag 증거**: 자격증명 없음(마스킹 코드가 credential 값을 남기지 않도록 처리한 결과).

## C. Codex 구조정리(certs를 gitignore·배포 시 생성/외부 주입)의 내 테스트 영역 영향
**결론: 내 테스트 영역에 깨지는 지점 없음.**
- `tests/integration/test_web_container.py`: **런타임에 자체 합성 cert/key를 생성**(x509 빌드 → `cert.pem`/`key.pem`을 temp에 써서 마운트)하고 **`deploy/certs`를 읽지 않는다**. `/etc/ssl/private/saintvision.key`는 컨테이너 **타깃 경로**일 뿐 repo 파일 참조 아님 → **무영향**.
- 내가 오늘 다룬 fixture들(`tests/db_login.py`, `tests/db_provision.py`, `tests/integration/conftest.py`, `tests/vf_docker.py`)과 `credential_conformance` 주변: **cert 파일 존재 전제 없음** → 무영향.
- `deploy/certs` 파일을 실제 소비하는 곳은 `docker-compose.prod.yml`(bind-mount)뿐이며, `tools/deploy_intranet.ps1`이 **부재 시 생성 분기**(Test-Path→generate)를 갖고 `tools/generate_tls_cert.py`가 생성기다. 따라서 **certs를 gitignore + 배포 시 생성/주입**해도 테스트는 깨지지 않는다(구현은 사용자 승인 후, 이건 영향 분석만).

## D. 방법·한계
- tracked 파일 기준(`git grep -l`/`git ls-files`)으로 파일 목록·카운트·구조만 확인, **출력 시 비밀번호를 마스킹**해 값을 보지 않고 성격만 판정. 실제 노출 범위 전체는 Codex 담당. 나는 마스킹/증거/테스트 각도에 한정.
- **권고(조율 결정, 내가 실행 안 함)**: A의 항목은 Codex 전체 finding에 합류. `.env.example`의 dev 비밀번호와 test-role 합성 비밀번호는 회전/치환 여부를 사용자가 판단. 개인키는 dev 전용이나 공개된 이상 dev용도 회전 권장.
