---
doc_id: "HIST-CODEX-S11-LOCAL-RETENTION-JOURNAL-001"
title: "S11-ST Local 저장 실패 변환과 PITR retention durable journal 구현"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T18:43:16+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b1df022603852b7fc3762b118eef5587ae60667f"
implementation_sha: "3178edc8ca65f989bf80852cd6776803fe2a2991"
task_ids: ["S11-ST"]
tags: ["S11-ST", "object-store", "retention", "journal", "fail-closed"]
---

# S11-ST Local 저장 실패 변환과 PITR retention durable journal 구현

## 1. 범위와 결과

승인된 PR #185 설계 §8-4 중 공개 계약이나 migration을 바꾸지 않는 두 경계를 PR #198에 구현했다.

- Local object provider의 host `OSError`를 기존 `STORE-0001`/503/retryable로 변환하되 경로와 errno는 공개하지 않는다.
- PITR retention apply를 durable receipt/journal로 제어해 중단 뒤 재개하고 이미 끝난 삭제를 반복하지 않으며 다음 retention 주기는 완료 receipt를 보관한 뒤 새 journal로 시작한다.

공개 JSON Schema, HTTP route, ProblemDetails code와 DB migration 변화는 없다. 운영 artifact는 journal schema `inv.pitr-retention-apply-receipt.v2`, failure class `RETENTION_APPLY_PARTIAL`, partial exit 4, stale journal을 명시적으로 보관·재계획하는 `--abandon-journal`이다.

## 2. 구현 불변식

### 2.1 Local provider

`LocalObjects`의 open/fstat/flock/close 실패만 provider outage로 변환한다. lock 내부 consumer body 전체를 감싸지 않으므로 workspace/generation 쪽의 unrelated `OSError`를 storage outage로 오분류하지 않는다. 실제 object call 변환은 `_LegacyObjectSession`의 put/get/exists/hash/delete에 한정했고, put/delete의 `FileNotFoundError`도 provider mutation 실패로 닫았다. get/hash의 missing-object 의미는 유지한다. `ResultView`도 더 이상 `provider.legacy.locked()`를 직접 열지 않고 canonical `object_store_session(provider)`를 사용하므로 Local read EIO가 raw 500으로 새지 않고 `STORE-0001`/503/retryable로 닫힌다.

### 2.2 retention apply

active journal은 temp write → file fsync → atomic replace → parent directory fsync 순서로 쓴다. 각 삭제 후보마다 다음 순서를 반복한다.

1. 디스크에서 현재 plan과 retained label을 다시 읽는다.
2. pending·존재 target이 현재 delete set에 있는지 확인한다. retained/unknown-age backup 또는 boundary 이후 WAL은 거부한다.
3. root identity, candidate identity(device+inode), 살아 있는 backup label digest를 다시 확인한다. directory ctime은 자식 삭제나 권한 복구로 정상 변경되므로 identity에 쓰지 않는다.
4. backup rmtree 직전에 plan hash·후보 이름·device+inode·원 label digest에 결속된 외부 removal marker를 같은 directory의 고유 temp에 write·file fsync한 뒤 atomic replace·backups directory fsync로 발행한다. 최종 이름에는 완전한 본문만 보이며 replace 이전 hard interruption이 남긴 temp는 authoritative marker가 아니다. label이 이미 지워진 partial은 marker가 정확할 때만 재개하며, journal만 자기 일관적으로 위조해 label 없는 directory를 넣어도 거부한다.
5. unlink/rmtree 뒤 후보 부모 디렉터리를 fsync하고 marker를 제거·fsync한다. 그 다음에만 target을 removed로 바꾸고 journal을 다시 durable write한다.

`running`·`partial`만 resume 대상이다. 새 backup 등으로 boundary가 바뀌어 정상 재개가 거부될 때만 운영자가 `--apply --abandon-journal`을 명시한다. 이 경로는 기존 receipt를 `<stem>.abandoned-<planSha256>-<unique>.json`으로 보관하고 검증된 marker를 정리한 뒤 현재 디스크에서 새 plan을 만들며, partial residue를 추측 삭제하지 않는다. `completed` active receipt는 `<stem>.completed-<planSha256>-<unique>.json`으로 보관한 뒤 새 disk-derived journal을 만든다. 자세한 운영 절차는 [[VF-CL-04 replica 복구와 PITR 운영 runbook]] §4에 기록했다.

## 3. 독립 검토 반영

초기 head `e1cbf9a9`에 대한 Claude 검토는 E1~E5를 찾았다. 기존 #150 시험과 hand-made plan 재사용의 모순, 자기 일관적으로 바꾼 journal의 retained target 삭제, completed journal의 일회용화, session 변환 범위와 시험 공백, 삭제 parent fsync 누락이다. `b0d1eeac`에서 모두 수정했고 `93d7a656`에서 실제 Linux `object_store_session(LocalObjects)` put/read/remove 회귀 3건을 추가했다.

hosted Backend run `36396672596`은 Linux가 삭제 직후 같은 경로에 inode를 재사용하는 반례를 양 matrix에서 각각 1건 검출했다. `1c85bd3e`에서 candidate identity에 ctimeNs를 결속했지만, Claude r2는 directory ctime이 partial rmtree와 권한 복구 때도 바뀌어 C2~C4 재개를 영구 거부하는 N1을 찾았다. 같은 검토에서 stale partial이 새 backup 이후 영구 고착되는 N2, `result_view` 직접 legacy read의 raw EIO N3, label 없는 forged journal target N4, Local init/flock 시험 공백 N5도 확인했다.

head `9cbade0e`는 N1~N5를 모두 반영한다. ctime 결속 대신 외부 marker를 rmtree 전에 durable하게 기록하고, 교체-directory 시험은 원 inode를 다른 경로에 살아 있게 둬 실제 identity 차이를 보장한다. stale journal은 명시적 abandon만 허용하며 receipt는 삭제하지 않고 archive한다. result view는 canonical session으로 통일했고 Linux open/flock 및 C2(caught EIO)·C3(label 삭제 뒤 hard interrupt)·C4(chmod/ctime 변화) 회귀를 추가했다. force-push는 사용하지 않았다.

Claude r3는 N1·N3·N4·N5 해소를 확인하고, marker 최종 이름에 직접 쓰던 구간의 torn-file P1과 운영 문서 C1을 병합 조건으로 남겼다. `c3305491`은 marker를 temp → file fsync → atomic replace → directory fsync로 바꿨고, 최종 `3178edc8` 시험은 replace 직전 hard interruption에서 orphan temp를 의도적으로 남겨도 최종 marker는 없으며 다음 실행이 새 고유 temp로 완료됨을 고정한다. runbook은 abandon·marker·label-less residue·v1 fail-closed·동시 apply 금지를 명문화했다. 두 commit 모두 일반 push이며 force-push는 없었다.

Claude r4는 head `3178edc8`에서 C1~C3 해소와 전체 hosted green을 대조해 승인했다(issuecomment `5867407803`). self-close하지 않으며 #173 뒤 retarget·병합은 코디네이터 담당이다.

## 4. 검증

### 4.1 로컬 Windows / Python 3.14

| 명령 | 결과 |
|---|---|
| `pytest tests/test_pitr_archive_retention.py -q` | 37 passed, exit 0 |
| `pytest tests/test_s11_local_retention_faults.py -q` | 32 passed / 12 Linux-only skipped / 0 failed, exit 0 |
| `pytest tests/core/test_artifact_content_contract.py -q` | 18 passed / 0 failed, exit 0 |
| `pytest tests/test_route_coverage.py -q` | 40 passed, exit 0 |
| `black --check` 대상 4파일 | exit 0 |
| `py_compile` 대상 4파일 | exit 0 |
| `git diff --check` | exit 0 |
| `python tools/check_docs.py` | exit 0 |
| `python tools/check_contract_bindings.py` | exit 0, fixture 55·response type 20·anchor site 26·replay guard 14 |
| `python tools/check_frontend_integrity.py` | exit 0, 9 rules / 0 violations |
| `python tools/check_ontology.py` | exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | exit 0 |
| `python tools/check_response_freshness.py` | advisory 10/10 |
| `python tools/sync_obsidian.py --check` | exit 3, 기존 공유 충돌 4건(`both-diverged` 3·`destination-edited` 1), vault write 0; 코디네이터 정본 sync 대상으로 인계 |

### 4.2 hosted

- Backend run `36397909988`, superseded head `1c85bd3e`: success. Python 3.12와 3.14가 각각 3164 passed / 47 declared skipped / 2 deselected / 0 failed였고 exact skip-map gate도 통과했다.
- 최신 Backend run `36402267753`, head `3178edc8`: success. Python 3.12와 3.14가 각각 3174 passed / 47 declared skipped / 2 deselected / 0 failed였고 exact skip-map gate도 통과했다. Linux-only C2~C4·Local open/flock·result-view session 회귀와 신규 marker interruption 회귀가 skip 증가 없이 실행됐다.
- 최신 Core run `36402267783`, head `3178edc8`: success. main 3479 passed / 17 declared skipped / 2 deselected / 0 failed, LAN installer 15 passed, CX01 recovery 18 passed / 2 declared internal-network skips, Docker host 2 passed / 0 skipped다. exact skip-map, Python build, Go, TypeScript, cleanup과 S01 storage roundtrip가 모두 통과했다.
- 최신 Docs run `36402267780`와 Desktop Browser run `36402267735`: success.

모든 hosted 합계는 run 종료 뒤 기록했다. skip은 통과에 합산하지 않았다.

## 5. 정직한 경계와 인계

- Windows 로컬에서는 Linux open/flock·file/directory fsync·partial rmtree 12건을 skip했다. 합격 증거는 hosted Linux 실행 결과다.
- 실제 disk-full, quota, 전원 차단, 운영 WAL archive와 물리 PITR restore는 실행하지 않았다. 이 결과는 코드와 hosted filesystem seam 검증이지 운영 복구 인수가 아니다.
- journal은 이상·unknown field·현재 policy drift를 fail-closed하지만, 관리자에 대한 암호학적 tamper-proof 저장소는 아니다.
- PR #193과 함께 병합할 때 그 producer의 Local `osError` 기대 수와 BAK-02 residue 판정을 제품 표면에 맞춰 갱신해야 한다.
- Claude 독립 재검토 r4는 승인이다. 다음 담당은 코디네이터로, #173 뒤 retarget·병합 순서를 지키고 #193과 뒤에 병합되는 쪽에서 BAK-02 fixture/plan/`RetentionApplyPartial`·Linux osError 기대 수를 갱신한다. Codex는 self-close나 병합을 하지 않는다.
- 비차단 후속은 abandon 뒤 label 없는 residue를 CLI에 표시(P2), 단일 writer lock(P3), completed/no-journal abandon 및 marker identity 결속 변이 M17·M19·M20(P4), 삭제별 재계획 이차 비용, v1 journal 자동 재개·abandon 부재다.
