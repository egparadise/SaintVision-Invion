---
doc_id: "ERROR-ACCOUNT-KERNEL-20260911"
title: "ACCOUNT-KERNEL 오류와 해결"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T13:10:00+09:00"
source_of_truth: "Git"
---

# 계정·커널 통합 오류와 해결

Claude 5e0fed9와 Codex 97e68af를 통합 검토했다. [[Codex 계정과 실행 커널 통합 계약]]의 수정은 Codex 작성이며 Claude의 독립 재검토가 필요하다.

| 확인 사항 | 조치와 검증 |
|---|---|
| projects/settings/adapters router에 /v1 prefix 없음 | 공통 API 경로로 정정하고 실제 HTTP 시험 추가 |
| 로그인만으로 user status/resource offer 변경 가능 | 별도 운영자 관리 grant를 신설하고 viewer/owner 모두 무권한이면 거부 |
| 다른 project의 member 목록 조회 허용 | 현재 멤버십 검사, 미존재와 비멤버 거부 응답 일치 |
| 마지막 owner 검사·offer 교체에 writer 잠금 없음 | Project, Node→Capability 직렬화와 실제 2-thread PostgreSQL 시험 |
| archived project의 owner가 재활성화할 수 없음, 목록의 실행 권한은 역할만 계산 | 상태 복구에 한정된 owner 검사 및 실제 현재 권한 표시 |
| project_kernel_link definer가 인자 tenant만 검사 | 현재 transaction tenant와 일치하는 경우에만 결과 공개, 과거 migration은 보존 |
| 잘못된 JWT가 업무 계층에서 처리되지 않는 DomainError 발생 | 동일 AccessTokens 실패를 업무 인증 오류 401로 변환 |
| Workspace의 원격 도구 준비 여부를 CP 로컬 CLI에서 계산 | 미관측 원격 상태 unknown, CP 설치 관측의 범위 명시 |
| 기존 core 검사에 최종 revision 0025 고정 | 두 공개 branch 부모 보존·merge·0027 head를 검사하도록 갱신 |
| 첫 Docker API 시험 setup에서 FastAPI.add_event_handler 없음 | 현재 설치된 API의 router lifespan_context 조합으로 변경. 이 실패는 제품 성공으로 집계하지 않음 |
| 현재 FastAPI의 지연 include wrapper에는 path가 없음 | 세 업무 router의 선언된 route를 직접 사용하여 kernel Run 경로를 가리지 않고 분기 |
| 업무 AUTH 오류 기본값이 403 | 잘못된/미등록/중지된 계정의 인증 실패를 명시적 401로 고정 |
| 새 public project가 kernel에 없으면 Run ledger FK 쓰기가 권한 검사보다 먼저 실패 | Control.create에서 현재 grant를 먼저 검사, 미연결 프로젝트도 403으로 거부 |

진단 로그·시험 DB 연결 설정은 .work의 접근 제한된 실행 폴더에 보존한다. 공개 기록에는 testcase 상태와 코드 SHA만 사용한다. 이 작업으로 운영 Node/DB/로그인/방화벽을 변경하지 않았다.
