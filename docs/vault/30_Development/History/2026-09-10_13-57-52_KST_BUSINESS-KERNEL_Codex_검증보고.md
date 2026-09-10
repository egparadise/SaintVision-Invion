---
doc_id: "HIST-BUSINESS-KERNEL-VERIFY-001"
title: "2026-09-10_13-57-52_KST_BUSINESS-KERNEL_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:57:52+09:00"
source_of_truth: "Git"
---

# BUSINESS-KERNEL 검증·인계

task BUSINESS-KERNEL / owner Codex / reviewer Claude pending. base `4290467fec203c0e8f290bd816c5d30ca1bd34bd`, 구현 `255b29e2b74a61bb8ef3dd798cacee10e7faecec`, branch `agent/codex/business-kernel`, [draft PR #16](https://github.com/egparadise/SaintVision-Invion/pull/16). PR14 검토 기준 `c06f59c87c16ebbbc32459a3116ee9144e9cd6bf`를 전체 merge하지 않고 [[Codex 업무 binding과 실행 커널 연결 계약]]의 안전한 kernel 경계로 연결했다. 입력/범위는 [[2026-09-10_13-29-45_KST_BUSINESS-KERNEL_Codex_개발과정]]이다.

실제 public Project/Member/User/Workspace/Workload/Run을 명시적으로 연결하고 현재 권한 교집합, 서버 캡처 입력, 새 quorum 승인, 원자 예약/큐, stop receipt/Evidence 기반 binding 상태와 자동 lock 해제를 검증했다. 클라이언트 state 제출·가짜 Approval·Project/lock scope 우회는 거부한다. queued 뒤 권한이 철회되면 Node 취소 tombstone으로 정리하고, 관측 한도 오류는 새 nonce로 총 3회만 재시도한다.

## 실제 검증

- 전체 Python **962 passed**, failure/error/skip **0**. 업무 전용 **16개**, 샤드 **21개**, Workspace **20개**는 전체의 부분집합이며 중복 합산하지 않는다.
- Go race **40 top-level / 94 leaf cases**. Node binaries·production image·Python package·TypeScript/Go 계약 컴파일과 생성물 drift 검사 통과.
- 빈 DB 및 canonical 0018·0010·0019·0020에서 0021로 upgrade/replay, production inv_kernel 그룹과 FORCE RLS·열 권한 검증. PR14 실험 0024 DB를 운영 변환한 결과는 아니다.
- Backend Python 3.12/3.14, 문서 원문 hash/링크·Ontology 검증 통과. 실제 PostgreSQL·JWT·mTLS·Go Node·Docker·파일/Git·Evidence를 사용했다. 장비는 CI Linux 호스트이며 실제 5대 PC 시험이 아니다.
- 로컬 Windows: 초기 핵심/migration 217 passed/1 failed 후 graph 기대값을 수정, 해당 23개 통과. 관측 TLS 추가 후 관련 51개 통과. 계약 생성, check_docs, check_ontology, git diff --check exit 0. Linux Docker daemon 정보 조회 exit 1이므로 로컬 Node 실행 성공을 주장하지 않는다.

| Workflow | Trigger | 구현 SHA 결과 |
|---|---|---|
| Core Build | push | [success 34438622367](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438622367) |
| Core Build | pull_request | [success 34438625725](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438625725) |
| Backend Build | push | [success 34438622555](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438622555) |
| Backend Build | pull_request | [success 34438625686](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438625686) |
| Documentation Build | push | [success 34438622380](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438622380) |
| Documentation Build | pull_request | [success 34438625659](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438625659) |

Artifact `10137278486`, archive SHA-256 `e0efff37b4c659662e8062973bb540568a00a34151e60cf0e59dc7704abcf73d`, 내려받아 XML/JSONL을 확인한 시각 `2026-09-10T13:57:47+09:00`. `Evidence/businesscode-255b29e-*` 6개 파일에 원본 시험 결과와 provenance/checksum을 보존했다. 출력의 private key/token/운영 credential은 문서에 수집하지 않았다.

## 오류·수정

[[BUSINESS-KERNEL 통합 검증 오류]]와 [[BUSINESS-KERNEL 통합 검증 해결]]에 초기 migration 기대값, queued 이후 권한 철회로 남은 관찰 대기, 동시 Node 관측 거부를 기록했다. 위 결과는 수정 후 같은 구현 SHA의 재검증이다. 이전 SHA에서 중단·취소·실패한 CI는 성공 수치에 포함하지 않는다.

## 전달 상태와 다음 담당자

이 보고서를 포함한 후속 commit도 CI를 확인하고 `sync_obsidian.py --check → --apply → --check`를 수행한다. 사전 check는 충돌 0이었다. 최종 SHA·CI ID·실제 sync 파일 수/hash/시각은 PR #16의 마지막 인계 영수증에 기록해 자기 SHA 재기록 루프를 피한다. 아직 실행하지 않은 후속 CI/sync를 이 문서에서 완료로 표시하지 않는다. Obsidian은 로컬 사본이며 OneDrive cloud upload는 별도다.

Claude: 독립 review, 신뢰 provisioning과 업무 CRUD production 조합, 방치된 승인/lock 보존·TTL 정리, 필요 시 PR14 실험 DB의 별도 실제 이관 계약. Gemini: 실제 binding API와 두 승인/불확실 전달/자동 lock 해제/Evidence 화면 및 브라우저 검증. 실제 메시지를 보내거나 독립 인수를 받은 상태는 아니다.

Codex 다음은 kill switch/drain·주기 reconciliation이다. 첫 Run/checkout/editor·PTY·remote Git·대용량·Node 간 파일 이전, Windows/GPU/BuildKit·Context/RO·실제 5대 시험도 남는다. baseline 48 tasks 전체 완료, 운영 배포, 임의 외부 editor 강제 중지 또는 PR14 전체 병합을 주장하지 않는다.
