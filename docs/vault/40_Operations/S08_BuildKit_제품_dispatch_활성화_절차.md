---
doc_id: "RUNBOOK-S08-BUILDKIT-PRODUCT-ENABLE-V1"
title: "S08 BuildKit 제품 dispatch 활성화 절차 — 켜기 전에 확인할 것, 켜는 위치와 순서, 켠 직후 관측, 끄기와 격리 해제 (카드 238)"
version: "1.3.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "user"
updated: "2026-10-02T22:17:30+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "ed6033da"
task_ids: ["S08-BE"]
tags: ["operations", "s08", "buildkit", "runbook", "intranet", "claude"]
---

# S08 BuildKit 제품 dispatch 활성화 절차

## 0. 이 문서가 하는 일, 그리고 하지 않는 일

**이 문서는 켜지 않는다.** 사용자가 사내망(노드 1~5)에서 **언제든 안전하게 켤 수 있도록**, 켜기 전에 성립해야 하는 것을 **명령으로 확인**하고, 켜는 **정확한 위치와 값과 순서**를 적고, 켠 직후 **무엇을 보면 켜진 것인지**를 DB·로그 쿼리로 적고, 이상하면 **즉시 끄고 격리를 해제하는** 경로를 적는다. 이 문서를 읽고 실행하는 동안 어떤 설정도 바뀌지 않는다 — §3을 사용자가 직접 실행할 때만 바뀐다.

**모든 판정은 런타임 값에서 읽는다.** 이 문서는 "지금 그렇다"를 적지 않는다. 각 전제에는 **그 전제를 확인하는 명령**이 있고, 사용자가 실행한 시점의 출력이 판정이다. 특정 train의 SHA나 착지 스크립트 이름을 현재형으로 고정하지 않는다 — 그런 서술은 다음 train에서 거짓이 되고, 거짓이 된 체크리스트는 체크리스트가 아니다. 이 문서가 인용하는 측정은 **측정 시각과 함께** §7에 모아 두었고, 본문의 판정 자리에는 **명령**만 있다.

**비밀은 출력하지 않는다.** DSN·비밀번호·private key·토큰은 operator-private 경로(`.work/intranet/`, 노드의 `deploy/lan/` 산출물)에만 있다. 이 문서의 어떤 명령도 그 값을 화면에 적지 않는다. 인증서는 **지문(SHA-256)만** 비교한다.

**`sudo`가 필요한 단계는 사용자만 할 수 있다.** 그런 단계는 본문에 **`[sudo]`** 로 표시하고 §6에 모아 두었다. 코디네이터도 agent도 노드의 sudo 비밀번호를 갖고 있지 않다.

**선행 절차는 복제하지 않는다.** 노드 기동·CP 기동·epoch 프로비저닝은 [[서비스-시작-재시작-복구-절차]]와 [[train3-11_착지_직후_첫_행동_2026-10-02]]가 정본이고, 사용자 조치 전체 순서는 [[사용자 조치 단일 체크리스트]]가 정본이다. 이 문서는 **그 위에서 "BuildKit 제품 dispatch를 켠다"는 한 가지 결정**만 다룬다.

---

## 1. 켜기 전 전제 — 일곱 가지, 각각 명령으로 확인한다

아래 표의 **확인** 열이 이 절의 본문이다. 모든 명령은 **배포된 checkout**에서 실행한다(그 checkout의 SHA가 판정의 기준이다).

```bash
# 이 절의 모든 명령이 가리키는 기준값. 출력해 두고 아래 판정과 함께 기록한다.
cd /path/to/deployed/checkout        # 배포에 쓰인 checkout
git rev-parse HEAD                    # 배포 SHA (이 문서는 이 값을 고정하지 않는다)
git status --porcelain | head         # 비어 있어야 한다: 배포본이 tree와 같아야 판정이 의미를 갖는다
```

| | 전제 | 성립하지 않으면 |
|---|---|---|
| **A** | 배포된 코드가 그 설정을 **네 자리에서** 읽는다(정의·composition root·tick·claim 전) | 켜도 경로가 열리지 않는다 |
| **B** | 배포 설정이 그 변수와 `INV_WORKER_CONFIG`를 **worker 프로세스에** 전달한다 | 호스트에 export해도, control-plane에만 넣어도 그 경로는 켜지지 않는다 |
| **C** | DB가 **`0059`와 `0060` 두 표를 가진 정본 head**다 | producer가 admission 행을 넣을 표가 없다 |
| **D** | 그 두 표를 쓰는 **producer와 product loop가 착지해 배포본에 있다** | 행이 쌓이고 아무도 승격·dispatch하지 않는다 |
| **E** | transport가 **durable quarantine 채널과 함께** 구성된다 | 모든 dispatch가 `RES-0006`으로 거부된다 |
| **F** | 대상 node가 **online·heartbeat 신선·channel epoch 일치**다 | lease·probe 단계에서 거부된다 |
| **G** | 배포 SHA에서 **hosted 시험이 green**이다 | 켜는 것이 아니라 먼저 그 실패를 본다 |

### A. 코드가 그 설정을 읽는가

```bash
grep -rn "PRODUCT_ENABLE_SETTING\|INV_BUILDKIT_PRODUCT_ENABLED" \
  --include=*.py services/control-plane/src/inv | grep -v "/tests/"
```

**판정**: **네 자리**가 나와야 한다 — 그 값이 `1`이 아니면 경로가 네 번 막힌다.

| 자리 | 언제 보는가 |
|---|---|
| `build_execution.py` | `PRODUCT_ENABLE_SETTING`/`PRODUCT_ENABLE_VALUE`를 **정의**하고, `BuildExecutionService`가 dispatch마다 다시 본다 |
| `worker.py` | **프로세스 시작 시**(composition root). 꺼져 있으면 제품 runtime을 **구성조차 하지 않는다** |
| `build_product_runtime.py` | 각 tick 시작(`BuildProductRuntime.once`) — 꺼져 있으면 `RES-0006` |
| `build_execution_worker.py` | **queue 행을 claim하기 전에** — 꺼져 있다는 사실을 알려고 durable 행을 소비하지 않는다 |

### B. 배포 설정이 그 변수를 프로세스에 전달하는가

```bash
grep -n "INV_BUILDKIT_PRODUCT_ENABLED\|INV_WORKER_CONFIG" docker-compose.prod.yml \
  || echo "선언 없음: 이 compose로 뜬 컨테이너는 이 변수들을 볼 수 없다"
```

**판정**: **worker 서비스**(§3-0의 composition root가 사는 프로세스)의 `environment:` 목록에 `INV_BUILDKIT_PRODUCT_ENABLED`와 `INV_WORKER_CONFIG`가 **둘 다** 있어야 한다. compose의 `environment:`는 **열거된 이름만** 컨테이너로 전달하므로, 호스트 셸에서 `export`하거나 `.env`에 적어도 **열거되지 않은 변수는 들어가지 않는다**. `control-plane`에만 있는 것은 이 경로를 켜지 못한다 — API 프로세스에는 그 구성이 없다. 선언이 없으면 **§3-1(BLOCKED)**이 먼저다.

### C. DB가 **제품 경로의 두 표**를 가진 정본 head인가

제품 producer의 정본은 `0060_build_execution_admissions`이고 그 `down_revision`이 `0059_build_execution_intents`다. **0059만 있는 DB에서도 통과하는 gate는 gate가 아니다** — 측정했다: 0059까지만 올린 DB에서 `admissions_table`이 `f`로 나온다(§7). 그리고 **파일명 정렬은 migration head의 정본이 아니다** — 정본은 graph의 단일 head다.

```bash
# 1) 배포본이 말하는 정본 head (단일 head여야 한다; 둘 이상이면 그 자체가 차단 사유다)
python tools/migration_graph.py --head
```

```bash
# 2) DB가 그 head이고 두 표가 모두 있는지. 비밀은 출력하지 않는다.
canonical=$(python tools/migration_graph.py --head | tail -1)
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d saintvision -At -F'|' -c \
  "SELECT (SELECT version_num FROM alembic_version) AS db_head,
          (to_regclass('inv.build_execution_intents')    IS NOT NULL) AS intents_table,
          (to_regclass('inv.build_execution_admissions') IS NOT NULL) AS admissions_table,
          (SELECT count(*) FROM inv.control_epoch WHERE singleton) AS epoch_rows"
printf '정본 head: %s\n' "$canonical"
```

**판정**: 네 값이 모두 성립해야 한다 — `db_head`가 **`$canonical`과 문자 그대로 같고**, `intents_table`과 `admissions_table`이 **둘 다 `t`**, `epoch_rows`가 `1`. 하나라도 아니면 켜지 않는다.

- `admissions_table`이 `f`면 **배포 DB가 0059까지만 올라간 것**이고, producer가 admission 행을 넣을 표가 없다. `0060` 적용이 먼저다.
- `db_head != $canonical`이면 배포본과 DB가 **다른 tree**다.
- `epoch_rows`가 `0`이면 커널의 모든 트랜잭션이 `LEASE-0004`로 실패한다([[서비스-시작-재시작-복구-절차]] §3-2가 정본이다. 갓 만든 DB는 이 값이 `0`이다 — epoch는 migration이 아니라 **운영자가** 프로비저닝한다).

### D. queue를 소비하는 worker loop와 producer가 배포본에 있는가 — **런타임으로 읽는다**

이 전제는 **PR 하나의 상태**에 달려 있고, 그 상태는 바뀐다. 그래서 문서가 "있다/없다"를 적지 않고 **읽는 명령**을 적는다.

```bash
# 1) 배포본에 worker를 구성하는 제품 코드가 있는가 (시험 제외)
grep -rn "BuildExecutionWorker(" --include=*.py services | grep -v "/tests/" \
  || echo "worker를 구성하는 제품 코드 없음"

# 2) 그 worker를 돌리는 프로세스/서비스 정의가 있는가.
#    서비스 **이름**은 이 문서가 정하지 않는다(카드 241이 정의를 가져온다) — 그래서 이름이 아니라
#    코드가 요구하는 것으로 찾는다: 실행 모듈과 그 프로세스가 반드시 읽는 환경 변수.
grep -rn "inv\.worker\|INV_WORKER_CONFIG\|INV_BUILDKIT_PRODUCT_ENABLED" \
  docker-compose.prod.yml deploy/ 2>/dev/null \
  || echo "worker 프로세스를 정의하는 배포 설정 없음"

# 3) 그 작업(worker loop + producer)을 가져오는 PR의 상태와 포함 여부
for pr in 311 312 318 323 327 331; do
  ref=$(gh pr view "$pr" --json headRefName --jq .headRefName)
  sha=$(gh pr view "$pr" --json headRefOid  --jq .headRefOid)
  state=$(gh pr view "$pr" --json state,reviewDecision --jq '[.state,(.reviewDecision//"-")]|join("/")')
  git fetch -q origin "$ref" 2>/dev/null || true
  if git merge-base --is-ancestor "$sha" HEAD 2>/dev/null; then
    printf '#%s %s %s IN-TREE\n'     "$pr" "${sha:0:8}" "$state"
  else
    printf '#%s %s %s NOT-IN-TREE\n' "$pr" "${sha:0:8}" "$state"
  fi
done
```

**`IN-TREE`는 gate가 아니다.** 어떤 PR의 head든 임의의 후보 tree에 합치면 조상이 되므로 "조상이다"는 **검토를 통과해 착지했다**는 뜻이 아니다. 운영 배포 tree의 gate는 **세 가지를 함께** 요구한다 — `MERGED`, 착지 tip의 조상, 그리고 그 head에서 hosted 두 lane이 `success`.

```bash
# 4) 운영 배포 tree의 fail-closed gate
integration=$(git ls-remote origin refs/heads/integration/all-agents-unified | cut -f1)
git fetch -q origin integration/all-agents-unified
blocked=0
for pr in 311 312 318 323 327 331; do
  state=$(gh pr view "$pr" --json state --jq .state)
  merge=$(gh pr view "$pr" --json mergeCommit --jq '.mergeCommit.oid // ""')
  head=$(gh pr view "$pr" --json headRefOid --jq .headRefOid)
  review=$(gh pr view "$pr" --json reviewDecision --jq '.reviewDecision // "-"')
  landed="no"
  if [ -n "$merge" ] && git merge-base --is-ancestor "$merge" "$integration" 2>/dev/null; then
    landed="yes"
  elif git merge-base --is-ancestor "$head" "$integration" 2>/dev/null; then
    landed="yes(head)"
  fi
  green=$(gh run list --commit "$head" --limit 20 --json name,conclusion \
            --jq '[.[] | select(.name == "Backend Build" or .name == "Core Build")
                       | select(.conclusion == "success") | .name] | unique | join(",")')
  printf '#%s state=%s review=%s landed=%s green=[%s]\n' "$pr" "$state" "$review" "$landed" "$green"
  # 출력은 gate가 아니다. 네 조건을 모두 blocked에 넣는다 (#335 r2 N1).
  if [ "$state" != "MERGED" ]; then blocked=1; fi
  if [ "$landed" = "no" ]; then blocked=1; fi
  case "$green" in
    *"Backend Build"*) : ;;
    *) blocked=1 ;;
  esac
  case "$green" in
    *"Core Build"*) : ;;
    *) blocked=1 ;;
  esac
  case "$review" in
    APPROVED) : ;;
    *) blocked=1 ;;
  esac
done
if [ "$blocked" -ne 0 ]; then
  echo "BLOCKED: MERGED·착지 tip의 조상·exact head의 Backend/Core success·APPROVED 중 하나라도 아닌 PR이 있다 — 켜지 않는다"
fi
```

**판정(운영 배포 tree)**: 위 루프가 `BLOCKED`를 출력하지 않아야 한다 — **네 조건이 전부 gate**다: `state=MERGED`, `landed=yes`(merge commit이 착지 tip의 조상), 그 head에서 **Backend Build와 Core Build가 `success`**, 그리고 **`reviewDecision=APPROVED`**(독립 검토). `green`이 빈 칸이면 그 SHA에서 그 lane이 돌지 않은 것이고(`skipped`는 green이 아니다) 그것도 **증거 없음 = blocked**다.

> **주의 — `reviewDecision`은 머지 뒤에 비어 보일 수 있다.** 그런 PR은 **승인 근거를 따로 확인**해야 하고(그 PR의 승인 코멘트 또는 진행판 `latest_codex_card`가 적는 exact head와 run id), 확인하지 못하면 **blocked로 둔다**. 출력만 보고 통과시키는 것이 r2가 지적한 바로 그 결함이다.

**판정(후보 tree에서 연습할 때)**: 착지 전에 이 절차를 시험해 볼 수는 있다. 그때는 `state=MERGED`가 성립하지 않으므로 **연습이라고 적고** 운영 활성화의 전제로 쓰지 않는다.

PR 번호 목록은 S08 경로를 만든 작업들이다 — 계약(`#311`), 제품 caller(`#312`), quarantine channel(`#318`), intent queue(`#323`), claim fencing(`#327`), **worker loop과 producer(`#331`, 카드 232 — `0060`과 `worker.py`의 composition root를 가져온다)**.

### E. transport가 durable quarantine 채널과 함께 구성되는가

```bash
# 제품 경로에서 transport를 구성하는 코드가 있는가 (시험 제외)
grep -rn "NodeAgentReceipts(" --include=*.py services | grep -v "/tests/" \
  || echo "transport를 구성하는 제품 코드 없음"

# 그 구성이 두 조각을 모두 받는지 — 둘 중 하나만 주면 생성 자체가 VERIFY-0022로 거부된다
grep -n "records_durable_quarantine\|quarantine_client\|quarantine_channel" \
  services/control-plane/src/inv/buildkit_transport.py | head
```

**판정**: `NodeAgentReceipts`는 `quarantine_client`와 `quarantine_channel`을 **함께** 받을 때만 `records_durable_quarantine = True`가 되고, 클래스 기본값은 **`False`** 다. `BuildExecutionService`는 **외부 dispatch 전에** 그 capability를 요구하고 없으면 `RES-0006`으로 거부한다 — 잃은 경쟁을 기록할 수 없는 dispatch는 하지 않는다는 뜻이다. 또 dispatch 직전 **live nonce 교환**(`preflight_quarantine`)으로 그 채널이 지금 살아 있고 같은 tenant/node/epoch를 답하는지 확인한다. 설정된 클라이언트는 런타임 capability가 아니다.

채널의 계약은 [[S08-BE_node-agent_durable_quarantine_channel]]이 정본이다 — mTLS TLS 1.3·certificate pin·no-proxy·no-redirect로 `POST /v1/builds/quarantine`만 부르고, 노드는 응답 전에 journal을 write → fsync → atomic rename → directory fsync로 기록한다. `requestId`가 idempotency key이고, 같은 key에 다른 내용은 `NODE-0015`로 거부된다.

### F. 대상 node가 지금 받을 수 있는 상태인가

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d saintvision -c \
  "SELECT n.node_id, n.status, clock_timestamp() - n.heartbeat_at AS heartbeat_age,
          (n.recovery_epoch IS NOT NULL) AS epoch_set,
          c.enabled AS channel_enabled, c.certificate_not_after,
          (c.recovery_epoch = n.recovery_epoch) AS channel_epoch_matches
     FROM inv.nodes n
     LEFT JOIN inv.node_channels c ON c.tenant_id = n.tenant_id AND c.node_id = n.node_id
    ORDER BY n.node_id"
```

**판정**: 대상 node가 `status = online`, `heartbeat_age`가 **15초 이내**(`NodeChannels.snapshot`이 그 창을 요구한다), `channel_enabled = t`, `channel_epoch_matches = t`, `certificate_not_after`가 미래여야 한다. `recovery_epoch`가 node와 channel과 **CP의 `INV_RECOVERY_EPOCH`** 세 곳에서 같아야 한다 — 다르면 `NODE-0033`이다.

### G. 배포 SHA에서 hosted 시험이 green인가

```bash
gh run list --commit "$(git rev-parse HEAD)" --limit 20 \
  --json name,event,status,conclusion,databaseId \
  --jq '.[] | [.name, .event, .status, (.conclusion // "-"), (.databaseId|tostring)] | @tsv'
```

**판정**: 그 SHA에서 **Backend Build**와 **Core Build**가 `success`여야 한다(`skipped`는 green이 아니라 "실행되지 않았다"다 — path filter로 건너뛴 lane은 그 SHA에 대해 아무 말도 하지 않는다). S08 경로의 계약·fencing 시험은 그 두 lane에서 돌고, 그것이 **켜기 전 마지막 기계 확인**이다.

---

## 2. 사내망 노드 준비 확인 — rootless BuildKit · node agent · mTLS pin

이 절의 명령은 **노드에서** 실행한다. CP 호스트에서 실행하는 §1과 섞지 않는다.

### 2-1. node agent가 그 노드의 journal·epoch로 살아 있는가 — **[sudo] 아님**

```bash
# 노드에서: 기동 산출물은 deploy/lan/ 절차가 만든 것이고, 이 명령은 상태만 읽는다.
node_id=$(python3 -c 'import json;print(json.load(open("manifest.json"))["nodeId"])')
docker ps --filter "name=saintvision-${node_id,,}" \
          --format '{{.Names}}\t{{.Status}}\t{{.Image}}'
docker inspect --format '{{index .Config.Labels "ai.saintvision.node"}}' "saintvision-${node_id,,}"
```

**판정**: 컨테이너가 `Up`이고 label의 node id가 `manifest.json`의 값과 같아야 한다. 노드 기동 자체는 `deploy/lan/start-node.sh`가 정본이고 그 스크립트는 **인증서·키 쌍 일치와 만료**를 먼저 검사한다(`openssl verify`, `-checkend 60`, 공개키 지문 비교). 이미 떠 있는 컨테이너를 다시 만들지 않는다 — journal을 보존해야 한다.

### 2-2. CP가 pin한 인증서가 그 노드의 인증서인가

```bash
# 노드에서 지문만 출력한다(개인키는 출력하지 않는다).
openssl x509 -in node-cert.pem -noout -fingerprint -sha256 \
  | tr 'A-F' 'a-f' | sed 's/.*=//; s/://g'
```

```bash
# CP 호스트에서 pin된 값(지문)만 읽는다.
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d saintvision -At -c \
  "SELECT node_id, certificate_sha256 FROM inv.node_channels ORDER BY node_id"
```

**판정**: 두 값이 **문자 그대로** 같아야 한다. 다르면 `NODE-0032`(pinned Node certificate rejected)로 모든 호출이 끊긴다. 인증서를 교체했다면 `inv.node_channels`의 pin을 함께 갱신하는 것이 운영 행위다 — 이 문서는 그 갱신 절차를 복제하지 않는다.

### 2-3. rootless BuildKit이 그 노드에서 실제로 빌드하는가 — **일부 [sudo]**

제품 경로가 쓰는 것과 **같은 transport로** rootless BuildKit을 한 번 왕복시키는 도구가 저장소에 있다(참조 lane이고 제품 Evidence를 만들지 않는다).

```bash
# 노드에서: 무엇을 요구하는지 먼저 읽는다.
python3 tools/run_buildkit_rootless_roundtrip.py --help
```

```bash
# rootless 상태 점검(노드에서). daemon 설치·기동은 운영 행위이고, 설치가 필요하면 [sudo]다.
systemctl --user is-active buildkit || echo "user 단위 buildkit 비활성"
buildctl --addr "${SV_BUILDKIT_ADDRESS:-unix:///run/user/$(id -u)/buildkit/buildkitd.sock}" \
         debug workers
id -u; grep -c . /proc/self/uid_map   # rootless 여부의 근거(uid map이 1:1이 아니어야 한다)
```

**판정**: `debug workers`가 worker를 하나 이상 출력하고, `uid_map`이 rootless 매핑이어야 한다. 사용자 네임스페이스나 AppArmor/seccomp 완화가 필요하다면 그것은 **`[sudo]` 단계**이고 §6에 있다. hosted runner에서의 같은 측정은 그 완화를 **limitation으로 기록**한다 — 실물 노드 인수가 따로 필요한 이유가 그것이다([[사용자 조치 단일 체크리스트]] §10).

**같은 측정을 한 번에 돌리는 경로가 이미 있다.** 저장소의 참조 lane이 rootless daemon을 띄우고 **제품과 같은 transport로** 왕복까지 하며, 그 lane은 hosted에서도 돌고 있다. 노드에서 같은 것을 돌릴 때는 lane 스크립트의 환경 계약을 그대로 쓴다(여섯 변수 전부 필수이고, 하나라도 없으면 스크립트가 멈춘다):

```bash
# digest 고정 이미지의 출처는 저장소의 참조 lane 정의다. 값을 손으로 적지 않고 거기서 읽는다.
ROOTLESS_IMAGE=$(python3 -c "import pathlib, re; print(re.search(r'BUILDKIT_ROOTLESS_IMAGE:\s*(\S+)', pathlib.Path('.github/workflows/s08-buildkit-reference.yml').read_text(encoding='utf-8')).group(1))")
printf '%s\n' "$ROOTLESS_IMAGE"
case "$ROOTLESS_IMAGE" in
  *@sha256:*) : ;;
  *) echo "BLOCKED: digest 고정 이미지가 아니다 — 참조 lane 정의를 먼저 확인한다" ;;
esac
```

그 값(`docker.io/moby/buildkit@sha256:…`)이 **참조 lane이 실제로 쓰는 digest 고정 이미지**이고, lane 정의가 그 pin을 옮기면 위 명령이 따라간다. 그 다음 여섯 변수를 모두 주어 lane을 돌린다 — 하나라도 없으면 스크립트가 **즉시 멈춘다**:

```bash
# 노드에서. 값은 그 노드의 경로이고, 비밀은 들어가지 않는다.
export SV_BUILDKIT_BIN_DIR=/path/to/buildkit/bin
export SV_BUILDKIT_RUNTIME_IMAGE="$ROOTLESS_IMAGE"
export SV_BUILDKIT_CONTAINER_NAME="sv-s08-check-$(date +%s)"
export SV_BUILDKIT_OUTPUT_DIR="$PWD/dist/s08-buildkit-check"
export SV_BUILDKIT_RUNTIME_DIR="$XDG_RUNTIME_DIR/s08-buildkit-check"
export INV_EVIDENCE_CODE_SHA="$(git rev-parse HEAD)"
bash tools/run_buildkit_rootless_lane.sh
```

그리고 **그 lane의 hosted 결과**는 배포 SHA에서 이렇게 읽는다(label opt-in이거나 dispatch이므로 돌지 않았을 수 있고, 그때는 "증거 없음"이 정답이다):

```bash
gh run list --workflow s08-buildkit-reference.yml --commit "$(git rev-parse HEAD)" --limit 5 \
  --json event,status,conclusion,databaseId \
  --jq '.[] | [.event, .status, (.conclusion // "-"), (.databaseId|tostring)] | @tsv' \
  || echo "그 SHA에서 참조 lane이 돌지 않았다"
```

---

## 3. 켜기 — **어느 프로세스**에, 무엇을, 어떤 순서로

**§1의 A~G가 모두 성립한 뒤에만 이 절을 실행한다.** 하나라도 아니면 켜는 것이 아니라 그 항목을 먼저 해결한다.

### 3-0. 켜는 대상은 **worker 프로세스**다 (control-plane이 아니다)

제품 경로의 composition root는 `services/control-plane/src/inv/worker.py`의 `main()`이다. 그 함수가 **그 프로세스의 환경에서** 플래그를 읽고, 켜져 있을 때만 `configured_tenant_product_runtime()`으로 `BuildExecutionAdmissionStore` → `BuildExecutionWorker` → `BuildExecutionService`를 **구성한다**. control-plane(API) 프로세스에는 그 구성이 없다 — 그러므로 **control-plane에만 변수를 넣으면 제품 dispatch는 켜지지 않는다.**

그 함수가 그 프로세스에서 요구하는 것(코드에서 읽은 그대로):

| 무엇 | 요구 |
|---|---|
| `INV_WORKER_CONFIG` | worker 전용 read-only volume의 `/run/saintvision-worker/worker.json`. `trusted_file`이 regular file·**64KiB 이하**·**group/other 쓰기 권한 없음**(`mode & 0o022 == 0`)을 요구하고, `strict_object`가 **중복 JSON key를 거부**한다 |
| 설정 최상위 key | `tenantId`·`tls`는 **필수**, 그 밖에는 `outputRoot`·`buildExecution`만 허용(다른 key가 있으면 시작 거부) |
| `buildExecution` | **정확히 아홉 key**: `buildctlPath` · `address` · `sourceRoot` · `referenceHealthReceipt` · `productReceiptDirectory` · `builderInstanceId` · `builderProfileId` · `providerRecoveryEpoch` · `nodeId`. 하나 빠지거나 하나 더 있으면 `Exact build execution configuration required`로 거부(§7에서 실제로 확인했다) |
| `tls` | `NodeTLSClient(ca_file=…, certificate_file=…, key_file=…)` 로 그대로 전달된다 — mTLS 자료의 **컨테이너 경로** |
| `INV_RUNTIME_DSN` | 커널 LOGIN role의 DSN(**superuser·BYPASSRLS·스키마 소유자는 거부된다**) |
| `INV_RECOVERY_EPOCH` | `inv.control_epoch`의 값과 같아야 한다 |
| `INV_BUILDKIT_PRODUCT_ENABLED` | **정확히 `1`**. 다른 값(`true`, `yes`, `01`)은 꺼진 것과 같다 |
| 명령 | `python -m inv.worker` (상주 loop). `--once`는 한 tick만 돌고 끝난다 — 활성화 확인용으로 쓸 수 있다 |

플래그가 켜져 있는데 `buildExecution`이 없으면 worker는 **시작하지 않는다**(`Build execution configuration unavailable`). 즉 **반쯤 켜진 상태는 없다.**

### 3-1. 배포 정의와 설정 volume을 먼저 검증한다

`docker-compose.prod.yml`의 `worker` 서비스는 `python -m inv.worker`를 실행하고 포트를
공개하지 않는다. API와 worker가 함께 읽는 `api.json` 계열은 `api_config` volume으로,
`worker.json`과 그 Node TLS 자료는 별도 `worker_config` volume으로 전달한다. 두 mount는
모두 read-only이고, control-plane은 `worker_config`를 mount하지 않는다.

보호된 설정 디렉터리의 worker TLS 경로는 반드시 flat
`/run/saintvision-worker/<file>`이어야 한다. 다음 명령은 기존 volume을 덮어쓰지 않고 두
새 volume을 함께 만들고 검증한다. 둘 중 하나라도 실패하면 이 실행이 만든 volume만
정리한다.

```bash
python tools/prepare_server_config.py \
  --directory /path/to/deployment/config \
  --volume saintvision-api-config-v1 \
  --worker-volume saintvision-worker-config-v1 \
  --image sha256:<reviewed-backend-image-id>
```

운영자 환경 파일에는 서로 다른 두 이름을 넣는다. `docker compose config`가 성공하기
전에는 서비스를 시작하지 않는다.

```bash
INV_CONFIG_VOLUME=saintvision-api-config-v1
INV_WORKER_CONFIG_VOLUME=saintvision-worker-config-v1
docker compose -f docker-compose.prod.yml config --quiet
```

### 3-2. 운영자 환경 파일에 값을 넣는다

```bash
# CP 호스트에서. 이 파일은 저장소에 없고 operator-private이다.
printf 'INV_BUILDKIT_PRODUCT_ENABLED=1\n' >> /path/to/deployment/.env
grep -c '^INV_BUILDKIT_PRODUCT_ENABLED=1$' /path/to/deployment/.env   # 1이어야 한다
```

`worker.json`(= `INV_WORKER_CONFIG`)도 그 전에 자리를 잡아야 한다 — **값은 이 문서에 적지 않는다**(노드 경로·builder 식별자·epoch는 배포마다 다르다). 권한만 확인한다:

```bash
# 컨테이너가 읽을 파일의 권한. group/other 쓰기 비트가 있으면 worker가 시작을 거부한다.
docker compose -f docker-compose.prod.yml exec -T worker \
  stat -c '%a %U %n' /run/saintvision-worker/worker.json
```

### 3-3. 재시작 순서

순서가 있다. **DB 확인 → node agent 확인 → worker 재시작 → 읽기 확인**이고, control-plane은 이 플래그와 무관하므로 **건드리지 않는다**(API 쪽 동작을 바꾸지 않는다).

| 순서 | 무엇 | 명령 | 왜 이 순서인가 |
|---|---|---|---|
| 1 | PostgreSQL이 살아 있는지 **확인만** | `docker compose -f docker-compose.prod.yml ps postgres` | 재시작하지 않는다. 나머지 실패는 거의 전부 이것의 증상이다 |
| 2 | node agent가 떠 있는지 **확인만** (§2-1) | `docker ps --filter "name=saintvision-<node>"` | 컨테이너를 다시 만들면 journal·epoch 화해가 필요해진다 |
| 3 | **worker 재시작** | `docker compose -f docker-compose.prod.yml up -d --no-deps worker` | 환경 변수는 **프로세스 시작 시점**에 읽힌다(`worker.py`의 `main()`이 그때 `os.environ`를 보고 runtime을 구성한다). 재시작 없이는 켜지지 않는다 |
| 4 | **그 프로세스**에서 읽기 확인 | `docker compose -f docker-compose.prod.yml exec -T worker printenv INV_BUILDKIT_PRODUCT_ENABLED` | `1`이 출력돼야 한다. 다른 값이면 §3-1·§3-2를 다시 본다 |
| 5 | **구성이 성립했는지** 확인 | `docker compose -f docker-compose.prod.yml ps worker` 와 `docker compose -f docker-compose.prod.yml logs --tail 20 --no-color worker` | 구성이 어긋나면 그 프로세스는 **시작하지 못하고 종료**한다(`worker.py`의 `main()`이 `SystemExit("Explicit delivery worker configuration unavailable")`를 낸다). 그래서 **`ps`가 `Up`이 아니거나 로그 마지막 줄이 그 문장이면 구성이 틀린 것**이고, 이 확인은 **아무 것도 실행하지 않는다** |

> **`--once`를 확인용으로 쓰지 않는다** (#335 r2 N4). `python -m inv.worker --once`는 설정만 보는 것이 아니라 **한 tick을 실제로 실행한다** — `worker.py`가 `build_runtime.once(tenant)`와 `worker.once(tenant)`를 차례로 부르므로, admission이 하나라도 `ready`면 **승격하고 dispatch한다**(외부 side effect와 소비된 claim이 남는다). 구성만 보려면 위 5행처럼 **프로세스가 떠 있는지와 그 종료 문장**을 본다.

**`[sudo]` 아님**: 위 명령은 docker 그룹 권한으로 충분하다. 그 그룹 권한 자체를 부여하는 일이 `[sudo]`다(§6).

---

## 4. 켠 직후 관측 — 한 번의 dispatch를 끝까지 따라간다

아래 쿼리는 **순서대로** 한 번씩 돌린다. `:tenant`와 `:run`은 운영자의 실제 값이다(`psql -v tenant=... -v run=...` 또는 셸 변수). **이 절은 값을 바꾸지 않는다 — 읽기만 한다.**

**순서가 중요하다.** 제품 경로는 **admission(0060)이 먼저**다: trusted producer가 `inv.build_execution_admissions`에 `ready`로 기록하고, product loop의 각 tick이 그 행을 **재검증해 승격**할 때 비로소 0059 intent와 `inv.build.intent_enqueued`가 생긴다. 그래서 intent가 0건인 장애를 "producer/consumer 없음"으로 읽기 전에 **admission을 먼저 봐야 한다** — `ready`로 재시도 중인지, `quarantined`로 멈췄는지가 그 자리에 있다.

### 4-0. admission이 들어왔고 승격되는가 (**0060, 가장 먼저**)

```sql
SELECT run_id, status, retry_count, last_error_code,
       created_at, next_attempt_at, promoted_at, quarantined_at
FROM inv.build_execution_admissions
WHERE tenant_id = :'tenant'
ORDER BY created_at DESC
LIMIT 20;
```

```sql
-- 상태별 요약: 무엇이 쌓였고 무엇이 멈췄는가.
SELECT status, count(*) AS rows,
       min(next_attempt_at) AS next_due, max(retry_count) AS worst_retry,
       count(*) FILTER (WHERE last_error_code IS NOT NULL) AS with_error
FROM inv.build_execution_admissions
WHERE tenant_id = :'tenant'
GROUP BY status
ORDER BY status;
```

```sql
-- admission → intent 1:1 결속. 같은 (tenant, project, run)이 양쪽에 있어야 한다.
SELECT a.run_id, a.status AS admission_status, a.retry_count, a.last_error_code,
       i.status AS intent_status, i.attempt_count,
       (i.run_id IS NOT NULL) AS intent_exists
FROM inv.build_execution_admissions a
LEFT JOIN inv.build_execution_intents i
       ON i.tenant_id = a.tenant_id AND i.project_id = a.project_id AND i.run_id = a.run_id
WHERE a.tenant_id = :'tenant'
ORDER BY a.created_at DESC
LIMIT 20;
```

```sql
-- 승격 사건. 이 행이 있어야 "그 admission이 intent가 됐다"가 관측된 것이다.
SELECT o.run_id, o.created_at, o.payload ->> 'projectId' AS project_id
FROM inv.outbox o
WHERE o.tenant_id = :'tenant' AND o.event_type = 'inv.build.intent_enqueued'
ORDER BY o.created_at DESC
LIMIT 20;
```

**읽는 법**:

| 관측 | 뜻 |
|---|---|
| `status = 'promoted'` + `promoted_at` + 같은 run의 `intent_exists = t` + 승격 사건 1건 | 정상 경로. 이제 §4-1로 간다 |
| `status = 'ready'`인데 `retry_count`가 오르고 `next_attempt_at`이 미래 | **재시도 중**이다(예: node가 stale이면 backoff). intent가 0건인 것은 producer 없음이 아니라 **승격이 아직 못 된 것**이다 — `last_error_code`가 이유다 |
| `status = 'quarantined'` + `quarantined_at` + `last_error_code` | 그 admission은 **승격되지 않는다**. `VERIFY-0002`는 저장된 digest가 payload와 다르다는 뜻이고(재계산으로 잡는다), 그 밖의 code는 재검증 실패다. 되돌리지 않고 기록한다(§5-3) |
| admission이 0건 | **producer가 아무것도 넣지 않았다.** §1-D의 gate와 §3-0의 설정을 다시 본다 |

### 4-1. 그 다음 intent가 들어왔는가

```sql
SELECT run_id, status, attempt_count, last_error_code,
       created_at, claimed_at, completed_at, quarantined_at, next_attempt_at
FROM inv.build_execution_intents
WHERE tenant_id = :'tenant'
ORDER BY created_at DESC
LIMIT 20;
```

**읽는 법**: `status`는 `pending → claimed → completed`가 정상 경로다. `pending`에 머무르면 **소비자가 없다**(§1-D). `claimed`에서 멈추면 dispatch가 진행 중이거나, 이미 소비된 claim이 있어 되돌릴 수 없는 상태다 — 그때 `last_error_code`가 이유를 적는다. `quarantined`는 **되돌리지 않고 기록한 상태**이고 §5-3으로 간다.

### 4-2. 그 dispatch가 **일회성 claim**을 소비했는가

```sql
SELECT i.run_id, i.status, i.attempt_count,
       (k.key IS NOT NULL) AS dispatch_claim_consumed
FROM inv.build_execution_intents i
LEFT JOIN inv.idempotency k
       ON k.tenant_id = i.tenant_id AND k.project_id = i.project_id
      AND k.operation = 'build.dispatch' AND k.key = i.dispatch_claim_key
WHERE i.tenant_id = :'tenant'
ORDER BY i.created_at DESC
LIMIT 20;
```

**읽는 법**: `dispatch_claim_consumed = t`이면 그 결정은 **이미 한 번 외부로 나갔다**. 그 뒤로는 그 행을 `pending`으로 되돌릴 수도, `quarantined`로 바꿀 수도 없다 — DB의 trigger가 `build_execution_intent_dispatch_consumed`로 거부한다. 이것이 "같은 결정이 두 번 빌드되지 않는다"의 실제 구현이고, 운영 중 가장 중요한 한 칸이다.

### 4-3. lease가 그 run에 잡혔다가 반납됐는가

```sql
SELECT l.run_id, l.resource_id, l.lease_id, l.fencing_token,
       l.granted_at, l.expires_at, l.released_at, (l.stop_receipt IS NOT NULL) AS stopped
FROM inv.resource_leases l
WHERE l.tenant_id = :'tenant' AND l.run_id = :'run'
ORDER BY l.granted_at;
```

**읽는 법**: 완료된 dispatch는 `released_at`과 `stop_receipt`가 **함께** 채워진다(DB의 CHECK가 그 둘을 묶는다). `released_at`이 비어 있고 node가 `quarantined`면 §5-3이다.

### 4-4. Evidence가 cleanup receipt와 함께 저장됐는가

```sql
SELECT evidence_id, created_at,
       (envelope ? 'cleanupReceipt') AS has_cleanup_receipt,
       envelope -> 'cleanupReceipt' ->> 'writerKind' AS cleanup_writer
FROM inv.evidence
WHERE tenant_id = :'tenant' AND run_id = :'run'
ORDER BY created_at;
```

**읽는 법**: `has_cleanup_receipt = t`이고 `cleanup_writer`가 node agent여야 한다. Evidence envelope은 **cleanup receipt를 포함한 상태로 digest가 계산된 뒤** 저장된다 — 그래서 cleanup 없는 완료는 존재할 수 없다.

### 4-5. outbox 사건 — 완료·격리·채널 불가 세 가지만 본다

```sql
SELECT event_type, count(*) AS events,
       min(created_at) AS first_at, max(created_at) AS last_at,
       count(*) FILTER (WHERE published_at IS NULL) AS unpublished
FROM inv.outbox
WHERE tenant_id = :'tenant' AND event_type LIKE 'inv.build.%'
GROUP BY event_type
ORDER BY event_type;
```

| `event_type` | 뜻 |
|---|---|
| `inv.build.dispatch_completed` | 그 dispatch가 **끝났다**. payload가 `evidenceId`·`evidenceDigest`·`leaseId`를 적는다 |
| `inv.build.node_quarantined` | dispatch 뒤 검증이 실패해 **node를 격리했다**. 원래 오류는 보존된다 |
| `inv.build.quarantine_preflight_unavailable` | 채널이 **dispatch 전에** 살아 있지 않았다. 외부 side effect는 없고 node는 격리되지 않는다 |

```sql
SELECT o.run_id, o.created_at,
       o.payload ->> 'evidenceId'     AS evidence_id,
       o.payload ->> 'evidenceDigest' AS evidence_digest,
       o.payload ->> 'leaseId'        AS lease_id
FROM inv.outbox o
WHERE o.tenant_id = :'tenant' AND o.event_type = 'inv.build.dispatch_completed'
ORDER BY o.created_at DESC
LIMIT 10;
```

**읽는 법**: `evidence_digest`가 §4-4의 envelope에서 계산된 값과 같아야 한다. 두 값이 다르면 그것은 운영 조치가 아니라 **보고할 결함**이다.

### 4-6. 로그에서 같은 사건을 확인한다 (비밀 미출력)

```bash
# 제품 dispatch가 사는 프로세스는 worker다. reason code만 보고 payload는 출력하지 않는다.
docker compose -f docker-compose.prod.yml logs --since 30m --no-color worker \
  | grep -E "Explicit delivery worker configuration unavailable|build intent could not be safely requeued|RES-0006|IDEM-0001|NODE-00(15|32|33)" \
  | tail -40
```

**읽는 법 — 그리고 로그가 말해 주지 않는 것** (#335 r2 N5). 제품 loop는 **tick마다 아무것도 기록하지 않는다**: `worker.py`의 `consume_builds()`가 결과를 지역 변수에만 담고(`outcome`) 로그를 남기지 않으며, 예외도 그 변수로 삼켜진다. 그래서 **켜졌는지·돌고 있는지의 정본 관측은 §4의 DB 행**이고 로그는 보조다. 로그에서 볼 수 있는 것은 셋이다 — ① 시작 실패(`Explicit delivery worker configuration unavailable`), ② `build intent could not be safely requeued`(`build_execution_worker.py`의 유일한 로그 — 되돌릴 수 없는 상태를 기록한다), ③ 그 외 reason code가 보일 때. `RES-0006`이 반복되면 capability 부족(§1-E), `NODE-0033`은 epoch·node 상태(§1-F), `NODE-0032`는 인증서 pin(§2-2)이다. **control-plane 로그에는 이 경로가 없다** — API 프로세스는 제품 runtime을 구성하지 않는다.

---

## 5. 이상하면 — 즉시 끄기, 그리고 격리는 해제가 아니라 기록이다

### 5-1. 좁은 끄기: 제품 dispatch만 끈다 (승인 불필요, 운영자 단독)

끄는 대상도 **worker 프로세스**다. control-plane을 재시작해도 worker가 시작할 때 복사한 `1`은 그대로 남는다.

```bash
# 값을 0으로 바꾸고 worker를 재시작한다. 변수를 지우는 것도 같은 효과다.
sed -i 's/^INV_BUILDKIT_PRODUCT_ENABLED=1$/INV_BUILDKIT_PRODUCT_ENABLED=0/' /path/to/deployment/.env
docker compose -f docker-compose.prod.yml up -d --no-deps worker
# 꺼졌다는 증거는 그 프로세스의 환경이다. 0(또는 빈 값)이어야 한다.
docker compose -f docker-compose.prod.yml exec -T worker printenv INV_BUILDKIT_PRODUCT_ENABLED \
  || echo "변수가 없다 — 그것도 꺼진 상태다"
```

**효과**: 제품 loop는 **tick 시작에서** 거부하고(`BuildProductRuntime.once`가 `RES-0006`), worker는 **행을 claim하기 전에** 다시 거부한다. 그래서 `ready` admission과 `pending` intent는 그대로 남고 소비되지 않는다. 이미 claim된 행은 그 dispatch의 결말(완료 또는 격리 기록)을 따른다 — 끄는 것이 **진행 중인 dispatch를 되돌리지는 않는다**.

**확인까지 한 쌍으로 본다**: `printenv`가 `1`을 그대로 출력하면 **아직 꺼지지 않은 것**이다(재시작이 안 됐거나 다른 서비스를 재시작했다). 그때는 §3-3의 3·4행을 `worker`에 대해 다시 실행한다.

### 5-2. 넓은 끄기: tenant kill switch (**2인 승인 필요**)

실행 자체를 멈춰야 하는 상황이면 kill switch가 정본이다. 제안 → challenge → **서로 다른 두 사람의 승인** → 실행이고, 모든 호출에 `Idempotency-Key`가 필요하다.

```bash
# 1) 현재 상태와 version을 읽는다(승인과 실행이 같은 version을 가리켜야 한다).
curl -sS -H "Authorization: Bearer $TOKEN" "$CP/v1/operations/kill-switch"

# 2) 제안 — operation은 kill, nodeId는 null이다.
curl -sS -X POST "$CP/v1/operations/containment-approvals" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d '{"operation":"kill","nodeId":null,"expectedVersion":<version>,"reasonCode":"incident"}'

# 3) 승인자마다: challenge로 nonce를 받고 decision으로 승인한다(요청자 본인은 승인에 쓰이지 않는다).
#    decision도 Idempotency-Key가 필수다 — 정본 API가 그 헤더를 검증하므로 없으면 422다.
curl -sS -X POST "$CP/v1/operations/containment-approvals/<approvalId>/challenge" \
  -H "Authorization: Bearer $APPROVER_TOKEN" -H 'Content-Type: application/json' -d '{}'
decision_key=$(uuidgen)   # 재시도할 때는 이 key와 body를 그대로 다시 쓴다
curl -sS -X POST "$CP/v1/operations/containment-approvals/<approvalId>/decision" \
  -H "Authorization: Bearer $APPROVER_TOKEN" -H "Idempotency-Key: $decision_key" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve","contentDigest":"<contentDigest>","nonce":"<nonce>"}'

# 4) 실행.
curl -sS -X POST "$CP/v1/operations/kill-switch" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d '{"expectedVersion":<version>,"reasonCode":"incident","approvalId":"<approvalId>"}'
```

`reasonCode`는 `maintenance`·`incident`·`operator_request` 중 하나다. `requiredApprovals`는 **2**로 고정이고, 같은 사람의 두 번째 표는 받아들여지지 않는다.

**`Idempotency-Key` 규칙**: 제안·**각 승인자의 decision**·실행 **세 종류 모두**에 필요하다(정본 API가 각 경로에서 그 헤더를 검증한다). 재시도할 때는 **같은 key와 같은 body**를 다시 보낸다 — 같은 key에 다른 내용이면 `IDEM-0001`로 거부된다. 승인자가 둘이면 **각자 자기 key**를 쓴다.

### 5-3. 격리된 node — **되돌리지 않고 기록한다**

제품 경로가 node를 격리했다면 그것은 고장이 아니라 **기록된 미화해 상태**다. 격리는 "잃은 경쟁을 적을 수 있었다"는 증거이고, 해제는 그 화해를 **사람이 선언하는 행위**다.

```sql
-- 무엇이 왜 기록됐는가. 되돌리기 전에 먼저 읽는다.
SELECT r.operation, r.node_id, r.reason_code, r.created_at,
       (r.response IS NOT NULL) AS answered
FROM inv.containment_requests r
WHERE r.tenant_id = :'tenant' AND r.operation IN ('drain', 'resume')
ORDER BY r.created_at DESC
LIMIT 20;

-- 그리고 그 격리를 만든 사건.
SELECT run_id, created_at, payload ->> 'nodeId' AS node_id,
       payload ->> 'reasonCode' AS reason_code
FROM inv.outbox
WHERE tenant_id = :'tenant' AND event_type = 'inv.build.node_quarantined'
ORDER BY created_at DESC
LIMIT 10;
```

해제는 **`resume`이고 같은 2인 승인 경로**다(§5-2의 세 단계에서 `operation`을 `resume`, `nodeId`를 그 node로 바꾼다). 마지막 실행만 다르다:

```bash
curl -sS -X POST "$CP/v1/nodes/<nodeId>/resume" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d '{"expectedVersion":<version>,"reasonCode":"operator_request","approvalId":"<approvalId>"}'
```

**해제 전에 성립해야 하는 것**: node가 `draining` 또는 `quarantined`이고 **settled**여야 하며(활성 lease·미전달 사건·미정산 run이 없어야 한다 — `GET /v1/nodes/<nodeId>/control`이 그 세 수를 적는다), epoch가 화해돼 있어야 한다(`NODE-0033`). `resume`은 **quarantine 화해의 유일한 경로**이고, 그 요청은 actor·사유·요청 id와 함께 `inv.containment_requests`에 **durable하게 남는다**.

**기록 원칙 — 되돌리지 말고 적는다.** 격리된 행(`status = 'quarantined'`)과 소비된 claim은 DB가 바꾸지 못하게 막는다. 운영자가 할 일은 그 상태를 **지우는 것이 아니라** (1) 왜 그렇게 됐는지 §4의 쿼리로 읽고, (2) 노드에서 무엇이 남았는지 확인하고, (3) 화해를 2인 승인으로 선언하고, (4) 그 과정을 이 문서가 아니라 **History/인시던트 기록**에 남기는 것이다.

---

## 6. `[sudo]`가 필요한 단계

| | 단계 | 왜 sudo인가 |
|---|---|---|
| 1 | 노드 사용자에게 docker 그룹 권한 부여 | 그 권한 자체가 호스트 권한 변경이다. [[사용자 조치 단일 체크리스트]] §5가 정본이다 |
| 2 | rootless BuildKit 설치·user 단위 등록, `systemd-logind` lingering 활성화 | 시스템 패키지·user 서비스 영속화 |
| 3 | `kernel.unprivileged_userns_clone`·AppArmor/seccomp 프로파일 조정이 필요한 경우 | 커널·보안 프로파일 변경. 필요 여부는 §2-3의 출력이 말한다 |
| 4 | 노드 방화벽에서 CP → node agent 포트 개방 | 네트워크 정책 변경 |

이 네 가지 중 **어떤 것도 이 문서가 실행하지 않는다.** 필요하면 사용자에게 명령과 이유를 전달하고 기다린다.

---

## 7. 이 PC에서 확인한 것, 그리고 확인하지 못한 것

측정 시각 **2026-10-02 21:0x~22:0x (+09:00)**. 측정 tree는 이 branch이고, **`#331`(카드 232, `0060`과 `worker.py`의 composition root)을 포함한 train 26 후보를 merge한 뒤** 다시 측정했다. **아래는 과거 측정이고 현재 상태의 주장이 아니다** — 판정은 §1의 명령을 사용자가 실행한 출력이다.

| 확인 | 방법 | 결과 |
|---|---|---|
| §1-C의 gate가 **0059만 있는 DB를 거부**하는가 | disposable DB를 `alembic upgrade 0059_build_execution_intents`까지만 올리고 gate 실행 → 그 다음 `head`까지 올려 다시 실행 | **0059: `admissions_table = False`(거부)**. head: `db_head = 0060_build_execution_admissions` · 두 표 모두 `True` · `tools/migration_graph.py --head`와 **문자 그대로 일치**. 갓 만든 DB의 `epoch_rows`는 `0`(운영자 프로비저닝 항목) |
| §4-0의 admission 쿼리 4개 | 같은 head DB에 psycopg로 **실제 실행** | 4/4 실행 성공(행 0개 — 아직 producer 입력이 없다). `inv.build_execution_admissions`의 `status`·`retry_count`·`next_attempt_at`·`promoted_at`·`quarantined_at`과 `inv.build.intent_enqueued` 사건이 그 head에 존재함을 확인 |
| §4-1~§4-6의 SQL 10개 | 같은 방식으로 **실제 실행**(placeholder만 psycopg 형식 `%(tenant)s`로, `LIKE 'inv.build.%'`의 `%`는 psycopg 규칙대로 두 번 — 문장과 열 이름은 위와 같다) | 10/10 실행 성공(행 0개) |
| §3-0의 **아홉 key 엄격 요구** | `configured_tenant_product_runtime()`에 **여덟 key**(`nodeId` 누락)와 **열 key**(여분 1개)를 실제로 넘겨 호출 | 둘 다 `ValueError: Exact build execution configuration required` — **DB에 닿기 전에** 거부한다 |
| §3-1의 worker 서비스 정의가 **배포본에 없음** | `grep -n "INV_WORKER_CONFIG\|worker" docker-compose.prod.yml` | 결과 **0건**. `INV_WORKER_CONFIG`는 `deploy/CONFIGURED-SERVER.md`의 서술에만 있고 compose 정의에는 없다 → §3은 **BLOCKED** |
| ~~§3-1의 worker 서비스 YAML~~ | (r1에서 `yaml.safe_load`로 확인했다) | **r2에서 그 블록을 지웠다** — 이 문서가 **지어낸** 정의였고 `tools/prepare_server_config.py`의 실제 지원 범위와 달랐다. 정의는 **카드 241**이 가져온다(§3-1) |
| §2-3의 digest 고정 이미지 출처 | `.github/workflows/s08-buildkit-reference.yml`에서 `BUILDKIT_ROOTLESS_IMAGE`를 읽는 명령 실행 | `docker.io/moby/buildkit@sha256:…` 형식(digest 고정)을 돌려준다 |
| `tools/prepare_server_config.py`의 범위 | `collect()`를 읽었다 | `api.json`과 **그 파일이 참조하는 파일만** config volume에 넣는다(`identity.jwks_file`·`configurationReadiness`·`workspace`의 참조). **`worker.json` 경로는 없다** → §3-1의 두 번째 측정 |
| `--once`가 무엇을 하는가 | `services/control-plane/src/inv/worker.py`의 `--once` 분기를 읽었다 | `build_runtime.once(tenant)`와 `worker.once(tenant)`를 **실제로 호출한다** — 구성 검사가 아니라 **한 tick 실행**이다. 그래서 §3-3의 확인용 명령에서 **빼고** 경고를 달았다 |
| 제품 loop의 로그 | `consume_builds()`와 `build_execution_worker.py`의 `LOGGER` 사용을 읽었다 | loop는 **tick마다 아무것도 기록하지 않는다**(`outcome`을 변수에만 담는다). 그 경로의 로그는 **시작 실패 문장**과 `build intent could not be safely requeued` **하나**뿐 → §4-6을 `worker` 대상으로 바꾸고 그 사실을 적었다 |
| §1-A·B·E의 `grep` 명령 | 이 checkout에서 실제 실행 | **A는 네 자리**(`build_execution.py` 정의와 service 검사, `worker.py:78` 구성 분기, `build_product_runtime.py:330` tick, `build_execution_worker.py:443` claim 전)에서 줄이 나왔다. **B는 "선언 없음"**(worker 서비스도 `INV_WORKER_CONFIG`도 compose에 없다). E의 `NodeAgentReceipts(` 제품 호출은 **`build_product_runtime.py` 한 곳**(= `#331`이 가져온 composition) |
| §1-D (4)의 착지 gate | `gh pr view` + `git ls-remote` + `git merge-base --is-ancestor` 실제 실행 | 여섯 PR 모두 **`OPEN`**(merge commit 없음)이고 착지 tip의 조상이 아니다 → 운영 기준으로는 **`BLOCKED`**. 이 tree는 후보 tree이므로 §1-D의 "연습" 판정이다 |
| 셸 블록 문법 | 이 문서의 모든 bash 블록을 추출해 `bash -n` | exit 0 |
| `tools/run_buildkit_rootless_roundtrip.py --help` · `tools/run_buildkit_rootless_lane.sh` | 실제 실행 · `bash -n` | 사용법 출력 · exit 0. lane이 요구하는 여섯 환경 변수를 §2-3에 그대로 적었다 |

**확인하지 못한 것** — 모두 사내망 노드나 살아 있는 배포가 필요하고, 이 PC에서 실행하면 거짓이 된다:

- §2의 노드 명령(`docker ps`·`openssl`·`buildctl debug workers`·`systemctl --user`) — **노드에서만** 의미가 있다. 문법만 확인했다.
- §3-2·§3-3의 환경 파일 쓰기와 재시작, §3-3 5행의 상태 확인, §5-1의 `printenv` — **그 프로세스를 돌릴 배포 정의가 이 tree에 없으므로**(§3-1) 실행할 대상이 아직 없다. **카드 241이 그 정의를 가져온 뒤** 처음 켜는 사람이 그 출력을 남긴다.
- **worker 서비스 이름·image·mount 경로와 `worker.json` 준비 명령** — 이 문서는 **지어내지 않는다**(r2). 카드 241의 정의가 정본이고, 그때 §1-B·§1-D(2)·§3-1·§3-3을 그 이름으로 다시 읽는다.
- §5의 `curl` 호출 — 살아 있는 CP와 **두 사람의** 토큰이 필요하다. 요청 본문과 **필수 헤더**는 정본 코드·schema에서 읽어 적었다(`app.py`의 decision 경로가 `Idempotency-Key`를 검증한다 — 그래서 §5-2의 decision 예제에 그 헤더가 있다).
- **제품 dispatch 한 번의 실제 관측** — admission·intent·claim·Evidence를 실제로 만드는 것은 producer와 worker 프로세스이고, 그 배포 정의가 없다. §4의 쿼리는 **그 경로가 생긴 뒤 처음 켜는 사람이 실행할 것**이고, 쿼리 자체는 위에서 실제로 돌려 확인했다.
- `0060`의 `ready`/`quarantined` **표본 행**을 만들어 §4-0의 출력을 눈으로 보는 것 — admission insert guard가 세 문서의 tenant/project/정책 결속과 digest 재계산을 요구하므로, 손으로 만든 행이 아니라 **producer가 넣은 행**이어야 의미가 있다. `#331`의 real-PG 시험이 그 경로를 덮고, 이 문서는 **쿼리가 그 head에서 실행된다는 것까지** 확인했다.

---

## 8. 다음 첫 행동

1. **Codex**: 이 절차의 검토. 특히 §3-1(배포 설정에 변수를 선언하는 PR의 소유자)과 §1-D의 PR 목록이 이 경로의 실제 전제 집합인지.
2. **배포 설정 담당**: `docker-compose.prod.yml`의 `control-plane`(그리고 worker 서비스가 생길 때 그 서비스)에 `INV_BUILDKIT_PRODUCT_ENABLED=${INV_BUILDKIT_PRODUCT_ENABLED:-0}` 한 줄. 그것이 없으면 사용자는 켤 수 없다.
3. **사용자**: §1을 실행해 A~G의 출력을 남긴다. 그 출력이 "무엇이 막고 있는가"의 정본이고, 이 문서를 다시 쓰게 만드는 입력이다.
4. **Claude**: `#331`이 착지하면 §1-D·§4를 그 tree에서 다시 돌려 이 문서를 갱신한다(쿼리는 그대로일 것이고, 바뀌는 것은 §7의 측정이다).
