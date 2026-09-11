---
doc_id: "HIST-BACKUP-ROOT-REPORT-20260912"
title: "2026-09-12 BACKUP-ROOT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:53:19+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-ROOT Codex 검증보고

CX-01/CX-02/CX-07 · S08-ST/S11-ST. owner Codex / reviewer Claude pending. base e46d30d →8994eca → **6a72b9d37348f73ffbfe4230e7585b8755f203b8**, PR19 draft, agent/codex/workspace-bridge. [[2026-09-12_BACKUP-ROOT_Codex_착수]].

## 작업한 것

명시적 ReadRoot를 모든 실제 파일 verifier에 전달한다. root identity pin·열린 디렉터리/파일 확인으로 root 밖 경로와 링크를 차단하고, 교체/변경된 파일을 성공 관측으로 내보내지 않도록 검사한다. root 누락/탈출은 실제 DB 성공 기록을 남기지 않으며 batch는 정상 항목을 계속 검증한다. 크기 N+1 한도·최대4MiB chunk·unbuffered 두 번의 digest 비교를 적용했다. [[Codex 허용 저장소 파일 검증 계약]] / ADR-085. migration 변경 없음.

## 확인한 것

| 명령·환경 | 결과 | 근거 |
|---|---|---|
| 원본 e46d30d와 root 경계 대조, 실제 Windows 합성파일 | 외부/junction/hardlink3개 원본 외부 bytes 읽음, 수정본 모두 거부, exit0 | [재현](../Evidence/backup-root-reproduction.json) |
| check_kernel_docker.py --prepared ... --tests test_backup_verification_integrity/test_verification/test_verification_readroot/test_pilot/integration/test_recovery_drill | 최종 **103 passed,0 skipped,exit0**, clean6a72b9d | [Linux case·source hash·이미지·정리](../Evidence/backup-root-6a72b9d.json) |
| cx01_local.py test_backup_verification_integrity/test_verification/test_verification_readroot/test_pilot | 최종 **80 passed,0 skipped,exit0**, clean6a72b9d, 실제 Windows/PostgreSQL | [Windows case](../Evidence/backup-root-windows-6a72b9d.json) |
| git push origin agent/codex/workspace-bridge | 구현8994eca/수정6a72b9d exit0 | PR19 |
| 같은 SHA Actions6개 | 계정 결제/한도로 job 미시작 failure | [ID/annotation](../Evidence/backup-root-6a72b9d-ci.json) |

Linux103 = DB 무결성14 + 파일 hash13 + root23 + pilot35 + 복원18. Windows80 = DB14 + hash13 + root18 + pilot35이며 공통 시험은 합산하지 않는다. 원본 결함 재현/사전검증/실패 후 재검증을 최종 통과 수에 중복 가산하지 않는다. 초기 Linux102 중1개 실패와 보완을 [[2026-09-12_BACKUP-ROOT_오류와해결]]에 남겼다.

## 남은 것과 다음 담당

- Codex: Claude71cf2c0 storage_check의 실제 node binding·trusted root·기존 자체 hash 구현을 독립 검토하고 정본 경계를 연결한다. 다음에는 durable 성공/실패 관측과 실제 운영 Evidence 연결을 진행한다.
- Claude: 6a72b9d/ADR-085 독립 검토 및 storage_check consumer 계약 조율. 검토는 수신 대기이며 대신 승인하지 않았다.
- Gemini:1133666의 KPI 동적 subtitle/SLO 테스트 보고를 수신했다. 실제 UI/원격 인수는 별도 검증이며 Codex 원격7개를 대체하지 않는다.
- CX-03: 2026-09-12T02:53:57+09:00 [읽기 전용 LAN 확인](../Evidence/backup-root-lan-20260912.json): .225 online/True·lan-observe-v1, killSwitch=True, userWorkloadSubmission=False. 설치 결과 및 실제 실행 경로 확인 뒤7개를 재개한다. 운영 계정·Node·PKI 변경 없음.

이번 파일 관측은 immutable snapshot·object store·실제 운영 RPO·5대 인수가 아니다. Windows/Linux의 정상 로컬 파일만 확인한 범위를 계약에 명시했다. CI·독립 검토·운영 인수가 남아 전체 추정 **57.29% 완료 /42.71% 잔여 유지**. Claude가 제안한 S12-ST25→50/57.81%는71cf2c0 collector 독립 검토 후 산식에 반영할 후보이고, Gemini65.63% 역시 별도 작성자 보고다.

문서·Ontology 검사, 보고 push, PR 설명 갱신과 Obsidian 동기화 결과는 아래 전달 기록에 추가한다.


문서 검사: check_docs.py exit0(원문24·문서305·작업48), check_ontology.py exit0, git diff --check exit0. 변경 Python5개 Black 적용. PR19 설명 갱신/draft 유지. Obsidian 외부2개 원문 보존/검토 후 동일 bytes 인수 및 정상 export를 진행한다.
