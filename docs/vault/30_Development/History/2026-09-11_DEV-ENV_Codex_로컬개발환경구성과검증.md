---
doc_id: "HIST-DEV-ENV-20260911"
title: "Codex 로컬 개발 환경 구성과 검증"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T01:08:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["history", "development", "verification"]
---

# 실제 구성 결과

Task DEV-ENV, owner Codex. Base `175b6f04abc5bb441f112a0015bccfa8d211ba09`, branch `agent/codex/dev-environment`. 구현 `216027ed49dcd0ee78277d7fc1f5bf25a02b9384`, 도구 공통 명령 연결 `5efc13567c8fe93294247a7a3189db75d353351f`. 2026-09-11 01:08 KST 기준 로컬 개발 기능은 실행 검증됐고 CI·독립 검토·원격/GPU 인수는 미완료다.

## 사용 가능한 환경

- Windows 바탕화면 `SaintVision 개발 시작.lnk` 생성. 시작/기존 프로세스 재사용/일회용 브라우저 로그인. 실제 브라우저 열기 요청 수행.
- Studio `http://127.0.0.1:18100`. Windows 현재 사용자용이며 LAN 외부 bind 없음.
- 실제 Node 화면 `http://localhost:3000`에 개발 Studio 이동 링크 반영. 현재 Node 192.168.45.225 한 대, 관측 프로필 유지.
- SaintVision 개발 checkout·일반 Python·AI CPU 학습 프로젝트 3개 등록. AI 프로젝트는 main과 Codex/Claude/Gemini/Antigravity의 실제 worktree 5개, 전체 Workspace 7개.
- AI/일반 프로젝트 6개 작업 폴더에 독립 Python venv와 pip 구성. 도구별 `.saintvision/README.md`에 실제 project/workspace ID가 고정된 CLI 명령 제공. 기존 사용자 파일 덮어쓰기 거부.
- 초기 작업 한도 0.5 CPU, 256 MiB, 120초, 동시 1건. CPU 0.25–1/RAM 128–512 MiB/최대 300초 범위 내 변경 가능.
- Docker image `sha256:5efa1fae77f5d8bc330fd75ff4e03d35c95bef84ab5fca7852001a2e8ad781f9`. 기존 로컬 Python 3.11 base의 layer 일치를 확인했다.

## 실제 명령과 증거

| KST | 실제 명령/동작 | 결과 |
|---|---|---|
| 00:50–00:53 | dev_studio.py init/build-image/create/register; Start-DevStudio.ps1 | 호환성 오류 정정 후 exit 0, 프로젝트/서버 구성 |
| 00:53 | Edge/Playwright 로그인→AI 학습→결과 다운로드 | exit 0, CPU 500m/RAM 268435456 bytes 실제 적용, 출력 파일 3개 hash 일치 |
| 00:55 | check_dev_studio.py 실제 Docker 5개 시나리오 | exit 0, 격리·멱등성·exit 7·timeout 124·취소·runner 강제 중단 후 정리 |
| 00:55–00:56 | apps/web npm ci --ignore-scripts --offline; npm run build | exit 0, TypeScript/Vite build |
| 00:56–01:01 | venv ensurepip; 실제 AI/Python 단위 테스트; Orca file open | exit 0, 실제 README 열기 확인 |
| 01:02–01:03 | 동일 216027e 코드에서 Docker 5개 시나리오 및 실제 브라우저 학습 | exit 0, 모든 소유 컨테이너 종료 확인 |
| 01:05 | 별도 Codex Workspace의 등록 CLI test | exit 0, 실제 5efc135 코드·Workspace 경로 일치 |
| 01:06–01:07 | 브라우저 Workspace 5개·선택 보존·503 주입·자동 복구·Node 링크 | exit 0, stale 개발 화면 숨김 및 복구 확인. 주입 시험은 실제 Node 장애 시험과 별개 |
| 01:07 | pytest tests/core/test_dev_studio.py -q | exit 0, 16 passed |

실제 실행 ID:

- 브라우저 학습: `dev_c0392ef4e18044e0be93044a33fa35d3`, 종료 0, 합성 데이터 학습 51행/평가 50행, 평가 MSE 약 `1.65e-12`.
- AI main 테스트: `dev_6a5ec79b80774c00a69364faedfcbad4`, 종료 0.
- 일반 Python 테스트: `dev_ca803b201af743db8ba02e92eacdaff5`, 종료 0.
- 별도 Codex Workspace 테스트: `dev_4a22aac7ee3b4b91939a90d900d36439`, 종료 0.

실행별 이미지 ID·input/stream/artifact hash·실제 Docker 설정·dirty/code-file provenance는 [[dev-env-5efc135.json]]에 있다. 코드 변경 전·후 테스트 SHA를 혼동하지 않는다. 소스 기록은 해당 실제 해시로 판별한다. 영구 Windows 서비스·OS 재부팅 시험·실제 업무 데이터 학습을 수행했다고 보고하지 않는다.

## Git·CI

216027e와 5efc135 모두 origin 작업 브랜치 push exit 0. main 병합이나 독립 reviewer 승인은 수행하지 않았다.

- 216027e: Frontend 34499568168, Docs 34499568188, Backend 34499568383, Core 34499568234.
- 5efc135: [Core 34499867342](https://github.com/egparadise/SaintVision-Invion/actions/runs/34499867342), [Docs 34499867252](https://github.com/egparadise/SaintVision-Invion/actions/runs/34499867252), [Backend 34499867242](https://github.com/egparadise/SaintVision-Invion/actions/runs/34499867242).
- 전부 계정 결제 실패/사용 한도 때문에 job 시작 전 차단. 제품 검사 실패로 단정하지 않으며 CI 성공으로도 기록하지 않는다. 사용자 지시대로 billing 변경이나 반복 재실행을 하지 않았다.

## 동기화와 인계

`check_docs.py`, `check_ontology.py` exit 0. 기존 LAN sync state에서 안전하게 이어받아 `sync_obsidian.py --check --state .work/dev-sync-state.json --adopt-identical`에서 충돌 0 확인. 01:08 KST apply는 7개 파일을 내보냈고 전체 304개 파일 hash 일치를 확인했다. 후속 check는 pending 0/conflicts 0. 이 결과를 추가한 보고서 1개도 다시 동기화한다. OneDrive 클라우드 전파 완료를 주장하지 않는다.

사용 안내: [[2026-09-11_DEV-ENV_사용안내]]. 오류와 정정: [[2026-09-11_DEV-ENV_오류와해결]]. 개발/제품 경계: [[Codex 개발 Studio와 제품 실행 경계]].

다음 담당: Codex는 원격 Node 실행 활성화 및 제품 admission/자원 예약/Evidence 연결, GPU·실제 패키지 런타임 검증. Claude는 독립 코드/운영·복구 검토, Gemini는 도구 여정·브라우저/접근성 검토. 실제 Agent 전달·검토 완료가 아니라 인계 대기다. 현재 로컬 CPU 개발 환경을 전체 분산 개발 플랫폼 완료로 표시하지 않는다.
