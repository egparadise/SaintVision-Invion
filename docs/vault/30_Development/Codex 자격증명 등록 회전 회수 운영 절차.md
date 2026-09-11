---
doc_id: "CODEX-CREDENTIAL-PROVISION-001"
title: "Codex 자격증명 등록 회전 회수 운영 절차"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:26:09+09:00"
source_of_truth: "Git"
---

# Codex 자격증명 등록 회전 회수 운영 절차

CX-02 / owner Codex, 독립 reviewer Claude pending. ADR-079. 기존 Credential Protocol·LinuxFileCredentials·PostgresCredentialRegistry와0035를 사용한다. 추가 migration·공개 관리 API·두 번째 resolver는 없다. 구현/검증은 [[2026-09-12_CREDENTIAL-PROVISION_Codex_검증보고]].

## 적용 범위와 사전 조건

`tools/provision_credentials.py`는 보호된 운영자 CLI다. DB 연결은 credential_versions table owner 또는 superuser만 허용하며 inv_app/inv_kernel runtime 계정은 변경할 수 없다. 광범위 DB 운영자 권한을 웹/API에 노출하지 않는다. 운영자 역할은 PostgreSQL current_user에서 얻고 manifest의 주장으로 대체하지 않는다.

register/grant/rotate는 실제 backend 서비스와 같은 Linux 파일 공간·UID에서 실행한다. 기존 private root0700, 일반 secret 파일0600·단일 링크·1~65536bytes가 필요하다. 파일 이름은32개 소문자hex + .secret이며 경로 segment symlink, 다른 owner/mode/inode·변경 byte는 기존 descriptor/hash 검사로 거부한다. 이 도구는 secret 파일을 생성·덮어쓰기·삭제하지 않는다. 보호된 자격증명 관리 절차로 미리 만든 파일만 검사한다. secret을 Git/Obsidian/명령행/일반 환경 문자열에 넣지 않는다. DSN은 별도 보호 프로세스 설정의 INV_CREDENTIAL_ADMIN_DSN에서 읽고 다른 변수명은 --dsn-env로 지정한다.

현재 tenant/project/subject/Run과 recovery epoch가 필요하다. 준비·권한 부여는 현재 살아 있는 Run과 enabled/can_request project grant를 확인한다. kill switch가 켜져 있어도 운영자 준비는 가능하지만 backend의 실제 사용은 계속 거부된다. 회수는 Run 종료·project 비활성화·파일 소실 후에도 가능하며 현재 epoch와 존재하는 해당 Run/범위는 확인한다.

## manifest 계약

manifest는 보호 JSON 파일이며 최대32KiB다. 비밀 원문·DSN·파일 hash는 넣지 않는다. 알 수 없는 필드, 누락, 잘못된 형식은 거부한다. UUID는 canonical 소문자 형식, project/Run은 정본26문자 ID, subject는 실제 current project grant의 내부 식별자다. 파일 읽기의 inode/SHA-256 metadata는 CLI가 계산하고 DB 내부에만 기록한다.

| action | 필수 필드 | 결과 |
|---|---|---|
| 모든 action | tenant, project, subject, run, epoch, credential, version | 모두 명시적 scope, 자동 선택 없음 |
| register 추가 | file, purpose, destination | immutable version만 등록, 사용 권한 없음 |
| grant 추가 | expires | 등록된 버전에 해당 subject/Run 권한 부여 |
| revoke 추가 | 없음 | 해당 버전의 subject/Run 권한 회수, 파일은 열지 않음 |
| rotate 추가 | file, purpose, destination, expires, oldVersion | 새 immutable version 등록 + 같은 scope old grant 회수 + new grant 부여를 원자 처리 |

purpose는 ADR-077의 llm.invoke, git.read/publish, storage.read/write/gc, backup.write/restore 중 하나다. destination은 서버가 관리하는 소문자 alias이며 URL/토큰이 아니다. expires는 timezone을 포함한 ISO8601 시각이며 DB 시각 기준 미래여야 한다. rotate는 oldVersion과 다른 version/file을 준비하고 이전 버전과 purpose/destination이 같아야 한다.

## 실행 순서

다음 경로는 배포 예시이며 실제 운영 설정은 아직 등록하지 않았다. 현재 DB 입력과 service-owned 파일을 확인하여 보호 manifest를 먼저 준비한다. 프로세스의 DSN 보호 설정을 통해 연결하고 manifest에 DB 연결 문자열을 넣지 않는다.

```sh
python tools/provision_credentials.py register --root /srv/saintvision/credentials --manifest /srv/saintvision/operator/register.json --check
python tools/provision_credentials.py register --root /srv/saintvision/credentials --manifest /srv/saintvision/operator/register.json --apply
python tools/provision_credentials.py grant --root /srv/saintvision/credentials --manifest /srv/saintvision/operator/grant.json --check
python tools/provision_credentials.py grant --root /srv/saintvision/credentials --manifest /srv/saintvision/operator/grant.json --apply
```

기본은 --check다. DB 행/감사 기록은 쓰지 않고 조회·검증·단기 행 잠금 후 종료한다. 사전 검사는 이후 상태를 예약하지 않으므로 --apply 때 모두 재검사한다. 출력 status는 checked/applied/unchanged이며 reference와 executionAuthorized=false만 제공한다. exit0은 해당 관리 동작 결과이지 실행 승인/Provider 호출 성공이 아니다. 인자·DB·파일·manifest 실패는 비밀 없는 고정 오류와 exit2이며 성공처럼 처리하지 않는다.

rotate/revoke도 같은 형식으로 해당 action용 manifest에 --check 후 --apply를 사용한다. root는 CLI 공통 인자지만 revoke는 파일을 읽거나 변경하지 않는다. 실제 외부 Provider의 원래 token 자체를 폐기하는 기능은 아니다.

## 회전·재시도·복구의 불변 조건

동일 version은 metadata가 완전히 같을 때만 재사용한다. 다른 파일/inode/hash로 바꾸려면 새 version을 사용한다. grant의 enabled/revoked/expiry/epoch가 달라지면 이전 manifest 재시도로 되살리지 않는다. 특히 expires를 다시 계산하여 자동 연장하지 않는다. 불확실한 commit 응답은 같은 고정 manifest로 재시도한다.

rotate는 지정 subject/Run 하나의 권한만 바꾼다. 다른 Run에 남은 old version 권한은 자동 회수하지 않으므로 운영자는 전체 사용 범위를 별도로 추적해야 한다. 이미 회수/만료/old-epoch인 predecessor로 새 권한을 만들지 않는다. 이미 완료된 회전의 정확한 재시도만 허용한다. 두 회전이 같은 old grant를 경쟁하면 하나만 새 권한을 만들 수 있다.

current epoch→tenant control→Run→project grant/credential grant 순서로 잠그고 한 DB transaction에서 version/grant와 inv.credential.register/grant/revoke/rotate 감사 event를 commit한다. audit 실패 시 모두 rollback한다. runtime writer 권한은 추가하지 않는다. 감사에는 credential/version/subject/DB 운영자 role과 회전 oldVersion만 남기며 secret/file path/hash/DSN은 남기지 않는다.

복원으로 epoch가 달라지면 사용은 계속 거부된다. 현재 epoch·scope를 확인하고 새 version의 명시적 register/grant를 수행한다. 오래된 grant를 자동 갱신하지 않는다. root/volume 복원으로 inode가 달라져도 old reference가 새 파일로 자동 재지정되지 않는다. 키 삭제·옛 파일 GC·서비스 배포/Provider 연결·독립 승인·운영 인수는 별도다.
