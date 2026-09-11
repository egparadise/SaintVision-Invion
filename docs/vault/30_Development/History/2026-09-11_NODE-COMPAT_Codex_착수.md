---
doc_id: "HIST-NODE-COMPAT-INIT-20260911"
title: "NODE-COMPAT Codex 실행 연결 후속 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T09:24:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "node", "recovery"]
---

# NODE-COMPAT 실행 연결 후속

- Task: NODE-COMPAT (S03-BE/S12-BE 후속), owner Codex, reviewer Claude 검토 대기.
- Base SHA: `794ac8e2dd7829dfc04e5c012468cb65a5a2e4f6`, branch `agent/codex/dev-environment`의 기존 독립 checkout을 이어 사용한다.
- 기준: GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/task-registry 1.0.0, ADR-INDEX-001 1.19.0, agent-delivery/core-reliability 1.0.0. 사용자 후속 진행 및 비임계 작업 승인 계승.

서버 03:32 재부팅 후 웹/관측/Studio 프로세스가 종료된 것을 확인했다. 기존 DB를 보존하고 서비스를 재시작한 뒤 09:18에 다른 PC `192.168.45.225`의 fresh mTLS 관측을 확인했다. 프로필은 `lan-observe-v1`; 실제 업무 실행 가능 상태는 아니다. SSH 22번 연결은 timeout이었다.

이번 범위: 로그인 후 서비스 재기동과 중복 시작 방지, Node Docker API 고정 1.45와 서버 API 1.41 불일치의 제한된 협상, 출력 로그 호환성, 기존 격리를 유지하는 실제 로컬 Node 시험, 원격 실행 시험 설치본 인계. API/DB 승인 계약을 우회하거나 가상 승인자를 등록하지 않는다. 원격 시험은 다른 PC 설치 완료가 관측된 이후에만 수행한다.

합격 증거: 지원 범위/잘못된 daemon 응답/동시 협상/실패 재시도 및 mutation 중복 금지 시험, 실제 Docker의 격리·출력 해시·종료/삭제 확인, 반복 시작에서 같은 listener 유지, 현재 서비스 및 Node 관측, Git/CI/Obsidian 기록. 로컬 시험과 두 PC 시험, 제품 Run/Evidence를 구분한다.
