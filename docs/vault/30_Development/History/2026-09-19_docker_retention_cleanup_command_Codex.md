# Docker 보존 자원 정리 명령과 ckd-hyg 정리 보강

- 기준: `8b7ddc4`
- 구현: `tools/cleanup_owned_docker.py`
- 후속 tip: 이 문서와 코드 반영 후
- 실행: `.venv\Scripts\python.exe tools/cleanup_owned_docker.py --min-age-minutes 30`
- 삭제 플래그 없음; 실제 삭제 0건

## 명령 계약

- 기본은 JSON inventory만 출력한다. `--delete` 없이는 삭제하지 않는다.
- 알려진 소유 라벨(`acceptance`, `bridge-test`, `developer-studio`, `kernel-test`, `remote-test`, `test`, `upgrade-test`)이 없으면 보존한다.
- `saintvision-lan-db*`, `saintview-orthanc*` 접두사는 코드 수준 보호 목록이다.
- 기본 30분 age gate를 통과한 정지 컨테이너, 무연결 네트워크, 라벨 볼륨만 후보가 된다.
- 삭제 시 컨테이너/볼륨/네트워크별로 제거 후 inspect를 다시 수행하고, 미확인 제거는 `retained`로 기록한다.
- 출력은 `removed`와 `retained`로 나뉘며 보존 사유를 포함한다.

## 이번 inventory

라벨·생성 시각을 확인한 결과 eligible 후보는 42개였지만 모두 `deletion requires --delete`로 보존됐다. 보호 대상은 `saintvision-lan-db-bff1a31d`, `saintview-orthanc`, `saintview-orthanc-h1`, `saintview-orthanc-h2`로 별도 표시됐다. 현재 사용 중인 `svcx01-pgaudit-*`도 소유 라벨이 없어 보존됐다. `sv-bridge-unit-*` 두 개는 `ai.saintvision.bridge-test` 라벨과 Created 상태를 확인했지만 삭제하지 않았다.

후속 독립 검토에서 볼륨 누락을 발견해 수정했다. `docker volume ls -a -q`를 `docker volume ls -q`로 바꾸고, volume inspect의 `CreatedAt`을 읽도록 했다. 종류별 inventory 실패는 `unverified`에 기록한다. 수정 후 나열 결과는 `container=4, network=11, volume=84`, `unverified=0`이며 삭제는 0건이다. evidence 보존 라벨(`acceptance`, `developer-studio`, `remote-test`, `upgrade-test`)은 14일 기준을 적용하고 보고서에 `intentional evidence retention`을 표시한다.

## ckd-hyg 정리

`tests/test_check_kernel_docker_hygiene.py`의 finally를 공용 `tests/vf_docker.py::cleanup_owned`로 전환했다. 이제 probe 컨테이너는 소유 라벨을 확인하고 제거 후 inspect를 재확인한다. 공용 helper 회귀시험은 `7 passed`다.

저장소에 없는 임시 코드가 만든 `sv-bridge-unit-*`는 생성자와 커밋 provenance를 찾을 수 없는 orphan resource로 기록한다. 다음 삭제는 Claude Docker 작업 종료 후 동일 명령의 `--delete`를 명시적으로 실행할 때만 수행한다.

## Encoding-damaged audit notes — corrected record (2026-09-19)

The preceding appended inventory/deletion notes in this file were written with damaged character encoding and are not reliable as readable evidence. This section replaces those additions; the earlier committed bytes remain available in Git history and are not treated as verified here.

- Source correction: container enumeration requires docker container ls -a -q; volume and network listing use their respective ls -q commands. The earlier shared-argument implementation omitted or misplaced -a and could silently produce incomplete inventories.
- Self-check correction: compare each enumerated count with an independent Docker Engine API count, not a second form of the same ls command. If a kind differs, report it as unverified, exclude it from deletion, and abort --delete.
- Verification recorded by the operator: inventory was container 53/53, volume 85/85, network 11/11; symmetric removal of -a from both container commands was detected as enumerated=3 versus independent=53 and --delete aborted with zero removals. The test/reversal result was 12 passed, as reported in the same-day independent review.
- Authorized cleanup evidence: 5 containers and 6 named volumes were removed and individually confirmed absent. Counts changed from container 53, volume 85, network 11 to 48, 79, 11. Protected saintvision-lan-db* and saintview-orthanc* resources remained present. The 69 anonymous volumes were untouched.
- Upstream prevention evidence: the Docker-run audit found implicit PostgreSQL volume creation paths; affected launchers now use tmpfs or explicit named volumes with ownership labels. The dedicated regression set reported 14 passed.
- Anonymous-volume snapshot: 69 Docker-generated 64-hex volumes, 3 attached and 66 unattached at measurement time. docker volume inspect provided CreatedAt; container inspect provided image and mount linkage. Storage was about 3.7 GiB: Codex's sum of rounded per-volume docker system df -v SIZE fields was 3.843 GiB, while the user's independent docker system df -v measurement was about 3.665 GiB. Keep the two method-specific results distinct.
- User decision is complete: preserve all 69; do not delete or re-propose cleanup unless the user explicitly changes the decision. The evidence and rationale are in the following section.

Evidence provenance: the command outcomes above are same-day records from the Codex/operator and independent review; this correction reconciles their intended content, it does not claim a fresh Docker run during the audit-of-audit.

## User decision: preserve anonymous volumes

On 2026-09-19 the user decided to preserve the 69 existing anonymous Docker volumes. This is a completed decision, not a pending decision. Do not nominate them for cleanup or delete them unless the user explicitly changes the instruction. Rationale: upstream launchers now avoid creating new anonymous volumes; approximately 3.7 GiB does not require urgent reclamation; ownership is unprovable and deletion is irreversible. `cleanup_owned_docker.py` still excludes them and exposes `anonymousVolumePolicy.status=preserve-by-user-decision`.

Snapshot: 69 volumes with 64-hex Docker-generated names and no ownership labels; UTC creation distribution 2026-09-09: 4, 2026-09-11: 1, 2026-09-14: 9, 2026-09-15: 20, 2026-09-18: 35. Three attached to PostgreSQL data paths: `/saintvision-inv-db`, `/saintvision-core-test-20260909`, `/inv-codex-core-pg`, each image `pgvector/pgvector:pg16`, destination `/var/lib/postgresql/data`; 66 unattached at snapshot.

Measurement provenance: Codex summed individually rounded per-volume `SIZE` values from `docker system df -v` and converted displayed units, yielding 3.843 GiB. User independently reported approximately 3.665 GiB from `docker system df -v`. Preserve both method-specific figures; report approximately 3.7 GiB. Creation distribution is from `docker volume inspect` `CreatedAt`; linkage is from `docker container inspect` mounts and image metadata. No deletion was performed.
