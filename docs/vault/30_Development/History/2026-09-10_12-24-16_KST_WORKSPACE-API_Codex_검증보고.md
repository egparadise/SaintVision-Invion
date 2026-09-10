---
doc_id: "LOG-WORKSPACE-API-VERIFY-001"
title: "2026-09-10_12-24-16_KST_WORKSPACE-API_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T12:24:16+09:00"
source_of_truth: "Git"
---

# WORKSPACE-API 검증 보고

Task WORKSPACE-API, owner Codex, independent reviewer Claude pending. S03-BE 및 S06-BE/DB/ST, OUT-03/06/07·AC-03/06/07 후속. base `100ae37e12a5a8f815e772711563269ea6d63408`, branch `agent/codex/workspace-api`, [draft PR #13](https://github.com/egparadise/SaintVision-Invion/pull/13). 지침/Skill 버전과 시작 scope는 [[2026-09-10_11-59-00_KST_WORKSPACE-API_Codex_개발과정]]에 기록했다. 구현 계약은 [[Codex Workspace 공개 API와 실행 커널 통합 계약]], ADR-046/047이다.

## 검증한 결과

코드 SHA `e9dd3419f04f20d729cdb28cf93387028dd9e292`에서 실제 JWT 요청을 DB의 frozen Workspace·새 distinct 승인·원자적 예약/claim/서명 queue·mTLS Node·실제 Git 수정·checkpoint/Evidence·Run 완료에 연결했다. API는 큐 등록에 202 accepted를 반환하고 실제 실행 전에는 DB 상태가 scheduled다. 출력은 기존 kernel 경로에서 해시 검증 후 완료하며 HTTP가 실행 성공을 만들어내지 않는다.

prepare의 정책 거절은 frozen row/approval을 남기지 않는다. enqueue 등록 실패는 승인 소비·lease·queue를 모두 rollback한다. 네트워크 관측 중 requester/approver 권한·Node 프로젝트 소속 회수 또는 취소가 발생하면 실행을 등록하지 않는다. 반복 요청은 같은 command 관찰이며 Node가 offline이어도 재실행하지 않는다. replay도 현재 프로젝트 권한을 확인한다.

현재 선언한 양쪽 공개 migration head에서 0019 통합 head로 실제 임시 PostgreSQL DB를 upgrade하고 반복 upgrade했다. runtime 시험은 migration의 비특권 NOLOGIN inv_kernel 그룹으로 수행했다. production Docker image build/비root UID/설정 없는 시작 거절을 확인했다. 운영 DB 적용이나 장비 배포는 수행하지 않았다.

## 실제 증거

| 항목 | 명령·결과 |
|---|---|
| 전체 Python | `python -m pytest --junitxml=dist/core-tests.xml -o faulthandler_timeout=45`; 922 passed, failure/error/skip 0 |
| Workspace 선행 검사 | resume 11개 + 공개 API 9개 = 20개 passed. 전체 Python에도 포함되므로 중복 합산하지 않음 |
| Linux Go | `go test -race -json ./...`; 40 top-level / 94 leaf case, failure/skip 0 |
| Backend | Python 3.12/3.14 CI success; 모델/schema·migration·서비스 회귀 포함 |
| Frontend | 동일 코드 PR CI에서 Vitest/TypeScript/Vite build success. fixture 단위 시험이며 실제 브라우저 인수 아님 |
| DB history | `python tools/check_migration_upgrade.py`; 양쪽 기존 head → 통합 head → 반복 head, 제한 역할 권한 확인 |
| Production package | Python wheel/sdist, Go/TS 계약, Docker image 및 설정 누락 거절 검사 success |
| 문서 | `python tools/check_docs.py`, `python tools/check_ontology.py` 로컬 exit 0 및 동일 코드 Documentation CI success |

Core push [34432676544](https://github.com/egparadise/SaintVision-Invion/actions/runs/34432676544), Documentation push [34432676630](https://github.com/egparadise/SaintVision-Invion/actions/runs/34432676630). Artifact `10135184510`, 확인 `2026-09-10T12:24:16+09:00`, ZIP SHA-256 `af463725a917db62894094f52034efd07a7703fab18d9a78e83b1c685069ec30`. JUnit/XML·Go JSONL·provenance는 `docs/vault/30_Development/Evidence/apicode-e9dd341-*`에 원본 그대로 보존했다. 파일별 hash는 provenance에 있다.

로컬 Windows의 최초 빠른 검사 195 pass/14 skip은 DB/Linux 미실행을 명시했다. 이후 신규 경계 3개 및 migration/schema 검사 30개도 pass였으나 중복 검사 수를 합산하지 않는다. 실제 실행 합격 수는 위 Linux CI만 사용한다. Frontend `npm ci --no-audit --no-fund`, `npm run build`도 exit 0이었다.

## 오류와 통합 판단

[[WORKSPACE-API 통합 검증 오류]], [[WORKSPACE-API 통합 검증 해결]]에 최초 4a60a15의 API 상태 코드 기대값 1건, migration 가정 2건, Frontend 타입 오류를 남겼다. d486109의 920개 통합 통과는 중간 증거다. 최신 922개 성공과 혼동하지 않는다. Node 프로젝트 소속 보완은 Codex 자체 검토 결과이며 독립 review가 아니다.

integration/all-agents-unified `2244853` 및 Claude `be629a2`를 별도 worktree에 통합했다. History 양쪽 내용을 보존했고, Backend 검사는 Node/Go 전용 Core job과 구분해 유지했다. 시험은 매번 생성한 별도 DB를 쓰며 기존 사용자 DB의 모든 schema를 삭제하는 fixture를 가져오지 않았다.

## 동기화와 전달

코드 e9dd3419f04f20d729cdb28cf93387028dd9e292 기준 Obsidian check → apply → check는 2026-09-10T12:16:25+09:00에 모두 exit 0, 236 파일 hash 일치/pending 0/conflict 0이었다. Gemini 보고서 두 파일의 차이는 CRLF/LF뿐이었고 원본 bytes/hash를 Evidence/workspace-api-sync-line-endings.json에 보존했다. 문서 정본과 같은 내용인지 확인한 hash만 수용했다. OneDrive cloud 업로드 완료는 확인하지 않았다.

이 보고서와 Evidence를 포함한 최종 commit은 push 뒤 같은 SHA의 Core/Backend/Docs/Frontend PR CI 및 Obsidian sync를 재확인한다. 최종 SHA·CI ID·artifact hash·sync 시각은 PR #13의 전달 receipt에 기록한다. reviewer 수락이나 main merge/운영 배포를 수행했다고 표시하지 않는다.

## 실제 남은 항목과 다음 owner

| 담당 | 다음 작업 |
|---|---|
| Codex | 샤드의 새 승인 기반 재실행·대체 Node·다중 Node 통신/결과 집계 복구. terminal parent를 부활시키지 않고 recovering의 새 계획 또는 새 parent Run 계약 필요 |
| Codex | 대용량/장시간 Workspace, 인터랙티브 PTY·remote Git, 동적 pool/locality 통합, kill/drain·Windows/GPU/BuildKit, Context/RO/Eval, 5대 장비 부하·장애·복원 |
| Claude | PR #11/#12/#13 독립 검토, public 보완 업무 서비스 연결과 중복 11개 개념의 ID/단위/데이터 이관. 첫 Run 계획·복원 checkout의 업무 Adapter·editor writer quiesce 연결 |
| Gemini | project-scoped 실제 JWT/2인 승인/prepare/enqueue/조회 화면 연결. 승인 실패 후 성공 fallback·무작위 heartbeat·demo 데이터 제거 및 실제 브라우저 검증 |
| 운영 입력 | 실제 IdP/CA·DNS·Node 등록·private roots·DB LOGIN/grants·worker/outputRoot·저장소 및 장비 구성과 인수 |

최초 포함 총 3 attempt, 파일 총합 32 KiB/manifest 64 KiB 및 제한 profile 한도를 유지한다. 일반 OPA/ROOF 전체 정책 엔진·public 데이터 이관·첫 Run 생성부터 편집까지의 제품 전체 여정·운영 장비 인수는 이번 API 연결만으로 완료되지 않는다.
