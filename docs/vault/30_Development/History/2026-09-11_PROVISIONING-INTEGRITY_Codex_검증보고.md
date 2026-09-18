---
doc_id: "HIST-PROVISIONING-INTEGRITY-REPORT-20260911"
title: "PROVISIONING-INTEGRITY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:24:11+09:00"
source_of_truth: "Git"
---

# 계정 준비·실행 권한 무결성 검증

[[2026-09-11_PROVISIONING-INTEGRITY_Codex_착수]]의 base c9dea3f 위에 Claude c6ed473을 b4eaa8d로 가져와 독립 검토하고, Codex 구현 `a6054f3fdbbd650150453cac5d6ca0225fa64af8`를 agent/codex/provisioning-integrity에 push했다. [검토용 draft PR #21](https://github.com/egparadise/SaintVision-Invion/pull/21)은 선행 agent/codex/result-observation을 기준으로 한다. main 병합·운영 적용은 미수행이며 Codex 수정의 독립 reviewer Claude는 대기다. 원문 [[Claude_통합코드_독립검토]]와 Codex 판단/오류를 구분해 보존한다.

## 구현과 검증된 동작

명시한 OIDC 계정·project·grant만 준비하며 기존 로그인 subject·role·비활성 연결·grant 범위·epoch는 바꾸지 않는다. read-only check와 apply를 구분하고 apply는 현재 상태를 DB lock 아래 재확인한다. 요청/승인 grant는 현재 역할과 일치해야 한다. 모든 새 연결·권한·불변 감사는 한 transaction이다. 동시 중복 요청은 1개 감사만 만들며 늦은 DB 실패와 정지 경합은 전체 rollback/거부된다. 실제 JWT 계정으로 업무 프로젝트 생성→운영 도구 준비→kernel draft 생성·결과 조회→역할 회수 후 거부를 검증했다.

0030은 공개된 Codex/Claude 두 결과 이력을 보존한다. 마지막 subject 판정은 현재 tenant/active 계정/external_subject/enabled mapping을 모두 확인한다. 결과 다운로드는 기존 canonical 경로를 유지하고 덜 제한적인 alternate resolver의 inv_app 권한을 회수했다. CLI는 DSN을 환경 변수로 받고 오류 출력에서 자격 증명을 숨긴다. 계정 연결 성공에도 executionReady=false다. Node/Workspace/admission 조건은 별도로 충족해야 한다.

계약은 [[Codex 계정 준비와 실행 권한 계약]]/ADR-068, 발견과 수정 근거는 [[2026-09-11_PROVISIONING-INTEGRITY_오류와해결]]이다. 등록된 48 task의 선행·CI·독립 검토·장비 인수가 모두 끝났다는 뜻은 아니다.

## 실제 명령과 증거

| 검증 | 결과 |
|---|---|
| python -m pytest tests/core tests/test_migrations.py -q --tb=short | 구현 중 290 passed, exit 0 (26.18초). 최종 clean 전체 기본 재실행으로 표시하지 않음 |
| 첫 격리 통합: readiness/provisioning/account/result | 29 passed, exit 0, dirty b4eaa8d 소스; 이후 CLI 3개 추가 |
| 최종 prepare-only 및 아래 격리 회귀 | clean a6054f3, 283 passed, 실패/오류/skip 0, exit 0, 2026-09-11T05:24:00.663706+00:00 |
| 14개 공개 prior → integrated head → head 재실행 | 최종 test_account_integration에서 통과; 기존 sentinel/Workspace 도구 값 보존 |
| tools/export_schemas.py --check | 업무 19개 schema 일치, exit 0 |
| tools/check_docs.py / tools/check_ontology.py / git diff --check | 구현 commit 시 각각 통과, exit 0. 최종 문서 검사·sync는 아래 후속 기록 |

Python은 C:/Project/SaintVision-Invion/.venv/Scripts/python.exe, Go는 로컬 1.27.1이다.

```text
python tools/check_kernel_docker.py --go C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe --prepare-only
python tools/check_kernel_docker.py --prepared .work/sv-kernel-7c8a5e181b8e/prepared.json --tests tests/test_business_results.py tests/test_result_readiness.py tests/test_account_integration.py tests/test_projects.py tests/test_settings.py tests/test_login.py tests/test_api.py tests/test_pools.py tests/test_migrations.py tests/test_contracts.py tests/integration/test_provisioning_integrity.py tests/integration/test_result_observation.py tests/integration/test_account_production.py tests/integration/test_workspace_start.py tests/integration/test_business_handoff.py tests/integration/test_containment.py
```

[최종 통합 Evidence](../Evidence/provisioning-integrity-a6054f3.json) SHA-256 `d6dbe89d1c46e934a9a515ba21f983777922f0a88ec2049a5ad52a354859ccc6`. code/source/binary/image와 283 case, 실제 cleanup을 기록했다. 실제 로컬 Node 컨테이너의 실행·실패·취소·출력 복구가 포함되며 두 물리 PC나 GPU 시험이 아니다. private pytest 로그/DSN/토큰/개인키는 공개하지 않는다.

[CI 기록](../Evidence/provisioning-integrity-a6054f3-ci.json): Backend 34565555467, Core 34565555567, Docs 34565555523. 기존 계정 결제/spending 제한으로 job 시작 전 실패했으며 계정 변경/반복 재시도는 하지 않았다.

## 남은 작업과 인계

[실제 Node 관측](../Evidence/provisioning-integrity-live.json)의 원격 192.168.45.225는 여전히 관측 전용 profile이다. 실행 설치 JSON 미수신으로 실제 원격 7개 시험은 미수행이다. [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]에 따라 설치 후 실제 image/profile을 확인해야 한다. 운영 계정·DB·epoch·kill switch·Node profile은 변경하지 않았다.

- Codex: 실제 worker 설치 확인 뒤 원격 실행·취소·복구 7개 인수, reviewer 회신 통합, 이후 Node tool 관측과 GPU/다중 Node 범위.
- Claude: a6054f3/8b97c6a의 독립 검토, 확정된 운영 IdP/계정 입력으로 provisioning 적용 준비, Workspace 파일 준비·public 제공량과 kernel 자원 연결, 운영 복구 리허설.
- Gemini: canonical 결과/다운로드/readiness와 draft→prepare→승인→enqueue를 실제 UI에 연결하고 브라우저 인수. 현재 root의 작업 중 UI는 수정하지 않았다.

Git/Obsidian 및 draft PR로 검토 자료를 제공한다. 다른 Agent에게 직접 메시지를 보내거나 검토 승인으로 표시하지 않았다.

2026-09-11T14:24:50+09:00 최종 문서 검사: `python tools/check_docs.py`는 원문 24개/버전 문서 234개/48 task 검사를, `python tools/check_ontology.py`는 RDF/SHACL 검사를 통과했다(각 exit 0). `git diff --check`도 exit 0이었다. `python tools/sync_obsidian.py --check --state .work/provision-sync-state.json`은 366개 관리 파일/12개 반영 대기/충돌 0, 이어 `--apply`는 12개 파일 반영/366개 hash 일치, `--check`는 반영 대기 0/충돌 0으로 모두 exit 0이었다. 이 실행 기록 추가분을 같은 state로 후속 반영한다. 원문/미관리 파일은 변경하지 않았다. 다음 독립 reviewer는 Claude다.
