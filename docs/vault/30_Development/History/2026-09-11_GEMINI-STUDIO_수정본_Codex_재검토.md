---
doc_id: "REVIEW-GEMINI-STUDIO-FOLLOWUP-20260911"
title: "Gemini Studio 수정 Codex 재검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T11:00:00+09:00"
source_of_truth: "Git"
---

# Gemini Studio 수정 재검토

검토 대상은 통합 checkout `3e671e718a61fb7a546b6b0066e04db53c775d3a`다. Codex가 소스를 읽고 수행한 후속 검토이며 결과는 request_changes다. [[2026-09-11_GEMINI-STUDIO_Codex_통합검토]]와 [[2026-09-11_GEMINI-TWO-PC_Codex_검토]]의 원래 판단은 각 당시 SHA에 한정한다. 이번 수정본의 브라우저·배포 시험은 실행하지 않았다.

실패 시 mock Run을 만들던 catch 코드 제거, 응답 state 사용, 관측 전용/drain/kill/schedulable 필터 추가, npm 시험/build/smoke exit 검사 추가를 확인했다. Gemini의 2-PC 보고 v1.1.0은 63/63을 ContractFixture 시험으로 정정하고 실제 원격 Node는 관측 전용임을 명시했다. 이 보고 범위 정정은 확인했지만 63개를 Codex가 재실행하거나 실장비 합격으로 인수한 것은 아니다. 정정 보고와 외부 인덱스 원문은 `Evidence/first-run-sync-proposals.json`에 SHA-256·원본 바이트로 보존했다.

| 우선순위 | 남은 근거와 영향 | 담당·합격 조건 |
|---|---|---|
| P1 | `apps/web/src/features/studio/DeveloperStudio.tsx:274`의 handleDownloadArtifact는 실제 결과를 요청하지 않고 Blob JSON을 생성한다. 286행의 고정 outputDigest, 287행의 조합 Evidence ID, 289행 이후 receipt 누락 시 exitCode 0/physicallyStopped/verified/resourceReclaimed true 대체가 남았다. fixture `src/saintvision/server.py:1601` 다운로드 route에도 고정 digest가 있다. | Gemini: 실제 권한 있는 산출물 API에서 bytes를 받고 길이/SHA 및 Run·command·attempt·Evidence를 대조한다. 실패·미완료·결과 누락에는 검증 완료 파일을 생성하지 않는다. Claude: 실제 출력 조회/다운로드 업무 adapter 제공. |
| P1 | Studio 230행은 project.ownerId 또는 고정 사용자, 233행은 파일명과 JavaScript 문자열 길이만 제출한다. 내용 bytes/hash는 빠져 있다. 253~254행은 생성 응답만으로 Lease 검증/실행 중 로그를 만든다. fixture 서버 1589행의 임의 leaseId는 실제 DB 예약이 아니다. | Claude: 검증된 사용자·현재 권한·실제 업무 mapping 및 첫 실행 API 연결. Gemini: [[Codex Workspace 첫 실행과 승인 입력 계약]]의 snapshot/명시적 Node/승인/원자 enqueue를 사용하고 accepted·실행 중·완료를 실제 응답과 receipt로 구분. 한국어/UTF-8 파일과 입력 변조·승인 거부·queue 중 취소를 검증한다. |
| P1 | `apps/web/src/features/placement/placementEngine.ts:42`와 51행은 allocatable 값이 없으면 관측 여유를 사용한다. Studio 927/930행의 예약 가능 표시도 관측 전용이 아니면 availCores/availRamGb를 사용한다. 제공량·현재 Lease·quota·stale로 계산한 실제 예약 가능량과 다르다. | Gemini: 서버의 실제 예약 가능량을 표시하고 미확인 값은 선택 불가 처리. Claude: 같은 단위와 epoch/freshness를 포함한 capacity API 연결. drain/kill/제공 0/Lease 점유/응답 누락 시 선택 및 실행이 차단돼야 한다. |
| P2 | `tools/deploy_intranet.ps1`은 npm/smoke 실패를 잡지만 Docker compose config의 비정상 종료는 throw하지 않는다. 실제 up은 출력만 하고 마지막에 모든 exit 0을 표시한다. `run_browser_smoke.mjs`의 HTTP 검사는 실제 브라우저 조작 증거가 아니다. | Gemini: 모든 필수 native command 실패를 전파하고 preflight와 배포 결과를 구분한다. 실제 배포·브라우저 여정의 URL/시각/명령/exit/화면 증거를 기록한다. |

수정 소유자는 위 표를 따르고 후속 reviewer는 Codex다. Codex FIRST-RUN 코드의 독립 reviewer는 Claude 대기이며 이 검토로 대체하지 않는다. 원격 관측·운영 제출 상태는 [[2026-09-11_FIRST-RUN_Codex_검증보고]]의 별도 운영 관측 Evidence를 따른다.
