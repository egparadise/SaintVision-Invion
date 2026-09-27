---
doc_id: "SPEC-S01-READINESS-PREFLIGHT-001"
title: "S01-BE·S01-ST 준비 상태 preflight 수집기 설계"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T06:12:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S01-BE", "S01-ST", "preflight", "read-only", "redaction"]
---

# S01-BE·S01-ST 준비 상태 preflight 수집기 설계

## 목적과 입력

`tools/s01_readiness_preflight.py`는 사용자 입력 U1~U6이 준비된 직후 한 번 실행해
S01의 현재 합격 신호와 남은 차단을 redacted JSON 하나로 고정한다. 입력은 Control
Plane base URL, `unresolvedSettings`를 제공하는 별도 health URL, 실 access token을 담은
환경변수 이름, S01 inventory JSON, LAN pilot private state, Node CA bundle, 선택적인 HTTP
TLS CA bundle이다. 토큰·DSN은 CLI 인자로 받지 않고 환경 또는 보호 state에서만
읽는다. 입력이 없으면 합성하지 않고 해당 U 항목을 `BLOCKED`로 둔다.

S01 inventory `schemaVersion=s01-readiness-inventory:1`은 토폴로지와 정확히 5개 Node의
식별·DNS·OS·역할·certificate fingerprint, CPU 모델/코어, GPU 모델/VRAM/driver,
disk/NIC, 실제 capacity, 허용 상한·절대 폴더, NTP source/스큐, Storage 역할을 담는다.
CPU는 millicores, memory/storage는 bytes, GPU는 devices, network는 bitsPerSecond 정본
단위를 쓴다. 허용 상한은 capacity를 넘을 수 없고 CP 겸임 토폴로지는 정확히 한 Node만
`cp-colocated`여야 한다.

## 검사와 판정

| 검사 | 입력/U 항목 | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| `/v1/health` | U2·U3·U6 | 별도 health URL이 200이며 `unresolvedSettings=[]` | 응답/형식/미해결 설정 존재 | health URL 없음 |
| `/readyz` | U2·U3 | 200, `status=ready` | 그 외 | base URL 없음 |
| `/v1/session` | U2 | 실토큰 200과 무토큰 401·Bearer | 제공된 토큰 또는 익명 경계 불일치 | 토큰 없음 |
| Node 인증서 체인 | U3·U5 | inventory 5대가 모두 등록되고 CA 서명·유효기간·leaf `ca=false`·`SERVER_AUTH`·nodeId/epoch의 정확한 SPIFFE URI를 만족 | 제공된 체인/identity/fingerprint 불일치 | CA/state가 없거나 5대 등록 미충족 |
| DNS | U4 | inventory에 선언한 CP·portal·IdP·Node 이름 전부 해석 | 제공된 이름 중 해석 실패 | inventory/이름 없음 |
| inventory lint | U1·U5·U6 | 5 Node와 필수 값·단위·상한·폴더·NTP가 정합 | 값/형식/중복/상한 위반 | 파일 또는 필수 사용자 값 없음 |
| pilot PG 대조 | U5 | read-only transaction에서 등록 5 Node의 CPU/RAM/profile/cert가 inventory와 일치 | DB/등록/관측 값 불일치 | state/DSN/inventory 없음 |

U 항목 판정은 연결된 검사 중 `FAIL > BLOCKED > PASS` 우선순위로 집계한다. 이 보고서는
S01 자동 `done` 판정이 아니며 Storage 왕복 SHA-256·retention/GC·독립 검토·운영 인수를
대신하지 않는다.

## 보안·읽기 전용·출력 계약

HTTP는 GET만 사용하고 redirect를 따르지 않는다. Node CA와 HTTP TLS CA는 분리하며 실토큰을
`http://` Control Plane으로 전송하지 않는다. pilot PG는 `REPEATABLE READ READ ONLY`,
2초 statement timeout, tenant local scope에서 SELECT만 수행한다. LAN state, serve/observe,
인증서와 heartbeat를 수정하지 않는다. output이 inventory·두 CA 또는 state 디렉터리와 그
하위에 있으면 삭제 전에 거부한다. 보호 검사를 통과한 output만 실행 시작 시 삭제해 실패 뒤
stale PASS가 남지 않게 한다.

JSON에는 schema version, 시각, `readOnly=true`, `redacted=true`, 검사/U별 status·고정
reason code·개수/불리언만 기록한다. URL, hostname, IP, Node/tenant ID, fingerprint, 경로,
토큰, DSN, 인증서 원문과 예외 문자열은 기록하지 않는다. exit code는 전부 PASS 0,
하나라도 FAIL 1, FAIL 없이 BLOCKED만 있으면 2다.

pilot PG 대조는 현재 snapshot 정본에 존재하는 CPU/RAM/profile과 channel certificate만
검증한다. GPU와 NTP는 해당 DB snapshot에 정본 필드가 없으므로 inventory lint의 사용자
입력 검증 범위이며, 이 수집기가 DB 관측 일치를 주장하지 않는다.
