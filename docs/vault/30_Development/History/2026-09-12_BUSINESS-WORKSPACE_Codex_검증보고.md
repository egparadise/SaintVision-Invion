---
doc_id: "HIST-BUSINESS-WORKSPACE-REPORT-20260912"
title: "2026-09-12 BUSINESS-WORKSPACE Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:34:12+09:00"
source_of_truth: "Git"
---

# 업무 API와 Windows 설정·영속 Workspace

CX-02 Codex owner/Claude reviewer pending. base8e4c856, 구현 **14de71d70db83363c6626028a010a0a152d268d2**, agent/codex/workspace-bridge. [[2026-09-12_BUSINESS-WORKSPACE_Codex_착수]], [[2026-09-12_BUSINESS-WORKSPACE_Codex_오류해결]].

## 작업한 것

Compose 업무DSN을 실제 INV_BUSINESS_DSN으로 수정했다. 업무 무토큰은401/WWW-Authenticate Bearer로 맞추고 프로젝트 권한403은 유지했다. Windows bind0777의 실제 거부를 확인하여 전용 config volume을 기본 배포 경로로 바꿨다. prepare_server_config.py는 참조된 설정만 새 volume에 복사하고 바이트·owner65532/file0600·현재신뢰를 검사한다. 기존 volume 거부와 실패시 자기 volume만 정리한다. 선택 Workspace overlay는 사전 준비된 영속volume만 연결한다.

## 확인한 증거

- 후보 image build exit0: **sha256:6730c9e66077bdfcbddffe607ee1bfbb9c03874a9bbeb507d836c649f2989ee5**, source14de71d.
- `python -m pytest -q tests/integration/test_server_container.py tests/core/test_deployment_credentials.py tests/core/test_server_config_volume.py tests/test_api.py::test_missing_credential_is_refused tests/test_api.py::test_unknown_credential_is_refused`: **27 passed,136.75초,exit0**, warning7. 격리 일반PostgreSQL16, 실제 migration/비소유자 분리role/실제 Docker UID65532/HTTP, 합성identity.
- 정상/Workspace/업무/업무+Workspace 기동, 무토큰·미등록subject401, 실제 프로젝트·Workspace201, kernelLinked=false/executable=false, 미연결Run403 확인. kernelrole를 업무DSN으로 쓰면 기동 거부.
- 영속 개인 Linux volume에 쓴 합성파일을 컨테이너 재시작 후 WorkingGenerations가 다시 열어 내용보존 확인, 새 호스트포트의 /readyz200 확인. **실제 편집 API·Step/PTY/원격Node 재개·전원장애 복구 인수는 아님**.
- 파일권한 기동거부3종, readonly config 쓰기 거부. 설정준비 실제volume 복사/재사용거부/만료신뢰 실패cleanup, 외부경로·alias거부와 미참조파일 제외. Windows→Linux volume 준비 경로의 실제 실행을 검증했다. 운영개인키 미사용.
- Compose 필수7변수·외부Workspace volume 선언10개, 설정도구7개, 컨테이너8개, 기존API인증2개=27. 중간실패와 수정은 오류해결 문서에 보존했다.
- `tools/check_docs.py`:365문서/48작업 exit0. `tools/check_ontology.py`:exit0. commit/push exit0. 같은SHA CI6개는 결제 제한으로 job미시작/failure: Core34699472812/34699469297,Backend34699472826/34699469363,Docs34699472686/34699469281. [Core CI](https://github.com/egparadise/SaintVision-Invion/actions/runs/34699472812). 독립 검토 pending.
- 23:31:27KST 운영 읽기점검: .225 online/fresh/observe,kill switch=true,epoch일치,DB0023→0037 미적용20개. 원격7개시험은 미완료. 계획/준비점검 exit1은 발견된 미완료게이트를 뜻하며 query실패 아님. 운영 쓰기 없음.

Evidence는 `../Evidence/business-workspace-20260912.json` 및 같은 접두어의 CI/Windows bind/LAN계획/준비상태다. credential·개인키는 포함하지 않았다.

## 다음 작업

[[2026-09-12_RUNTIME-CUTOVER_Codex_후보계획]]에 실제 입력·담당·전환순서를 정리했다. 공개 OIDC 설정값 요청은 진행 중이며 답변을 운영승인으로 추정하지 않는다. Codex는 DB role/Claude guard 독립 검토 및 전환계획 정합성을 이어 확인한다. Claude는 실제 운영계정·issuer 준비/독립 검토, Gemini는 정본factory에 대한 실제로그인·준비상태·화면 검증을 맡는다. migration/Node프로필/kill switch의 critical 운영변경은 적용하지 않았다.

전체 **57.81% 완료/42.19% 잔여** 유지. CI/독립검토/운영SSO/원격실행 인수 미완료. Obsidian 결과 후속 기록.

Obsidian 외부3개 편집 원문/hash를 보존·수신요약 후 동기화했다. 23:37:27KST e7f1844 기준759관리파일 hash일치/pending0/conflict0/check→apply→check exit0. receipt business-workspace-obsidian-sync-20260912.json. F1 추가독립확인은 별도보고로 이어간다.
