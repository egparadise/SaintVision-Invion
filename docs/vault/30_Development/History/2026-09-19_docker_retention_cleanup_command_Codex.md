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
