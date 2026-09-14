---
doc_id: "HIST-PROJECT-OBSERVATION-REPORT-20260914"
title: "2026-09-14 PROJECT-OBSERVATION Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:36:33+09:00"
source_of_truth: "Git"
---

# 실제 승인·샤드 조회와 부모 취소 연결

CX-01/CX-02 Codex owner/Claude reviewer pending. 제품4f518ea93bbea9766b99fbcf7aedfd695c693493, 컨테이너검증44939b9, branch agent/codex/workspace-bridge. [[2026-09-14_PROJECT-OBSERVATION_Codex_착수]], [[승인 샤드 화면 정본 API 계약]].

## 구현과 결정

실제 kernel factory에 project-scoped 승인목록/상세, 부모Run의 샤드조회3개 GET을 추가했다. 승인목록은 limit1..200·ApprovalId cursor·runId 필터, 기존 ApprovalView만 반환한다. 샤드조회는 기존 ShardRuntime status를 같은 DB transaction으로 재사용해 현재권한 검사를 유지한다. JSON Schema ApprovalPage/ShardObservation/하위타입 및 Python/TS/Go 생성물 정합화.

부모 전체취소는 기존 project/run cancel의 expectedVersion/Idempotency-Key를 사용한다. 별도 cancel-all 또는 수동reclaim 성공 API는 추가하지 않는다. durable cancellation 후에도 정지receipt가 없으면 resourceReleasePending=true 유지. 이 계약으로 기존 미제공4개 중 승인목록·샤드조회는 구현, 전체취소는 기존 정본으로 수렴, 수동회수는 자동회수상태 표시로 확정했다. Gemini 화면 연결은 아직 미완료다.

## 실제 확인

- `python -m pytest -q tests/integration/test_project_observation.py tests/integration/test_control_api.py`: **16 passed/26.58초/warning2/exit0**. 별도 Docker PostgreSQL16/tmpfs/난수DB·비소유자 runtime/합성JWT/실제 HTTP. 페이지·상세·project/tenant 격리·권한철회·실제 ShardRuntime.enqueue와 부모취소/replay·정지미확인예약보존·불완전plan409 확인. Node프로세스는 실행하지 않았으므로 실제원격시험이 아니다.
- `python -m pytest -q tests/core/test_approval_contracts.py`: **10 passed/1.07초/exit0**.
- `docker build -f deploy/Dockerfile.backend -t saintvision-backend-candidate:project-observation .`: exit0, image sha256:5bce0beacf9b4ae37330ff3361257d5e3acce598f63b6ca5c47026a063c0ce02.
- 이 이미지로 실제 packaged factory를 띄운 `tests/integration/test_server_container.py`: 수정 후 **8 passed/94.54초/exit0**. 비root65532, 설정보호, 새조회routes의 인증/빈결과/404, 실제DB·업무Workspace·영속volume재시작 기존검증 포함. 최초에는 테스트내부 new_id import가 기존전역이름을 가려3failed/5passed였다. import제거 후 해결. 최초실패를 성공으로 숨기지 않으며 credential이 포함될 수 있는 진단은 .work에만 보존한다.
- `python tools/generate_contracts.py`: exit0. 문서374개/48작업·ontology exit0(보고서 추가 전).

성공 XML은 Evidence/project-observation-20260914.xml 및 project-observation-container-20260914.xml. private 운영DSN/키는 포함하지 않았다.

## 외부 차단과 다음 행동

17:34:04 KST .225 TCP18443/22 모두 접속 불가. 이것만으로 전원꺼짐을 단정하지 않음. 별도 DB 관측도 offline/stale·lan-observe-v1,kill switch활성·storage관계2개/관측권한/공개교체묶음 차단. 운영schema/profile/epoch변경 없음. 원격 PC의 Windows/Docker Desktop 준비 상태를 사용자에게 비동기 요청했고, 응답 전 원격시험을 성공 처리하지 않는다.

4f518ea CI6건은 계정결제/한도로 job미시작/failure(Core34823177455/34823172218,Backend34823177456/34823172164,Docs34823177500/34823172168). CI통합검증 미완료. 실제OIDC 설정/독립검토·운영전환·원격7개·5대부하/장애인수 남음.

다음: Codex는 원격재연결 후 서명·profile·7개시험 준비를 이어가고, Gemini는 위정본 API 계약으로 화면연결/fixture없는브라우저검증, Claude는 신규조회권한·계약 독립검토와 운영OIDC 설정 준비. 공통 전체 **2775/4800=57.81% 완료/42.19% 잔여** 유지. 이 카드의 로컬구현을 전체개발/운영인수 완료로 선언하지 않는다.

최종 문서376개/48작업·ontology·diff검사 exit0. Go1.27.1 `go test ./internal/wire` exit0/no test files: 생성wire 패키지 컴파일 확인이며 시험수에 합산하지 않음. 44939b9 CI6건도 계정결제 제한으로job미시작/failure, Evidence project-observation-44939b9-ci.json.
