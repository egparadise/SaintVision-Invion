# Docker 잔여 provenance·cleanup 감사

- 기준: `bb2b6f1`
- 범위: 종료/Created 컨테이너와 라벨, 생성 도구의 finally/cleanup 경로
- 실행: `docker ps -a`, `docker volume ls`, `rg` 정적 대조
- 원칙: 이번 감사에서는 삭제하지 않음. Claude가 Docker를 사용하는 동안 보호 대상과 타 Agent 자원을 보존

## 접두사별 판정

| 접두사 | 생성 경로 | 정리 판정 |
|---|---|---|
| `ckd-hyg-*` | `tests/test_check_kernel_docker_hygiene.py` | 테스트 finally가 `docker rm -f`를 호출하지만 return code와 제거 후 inspect를 확인하지 않는다. 소유 라벨은 고정되어 있으나 정리 증거가 약한 P2 후보. |
| `sv-server-test-*` | `tests/integration/test_server_container.py` | `tests/vf_docker.py::cleanup_owned`로 컨테이너·볼륨을 독립 처리한다. 이번 감사에서 제거 누락을 새로 확정하지 않았다. 제거 후 inspect 확인을 공통 helper에 추가했다. |
| `sv-remote-workspace-*` | `tools/check_remote_workspace.py` | 완료된 경우에도 컨테이너를 stop만 하고 remove/network/volume 정리를 하지 않는다. 실패·불완료는 조사 보존을 의도한다. 7일 된 runner/db/node와 volume 잔여, 컨테이너 없는 node-state volume은 이 정책의 운영 잔여 후보다. 자동 삭제 결함으로 단정하지 않고 P2 운영 retention 후보로 기록한다. |
| `sv-workspace-upgrade-*` | `tools/check_workspace_upgrade.py` | stopped test runner를 evidence 검토용으로 보존한다고 명시한다. finally는 stop만 수행한다. 의도된 retention이므로 즉시 삭제하지 않고 보존 기간/정리 명령이 필요한 P2 후보다. |
| `saintvision-compat-*` | `tools/check_node_docker_compat.py` | stopped runner와 evidence를 검토용으로 보존한다고 명시한다. 예외 전용 cleanup이 아니므로 retention 정책 후보다. |
| `sv-bridge-unit-*` | 현재 작업 트리에서 생성 코드 미발견 | `ai.saintvision.bridge-test` 라벨과 Created 상태만 확인했다. 생성 소스·owner 미확정, 정리하지 않음. |

보호 대상 `saintvision-lan-db*`, `saintview-orthanc*`, 현재 사용 중인 `svcx01-pgaudit-*`는 보존했다.

## 공통 결론

이번 잔여의 다수는 예외 경로가 정리를 건너뛴 숨은 누수라기보다 `--keep`/조사 보존 정책이 무기한 retention으로 남은 경우다. 반면 테스트 helper의 rm 성공을 제거 증거로 사용한 문제는 확인되어 `cleanup_owned`가 제거 후 inspect를 수행하고 미확인 상태를 기록하도록 보강했다.

실제 삭제는 owner와 생성 run을 재확인하고 Claude Docker 작업이 끝난 뒤 별도 승인 범위에서 수행한다. 이번 감사에서는 어떤 컨테이너·볼륨·네트워크도 삭제하지 않았다.
