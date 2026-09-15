---
doc_id: "CONTRACT-READROOT-001"
title: "Codex 허용 저장소 파일 검증 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:53:19+09:00"
source_of_truth: "Git"
---

# Codex 허용 저장소 파일 검증 계약

ADR-085 · 구현 6a72b9d37348f73ffbfe4230e7585b8755f203b8. owner Codex / reviewer Claude pending. [[2026-09-12_BACKUP-ROOT_Codex_검증보고]].

## 입력과 정본

`services.verification.hash_file`, `verify_backup_bytes`, `verify_replica_bytes`, `verify_pending_backups`는 신뢰된 worker 설정에서 만든 `storage.readroot.ReadRoot`를 `allowed_root`로 받는다. 누락은 실패이며 이전의 임의 로컬 경로 호출과 의도적으로 호환되지 않는다. HTTP caller/DB location_ref가 자기 path의 parent를 root로 승인해서는 안 된다. root는 operator가 허용한 폴더로 한 번 구성하고 교체 감지 뒤 자동 재승인하지 않는다.

```python
# trusted_config.backup_root는 작업 요청과 별도로 관리하는 운영 설정이다.
root = ReadRoot(trusted_config.backup_root)
observation = hash_file(job_path, allowed_root=root, os_type=worker_os)
```

절대 경로·문법 보호를 유지하고 traversal/encoded alias를 재해석하지 않는다. 정상 파일만 허용하며 symlink/reparse·hardlink·root 아래 다른 device를 거부한다. Linux는 descriptor 기준 상대 open과 NOFOLLOW/NONBLOCK, Windows는 ancestor별 CreateFileW/OPEN_REPARSE_POINT와 READ 공유만 허용한 handle을 끝까지 유지한다. Windows는 local fixed drive만 지원한다. 신뢰된 OS 관리자·mount 재설정 공격을 방어하는 경계는 아니다.

## 실제 bytes와 기록

최초 크기 N에 대해 각 읽기를 최대 N+1 bytes, chunk를 int1~4MiB로 제한한다. 캐시 없는 두 번의 읽기 hash/size가 일치하고 전후 파일 버전·root identity가 유지돼야 반환한다. 일반적인 읽기 비용은 두 배다. Linux에서는 rename된 열린 fd가 남으므로 이름과 inode도 재확인한다. 실패하면 root/원본 OS error 내용을 HTTP 오류에 반사하지 않는다.

이는 두 읽기의 관측 일치이며 불변 파일시스템 snapshot이나 계속 정상인 백업이라는 보장이 아니다. 운영자는 게시 완료·쓰기 중지된 백업을 제공해야 한다. 디스크 자체의 장시간 I/O 정지에 대한 deadline, privileged writer/특수 FS·memory-map 경쟁 전체 보장, 원격 node 소유권 attestation, S3/object store 검증은 범위 밖이다. 이미 기록된 성공과 최근 실패를 연결할 durable 관측 계약도 후속이다.

백업의 tenant 행 잠금·기존 digest 비교·savepoint 규칙(ADR-084)을 유지한다. batch는 하나의 worker 설정 root 아래에서만 검증하며 실패 항목과 성공 항목을 분리한다. 서로 다른 root가 필요하면 각 승인 root별 batch를 구성한다. 복제본 helper는 이 파일 읽기 경계를 전달하지만 별도의 replica tenant 사전 확인/Node 관측 증명까지 이번에 완성했다고 주장하지 않는다. root는 tenant 권한 또는 node identity의 대체물이 아니다.

## Windows 근거와 검증 범위

공유 모드와 reparse open은 [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), fixed drive 판정은 [GetDriveTypeW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypew)를 참고했다. 실제 Windows 로컬 파일/junction/일반 writer 시험과 Linux 파일/symlink/FIFO/빠른 덮어쓰기·성장 시험을 수행했다. 이 공식 API 계약을 모든 파일시스템의 운영 인수 결과로 해석하지 않는다.

다음 Codex 작업은 Claude71cf2c0 storage_check의 자체 `path.open`/resolve_within 경계를 이 정본과 조율하고, caller가 준 `--node`와 실제 실행 기계의 binding을 독립 검토하는 것이다. 기존 도구를 root 인수 없이 합치거나 새 hash 구현을 복제하지 않는다.

