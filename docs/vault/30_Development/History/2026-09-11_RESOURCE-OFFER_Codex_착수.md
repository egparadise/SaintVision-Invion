---
doc_id: "HIST-RESOURCE-OFFER-START-20260911"
title: "RESOURCE-OFFER Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:40:09+09:00"
source_of_truth: "Git"
---

# 자원 제공량과 실행 예약 통합 착수

사용자의 작업 재개에 따라 14:32 KST 실제 원격 관측과 최신 Agent 코드를 확인했다. base d945633afb590feaef0dd5777edc7da4210a4d43, branch agent/codex/resource-offer-integrity. Claude 9ab84abbeecb9f0fdc0bb0746c8ddd76cbec419b를 b5d265a로 저자를 보존해 가져왔다.

GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001 v1.0.0, ADR-INDEX-001 v1.24.0, agent-delivery/core-reliability v1.0.0, S01-BE/DB·S05-BE/DB·S07-BE 및 연관 Claude S02-BE/DB 계약을 따른다. Prompt는 현재 재개 및 후속 정본/Agent 역할 확정 요청, Context는 위 문서·고정 소스, Harness는 격리 PostgreSQL/실제 JWT/Go·Docker 및 실제 LeaseStore 경합이다. 기존 설치 확인 없는 원격 시험을 수행한 것으로 기록하지 않는다.

목표: 명시된 관리자 제공량 변경이 한 Node의 모든 동종 kernel resource 예약 상한에 원자 반영되어 과도 예약/잘못된 GPU 선택/tenant 간 변경을 차단한다. 합격 증거: fractional CPU 변환·복수 resource 총합, 실제 Lease 예약/축소 경합, 미반납 lease 유지, 현재 관리 권한, 부분 실패 rollback, 실제 HTTP/DB 기록, migration 이력 보존. Codex owner/Claude reviewer 대기다. 운영 DB/계정/epoch/Node profile은 변경하지 않는다.

추가 사용자 질문에 따라 결과의 정본(result_view.py)과 세 Agent의 다음 단계·7개 원격 시험/운영 화면의 선행 조건도 문서로 확정한다.
