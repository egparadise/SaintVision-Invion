---
doc_id: "HISTORY-CARD209-IDP-FRESH-AUTH-LIVE-READBACK-20261002"
title: "Card 209 사내망 Keycloak fresh-auth mapper 적용과 read-back"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T06:45:07+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d0b2a4c6b05674a7d8d0ca011f080f580a873b06"
tags: ["card-209", "keycloak", "fresh-auth", "intranet", "evidence"]
---

# Card 209 사내망 Keycloak fresh-auth mapper 적용과 read-back

## 결론

사내망 IdP의 live realm에 `auth_time`·`amr` access-token mapper와 password/OTP execution
reference를 적용했고, 정본 `tools/check_idp_realm_config.py`의 live read-back이 drift 0으로
통과했다. 첫 적용과 동일 명령 재실행은 모두 exit 0이었다. 이 결과는 realm 설정 네 항목의
`MEASURED`이지, OTP 등록이나 실제 fresh-auth token claim의 측정은 아니다.

## 안전 경계와 dry-run

- 적용 전 읽기 전용 probe는 mapper 2개와 execution reference 2개가 모두 없음을
  `DRIFT_OBSERVED`/exit 3으로 기록했다. 이어 관련 mapper/execution JSON만 operator-private
  경로에 0600으로 백업했고, 파일 2개의 manifest SHA-256만 Evidence에 남겼다.
- 기존 `deploy/intranet/idp-realm.sh`의 full 경로는 사용자 profile과 password를 다시 쓰므로
  카드 범위에 맞지 않았다. code commit `7aea9cc3`에서 `fresh-auth-only` 모드를 추가했다.
  이 모드는 사용자 자격 파일을 읽지 않고 realm/client/scope를 생성하거나 일반 설정을 바꾸지
  않으며, 전제가 없으면 exit 2로 닫힌다.
- live 적용 중 사용자 레코드 조회·변경 0, OTP 등록 0, 비밀 출력 0이었다. 접속 주소·계정·토큰·
  private key는 Git·PR·Evidence에 기록하지 않았다.

## 실측

| 단계 | 결과 |
|---|---|
| pre-apply read-only diff | 네 fresh-auth 항목 불일치, exit 3 |
| 보호 백업 | 파일 2, manifest `55b2592b…89db6` |
| `fresh-auth-only` apply | exit 0 |
| live checker read-back | token contract 일치, drift 0, exit 0 |
| 동일 명령 재실행 | exit 0 |
| 재실행 뒤 read-only diff | 네 항목 일치, exit 0 |
| post snapshot | 파일 4, manifest `db7629cb…d1733` |
| PG-free 회귀 | 86 passed, `bash -n`·`git diff --check` exit 0 |

배포 스크립트 SHA-256 `95d48cb7…26980`과 remote 실행 파일이 같고, checker SHA-256
`287bbfc8…133dd`도 local 정본과 remote read-back 파일이 같음을 적용 뒤 대조했다.

## rollback

rollback은 사용자나 realm 전체를 되돌리지 않는다. operator-private pre-apply snapshot에서
없었던 mapper/config만 해당 object id로 삭제하고, 기존 값이 있었던 경우에만 보호 JSON으로
그 객체를 복원한다. 그 뒤 같은 live checker를 다시 실행한다. 보호 snapshot 본문은 비밀·운영
경계이므로 Git에 넣지 않았고, Evidence에는 위치와 manifest SHA-256만 남겼다. 이번에는 rollback을
실행하지 않았다.

## 남은 경계

- 사용자의 OTP 등록은 사람 작업이므로 수행하지 않았다.
- `prompt=login&max_age=300` 뒤 실제 access token의 `auth_time`·`amr` exact claim 관측은
  여전히 `NOT_OBSERVED`다.
- 근거: [[사내망_IdP_호스트명_인벤토리_런북_2026-09-30]],
  `docs/vault/30_Development/Evidence/idp-fresh-auth-live-readback-7aea9cc3.json`.
