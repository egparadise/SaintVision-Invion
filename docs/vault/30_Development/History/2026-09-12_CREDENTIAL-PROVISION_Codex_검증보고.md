---
doc_id: "HIST-CREDENTIAL-PROVISION-REPORT-20260912"
title: "2026-09-12 CREDENTIAL-PROVISION Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:26:09+09:00"
source_of_truth: "Git"
---

# 2026-09-12 CREDENTIAL-PROVISION Codex 검증보고

CX-02 / S01-BE·S08-ST, owner Codex / reviewer Claude pending. base3fb949a, 구현c0397a3, 시험 import 수정·최종 고정 **76ba5ba4b5f677640ec1750681aa9b8367ba203a**, branch agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_CREDENTIAL-PROVISION_Codex_착수]], [[Codex 자격증명 등록 회전 회수 운영 절차]].

## 작업 → 확인

보호 운영자 CLI의 register/grant/revoke/rotate를 구현했다. 기존 Linux reader와0035 registry를 사용하며 runtime의 DB 쓰기 권한을 확대하지 않았다. 버전 등록과 사용 권한 부여를 분리하고, 고정 scope·현재 epoch·active Run·현재 project 권한을 확인한다. revoke는 kill/project disable/파일 소실 이후에도 가능하다. 두 회전의 경쟁·동일 요청 replay·폐기 권한 부활 방지·감사 원자성을 검증했다. 실제 운영 자격증명 등록은 실행하지 않았다.

| 실제 명령·환경 | 결과 | 증거 |
|---|---|---|
| check_kernel_docker.py --prepare-only/--prepared, Linux·일회용 PostgreSQL | **90 passed, 0 skipped, exit0**, 소유 runner/DB/network 정리 성공 | [고정 SHA·case·명령·파일 hash](../Evidence/credential-provision-76ba5ba.json) |
| pytest tests/core/test_credential_provision_cli.py, Windows | **4 passed, 0 skipped, exit0** | [CLI 입력/오류 경계](../Evidence/credential-provision-76ba5ba-core.json) |
| git push origin agent/codex/workspace-bridge | c0397a3 및76ba5ba, exit0 | PR19 |
| 동일76ba5ba GitHub Actions 6건 | 계정 결제/한도 문제로 job 시작 전 failure | [CI ID/annotation](../Evidence/credential-provision-76ba5ba-ci.json) |

Linux90개는 새 provisioning20 + 기존 실제 backend48 + definer22다. 이중 실제 원격 Node/Provider 호출 시험은 없다. 이전154개와 중복되므로 누적 합산하지 않는다. migration과기존backend는 변경하지 않았고 새 migration을 추가하지 않아 upgrade22를 재실행하지 않았다. Windows4개는 Linux 파일 보안을 대체하지 않는다.

처음 c0397a3에서 Linux import 경로 누락으로 수집 exit2가 발생했다. 도구를 파일 경로로 명시적으로 로드하도록 고쳤고76ba5ba에서 전체90개가 실제 실행됐다. [[2026-09-12_CREDENTIAL-PROVISION_오류와해결]].

## 다음 첫 행동·담당

- Codex: Claude 새4b09dfc/c632d3f의 RPO capability/운영 복원 보고를 독립 검토하고 현재 recovery 정본과 조율한다. credential 신규 finding을 반영하며 Storage 무결성·원격 profile 수신 시7개 실장비 시험을 이어간다.
- Claude: 76ba5ba 및 ADR-079/운영 절차를 독립 검토한다. 기존 resolver에 실제 Provider adapter를 연결하고 보호된 운영 계정/정책 입력을 준비한다. 새 Linux resolver를 다시 만들지 않는다.
- Gemini: 등록/checked/권한부여/실제 실행 가능을 구분하고 현재 authenticated API/ResultView/PTY/drain 정본에 화면을 연결한다. CLI를 공개 웹 관리 API로 노출하지 않는다.
- 운영자/Orca: CI 계정, 원격 실행 profile, IdP/모델/허용 폴더·장비 입력과 PR21→22→19 순서를 추적한다. 실제 메시지 발송이나 Agent 세션 실행 기록이 아니다.

전체 추정은 **57.29% 완료/42.71% 잔여(기존 표시55/45) 유지**. 운영 등록/Provider·CI·peer·물리 원격 인수가 아직 없으므로 원래48개 task에 done/추가 단계 점수를 부여하지 않는다.

## 전달 검사

문서/ontology·최종 push·Obsidian check/apply/check 영수증은 이어 기록한다.

- 2026-09-12T01:28 KST: check_docs.py exit0(24 원본hash/288 versioned docs/48tasks), check_ontology.py exit0, 변경Python3개 black --check exit0, git diff --check exit0. 첫 Obsidian check는 외부 편집2개로 exit1·쓰기0; 보존/병합 후 최종 검사를 수행한다. PR19 본문에90/4 검증과 초기 import 수정·인수 차단을 반영했다.
