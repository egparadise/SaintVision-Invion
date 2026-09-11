---
doc_id: "REVIEW-GEMINI-TWO-PC-20260911"
title: "Gemini 2-PC 보고 Codex 검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T10:13:52+09:00"
source_of_truth: "Git"
---

# Gemini 2-PC 보고 검토

Codex가 통합 checkout `8dd1777a6cb7ceb58932660b95d50bb9e8be5812`의 `tools/verify_two_pc_distributed_execution.mjs`와 `src/saintvision/server.py`를 읽고 검토했다. 결과는 request_changes다. 기존 [[2026-09-11_GEMINI-STUDIO_Codex_통합검토]]에 추가되는 증거 검토이며, Claude가 Codex 코드를 독립 검토한 기록이 아니다. 다른 Agent에게 메시지를 전송하지 않았다.

Obsidian History 인덱스의 추가 2행 및 10:00 Gemini 보고 원문을 `Evidence/kernel-live-sync-proposals.json`에 SHA-256·원본 바이트로 보존했다. 외부 보고의 57/57·실제 2-PC·GPU 학습 완료 주장은 아래 이유로 실장비 합격 증거로 인수하지 않는다. 해당 script를 실제 운영 API에 실행하지 않았다.

| 우선순위 | 근거와 영향 | 수정 및 합격 조건 |
|---|---|---|
| P1 | 검증 script는 `nod_01JABCDEF01/05`, `run_01JRECOVERING`, `rcp_01JSHARD_03` 등 고정 ID의 HTTP 응답을 검사한다. `server.py:59` 이후 NODES/POOLS/RUNS/RECEIPTS는 in-memory fixture다. `server.py:1114`의 reclaim route는 실제 Node 정지를 확인하지 않고 dict의 `allPhysicallyStopped`를 true로 변경한다. | Gemini: fixture API 시험으로 명칭/완료 주장을 정정. 실제 두 PC 시험은 관측 Node ID·고정 입력/이미지·서명 receipt·물리 종료 및 Lease 반환 증거로 수행. Claude: 실제 kernel route를 연결한 운영 조합 제공. |
| P1 | script는 `Boolean(receipt.output?.sha256)`만 검사한다. `server.py:565`의 output은 비어 있지 않은 base64 data인데 SHA는 빈 바이트의 SHA-256 `e3b0c442…b855`다. digest 필드 존재는 바이트 무결성 검증이 아니다. | Gemini: 실제 출력 다운로드 후 byte count와 SHA-256을 계산·대조하고 Run/command/attempt/Evidence를 연결. 불일치·변조·다른 attempt의 출력은 반드시 실패. |
| P1 | GPU 단계는 POOLS fixture의 `totalCores === 28`, `totalMemoryBytes === 96 GiB`, 모델 이름만 검사한다. 이 값은 CPU 코어/RAM이며 CUDA 실행·GPU 메모리/장치 격리·학습 모델·분산 통신 증거가 없다. | Gemini: GPU 학습 통과 표현 제거. Codex는 실제 제공 장치와 드라이버/격리 확인 후 GPU workload·결과·회수 시험을 별도로 수행. |
| P2 | `FRONTEND_URL`은 콘솔 출력에만 쓰이고 script는 브라우저를 실행하지 않는다. CPU 관측 여유 계산에는 실제 제공량·Lease·stale·kill switch 조건이 없다. | Gemini: 실제 브라우저/API 여정을 검증하고 backend의 예약 가능량을 표시. HTTP script 통과를 화면 또는 예약 가능량 검증으로 보고하지 않음. |

검토 시 실제 관측 API는 `live-postgresql-mtls`, 원격 Node `nod_01M25VZZFBYQVFGYB11G7HC10J` 한 대 online, `lan-observe-v1`, `gpuCount: null`, `runs: []`, `offered: {}`, `killSwitch: true`, `userWorkloadSubmission: false`였다. 이 응답은 위 공개 Evidence에 함께 보존했다. UI fixture의 다섯 노드와 실제 연결 상태를 혼동하지 않는다.

검토한 외부 인덱스 원문 SHA가 보존본과 같음을 확인한 후 해당 파일의 sync 기준만 갱신했다. Git 정본에는 이 검토 결과로 수신 사실을 남기고, 외부 저자의 보고 본문은 원형 보존한다. 실측 kernel 결과와 다음 담당자는 [[2026-09-11_KERNEL-LIVE_Codex_검증보고]]를 따른다.
