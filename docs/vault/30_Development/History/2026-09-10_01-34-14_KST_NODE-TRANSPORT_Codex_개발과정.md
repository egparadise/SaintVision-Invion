---
doc_id: "DEV-NODE-TRANSPORT-001"
title: "Codex mTLS Node 실행 전달 개발 과정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:34:14+09:00"
source_of_truth: "Git"
---

# Codex mTLS Node 실행 전달 개발 과정

TaskCard: task_id node-transport; sprint S02/S03의 보안 경계 보완; area Backend/Core; owner Codex; reviewer Claude; depends_on node-runtime(구현/CI/보고 완료, 독립 검토 pending); branch agent/codex/node-transport; base `75e22940ca9807f603d4787619f9c8e9599e31dd`.

입력: GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/PLAN-S02 v1.0.0, ADR-INDEX-001 v1.4.0, NODE-RUNTIME-CONTRACT-001 v1.0.0, agent-delivery/core-reliability Skill v1.0.0. 사용자 남은 작업 진행 및 critical 외 일반 승인 유지. 앞 작업 PR #4와 실제 증거를 재확인했다.

OUT-02/AC-02·OUT-03/AC-03·OUT-04/AC-04 → 실제 TLS handshake/identity 실패·폐기/교체·응답 유실·stop receipt transaction 검증 → Go Node mTLS 실행 endpoint·Python pinned TLS client·현재 channel authority → node-transport.

scope: CA/hostname/EKU/URI/leaf fingerprint 검증, TLS 1.3, Node의 버전형 CP peer allowlist와 폐기 감지, private key 파일 취급, Control Plane channel CAS/revocation와 정지 receipt의 동일 transaction 권한 검사, 서명 permit의 실제 remote execution/재전달. CLI·공통 schema·Go/Python·migration·시험·CI·문서. Claude의 src/saintvision OIDC/등록/Heartbeat CRUD는 읽기 검토 후 별도 adapter 인계하며 중복 병합하지 않는다.

운영 CA/IdP·DNS/장비 설정·bootstrap 발급·Windows/GPU·Artifact/Run 성공 검증은 미확정 외부 조건으로 남긴다. 실제 인증서는 CI용 합성 CA에서 발급하고 운영 자격 증명을 바꾸지 않는다. baseline 48 task 상태와 S02/S03 선행·독립 검토는 승격하지 않는다.

예정 evidence: signed permit → Python mTLS client → Go Node → 실제 Docker → 정지 receipt → 원자 lease/outbox 반환. 잘못된 CA/인증서/URI/pin/epoch, 정책 rollback/만료/폐기, body/header 위조, 연결 중단·재전달, DB authority 변경 경쟁을 검사한다. next_handoff Claude 독립 검토·Node enrollment/capability/transport adapter, Gemini 서버 상태 연결.

## 2026-09-10T01:49:58+09:00 구현과 로컬 검사

Go 1.27.1 공식 archive SHA 확인 및 프로젝트 전용 설치/CI pin. Python 로컬 회귀 114 passed / 121 skipped(이 시점 신규 PostgreSQL 통합 16개 포함), exit 0. 이후 graceful shutdown/response binding 통합 2건 추가. Go real TLS 테스트 및 Linux cross-build 검사 진행. TLS fixture의 기본 httptest 인증서와 Python strict AKI 누락을 수정했고 explicit port 0 fallback 오류와 response socket 이전 후 deadline 누락을 보완했다. 인증 검증을 끄지 않고 synthetic certificate에 SKI/AKI를 추가했다.

[[Codex Node mTLS 전달과 인증서 권한 계약]] NODE-TRANSPORT-CONTRACT-001 v1.0.0 / ADR-INDEX-001 v1.5.0. 생성 NodePeerPolicy·NodeExecutionResult, migration 0005, operator-only channel CAS, mTLS execution/observation 구현. 다음은 실제 Linux/PostgreSQL/Docker CI 검증이며 현재 결과를 운영 실측으로 표시하지 않는다.

## 2026-09-10T01:56:38+09:00 원격 검증 및 전달

`git commit`·`git push -u origin agent/codex/node-transport` exit 0. 구현 `59baad93cbe2f11c7b758b0ee668b8fbd67ce8ac`의 Core #34379287327 및 Documentation #34379287316 success. GitHub artifact 원본에서 Python 237/0/0/0 및 Go 22 top-level/55 leaf case 통과를 확인했다. [[2026-09-10_01-56-38_KST_NODE-TRANSPORT_Codex_검증보고]]에 실제 증거를 보존했다. reviewer Claude 독립 검토 pending.
