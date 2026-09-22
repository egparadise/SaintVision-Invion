---
doc_id: "CLAUDE-REVIEW-PR95-CP-COLOCATED-WORKER-C0A67B3F-001"
title: "PR #95 'feat(lan): add explicit Windows CP co-located worker path'(head c0a67b3f, code 8007ae12, base 4143f375) 독립 검토 — 판정: 승인(관찰 5, 비차단) — server==node 기본 거부 + 명시 opt-in·state 영속·주소 유도 manifest v3·installer fail-closed가 ADR-100(겸임 1대·S05/S07 분모 제외)·lane v1.4와 정합, 기존 node1 state 하위 호환(읽기 전용 status 3 Node 정상), 키·비밀 미출력, 되살림 3건 KILLED"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T05:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c0a67b3f"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "LAN-pilot", "Windows", "Docker-Desktop", "ADR-100", "co-location", "security", "claude"]
---

# PR #95 `c0a67b3f` 독립 검토 (2026-09-23, 05:20 KST)

대상: `tools/lan_pilot.py`(+30: `--allow-server-node-colocation`, `serverNodeColocationAllowed` 영속, `configured_nodes` 유도·검증, manifest schema 3) · `deploy/lan/worker_config.py`(+20: `validate_topology`, `topology` 서브커맨드) · `prepare-worker.sh`/`finish-worker.sh`(+1: topology 검증 선행) · `Start-Worker.ps1`(+9: 주소 vs 선언·ADR-100 제외 검증) · `README.md`(+57) · `tests/test_lan_pilot_multinode.py`(+4 시험) · `tests/core/test_lan_worker_config.py`(+3 시험) · Codex History `2026-09-23_06-15-00_KST_LAN-PILOT-CP-COLOCATED_Codex_구현`(PR #95 브랜치에만 존재). 측정 트리 `D:\Project\sv-measure-claude`를 **`c0a67b3f`에 고정**(porcelain 0). 커널 `services/control-plane/src`·`contracts/`·`packages/` 변경 **0**. 실제 Windows worker 등록은 코디네이터 수행이라 미실행(Codex preflight: Docker API 1.41 < 1.45, WSL `Ubuntu` 부재로 **BLOCKED** — 정직 표기 확인).

## 1. 판정: **승인** (관찰 5, 비차단 — §7)

## 2. (a) 보안 의미 ↔ ADR-100

| 규칙 | 코드 | 정합 |
|---|---|---|
| server==node 기본 거부 | `validate_node_ips`(lan_pilot.py:127~140): `addr == server and not allow_server_node_colocation → ValueError` — 플래그는 **호출마다** 필요(영속 플래그가 있어도 `init`에 플래그 없이 서버 IP를 넘기면 거부) | ✔ |
| 명시 opt-in 영속 | `init`: 새 state `serverNodeColocationAllowed = flag AND serverIP∈node_ip`; 기존 state는 같은 조건에서만 `True`로 승격(:290~292) | ✔ 조용한 승격 없음 |
| 위조 방지 | `configured_nodes`(:78~91): 플래그 타입 strict bool, `coLocatedWithControlPlane`는 **주소에서 유도**해 선언과 다르면 거부, 겸임인데 플래그 없으면 거부 — load 경로 전체(serve/bundle/status/enroll)가 이 함수를 거치므로 state 파일 편집으로도 우회 불가(플래그까지 같이 위조해야 하고 그 파일은 private) | ✔ |
| **1대 한정** | `seen_ips` 중복 거부(:93) + 서버 주소는 하나 → 겸임 Node는 구조적으로 최대 1개 | ✔ ADR-100 "Node 1개" |
| S05/S07 timed wave 제외 | manifest v3: 겸임이면 `measurementEligible={s05:false,s07:false}`·`exclusionReason='cp-host-colocation'`, 독립이면 `null/null/null`(bootstrap이 적격을 **추정하지 않음**) — ADR §S05 규칙 2·§S07 규칙 2가 읽는 필드와 값이 동일 | ✔ |
| 자기 인증서·키 | 겸임 Node도 `add_requested_nodes`로 새 `nodeId`를 받고 CSR/enroll/cert/journal/container가 자기 것 — ADR "다른 Node의 인증서·private key 재사용 금지" | ✔ |

## 3. (b) schema v3 ↔ lane v1.4

lane v1.4 §토폴로지·§공통 필수 입력은 inventory에 `hostId`·`failureDomainId`·`coLocatedWithControlPlane`·`measurementEligible.s05/s07`·`exclusionReason`을 요구하고 "선언만 신뢰하지 않고 host identity에서 유도해 대조"를 요구한다. PR의 manifest v3는 뒤 세 필드를 넣고 co-location을 **주소 동일성**에서 유도한다 — 유도·대조 원칙과 값 규칙은 일치. `hostId`/`failureDomainId`는 manifest v3에 **없다**(관찰 O3: pilot bootstrap 범위 밖이지만 lane preflight가 나중에 필요로 하는 필드). 독립 Node의 `null` 적격은 lane "eligibility 누락이면 중단"과 충돌하지 않는다 — lane inventory는 별도 문서이고, bootstrap manifest가 `true`를 미리 박지 않는 쪽이 보수적이다.

## 4. (c) Windows/WSL installer ↔ 다중 노드 state·per-IP serve

- `artifact_for_client`(:243~259): 요청 source IP와 **정확히 하나**의 configured node가 일치해야 하고 `public/nodes/<nodeId>/<name>`을 준다. 겸임 Node의 `nodeIP == serverIP`이므로 Windows 호스트에서 `http://192.168.45.74:18081/worker.zip`을 받으면 source = 192.168.45.74 → 겸임 Node 번들만 반환. `127.0.0.1`/localhost로 받으면 어떤 node에도 안 맞아 **403**(`/healthz`만 loopback 허용) — README가 LAN 주소 사용을 지시하므로 정합(관찰 O4: WSL/컨테이너 안에서 받으면 NAT source라 403 — 문서화 권장). 첫 번째 configured node에만 있는 legacy fallback(`public/<name>`)은 겸임 Node가 뒤에 추가되므로 영향 없음.
- `serve`는 시작 시 state를 읽으므로 **재시작 필요** — README 명시 ✔; `allowedNodeIPs`/방화벽 remote 목록에 서버 주소가 한 번 들어감 ✔.
- installer: `prepare-worker.sh`·`finish-worker.sh`가 `worker_config.py topology manifest.json`을 **credential copy·container 시작 전에** 실행, `Start-Worker.ps1`도 방화벽 규칙 전에 같은 검증 — fail-closed 순서 정확. PowerShell 비교(`-ne $false`)는 JSON `null`을 `false`와 다르게 취급하므로 겸임 Node에서 `null`이 들어오면 throw ✔.

## 5. (d) 기존 node1 state 하위 호환 — PG-free + 읽기 전용 status

- PG-free: `tests/test_lan_pilot_multinode.py`(13) + `tests/core/test_lan_worker_config.py`(30) **43 passed**. `bash -n` 2 스크립트 exit 0, `Start-Worker.ps1` PowerShell parser error 0, `init --help`에 플래그 노출.
- 코드: 기존 state에 `serverNodeColocationAllowed`가 없으면 `.get(…, False)`; 기존 node에 `coLocatedWithControlPlane`이 없으면 주소에서 유도(`node.get(…, colocated)`) → Ubuntu 3대는 `False`. `same_identity`는 `IDENTITY=(nodeId,tenantId,epoch,serverIP,nodeIP,nodePort)`만 비교하므로 설치된 v2 manifest와 새 v3 번들의 identity 대조는 통과한다.
- **읽기 전용 status 1회**(PR 코드, `--state D:\…\.work\lan-5node\node1`, `status()`는 `load→node_status_rows→print`만이고 `save` 호출 없음 — 코드로 확인): `database: ready`, Node 3개 = `.143` online·observed, `.222` offline·미관측, `.210` online·observed, 세 Node 모두 `coLocatedWithControlPlane: false`. 코디네이터 관측(.143/.210 online, .222 대기)과 일치. state 파일 변경 없음.

## 6. (e) 키·비밀 취급 · 되살림

- diff에 private key·cert 본문·DSN·token을 출력하는 코드 없음. `init`/`status` 출력 추가 필드는 `coLocatedWithControlPlane` bool뿐. 번들 SHA-256은 기존대로 `bundle` stdout(별도 채널)이고 HTTP 응답에 hash를 싣지 않음 ✔. `Start-Worker.ps1`의 `-CertificateSHA256` out-of-band 대조 유지 ✔. History 페이지에 IP만 있고 비밀 없음 ✔.
- **되살림**(각각 원복, porcelain 0):

| 변이 | 결과 |
|---|---|
| A `configured_nodes`에서 "겸임인데 플래그 없음 → raise" 제거 | **2 failed**(`…cannot_be_forged`, `…requires_persisted_opt_in`) / 11 passed — KILLED |
| B `validate_node_ips`의 server==node 검사를 `if False` | **1 failed**(`…distinct_from_server`) / 12 passed — KILLED |
| C installer `validate_topology`가 겸임 Node에 `null` 적격 허용 | **2 failed**(`mismatch_is_rejected[s05]`,`[s07]`) / 28 passed — KILLED |

- 게이트(c0a67b3f 정확 트리): `check_docs` **864** · `check_contract_bindings` 54/19/14 · `check_response_freshness` · `check_doc_single_source --ratchet` 18 · `check_ontology` · `check_frontend_integrity` 9/0 · `export_schemas --check` 58/58 · `git diff --check 4143f375 c0a67b3f` — 전부 exit 0. 계약·커널 diff 0 파일.

## 7. 관찰(비차단)

- **O1** opt-in은 영속되며 CLI로 **철회 경로가 없다**(private-state.json 편집 필요). ADR §"되돌리기"의 "겸임 Node cordon·identity 보존" 절차와 맞추려면 `init --revoke-server-node-colocation`(identity는 남기고 provisioning만 차단) 같은 명시 경로가 다음 카드 후보.
- **O2** 다음 `bundle`부터 **모든** Node의 manifest가 v3가 된다. 새 스크립트를 옛 v2 `manifest.json`이 남은 디렉터리에서 실행하면 `validate_topology`가 타입 오류로 fail-closed(안전). README에 "재다운로드한 번들을 **새 디렉터리**에서" 문장이 있으므로 정합이나, Ubuntu 3대에는 재설치가 불필요함을 한 줄 명시 권장.
- **O3** manifest v3에 `hostId`/`failureDomainId`가 없다 — lane v1.4 preflight·ADR §"필수 기록"이 요구하므로 inventory-bound adapter 카드에서 추가(카드 17 O3와 같은 항목).
- **O4** 같은 호스트에서도 source IP가 LAN 주소여야 번들을 받는다(loopback·WSL NAT는 403) — README에 명시 권장.
- **O5** Codex preflight BLOCKED 항목(Docker API 1.41, WSL Ubuntu 부재)을 낮추는 우회를 하지 않은 것은 옳다. 코디네이터 실제 등록 뒤 `status`/`observe --once`의 별도 Node ID·online·snapshot이 있어야 "겸임 identity 1"이고, 5 Node는 네 번째 Ubuntu가 더 필요(Codex 서술 정확).

## 판정
**승인** — 기본 거부·명시 opt-in·영속·주소 유도·1대 한정·S05/S07 제외 필드가 ADR-100·lane v1.4와 정합하고, installer 세 진입점이 credential/container 전에 fail-closed하며, per-IP serve가 겸임 Node에 자기 번들만 주고, 기존 3-Node state는 코드·43 시험·읽기 전용 status에서 하위 호환이며, 키·비밀 출력 0, 되살림 3건 KILLED, 게이트 전부 0. 실제 등록·5 Node 충족·S05/S07 측정은 이 PR의 주장이 아니다(self-close 없음). PR #95 merge 가능.
