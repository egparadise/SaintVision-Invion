---
doc_id: "REVIEW-GEMINI-STUDIO-20260911"
title: "Gemini Studio Codex 통합검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T09:32:53+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "studio", "integration"]
---

# Gemini Studio 통합검토

작성자 Gemini / 검토자 Codex. 검토 대상은 별도 root checkout `integration/all-agents-unified`의 `b445974f6983aa4f74d3f25eb3063ff27786e38a` 및 09:26 Obsidian 보고다. 해당 checkout은 수정하거나 배포하지 않았다. 아래는 제한된 정적 코드 검토와 실제 서비스 관측이며 Gemini의 115개 시험을 재수행한 결과가 아니다.

## 수정 후 다시 검토할 사항

1. **P1 — 실행 실패를 새 실행처럼 표시.** `apps/web/src/features/studio/DeveloperStudio.tsx:233`에서 POST 실패 시 `mockRunId`를 만들고 원격 실행 로그를 추가해 결과 단계로 이동한다. 성공 경로도 응답 상태 확인 없이 `running`/Node 배치/파일 실행을 표시한다(224행). 전송 실패·권한 거부·미확정 응답을 실패/불확실로 보존하고, 서버의 실제 Run ID·state·Node 영수증으로만 갱신해야 한다. 임의 재전송 금지. owner Gemini.
2. **P1 — 화면 설정이 실제 실행 입력에 연결되지 않음.** 동일 파일 209~216행 POST body는 workspace/objective/requestedBy뿐이다. 편집 파일, 선택 Node, CPU/RAM, 불변 snapshot/승인/lease binding이 전달되지 않는데 실행 로그는 해당 설정을 실행한 것으로 표시한다. Claude가 실제 kernel binding API를 연결하고 Gemini가 그 계약을 사용해야 한다. 서버가 검증한 사용자/내용만 실행에 사용한다. 각각 서비스 owner Claude, UI owner Gemini, 공통 계약 Codex.
3. **P1 — 사용률 기반 여유량을 예약 가능량으로 간주.** `apps/web/src/features/placement/placementEngine.ts:26`은 CPU 사용률과 전체 RAM 차이만으로 배치 가능 여부를 계산하며 owner 제공 상한·기존 lease·stale snapshot·drain/kill switch를 반영하지 않는다. 현재 실제 worker는 online이지만 관측 전용이고 제공 자원이 없어 이 계산으로 업무를 배치할 수 없다. Codex kernel의 admission/lease 계산을 권위로 삼고 Gemini는 관측 여유와 예약 가능량을 별도 표시해야 한다.
4. **P1 — 배포/브라우저 완료 보고를 뒷받침하지 못하는 검사.** `tools/deploy_intranet.ps1`은 native command exit code를 검사하지 않은 채 PASS 문구를 쓰고, 마지막 단계는 Compose 실행 명령을 출력할 뿐 실행하지 않는다. `tools/run_browser_smoke.mjs:514`의 `every` 검사는 빈 배열에도 성공하고 5개 실제 Node나 mTLS 출처를 입증하지 않는다. Track 13은 fetch 응답 검사이며 브라우저 조작 증거가 아니다. 실패 exit 전달, 실제 배포 health 및 실제 브라우저/Node ID/Evidence 추적이 필요하다. owner Gemini.

현재 사용자의 실제 서비스는 Codex checkout의 3000/18100이며, fresh mTLS 연결된 worker 한 대와 관측 전용 프로필을 확인했다. Gemini 보고의 고정 프로젝트·5노드·OIDC/다중 Node 실행 완료 주장은 이 실측을 대체하지 않는다. 원문은 `Evidence/node-compat-sync-proposals.json`에 보존했다. 본 검토는 Gemini가 Codex 코드를 검토한 것으로 계산하지 않는다.
