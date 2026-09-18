---
doc_id: "HIST-RUNTIME-CUTOVER-CANDIDATE-20260912"
title: "2026-09-12 RUNTIME-CUTOVER Codex 후보계획"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:33:14+09:00"
source_of_truth: "Git"
---

# 운영 전환 전에 준비할 실제 입력과 증거

CX-02 Codex owner/Claude reviewer pending. 실행 명령이 아닌 후보 계획이며 운영 변경 승인 아님. 사용자 지시의 critical 제외 자동 진행 범위를 준수한다.

## 현재 관측

2026-09-12 23:31:27KST 실제 .225는 online/fresh, profile lan-observe-v1, epoch 일치. kill switch=true. 운영 DB0023_containment_approvals→후보0037_storage_sample_commit 미적용20개. 저장소 관계/역할·공개 교체 bundle도 미완료. 18100 SQLite 작업대와 새 정본 API는 서로 다른 서비스다. 후보를 켰다는 이유로 기존 작업대를 운영 계정 DB로 자동 전환하지 않는다.

## 입력과 담당

| 입력/게이트 | 담당 | 다음 행동 |
|---|---|---|
| 실제 OIDC issuer/audience/client ID 및 검증된 공개 JWKS | 사용자·Claude | 공개 설정 수신/계정 매핑 확인. Codex가 비밀 입력을 채팅으로 요청하지 않음 |
| 업무 inv_app 전용 LOGIN, kernel inv_kernel 전용 LOGIN | Claude·Codex | 같은 DB/옵션, 분리 권한. 기존 inv_app 그룹 NOLOGIN 유지 |
| 전용 config volume | Codex | prepare_server_config.py로 새 volume 생성·검증. 기존 운영키/volume 덮어쓰기 금지 |
| 영속 workingRoot volume | Codex | owner65532/mode0700, 백업·복원 및 편집 API 인수. 단순 재시작 파일 보존과 분산 복구 구분 |
| migration·후보 서버·별도 dispatcher 전환 | Codex·독립 reviewer·사용자 | 새 백업과 기존 복원 증거 연결,20개 migration hash 재확인, 서비스 중단/forward 복구 계획의 critical 적용 승인 |
| 원격 .225 실행 프로필 | Codex | 동일 Node identity/journal 보존, 검증된 profile/이미지/정책 교체, 실제7개 실행·취소·복구 시험 |
| 실행 허용 | 사용자·Codex | 운영 안전 확인 후 kill switch 변경 여부 결정. 이번 작업은 해제하지 않음 |
| UI 실제 정본 연결 | Gemini | kernelLinked/configured/executable 구분, 실제 계정으로 편집→승인→실행→결과 확인 |

## 후보의 사용 순서

14de71d 후보 코드를 기준으로 실제 입력을 검증하고 새 config volume을 준비한다. DB 복원 사본에서 migration/역할/프로젝트·Workspace 경로를 재검증한 다음 운영 변경 내용을 확정한다. 현재의 합성 issuer·TLS·resource ID·임의 profile은 운영 입력으로 재사용하지 않는다. 승인 및 독립 검토 전 운영DB upgrade·Node교체·실행허용을 수행하지 않는다.

CI는 계정 결제 제한으로 job 미시작 상태다. 로컬 컨테이너·실제 PostgreSQL 시험이 통과해도 이를 CI 및 실제 원격7개 시험으로 바꿔 기록하지 않는다.
