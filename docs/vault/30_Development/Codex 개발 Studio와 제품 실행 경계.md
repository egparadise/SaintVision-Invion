---
doc_id: "CONTRACT-DEV-STUDIO-001"
title: "Codex 개발 Studio와 제품 실행 경계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T00:59:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["contract", "development", "security"]
---

# ADR-061 개발 Studio

사용자는 2026-09-11 일반·AI·모델 학습 개발 환경과 Orca/Claude/Codex/Antigravity 연결을 요청했다. 개발 Agent와 제품 내부 Executor를 분리한다는 GUIDE-001에 따라, 기존 Windows 사용자에게 로컬 개발 작업 환경을 제공한다. owner Codex, reviewer Claude/Gemini 검토 대기.

## 권위와 범위

Studio의 `developer-container`는 개발자가 자신의 PC에서 제한된 Docker 빌드·테스트를 수행하는 도구다. 제품 `/v1` API·ToolGateway·2인 승인·Node permit·PostgreSQL Evidence 계약을 호출하거나 대체하지 않는다. `dev_` ID와 별도 SQLite journal을 사용하며 제품 Run 완료·원격 실행으로 표시하지 않는다. 기존 kill switch와 Node identity는 변경하지 않는다. 제품 내부 Agent는 이 개발 경로를 정책 우회용으로 사용해서는 안 된다.

웹은 127.0.0.1:18100에만 bind한다. Windows 사용자 권한으로 발급한 120초 일회용 fragment token을 원자 소비한 뒤 8시간 HttpOnly/SameSite=Strict 세션을 발급한다. 토큰은 hash만 저장한다. HTTP Host/Origin·중복 보안 헤더·본문 크기를 확인한다. 세션 정보와 journal은 해당 사용자 및 SYSTEM만 접근 가능한 디렉터리에 둔다. 이는 사내 다중 사용자 OIDC/SSO 구성이 아니다.

## 개발 실행

등록된 프로젝트의 명시적 src/tests/data 경로만 제한 크기로 읽는다. 숨김 파일·키·credential 파일·symlink/junction·상위 경로는 거부 또는 제외한다. 실행은 바뀐 소스의 실제 바이트와 SHA-256을 고정한다. Git commit, dirty 여부, 실행 도구 파일 hash, 실제 이미지 ID와 적용 CPU/RAM/PID/네트워크 설정을 기록한다. 같은 멱등 키의 같은 요청은 같은 작업을 반환하고 다른 요청은 거절한다.

Docker 실행은 단일 동시 작업, CPU 0.25–1, RAM 128–512 MiB, 최대 300초로 제한한다. 초기값은 CPU 0.5/RAM 256 MiB/120초다. UID 65532, rootfs read-only, cap drop ALL, no-new-privileges, network none, host bind/volume 없음, tmpfs 입력/출력, PID 64, bounded 로그를 사용한다. 실제 inspect 값이 다르면 실행하지 않는다. 컨테이너 안의 watchdog과 외부 timeout을 함께 사용한다.

결과 파일은 최대 2 MiB/50개이며 수신 시와 다운로드 시 SHA-256을 확인한다. 이것은 로컬 개발 결과 무결성 검사이며 외부 입력의 신뢰성이나 학습 품질 보증이 아니다. 실패·취소·중단을 성공으로 바꾸지 않는다. 재시작은 소유 label이 일치하는 잔여 컨테이너만 정리하며 입력을 보존한다. 정지를 확인하지 못하면 `recovery_required`로 실행 슬롯을 계속 점유한다. 무조건 재실행하거나 컨테이너·볼륨을 일괄 삭제하지 않는다.

## 도구·후속 연결

Orca CLI로 프로젝트와 도구별 Worktree를 준비한다. CLI 실행은 선택한 작업 폴더와 기존 계정 설정을 사용한다. 다른 Agent의 모델 호출·리뷰·유료 실행을 대신 했다고 표시하지 않는다. Antigravity는 설치된 `agy` CLI로 연결하며 GUI 프로젝트 자동 연결을 확인했다고 주장하지 않는다.

현재 원격 Node는 mTLS 관측 전용이며 새 작업의 대상으로 고를 수 없다. GPU/대규모 모델/프로젝트별 추가 패키지/원격 Node 실행/SSO/제품 Run 통합은 별도 계약·설치·실장비 검증 대상이다. 일반 업무를 위한 분산 플랫폼 전체가 완료됐다는 의미가 아니다.

Docker 자원 제한의 공식 근거: [Resource constraints](https://docs.docker.com/engine/containers/resource_constraints/). 설치된 CLI help를 기준으로 도구 인자를 검증했으며 Antigravity 모드는 [공식 실행 모드 문서](https://antigravity.google/docs/cli/modes/)와 대조했다.
