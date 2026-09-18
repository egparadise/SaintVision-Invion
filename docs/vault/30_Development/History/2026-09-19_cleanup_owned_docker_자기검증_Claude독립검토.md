---
doc_id: "REVIEW-CLEANUP-OWNED-DOCKER-SELFVERIFY-CLAUDE-001"
title: "cleanup_owned_docker.py 자기검증 수정(3f0cfef) 독립 검토 — 소스+실행. 값 미기록"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-20T08:30:00+09:00"
target_commit: "3f0cfef"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "docker", "cleanup", "delete-safety", "no-values"]
---

# cleanup_owned_docker.py 자기검증 수정 독립 검토

Codex가 오늘 만든 `tools/cleanup_owned_docker.py`(Docker 자원을 실제 삭제할 수 있는 도구)의 자기검증 추가 커밋 `3f0cfef "fix docker inventory completeness checks"`를 독립 검토했다. 이 도구는 두 번 같은 형태로 깨졌다(① `docker volume ls -a` 무효 플래그로 볼륨 0개 ② 그 수정 중 세 종류에서 `-a`를 모두 빼 컨테이너를 실행 중 3개만). 삭제 기능이라 두 번째 눈이 필요해, **소스를 읽는 데 그치지 않고 53-컨테이너 호스트에서 나열 모드를 실제로 돌리고, 내 소유 일회용 자원으로 삭제 경로를 격리 검증**했다(통합 tip `origin/integration`의 실제 커밋 기준). 값은 옮기지 않고 경로·성격·짧은 해시만 기록한다.

## 종합 판정
**위험 삭제(보호/무라벨 자원 삭제)에는 안전 — 실행으로 확인.** 그러나 **자기검증(count 대조)은 그것이 막으려던 완결성 버그류에 대해 사실상 공허하다.** 재발한 두 번째 버그(균일하게 틀린 플래그)를 잡지 못한다. 위험은 없으나(최악은 under-cleanup) 완결성 보장은 거짓 안심이다. → 진짜 독립 소스로 대체 권고.

## 검토 항목별 (실행 증거 포함)

### 1. 자기검증이 실제 불일치를 잡는가 — **아니오, 공허(주 finding)**
`_resources()`는 종류별로 두 명령을 돌려 개수를 비교한다: `list_args`(예 `docker container ls -a -q`)와 `count_args`(예 `docker container ls -a --format {{.ID}}`). **둘 다 같은 `ls`의 같은 플래그**이고 출력 포맷만 다르다 → 개수는 (레이스 없는 한) 항상 같다. 실행 대조:
- `docker container ls -q`(running-only) = **3**, `docker container ls -a -q`(all) = **53**, `docker info --format {{.Containers}}`(진짜 독립) = **53**.
- 도구 출력 `inventoryCounts.container = {enumerated:53, independent:53}` — 양쪽 다 `-a`라 일치.
- **핵심**: 만약 코드가 `-a`를 (다시) 빠뜨리면 `list_args`·`count_args` 둘 다 3을 반환→ 일치→ "verified"로 통과하며 50개를 놓친다. 즉 **두 번 실제로 난 버그(균일 플래그 오류)를 이 검증은 구조적으로 못 잡는다.** 잡는 것은 두 호출 사이의 레이스(자원 추가/삭제)뿐이다. 볼륨·네트워크도 동일(둘 다 `ls`의 포맷 변형).
- **권고**: 개수 대조를 **진짜 독립 소스**로. 컨테이너는 `docker info --format {{.Containers}}`(데몬 집계, ls 플래그와 무관)를 열거 개수와 대조하면 `-a` 누락을 실제로 잡는다. 볼륨/네트워크는 `docker system df -v` 등 다른 경로. (참고: 무효 플래그로 **에러**가 나는 ①형은 이미 returncode 검사가 잡는다. 못 잡는 것은 **성공하지만 불완전**한 ②형이다.)

### 2. 보호 접두가 코드 수준에서 확실히 제외되는가 — **예 (실행 확인)**
`_eligible` 첫 검사(L82) `if resource["name"].startswith(PROTECTED_PREFIXES): return False, "protected project prefix"`. `PROTECTED_PREFIXES=("saintvision-lan-db","saintview-orthanc")`. 나열 모드에서 **5건이 "protected project prefix" 사유로 retained**: `saintvision-lan-db-bff1a31d`, `saintview-orthanc`, `saintview-orthanc-h1`, `saintview-orthanc-h2`(컨테이너), `saintvision-lan-db-bff1a31d-data`(볼륨). 단위 확인: **인정 라벨(`ai.saintvision.test`)을 붙인 보호 이름도** `_eligible`=(False,"protected project prefix") — 보호 검사가 소유 검사보다 **먼저**라 **보호가 라벨보다 우선**. 다른 프로젝트 운영 자원은 어떤 경로로도 삭제 대상이 될 수 없음을 실행으로 입증.

### 3. 소유 라벨 없는 자원이 안 건드려지는가 — **예 (실행 확인)**
`_eligible` L84 `if not resource["owner"]: return False, "ownership label absent"`. `owner`는 7개 `OWNERSHIP_LABELS` 중 하나가 있어야 설정. 나열 모드: **91건이 "ownership label absent"로 retained**, eligible 집합(11건)에 **무라벨·보호 혼입 0**. 단위 확인도 무라벨→(False,"ownership label absent").

### 4. 나이 기준 vs 의도적 보존이 겹칠 때 — **보존이 이긴다 (실행 확인)**
L88 `threshold = max(minimum_age, policy_age)`. `policy_age`는 evidence-retention 라벨(acceptance/developer-studio/remote/upgrade)에 14일. **더 긴 쪽(보수적=보존)이 이긴다.** 나열 모드에서 **42건이 "intentional evidence retention"으로 preserved** — 이 경로가 실제로 실행됨. `--min-age-minutes`를 키워도 `max()` 때문에 정책이 지키려는 자원을 더 일찍 지우지 못한다(항상 정책 하한 유지).

### 5. 삭제 경로가 실수로 실행되기 쉬운가 / 실제 동작 — **구조 안전, 경로 동작 확인**
- 기본은 list(읽기전용), `--delete` 필수. `--delete`+`unavailable` 비어있지 않으면 `deleteAborted`·`return 2`(L141-144).
- **잔여 위험(2와 연결)**: abort는 `unavailable`이 채워질 때만 발동하는데, 균일 플래그 버그면 count가 일치→`unavailable` 비어→abort 안 됨→불완전 인벤토리로 `--delete` 진행. **단 이때도 위험 삭제는 없다** — 보호/무라벨/running 게이트가 열거된 자원마다 개별 실행되므로 불완전 인벤토리의 결과는 **under-deletion(일부 누락, 안전)**이지 보호·무라벨 삭제가 아니다. 즉 공허한 자기검증조차 위험-삭제 경로를 열지 않는다(최악은 청소 누락).
- **삭제 경로 격리 검증(내 자원만)**: 인정 라벨 `ai.saintvision.test`의 일회용 볼륨을 만들고 도구의 `_eligible`→True, `_remove`→`confirmed-removed`(재-inspect로 제거 확인). 전역 `--delete`는 **쓰지 않았다** — 이 호스트의 eligible 11건은 **타 에이전트의 test 자원**(sv-server-test/sv-bridge-unit/ckd-hyg)이라 전역 삭제는 "내가 만든 것만" 원칙 위반이기 때문. 함수 단위로 내 자원에만 실제 삭제를 태워 경로가 의도대로 동작함을 확인했고, 끝나고 내 볼륨만 제거·보호 컨테이너 4건 미접촉 확인.

## 권고 (Codex)
1. **(주)** 자기검증 count의 `count_args`를 같은 `ls`의 포맷 변형이 아니라 **진짜 독립 소스**(컨테이너: `docker info .Containers`)로. 그래야 재발한 `-a` 누락형(성공하지만 불완전)을 실제로 잡고 `--delete`를 중단시킨다. 현재는 레이스만 잡는다.
2. 나머지(보호 접두 우선·무라벨 제외·보존 우선·삭제 경로·abort)는 실행으로 안전 확인 — 변경 불필요.
Claude는 검토·실행 검증까지. 도구 자체는 소유가 Codex라 코드 수정은 인계.
