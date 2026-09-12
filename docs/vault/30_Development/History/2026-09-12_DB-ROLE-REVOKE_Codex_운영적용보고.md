---
doc_id: "HIST-DB-ROLE-REVOKE-REPORT-20260912"
title: "2026-09-12 DB-ROLE-REVOKE Codex_운영적용보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T20:49:30+09:00"
source_of_truth: "Git"
---

# 승인된 운영 직접 로그인 폐기 완료

CX-01 Codex owner/Claude reviewer pending, basea716699da74c0ee79b7239570695d6f42e958ab8 / agent/codex/workspace-bridge. [[2026-09-12_DB-ROLE-REVOKE_Codex_착수]]. 사용자가 직전 적용 승인 질문에 “이어서 해”라고 응답하여 이 운영 조치를 승인했다. 재승인을 요청하지 않았다.

## 수행

운영 inv_app 직접 세션0, 알려진 Python pytest/migration 시험 프로세스 없음, 실제 배포용 inv_lan_runtime이inv_kernel 구성원임을 사전 확인했다. 실행 SQL은 기존4ec4c5d의 `deploy/remediate-shared-app-role.sql`과 개행 정규화 후 동일함을 확인했다. 실제 파일SHA256은 Evidence에 남겼다. 역할 속성과 table/column grants,멤버십·RLS·policy hash를 사전 확보했다. 비밀번호 원문/hash는 기록하지 않았다.

2026-09-12 **20:47:51 KST**에 관리 연결에서 검증된 SQL을 적용했다. `ALTER ROLE inv_app NOLOGIN PASSWORD NULL`만 수행했으며 현재세션이 있으면 거부하는 guard가 포함됐다. 기존 세션 강제종료·다른 login credential 변경·schema upgrade·kill switch 해제·Node profile 교체는 수행하지 않았다.

## 사후 실제 검증

- inv_app LOGIN=false/password NULL=true. 확인한 inv_app/inv_kernel/inv_lan_runtime 역할 속성 중 의도한 변경만 발생.
- table/column grant digest 동일,멤버십·RLS 설정·policy digest 동일. migration head0023 그대로.
- 기존 저장소에 있던 시험 credential을 이용한 **실제 새 TCP 연결이 서버 인증 단계에서 거부됨**. 자격증명은 메모리에서만 읽고 보고서/명령 argv에 쓰지 않았다.
- 기존 inv_lan_runtime DSN으로 커널 tenant/epoch 검증 transaction과Node 조회 성공.
- **20:48:33 KST**의 변경 이후 Node snapshot fresh/lan-observe-v1 확인.20:48:38 KST 재확인에서inv_app NOLOGIN/passwordNULL 유지·직접세션0,kill switch true 유지.
- SQL 실행 자체는 성공했다. 최초 검증 wrapper는 접속 오류에SQLSTATE가없어 exit1로 판정했으며,후속 명시적 서버 인증 거부 판정과 재검증 exit0으로 정정했다. 같은SQL을 재적용하거나 노출password를 복원하지 않았다.

Evidence: [[db-role-revoke-live-20260912.json]]. `completedAt`은첫 검증 종료,`verificationCompletedAt`이최종 검증 종료다. 기존51개/별도SQL 거부·적용·replay 시험은 [[2026-09-12_DB-TEST-ROLE_Codex_검증보고]]의 고정SHA 근거를 재사용했으며 이번운영조치를새제품전체시험으로 쓰지 않는다.

## 남은 작업과 인계

**기존 운영 inv_app 직접 로그인 폐기의 승인 대기는 해소됐다.** 과거 진행판/보고서의 pending 기록은 당시 상태이며 이 보고서가 최신이다. 다른 Agent의 구 fixture/배포 bootstrap이 다시LOGIN을설정하면 재발할 수 있으므로각lane에4ec4c5d의수정 반영이필요하다. 이번관측은지속감시나재발불가능보장이아니다.

다음 Codex: 정본 server candidate의 설정·인증·운영DB 연결을 별도포트에서검증하고,이미복원시험한20개migration 적용과Node workspace profile 전환의구체적배포계획을이어간다. 이번로그인폐기승인을schema migration·서비스전체교체승인으로확장하지않는다. Claude: 역할shape guard/readiness와이번운영근거독립검토,각Agent:구공용역할ALTER fixture재실행금지. Gemini:정본candidate의실제인증/화면계약확인.

전체2775/4800=57.8125%,잔여42.1875% 유지. 제품CI·독립검토·원격실행인수는미완료이며,보안운영조치하나의완료와전체개발완료를구분한다. 문서검사·push/CI/sync결과는후속기입한다.

## 최종 전달

문서358개/48 task 및 ontology 검사 exit0. 운영 보고5f86076 commit/push exit0.20:50:01 KST 같은SHA CI6개 모두billing제한으로job미시작/failure, [[db-role-revoke-5f86076-ci.json]].20:49:54 KST 로컬 Obsidian726개hash일치/pending0/conflicts0, [[db-role-revoke-obsidian-20260912.json]]. OneDrive cloud 미확인. 영수증 추가 후 최종commit/push/sync를 수행한다.
