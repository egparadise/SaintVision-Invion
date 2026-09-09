---
doc_id: "REPORT-DURABLE-DISPATCH-001"
title: "Codex durable dispatch와 중단 복구 검증 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:47:29+09:00"
source_of_truth: "Git"
---

# Codex durable dispatch와 중단 복구 검증 보고

Task durable-dispatch / OUT-04·06·07 / owner Codex / reviewer Claude(pending). branch agent/codex/durable-dispatch, base `7d657602d3f48122c20207cfff0919755e97f959`, 구현 `3a3858eb9b1b3be63e250dc5e9b1bbb5156cd117`. GUIDE/GOV/Backend·DB·Storage v1.0.0, ADR-INDEX v1.7.0, DURABLE-DISPATCH-CONTRACT-001 v1.0.0, agent-delivery/core-reliability Skill v1.0.0. 기존 draft #6 위의 한정 Core 구현이며 전체 업무 또는 운영 환경 합격을 의미하지 않는다.

## 구현 결과

- ToolGateway는 권한/Lease/policy/runtime를 확인하고 claim·signed permit·enqueue event를 같은 DB transaction에 저장한다. caller에는 임시 direct start 권한을 동시에 주지 않는다. signer/DB/event 실패는 전부 rollback한다.
- migration 0007은 tenant RLS와 immutable permit/scope, queued→uncertain→stopped 단방향 상태, receipt 없는 stopped 금지를 추가했다. 기존 transient claim을 재발급해 queue로 바꾸지 않는다.
- 첫 전송을 DB에 예약하고 commit한 뒤 mTLS를 호출한다. crash/응답 유실/worker lease 만료 뒤에는 같은 permit의 observe/cancel만 허용한다. 늦은 worker 완료는 새로운 token을 덮어쓰지 않는다.
- Run 취소는 활성 execute의 45초 worker lease를 기다리지 않고 별도 cancel worker가 인수할 수 있다. 같은 Node의 다른 Run은 단일 실행 슬롯을 Node 잠금 아래 검사해 queued를 유지한다.
- 실제 Node stop receipt가 현재 인증서/epoch 및 Lease proof와 함께 commit돼야 queue가 stopped로 닫힌다. transport success flag·예외·unknown intent는 반환 근거가 아니다. receipt commit 뒤 queue 완료 전 crash도 재관찰로 닫힌다.
- inv-delivery-worker / python -m inv.worker, 명시적 tenant/DSN/epoch/TLS config, 2 worker·40초 I/O·45초 작업 lease·2~30초 backoff, --once 및 종료 신호 대기를 지원한다. 이 machine에 운영 service를 설치/기동하지 않았다.

## 실제 검증

2026-09-10T02:47:17+09:00 GitHub artifact #10117339270의 원본을 확인했다.

| 검증 | 실제 결과 | Evidence |
|---|---|---|
| Python 전체 | 301 tests, failures/errors/skipped 모두 0 | [[dispatch-3a3858e-tests.xml]] |
| Linux Go race | 24 top-level / 57 leaf cases, failures/test skips 0 | [[dispatch-3a3858e-unit.jsonl]] |
| 신규 DB 경계 | 13개: 원자 저장·rollback·8 worker·2 Run/Node slot·기존 claim 재사용 거절·grant 철회·취소 선점·RLS/guard·backoff·가짜 성공 거절 | JUnit |
| 신규 실제 Node | 5개: queue 실행·TLS 응답 유실 재관찰·활성 실행 취소·전송 전 crash·별도 worker CLI process | JUnit |
| Core Build | success, Linux/PostgreSQL 16/Docker/합성 CA, package·생성 drift·Go/TS 통과 | [#34384656712](https://github.com/egparadise/SaintVision-Invion/actions/runs/34384656712) |
| Documentation Build | success | [#34384656788](https://github.com/egparadise/SaintVision-Invion/actions/runs/34384656788) |

초기 5ee1df8970213bc98222285fa1dd1734b7958f1b의 Core #34384543556와 Documentation #34384543553도 success였다. 이후 Node slot 경계를 추가한 위 SHA를 최종 구현 증거로 사용한다. 이전 단계 #6의 최종 head 7d657602d3f48122c20207cfff0919755e97f959는 push/PR Core·Docs 4개 모두 success(#34383586085/#34383586073/#34383591678/#34383591707)와 Python 283/Go57·Obsidian160개 일치를 확인했다. 본 단계와 수치를 단순 합산하지 않는다.

로컬 기존 단위 147 passed, 새 PostgreSQL/Linux 18개는 실제 isolated 환경이 없어 skip. initial fixture 오류 및 slot 정정은 [[ERR-DISPATCH-001 Fixture 의존성과 Node 실행 슬롯 경계]]와 [[RES-DISPATCH-001 명시적 fixture 및 Node 예약 직렬화]]에 구분했다. 원시 artifact hash는 [[dispatch-3a3858e-provenance.json]].

## 검증 한계와 후속

- queue에 들어간 승인 작업의 전달/취소 worker를 구현했다. 사용자 workflow의 plan/approval request/PDP/runtime capability/queue signer 조합과 Frontend 화면 연결은 여전히 담당 owner 통합이 필요하다. 실행 exit 0을 Run succeeded/application Evidence로 승격하지 않는다.
- 최초 전송 전 crash·만료·grant 철회로 Node intent가 없으면 자동 재실행·자원 반환을 하지 않는다. 해당 작업은 uncertain 및 Lease 유지다. Node의 실제 부재 확인/안전한 폐기·새 승인, storage/checkpoint 회복의 후속 계약이 필요하다.
- 큐 envelope에는 argv가 있으므로 서버 DB와 backup 권한/암호화·secret 참조 정책이 필요하다. signing private key는 저장하지 않는다. 총 backlog·retention GC·운영 경보·IdP/PKI·5대 장비·Windows/GPU·장시간 SLO는 별도다.
- Claude는 독립 core 검토·업무 adapter와 기존 P1 heartbeat/backup 수정을, Gemini는 실제 API/OIDC/SSE 연결과 모의 실측/인수 표현 수정을 소유한다. Codex는 [[Codex 잔여 개발 작업과 합격 증거]]의 Storage publication·pin/GC·checkpoint 및 통합 경계를 이어간다.

외부 관리 문서 12개와 신규 Gemini Final Dossier 1건은 hash를 대조해 제안으로 수신했다. 이미 검토한 동일 hash 11개와 History 새 링크 1개이며, 이전 Codex 기록 삭제나 전 Sprint 운영 완료 주장은 채택하지 않았다. [[외부 인계 제안 수신과 정본 동기화 복구]] 및 [[Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성]]을 따른다. actual 수신·owner 수정·독립 재검토는 pending이다.

baseline 48 task/12 Outcome의 완료 조건을 완화하지 않는다. 운영 구성·실장비 입력이 필요한 단계와 별도 reviewer 승인 전 main merge/운영 배포는 수행하지 않았다. 최종 보고서 commit의 CI는 다시 같은 SHA로 확인해 draft PR에 남긴다.

## 산출물 SHA-256

- `inv-node`: `9da353316198dee1d8d54edc6c90c891dd6ba83fcf6d3cee8f74ad10a12ce754`
- `node-unit.jsonl`: `00f519dceb139d42d688460115f07fea691ff3c918806bda91f09e7f5d4fdfa9`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `8a32627dbf0de4fa3418c731904b29675be01679081272837a1f2111addfbe32`
- `core-tests.xml`: `53124f68706114cca9ecbd0cc322f278841ad4e2d8028e42e51cea97f6071f45`
- `saintvision_control_plane-0.1.0.tar.gz`: `8fc0219e1122320776c93550d2330ffbb2141f3e6adeeddace6a6cd83d6a9085`


## 2026-09-10T02:47:32+09:00 로컬 전달 검사

`python tools/check_docs.py` exit 0: 원문 24 hash/문서 118개/task48/outcome12/owner·링크·DAG 통과. `python tools/check_ontology.py` exit 0: RDF/SHACL/질의·projection 통과. `python tools/test_sync.py` exit 0: 충돌 보호 3개 시험 통과. `git diff --check` exit 0. 실제 export는 아래 기록한다.

## Obsidian 실제 동기화

- 2026-09-10T02:47:32+09:00 `python tools/sync_obsidian.py --check --state .work/dispatch-obsidian-sync-state.json`: exit 0; `CHECK: 169 managed files, 24 pending exports, 0 conflicts. No writes.`.
- 2026-09-10T02:47:33+09:00 `python tools/sync_obsidian.py --apply --state .work/dispatch-obsidian-sync-state.json`: exit 0; `EXPORTED: 24 files; all 169 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 다시 export하고 전체 파일 hash 일치를 확인한다. 최종 보고서 SHA-256은 PR 인계에 기록한다. 작업별 state로 확인 이후 발생한 다른 Agent 편집을 보호하며 공유 state를 무조건 덮어쓰지 않는다.
