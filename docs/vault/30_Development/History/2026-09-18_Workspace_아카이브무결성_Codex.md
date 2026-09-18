---
doc_id: "HIST-WORKSPACE-ARCHIVE-INTEGRITY-001"
title: "VF-CX-05 Workspace 이미지 아카이브 무결성 준비"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T12:06:39+09:00"
source_of_truth: "Git"
---

# VF-CX-05 Workspace 이미지 아카이브 무결성 준비

- owner Codex/reviewer Claude pending. basec5a0368, branch agent/codex/workspace-archive-integrity, 시작2026-09-18T12:06:39+09:00. 공통/개인/VF판·INDEX-VIRTUAL-COMPUTER-001/ROADMAP-VIRTUAL-COMPUTER-001/GOV-CONTINUOUS-001 1.0.0 및 agent-delivery1.1.0/core-reliability1.0.0 적용. VF-CX-02/03 기본 계약은 구현·로컬 검증 상태이며 이번 ready는 VF-CX-05의 원격 설치 전 아카이브 bytes 검증이다.

## 구현

- `check_workspace_package.py --verify-image-archives`: ZIP 안의 node-agent.tar/workspace-image.tar를1MiB chunk로 순차 SHA-256 대조. metadata 기본모드는 유지한다. 모든 member 크기를 먼저 확인하고 합계8GiB를 초과하면 읽기 전에 거부한다. 추출·Docker load·원격접속·키 갱신 없음.
- 두 archive별결과/verified와 requestedChecksPassed를 출력한다. checksum성공은 manifest의 선언값과 일치한다는 뜻이며, Docker image identity/서명/소스 provenance/실행/설치/mTLS/권한을 인증하지 않는다. 관련 플래그는 false 유지. CLI는 요청한 checksum 실패도 exit1로 반영한다.
- 시험21passed/exit0: 기존14 + 내부hash불일치/양쪽독립판정/합계예산 선제거부/고정진단/정상hash와이미지identity구분/정책만료유지7건. 원격/DB 없이 수행했다.
- 실제 기존 패키지: 두 아카이브checksum일치. certificateFresh/peerPolicyFresh는 여전히false, 전체exit1. 패키지를 설치 가능으로 승격하지 않는다. Evidence/workspace-archive-integrity/package.json.

## OneDrive 관측 정정

- 사용자 시계열:11:45경463776→11:58경476020→12:02:27481629→12:03:57481600. 첫관측~12:02:27은+17853, 조용한90초는-29. 쓰기버스트와 증감하는 상관으로 기록하며 일정속도 누수라는 표현은 채택하지 않는다.
- threads56/working set396MB/가용RAM2224MB는 사용자 실측이다. 환경조치 전후 비교 전에는 호스트 process초기화실패의 원인으로 확정하지 않는다. 사용자 이전 잔재삭제는 docker rm **비강제**였으며 Claude 원안 rm -f 동시성finding과 구분한다.
- 공유 vault 쓰기는 작업별로 모아 선택 동기화한다. OneDrive 종료/설정변경은 사용자 환경 조치로 남긴다.

## 다음 행동과 미완

- Claude: 이번 archive checksum/예산 경계 독립검토, R2-01~03 수정은 기존owner유지. Codex: 수정 도착 후 재검토 및 image 보안lane; business-kernel-role 미검증 유지.
- VF-CX-02/03: registry key 동등성은 실행권한이 아니다. tenant/project/manifestHash/registryVersionId/content 결속 및 대용량원격provider/GPU·분산runtime은 후속 구현/설계 범위로 유지한다. 이번05준비를 해당범위 완료로 합산하지 않는다.
- 운영자: .225 인증서/peer policy 갱신·fresh mTLS·실제 profile준비 후 Codex 원격인수재개. 현재운영DB/원격설치 미변경, CI billing 사용자조치대기, 독립검토/운영인수미완. 잔여42.19%는 기존산식이며 재평가하지 않았다.
