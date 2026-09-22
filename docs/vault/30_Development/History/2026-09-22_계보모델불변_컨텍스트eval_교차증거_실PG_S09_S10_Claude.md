---
doc_id: "HIST-CLAUDE-S09-S10-CROSSEVIDENCE-001"
title: "교차 증거(실PG) — S09 불변Context·RunRecord·eval / S10 계보·모델불변·배포digest 304 passed"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["evidence", "real-pg", "S09", "S10", "OUT-09", "OUT-10", "cross-cutting", "not-self-close"]
---

# 교차 증거(실PG) — S09/S10

c402c81a(경합·복구 166건, S04/S05/S07 기여)와 **같은 방식**이다: 새 코드를 만들지 않고, 이미 있는 실PG 시험을 이 호스트의 실제 PostgreSQL 16에 돌려 **인용 가능한 증거**로 남긴다. **self-close 아님** — 카드 닫기는 owner/reviewer 판정이다. Codex 대기열을 늘리지 않으려 검토 요청 없이 증거만 기여한다(긴급도 LOW-USEFUL).

## Provenance (이 헤더 없이는 통합 상태를 보증하지 않음)

- **측정 대상 SHA**: S10 실행은 `f0f0c790`, S09 실행은 `5f0b4cd2`. 두 SHA 사이 및 현재 origin tip `ec621cb2` 까지의 diff에 **Python 시험 closure(`services/control-plane/src`·`tests`·`migrations`) 변경 0** — `git diff --name-only <a>..<b>` 로 확인. 즉 세 SHA는 동일한 `inv`/`tests`/`migrations` 코드를 잰다(차이는 docs·apps/web 뿐). 이 문서는 origin tip `ec621cb2` 위에 얹는다.
- **인터프리터**: `.venv/Scripts/python.exe` (Python 3.14.6, pytest 9.1.1). 잘못된 인터프리터가 runnable을 unrunnable로 위장하는 함정 회피 확인.
- **cwd**: `C:\Project\SaintVision-Invion`.
- **실 DB**: 컨테이너 `saintvision-lan-db-bff1a31d`, PostgreSQL **16.14**, `127.0.0.1:55440`. `INV_TEST_ADMIN_DSN`(admin=postgres 유지DB)로 conftest가 **시험마다 disposable DB**를 새로 만들고 끝나면 버린다(기존 스키마 재설정 없음).
- **워크트리 clean 여부(정직)**: 측정 시점 워크트리는 **완전 clean 아님** — 남(Gemini)의 dirty 파일 3개(`apps/web/src/contracts/kernel-observation.ts`, `apps/web/src/features/studio/DeveloperStudio.tsx`, S01-FE Gemini History .md). **그러나 셋 다 Python 시험 closure와 무교차**(`git status --porcelain -- services/control-plane/src tests migrations` = 빈 출력). 따라서 Python 시험이 읽는 것은 커밋된 tree 그대로다. 남의 dirty 파일은 건드리지 않았다.

## S10 — OUT-10 (모델의 데이터·코드·평가·승인 역추적 + 배포 digest), AC-10

**실 PG 결과: 228 passed / 0 skipped / 0 failed (224.70s).** 14파일 전부 skip 없이 도달.

- 파일: `test_lineage`, `test_model_registry`, `test_deployment_guard`, `integration/test_model_commit`, `integration/test_model_registry_binding`, `integration/test_model_registry_revalidation`, `integration/test_model_locality`, `integration/test_model_view`, `integration/test_model_runtime`, `integration/test_model_retry`, `integration/test_model_license_readthrough`, `core/test_model_manifest`, `core/test_model_execution_registry`, `core/test_model_remote`.
- **되살림형이라 통과가 실제 단언에 도달**(passing-but-never-reached 함정 회피). `test_lineage.py` 소스 직접 확인한 대표 단언:
  - **모델 불변 버전**(S10-ST): 애플리케이션 역할이 `model_versions`를 UPDATE/DELETE 하면 DB가 거부(append-only). 동일 content_sha256 두 버전 금지. 서비스 우회 직접 SQL도 제약이 잡음.
  - **보존 pin**(S10-ST): pin은 **연장만**(단축 무시). verify+pin 없이는 release 거부, DB도 `stage='released'` 직접 UPDATE 거부.
  - **역추적**(S10-DB): 완전 연결 모델은 dataset/commit/image/eval/approval 전부로 역추적, `fullyTraceable=true`·`missing=[]`·`dangling=[]`. **negative**: 맨 모델은 `missing`에 4종 이름 지목(image는 필수 아님), subject가 사라진 edge는 `dangling`으로 보고(hits만 돌려주지 않음).
  - **배포 digest**(OUT-10): 배포 digest는 **모델 버전에서** 오지 caller에서 오지 않음. 승인은 정확한 content에 대한 것 — 다른 content 승인으로 배포 시 `AUTH-APPROVAL-DIGEST-MISMATCH` 거부. 미release·미승인 배포 거부, 두 active 배포 부분유니크 인덱스가 거부, 재배포는 이전 것을 superseded.
  - **tenant 격리**: tenant_b scope에서 model_versions/lineage/dataset_versions/images/commits 전부 0행.

## S09 — OUT-09 (근거 있는 Context·제한된 수정 루프), AC-09

**실 PG 결과: 76 passed / 21 skipped / 0 failed (110.88s).**

- **passed 76 내역**(collect-only 대조): `test_context_eval` 29 + `test_eval_execution` 15 + `integration/test_approvals` 25 + `integration/test_approval_review` 7 = 76.
- **skipped 21 = `integration/test_results.py` 전부**, 사유 **"Linux private storage"**(이 호스트에 Linux 사설 파일 스토리지 백엔드 부재). c402c81a의 "skip 48=Linux 파일백엔드 부재"와 같은 부류의 **정직한 env-게이팅**이며, 통과로 세지 않는다.
- **대표 단언**(소스 직접 확인):
  - **불변 Context**(S09-DB): 동일 content는 tenant당 한 번만 저장(P7), dedup은 tenant를 넘지 않음(존재 누출 방지), item version이 원본 변경을 넘어 살아남음(version+hash 저장 이유), 인식된 비밀은 **거부하고 아무것도 저장 안 함**(build_bundle에 배선), 초과 크기는 **잘라내지 않고 거부**, 애플리케이션 역할은 snapshot 삭제 불가, orphan snapshot만 수거되고 참조된 것은 보존.
  - **RunRecord 봉인 불변**(S09-DB): 미완성 run은 record 봉인 불가, 두 번 봉인하면 같은 record 반환, **봉인된 record는 재기록 불가**, run당 record 하나. (RunRecord **전체 완료 파이프라인(실 출력 바이트)**은 `test_results.py`라 Linux storage 부재로 skip — 아래 not_run.)
  - **eval golden**(S09-DB, AC-09 핵심): **위반은 아무리 점수가 좋아도 gate 실패**(누출은 점수로 상쇄되지 않음), DB가 위반 있는 gate 통과를 거부, 범주별 점수 분리 보고, 불완전 suite는 통과 아님, "금지 없음"을 선언한 forbidden case 거부(항상 통과=아무것도 증명 안 함), redact 안 한 adapter는 출력 저장 안 됨, 모델 pin 못 하는 adapter 기본 거부, adapter 실패는 fail이 아니라 error로 기록(timeout을 fail로 세면 재시도로 green), tenant 격리.
  - **diff·테스트·trace Artifact 연결**(S09-ST): diff/test/trace artifact는 **역할로 pin**(명명 규칙 아니라 쿼리), 미검증 artifact는 pin 불가, 나중 덮어쓰기는 pin이 탐지(ADR-010).

## not_run (정직한 미검증 — 통과로 옮기지 않음)

- **RunRecord 전체 완료 파이프라인(실 출력 바이트)**: `test_results.py` 21건, Linux 사설 파일 스토리지 백엔드 부재로 skip. RunRecord 봉인·불변 자체는 위 `test_context_eval`로 커버됨. 이 21건은 그 백엔드가 있는 호스트/CI에서 재실행 필요.
- **물리 노드 의존**(mTLS stop→verifier): `test_results.py`의 remote/storage fixture 경로도 위 skip에 포함.
- **CI hosted 실행**: gh 미인증이라 이 SHA의 Actions 결과는 아무도 못 읽음(사용자 로그인 대기). 위 수치는 로컬 실측이며 CI 통과와 동등하지 않다.

## 기여처와 인계

- **S10-DB**(Dataset/commit/image/model lineage), **S10-ST**(Model immutable version·보존 pin): 위 228건이 요구증거(lineage query·배포 digest·모델 불변)를 실측으로 채운다.
- **S09-DB**(불변 Context/RunRecord·eval), **S09-ST**(diff·테스트·trace Artifact 연결): 위 76건이 채운다(RunRecord 완료 파이프라인은 not_run 분리).
- **S10-BE**(두 Provider adapter·MLflow·승인 배포): eval executor/adapter conformance(`test_eval_execution` 15)와 배포 digest는 위에 있으나, **실제 두 외부 Provider 실행/취소/collect/attest는 CX-02 credential 경계 대기**(CL-05 기록과 동일). 이 부분은 이 증거 밖.
- owner/reviewer 판정 전까지 카드 상태 불변. 이 문서는 인용용 증거이며 self-close·검토요청 아님.
