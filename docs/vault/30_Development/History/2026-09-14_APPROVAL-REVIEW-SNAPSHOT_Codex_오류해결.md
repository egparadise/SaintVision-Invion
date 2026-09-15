---
doc_id: "HIST-APPROVAL-REVIEW-SNAPSHOT-ERROR-20260914"
title: "2026-09-14 APPROVAL-REVIEW-SNAPSHOT Codex 오류해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T23:30:50+09:00"
source_of_truth: "Git"
---

# 오류와 해결 기록

첫 격리PG 시험45pass/3fail. owner 집계/변경 SQL에 tenant 및 approval 조건을 빠뜨려 다른 fixture행을 포함했다. 대상 범위를 한정한 뒤 새 격리클러스터에서48pass/exit0,34.44s. 운영 DB 변경 없음. DSN 포함 가능성이 있는 pytest 원문은 비공개 .work에만 두고 공개 Evidence는 명령/exit/scope를 기록했다.

CI024a817은 계정 결제 제한으로6건 job 시작 전 실패. 코드 회귀 실패와 구분하고 동일 SHA 재실행은 계정 해소 후 수행한다.

Obsidian 최초 동기화는 외부편집3개를 감지해 exit1/쓰기0. 원문을 별도 Evidence에 보존하고 작성자 보고 수신과 독립 확인을 구분했다. 동일 보존 바이트 확인 후 기준선 채택, 정본 동기화를 수행한다. [[2026-09-14_APPROVAL-REVIEW-SNAPSHOT_Codex_검증보고]] 참조.
