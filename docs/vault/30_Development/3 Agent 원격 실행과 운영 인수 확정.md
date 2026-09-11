---
doc_id: "HANDOFF-REMOTE-ACCEPTANCE-001"
title: "3 Agent 원격 실행과 운영 인수 확정"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T15:54:00+09:00"
source_of_truth: "Git"
---

# 세 Agent의 다음 단계 확정

2026-09-11 인계 재검토: [[2026-09-11_Claude_잔여보고_Codex_독립검토]]에서 과거 0026 누수와 최신 적용 guard의 차단을 실측했고, 결과 중복 제거·현재 입력 조회를 f4fe37e에 통합했다. Claude는 이 보완의 독립 검토와 실제 운영 계정/Workspace 적용·전체 복원 리허설을 이어간다. Gemini는 별도 실행 권한과 입력 준비를 포함한 현재 7개 checks 배열을 표시한다. 아래의 결과 중복 제거 작업은 이 코드에 반영됐으며 운영 배포와 종단 인수는 아직 별도다. #13·15·16·17·18·20의 기존 병합 및 #11·#12의 중복 draft 종료를 새 원격 합격으로 해석하지 않는다.

사용자가 전달한 Gemini 제안을 검토해 역할 분담을 확정한다. 합격 조건은 프로필 이름만으로 만족되지 않는다. 실제 원격 Node는 nod_01M25VZZFBYQVFGYB11G7HC10J / 192.168.45.225, 서버는 192.168.45.99다. 화면의 Node-04는 이 실제 ID와 연결된 표시 이름일 때만 사용한다.

| owner | 다음 작업 | 합격 증거와 선행 조건 |
|---|---|---|
| Codex | 기존 identity/key/journal을 보존한 lan-workspace-v1 설치 확인, 실제 mTLS·image 검증, 격리 시험 DB의 원격 7개 인수 | Python, CPU 학습, 실행 전 취소, 실행 중 취소, 실패 종료, timeout, 서버 프로세스 중단 후 output recovery. 각 case의 상태·Node receipt·출력 해시/Evidence·자원 회수·중복 전달 불변성 확인 |
| Claude | 최신 kernel 독립 검토, 실제 운영 로그인/계정·프로젝트 권한과 Workspace 파일 준비·자원 제공 연결 | 현재 IdP 주체, 명시적 실행 grant, 실제 파일/승인 입력 연결, 운영 시작·복구 절차. 중복 결과 서비스는 canonical 계약에 따라 제거 |
| Gemini | 실제 응답에 기반한 telemetry/예약 가능량 및 운영 원격 dispatch 브라우저 인수 | 위 설치·시험 및 Claude 운영 계정/Workspace/권한·제공량 준비 이후 편집→승인→실행→취소/복구→다운로드를 실제 API로 확인. unknown/차단 사유 표시 |

Codex 장비 시험과 Claude의 운영 준비·Gemini API/UI 정리는 병행 가능하다. Gemini 최종 운영 브라우저 인수는 두 선행 결과가 모두 필요하다. 프로필 설치만으로 schedulable=true를 저장하거나 강제 표시하지 않는다. 현재 mTLS 인증/epoch/신선한 관측, 허용 프로필·image, 프로젝트 Node 권한, 실제 제공량·미반납 예약·사용량, drain/kill switch·승인/admission을 함께 판정한다. 가용량은 프로젝트·workload에 따라 달라지며 관측 전용과 실행 가능을 구분한다.

현재 격리 DB의 합성 JWT/승인자 장비 시험은 운영 로그인·일반 업무 승인과 별도다. 운영 kill switch 또는 grants를 장비 시험 성공만으로 해제/부여하지 않는다. 또한 현재 두 PC 검증은 CP 서버 1대와 원격 worker 1대이며, 두 실행 Node의 병렬 분산 학습이나 GPU 시험을 뜻하지 않는다.

실제 profile 설치 안내는 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]. 서버에 전달할 것은 설치 결과 JSON의 profile/agentImage/executionImage/보존 결과이며 개인키·토큰은 전달하지 않는다. 이번 확정은 실제 설치 결과가 도착했다는 뜻이 아니다.
