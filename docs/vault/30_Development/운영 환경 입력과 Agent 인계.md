---
doc_id: "OPERATING-INPUTS-001"
title: "운영 환경 입력과 Agent 인계"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-09-12T01:26:09+09:00"
source_of_truth: "Git"
---

# 운영 환경 입력과 Agent 인계

CX-02 운영 입력판. owner Codex(계약), 실제 설정 Claude, UI Gemini. 입력은 비밀 없는 값/alias만 기록한다. 키·토큰·DSN·인증서 개인키·서명 URL을 이 페이지에 붙이지 않는다. 실행/설정 변경을 수행한 페이지가 아니다.

## 현재 확인

2026-09-12 작업 중 기존 로컬 pilot overview를 읽었다. `nod_01M25VZZFBYQVFGYB11G7HC10J` 1대가 online, profile `lan-observe-v1`로 보고됐다. 이는 이번 직접 mTLS handshake/실행 시험을 수행한 증거가 아니다. 이전 사용자 입력의 서버192.168.45.99, worker192.168.45.225는 주소 이력이며 새 DNS/장비 등록의 자동 권한이 아니다. 나머지3대 장비와5대 전체 운영 증거는 미확인이다.

| 항목 | 현재 상태 / 필요한 비밀 없는 입력 | 입력 담당 | 차단되는 일 | 입력 전 가능한 일 |
|---|---|---|---|---|
| 조직 IdP | issuer, audience, client ID, 허용 redirect/origin, 운영 담당자 미확정 | 운영자→Claude | 실제 운영 로그인/권한 인수 | 기존 검증기·합성 tenant 시험 |
| 운영 사용자 | 실제 issuer/subject에 대응하는 사용자·프로젝트·distinct 승인자 | 운영자→Claude | 실제 업무 제출/승인 | 독립 권한 회귀 |
| DNS/TLS | Studio/API hostname, 인증서 발급/갱신 책임, 신뢰 CA 배포 | 운영자→Claude/Gemini | HTTPS 브라우저 인수 | 배포 manifest/인증 거부 시험 |
| .225 실행 profile | 설치 receipt/image/profile/identity 보존 및 현재 mTLS 관측 | 원격 운영자→Codex | 실제7개 원격 시험/PTY/Git 여정 | 설치 패키지·계약 검증 |
| 서버/worker 허용 폴더 | 각 PC의 절대 경로·소유자·용도·할당량, Windows↔WSL 경계 | 운영자→Claude/Codex | 운영 Workspace/저장 제공 | 제한 tmpfs/합성 파일 시험 |
| 추가3대 | 실제 Node identity/OS/자원·허용 폴더·네트워크, GPU는 실측 | 운영자→Codex | 5대 배치/장애 인수 | 2-PC 개발/시뮬레이션 구분 |
| Credential backend | 실제 Linux/DB backend0f5f4e8 검증; 운영 registry/secret 미등록 | Codex 구현, Claude 검토/Adapter, 운영자 등록 | 실제 hosted adapter 호출 | 보호 등록 CLI76ba5ba 확보·기존 backend의 Provider 연결 |
| AI Provider/모델 | provider/model/version, project 사용 범위, 비용 상한/책임 | 운영자→Claude | 실제 모델 호출/embedding 차원 고정 | provider-neutral adapter·오류 처리 |
| Git publication | sandbox repository/branch alias, 실제 distinct 승인자, 제한 credential 등록 | 운영자→Claude/Codex | 실제 원격 publish 인수 | 고정 provider/CAS·불확실 결과 시험 |
| 운영 object 제품 | 제품/고정 이미지/운영자/장비/용량/TLS/backup target 미확정 | 운영자와Codex 선정, Claude adapter | S3/50GiB/HA/운영 복구 인수 | 기존64MiB Linux LocalObjects·일반 adapter |
| Backup·KEK | 별도 목적지/운영자·복원 책임·키 관리 alias, 보존 기준은 ADR-076 | 운영자→Claude/Codex | 실제 객체/DB/Node 합동 복원 | 격리 DB 리허설 |
| CI 계정 | 마지막 확인은 계정 결제/한도 제한 | 운영자, Orca 추적 | 같은 SHA CI·최종 병합 인수 | 로컬 구현·검증·독립 검토 |

## 다음 첫 행동

- Claude CL-04/CL-02: [[Codex 운영 자격증명과 Storage 계약]] ADR-077과 실제 resolver를 받아 Provider Adapter 연결·독립 검토를 진행한다. 기존 CLI의 파일 존재 기반 로그인 상태를 verified로 승격하지 않는다. 운영 secret은 보호 registry에서만 등록한다.
- Codex CX-02: 실제 resolver/파일·DB 경합 검증을 전달했으며 보호 registry CLI/절차76ba5ba를 전달했고 Claude RPO 독립 검토와 Storage 인수를 진행한다. S3 제품별 인수는 실제 후보·운영 장비 결정 후 진행한다. CX-01 F1/F2 reviewer 응답도 추적한다.
- Gemini GM-03/04: 실제 backend가 반환하는 unknown/미설정/폐기 상태와 수정 담당 안내를 준비한다. 예시 자격증명이나 hardcoded Node5대로 채우지 않는다.
- Orca: 위 입력·owner·reviewer와 PR21→22→19 의존 순서를 추적한다. 타 Agent를 실제 실행하거나 메시지를 보낸 기록은 아니다.

## 운영자 입력 형식

비밀을 제외하고 아래 값을 보호 설정 담당자와 확인한 뒤 이 페이지에 반영한다. 확인되지 않은 칸은 `미확인`으로 유지한다.

- 조직 로그인/Studio: IdP 이름, issuer/audience/client ID, Studio/API hostname, TLS 관리 담당.
- 프로젝트/사람: 프로젝트 이름, 요청자와 독립 승인자, 사용할 도구/모델·비용 범위.
- 장비별: Node identity, PC 주소/OS, 허용 폴더와 용도/최대 제공량.
- 저장/복구: 제품 후보 또는 관리형 endpoint의 alias, 용량, 별도 backup 위치 alias, 운영/복원 담당.

입력만 받았다는 상태와 실제 연결·권한·복원 시험 통과 상태를 별도로 기록한다.

최신 구현/관측/검증: [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]]. 01:09:55 KST worker1대 관측 전용, kill switch=true·업무 제출/웹 인증=false.

운영 보호 등록/회전/회수 실행 절차는 [[Codex 자격증명 등록 회전 회수 운영 절차]]다. 이번에는 합성 credential만 검증했고 실제 운영 secret/DB/Node는 변경하지 않았다.
