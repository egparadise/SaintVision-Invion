---
doc_id: "REPORT-CLAUDE-CL02-001"
title: "Claude CL-02 운영 로그인·권한·Workspace·폴더 적용 검증"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-09-12T09:20:00+09:00"
source_of_truth: "Git"
---

# Claude CL-02 — 운영 로그인·권한·Workspace·폴더 적용

카드: [[Claude 작업 현황]] CL-02. owner Claude / reviewer Codex. 부모 task S02-BE, S02-DB, S02-ST, S03-DB.

## 이 작업이 해결하는 문제

운영 준비는 스위치 하나가 아니다. 로그인할 수 있는 사람이 여전히 작업을 요청할 수 없고, 존재하는 project는 **의도적으로** 커널에 연결돼 있지 않으며, 등록된 Node는 관리자가 양을 정하기 전까지 아무것도 제공하지 않는다. 각각은 서로 다른 사람이 넣는 별개의 운영 입력이고, 실패 모습은 언제나 같다 — 누군가 "권한이 없습니다"라는 말을 듣지만 진실은 "그 입력을 아직 아무도 넣지 않았다"이다.

그래서 세 가지를 **분리해서** 보고한다. 카드가 요구한 "권한 부여와 실행 admission 구분"이 이 분리다.

| 구분 | 묻는 것 | 없을 때의 해결 |
|---|---|---|
| `inputs` | 이 운영 입력을 누군가 넣었는가 | 명시된 담당자가 넣는다. **없음은 거부가 아니다.** |
| `grants` | 이 사람의 권한 사슬이 이 작업을 허용하는가 | 거부한 계층을 지목하고 그 계층의 부여자가 고친다 |
| `admission` | 커널이 애초에 실행을 받아들이는가 | **권한 문제가 아니다.** 권한을 더 줘도 열리지 않는다 |

## 만든 것

`tools/operational_readiness.py` — 운영 DB를 읽기 전용으로 조회해 위 세 가지와 **기록된 제공량 대 커널이 들고 있는 제공량**을 보고한다. 운영 DB에 안전하며, 보여주지 않은 근거로 판정하지 않는다.

`tests/test_operational_readiness.py` — 위 판정이 **실패할 수 있음**을 재현 가능하게 고정한 10개 시험. 각 시험은 실제로 관측한 상태에서 왔다.

## 실제 검증 결과 (로컬 PostgreSQL 16, head `0031_workspace_input_state`)

전부 준비된 tenant: `absent=[]`, `refusedBy=[]`, `mayRequestWork=True`, `wouldAdmit=True`, exit 0.

각 거부가 실제로 발동함을 확인했다.

| 상태 | 보고 | exit |
|---|---|---|
| 빈 tenant | 12개 입력 전부 ABSENT, 각각 담당자 명시(operator / project owner / node owner) | 1 |
| 역할이 `viewer` | `refusedBy=['role permits requesting work']`, mayRequestWork=False | 1 |
| user의 subject가 커널 매핑과 다름 | `refusedBy=['kernel subject mapping','operator grants']` | 1 |
| project가 커널에 연결 안 됨 | `refusedBy=['project linked to kernel']` | 1 |
| operator grant 비활성 | `refusedBy=['operator grants']` | 1 |
| 커널 subject 매핑 비활성 | `refusedBy=['kernel subject mapping']` | 1 |
| 제공 폴더 revoked | `absent=['contributed folders (active)']` | 1 |
| **권한 전부 정상 + kill switch ON** | `refusedBy=[]`, `mayRequestWork=True`, `admission.closed=['kill switch', …]`, `wouldAdmit=False` | 0 |
| Node heartbeat 정지 | `admission.closed=['a live node on the current epoch']`, 권한은 무결 | 0 |
| 기록 제공량 2000 ≠ 커널 제공량 1800 | `disagreeing=[(2000,1800)]` | 1 |

**카드가 요구한 구분의 증거는 8번째 줄이다.** 이 사람의 권한에는 아무 문제가 없고, 어떤 권한을 더 줘도 이 거부는 열리지 않는다. 두 가지를 한 숫자로 보고하면 운영자는 오후 내내 엉뚱한 문제를 고치게 된다. 그래서 닫힌 gate는 권한 실패로 세지 않고 exit 0으로 둔다 — 실행은 불가하지만 **권한 준비는 끝났다**는 것이 사실이기 때문이다.

시험이 실제로 실패를 잡는지 확인했다: 역할과 소속을 다시 합쳐 놓자 해당 시험만 실패했다(9 passed, 1 failed). 되돌리면 10 passed.

## 이 과정에서 찾은 것

1. **내 도구의 결함(고침)**: 첫 판은 "project 구성원인가"만 보고 `viewer`를 정상이라고 보고했다(exit 0인데 `mayRequestWork=False`). 소속과 역량은 해결 방법이 다른 별개의 실패다 — 전자는 "project에 추가", 후자는 "역할 변경". 계층을 둘로 나눴다.
2. **내가 거의 넣을 뻔한 "통과만 가능한 검사"**: `downgrade_target` 뒤에 되돌릴 수 없는 revision이 없다는 단언을 넣었는데, 그 함수가 정의상 *마지막* 되돌릴 수 없는 revision을 돌려주므로 뒤는 언제나 비어 있다. 절대 실패할 수 없는 검사였다. 역방향 독립 스캔과 비교하도록 바꾸고, 함수가 *처음* 것을 돌려주게 변조해 실패를 확인했다.
3. **운영 위험 하나**: `inv.operator_grants`는 subject로 keying돼 있어서, 사람의 OIDC subject를 재발급하면 operator grant가 조용히 고아가 된다. 위 3번째 줄에서 두 계층이 함께 거부되는 이유이며, 한쪽만 고치면 그 사람은 계속 거부된다. 도구가 둘 다 보고한다.
4. **신원 행은 불변이다**: `inv.business_subjects`와 `inv.operator_grants`는 trigger로 수정·삭제가 막혀 있다("disable instead"). 설계대로이며, 운영 절차는 비활성화를 써야 한다. 시험도 그렇게 한다.

## 선행 시험 결함 수정 (검토 중 발견)

`tests/core/test_workspace_api_boundary.py::test_integrated_migration_keeps_both_published_histories`가 `dee31e5`에서 이미 깨져 있었다(내 변경 이전임을 stash로 확인). 원인은 이 저장소에서 **여섯 번째·일곱 번째** 하드코딩된 revision 목록이다.

- `ordered[-1].revision == "0027_business_api_guards"` — migration이 추가되는 순간 깨진다. head를 그래프에서 유도하도록 바꿨다.
- `downgrade_target(revisions) == "0027_business_api_guards"` — head와 우연히 같았을 뿐 별개 개념이다(가장 최근의 되돌릴 수 없는/merge revision). 독립 역방향 스캔과 비교하도록 바꿨다.
- unmerged 경우를 만들려고 0019~0027을 이름으로 제거하고 있었다. 0028 이후가 생기자 남은 revision의 부모가 사라져 `unknown revision parent`가 나면서 **unmerged 경우 자체가 더 이상 시험되지 않고 있었다.** 첫 merge 직전에서 그래프를 자르도록 유도해 고쳤다.

수정 후 3 passed. 각 수정이 실패를 잡는지 확인했다: `chain()`의 unmerged 거부를 없애면 실패, `downgrade_target`이 첫 번째를 돌려주게 하면 실패.

## 없는 운영 입력 (명시)

카드가 "없는 운영 입력은 명시하고"를 요구하므로, 지어내지 않고 그대로 적는다. 아래는 **내가 만들 수 없고 실제 운영자·기계가 공급해야 하는 것**이다.

| 입력 | 담당 | 현재 |
|---|---|---|
| 실제 OIDC issuer와 사용자 계정 | 운영자 | 없음. 검증은 `sha256(issuer, sub)` 규칙대로 만든 subject로 했다 |
| 원격 PC(.225)의 실행 profile 설치 | 원격 PC 운영자, Codex 확인 | 미설치. 관측만 가능 |
| 실제 제공 폴더 경로와 소유자 동의 | Node 소유자 | 없음. 검증은 대표 경로 1개로 했다 |
| object 저장소 endpoint | Codex (S01) | `INV_OBJECT_STORE_ENDPOINT`가 `S01_PENDING` |

이 입력들이 들어오기 전까지 "운영 로그인이 동작한다"고 말하지 않는다. 지금 말할 수 있는 것은 **입력이 갖춰졌을 때 무엇이 통과하고 무엇이 거부되는지가 재현 가능하게 고정됐다**는 것이다.

## 남은 것과 다음 첫 행동

- 실제 운영자 계정·폴더·원격 profile이 들어오면 같은 도구를 운영 DB에 그대로 돌려 인수 증거로 삼는다. 담당 Claude, 입력은 운영자·Codex.
- 브라우저에서의 실제 로그인 여정은 Gemini 영역이며 이 보고의 범위가 아니다. 이 도구는 DB 사실만 말한다.
- CI는 세 Agent 공통으로 계정 결제·한도 문제로 차단돼 있다. 위는 전부 로컬 실측이다.
