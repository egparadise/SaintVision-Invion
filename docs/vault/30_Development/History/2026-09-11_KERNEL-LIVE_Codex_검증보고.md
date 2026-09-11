---
doc_id: "HIST-KERNEL-LIVE-REPORT-20260911"
title: "KERNEL-LIVE Codex 검증보고"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T10:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "kernel", "evidence"]
---

# KERNEL-LIVE 검증보고

Task KERNEL-LIVE / owner Codex / reviewer Claude 대기. [[2026-09-11_KERNEL-LIVE_Codex_착수]]의 base `32367cd` 이후 실제 Python/CPU 학습 프로젝트를 제품 커널로 실행하는 검증 환경을 구현했다. [[Codex Python 프로젝트 실행과 통합 시험 환경]]에 입력·이미지·결과 및 운영 연결 조건을 정리했다.

## 확인한 동작

10:02 KST 작업 중 소스로 전용 4개 시험 exit 0. HTTP 인증·별도 두 승인·원자 예약/queue·실제 Go mTLS Node·Python 실행·결과/Evidence·파일 checkpoint 경로다. 시험용 사용자/PKI와 독립 PostgreSQL을 사용했다. 기존 pilot DB나 사용자 계정에 synthetic 승인자를 추가하지 않았다.

- 일반 Python 프로그램 실행과 stdout 해시 검증.
- AI 시작 프로젝트의 합성 데이터 CPU 학습·별도 50개 평가 데이터·모델/metrics/loss 파일 확인.
- 승인 뒤 작업 파일을 바꿔도 고정한 승인 원본 실행.
- 물리 Node 정지 후 결과 저장 worker가 바뀌어도 동일 receipt로 결과 확정. 3개 동시 publication 요청에서 완료 1회, 재학습 없음.
- Python exit 7이면 Run failed, 활성 예약 0, 실행 컨테이너 제거, 성공 Evidence 없음.

확정 SHA의 시험 결과, 기존 취소/Workspace/샤드/containment 통합 시험, push/CI/sync 결과는 후속 기록한다. 오류는 [[2026-09-11_KERNEL-LIVE_오류와해결]]에 보존한다.

## 남은 경계

현재 로컬 개발 Studio는 기존 SQLite 개발 실행이고 이번 시험은 제품 커널의 PostgreSQL Run이다. 둘의 운영 사용자/권한/제출 연결은 아직 미완료다. 원격 PC는 `lan-observe-v1`로 연결되어 있으며 [[2026-09-11_NODE-COMPAT_다른PC실행안내]]의 설치 결과가 필요하다. GPU·장시간 학습·optimizer 중간 checkpoint 재학습·물리 2대/5대 시험 및 다른 Agent 독립 검토는 수행하지 않았다.
