---
doc_id: "RUNBOOK-S08-BUILDKIT-PRODUCT-ENABLE-V1"
title: "S08 BuildKit 제품 dispatch 활성화 절차 — 켜기 전에 확인할 것, 켜는 위치와 순서, 켠 직후 관측, 끄기와 격리 해제 (카드 238)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "user"
updated: "2026-10-02T21:25:08+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "843d283c"
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
| **A** | 배포된 코드가 그 설정을 **두 곳에서** 읽는다(service와 worker) | 켜도 경로가 열리지 않는다 |
| **B** | 배포 설정이 그 변수를 **프로세스에 전달**한다 | 호스트에 export해도 컨테이너는 보지 못한다 |
| **C** | DB가 **intent queue가 있는 migration head**다 | producer가 행을 넣을 표가 없다 |
| **D** | 그 queue를 소비하는 **worker loop와 producer가 배포본에 있다** | 행이 쌓이고 아무도 dispatch하지 않는다 |
| **E** | transport가 **durable quarantine 채널과 함께** 구성된다 | 모든 dispatch가 `RES-0006`으로 거부된다 |
| **F** | 대상 node가 **online·heartbeat 신선·channel epoch 일치**다 | lease·probe 단계에서 거부된다 |
| **G** | 배포 SHA에서 **hosted 시험이 green**이다 | 켜는 것이 아니라 먼저 그 실패를 본다 |

### A. 코드가 그 설정을 읽는가

```bash
grep -n "INV_BUILDKIT_PRODUCT_ENABLED" \
  services/control-plane/src/inv/build_execution.py \
  services/control-plane/src/inv/build_execution_worker.py
```

**판정**: 두 파일 모두에서 줄이 나와야 한다. `build_execution.py`가 `PRODUCT_ENABLE_SETTING`/`PRODUCT_ENABLE_VALUE`를 정의하고 `BuildExecutionService`가 dispatch마다 그 값이 **정확히 `1`** 인지 본다. `build_execution_worker.py`는 **queue 행을 claim하기 전에** 같은 검사를 한다 — 꺼져 있다는 사실을 알기 위해 durable 행을 소비하지 않기 위한 것이다. 즉 **검사는 두 번** 일어나고, 둘 다 같은 값을 본다.

### B. 배포 설정이 그 변수를 프로세스에 전달하는가

```bash
grep -n "INV_BUILDKIT_PRODUCT_ENABLED" docker-compose.prod.yml \
  || echo "선언 없음: 이 compose로 뜬 컨테이너는 이 변수를 볼 수 없다"
```

**판정**: `control-plane` 서비스의 `environment:` 목록에 그 이름이 있어야 한다. compose의 `environment:`는 **열거된 이름만** 컨테이너로 전달하므로, 호스트 셸에서 `export`하거나 `.env`에 적어도 **열거되지 않은 변수는 들어가지 않는다**. 선언이 없으면 §3-1이 먼저다.

### C. DB가 intent queue가 있는 head인가

```bash
# 비밀을 출력하지 않는다: 접속 정보는 운영자 환경에서 온다.
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d saintvision -At -c \
  "SELECT (SELECT version_num FROM alembic_version) AS head,
          (to_regclass('inv.build_execution_intents') IS NOT NULL) AS intents_table,
          (SELECT count(*) FROM inv.control_epoch WHERE singleton) AS epoch_rows"
```

**판정**: `intents_table`이 `t`이고 `epoch_rows`가 `1`이어야 한다. `head`는 배포본의 `ls migrations/versions/ | tail -1`과 **같은 revision**이어야 한다 — 다르면 배포본과 DB가 다른 tree다. epoch 행이 없으면 커널의 모든 트랜잭션이 `LEASE-0004`로 실패한다([[서비스-시작-재시작-복구-절차]] §3-2가 정본이다).

### D. queue를 소비하는 worker loop와 producer가 배포본에 있는가 — **런타임으로 읽는다**

이 전제는 **PR 하나의 상태**에 달려 있고, 그 상태는 바뀐다. 그래서 문서가 "있다/없다"를 적지 않고 **읽는 명령**을 적는다.

```bash
# 1) 배포본에 worker를 구성하는 제품 코드가 있는가 (시험 제외)
grep -rn "BuildExecutionWorker(" --include=*.py services | grep -v "/tests/" \
  || echo "worker를 구성하는 제품 코드 없음"

# 2) 그 worker를 돌리는 프로세스/서비스 정의가 있는가
grep -rn "build_execution_worker\|build-worker" docker-compose.prod.yml deploy/ \
  || echo "worker 서비스 정의 없음"

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

**판정**: (1)과 (2)가 모두 결과를 내고, (3)에서 **그 여섯이 전부 `IN-TREE`** 여야 한다. 하나라도 `NOT-IN-TREE`면 그 PR이 가져오는 조각이 배포본에 없다는 뜻이고, 그 조각이 producer나 worker loop이면 **켜도 아무 일도 일어나지 않는다**(행이 쌓이지도 않거나, 쌓이고 소비되지 않는다). PR 번호 목록은 S08 경로를 만든 작업들이다 — 계약(`#311`), 제품 caller(`#312`), quarantine channel(`#318`), intent queue(`#323`), claim fencing(`#327`), worker loop과 producer(`#331`).

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

---

## 3. 켜기 — 위치, 값, 순서

**§1의 A~G가 모두 성립한 뒤에만 이 절을 실행한다.** 하나라도 아니면 켜는 것이 아니라 그 항목을 먼저 해결한다.

### 3-1. 변수를 **배포 설정에** 선언한다 (§1-B가 "선언 없음"이었다면 필수)

`docker-compose.prod.yml`의 `control-plane` 서비스 `environment:`에 한 줄을 더한다. 값은 **정확히 `1`** 이어야 하고, 다른 값(`true`, `yes`, `01`)은 꺼진 것과 같다.

```yaml
    environment:
      # 기존 줄들 ...
      - INV_BUILDKIT_PRODUCT_ENABLED=${INV_BUILDKIT_PRODUCT_ENABLED:-0}
```

**기본값을 `0`으로 두는 형태를 쓴다** — 그러면 변수를 주지 않은 환경에서 켜지지 않고, 켜는 것은 운영자의 환경 파일 한 줄이 된다. 이 파일은 저장소에 있으므로 **이 변경은 PR로 들어간다**(소유자: Codex 또는 배포 설정 담당). 사용자가 노드에서 직접 고치면 다음 배포에서 사라진다.

### 3-2. 운영자 환경 파일에 값을 넣는다

```bash
# CP 호스트에서. 이 파일은 저장소에 없고 operator-private이다.
printf 'INV_BUILDKIT_PRODUCT_ENABLED=1\n' >> /path/to/deployment/.env
grep -c '^INV_BUILDKIT_PRODUCT_ENABLED=1$' /path/to/deployment/.env   # 1이어야 한다
```

### 3-3. 재시작 순서

순서가 있다. **DB → node agent → control-plane → (worker)** 이고, 각 단계는 다음 단계의 전제를 만든다.

| 순서 | 무엇 | 명령 | 왜 이 순서인가 |
|---|---|---|---|
| 1 | PostgreSQL이 살아 있는지 **확인만** | `docker compose -f docker-compose.prod.yml ps postgres` | 재시작하지 않는다. 나머지 실패는 거의 전부 이것의 증상이다 |
| 2 | node agent가 떠 있는지 **확인만** (§2-1) | `docker ps --filter "name=saintvision-<node>"` | 컨테이너를 다시 만들면 journal·epoch 화해가 필요해진다 |
| 3 | control-plane **재시작** | `docker compose -f docker-compose.prod.yml up -d --no-deps control-plane` | 환경 변수는 **프로세스 시작 시점**에 읽힌다(`BuildExecutionService`는 생성 시 `os.environ`를 복사한다). 재시작 없이는 켜지지 않는다 |
| 4 | 읽기 확인 | `docker compose -f docker-compose.prod.yml exec -T control-plane printenv INV_BUILDKIT_PRODUCT_ENABLED` | `1`이 출력돼야 한다. 다른 값이면 §3-1·§3-2를 다시 본다 |
| 5 | worker 프로세스 재시작(그 서비스가 배포본에 있을 때) | §1-D (2)가 찾은 서비스 이름으로 `up -d --no-deps <service>` | worker도 **claim 전에** 같은 변수를 보고, 그 값도 시작 시점에 복사된다 |

**`[sudo]` 아님**: 위 네 명령은 docker 그룹 권한으로 충분하다. 그 그룹 권한 자체를 부여하는 일이 `[sudo]`다(§6).

---

## 4. 켠 직후 관측 — 한 번의 dispatch를 끝까지 따라간다

아래 쿼리는 **순서대로** 한 번씩 돌린다. `:tenant`와 `:run`은 운영자의 실제 값이다(`psql -v tenant=... -v run=...` 또는 셸 변수). **이 절은 값을 바꾸지 않는다 — 읽기만 한다.**

### 4-1. 첫 intent가 들어왔는가

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
# reason code와 사건 이름만 본다. payload 전체를 출력하지 않는다.
docker compose -f docker-compose.prod.yml logs --since 30m --no-color control-plane \
  | grep -E "RES-0006|IDEM-0001|NODE-00(15|32|33)|inv\.build\.(dispatch_completed|node_quarantined|quarantine_preflight_unavailable)" \
  | tail -40
```

**읽는 법**: `RES-0006`이 반복되면 제품 경로가 **capability 부족으로 거부**하고 있다(§1-E). `NODE-0033`은 epoch·node 상태(§1-F), `NODE-0032`는 인증서 pin(§2-2)이다.

---

## 5. 이상하면 — 즉시 끄기, 그리고 격리는 해제가 아니라 기록이다

### 5-1. 좁은 끄기: 제품 dispatch만 끈다 (승인 불필요, 운영자 단독)

```bash
# 값을 0으로 바꾸고 control-plane(과 worker)을 재시작한다. 변수를 지우는 것도 같은 효과다.
sed -i 's/^INV_BUILDKIT_PRODUCT_ENABLED=1$/INV_BUILDKIT_PRODUCT_ENABLED=0/' /path/to/deployment/.env
docker compose -f docker-compose.prod.yml up -d --no-deps control-plane
docker compose -f docker-compose.prod.yml exec -T control-plane printenv INV_BUILDKIT_PRODUCT_ENABLED
```

**효과**: worker는 **행을 claim하기 전에** 거부하므로 pending 행은 그대로 남고 소비되지 않는다. 이미 claim된 행은 그 dispatch의 결말(완료 또는 격리 기록)을 따른다 — 끄는 것이 **진행 중인 dispatch를 되돌리지는 않는다**.

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
curl -sS -X POST "$CP/v1/operations/containment-approvals/<approvalId>/challenge" \
  -H "Authorization: Bearer $APPROVER_TOKEN" -H 'Content-Type: application/json' -d '{}'
curl -sS -X POST "$CP/v1/operations/containment-approvals/<approvalId>/decision" \
  -H "Authorization: Bearer $APPROVER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"decision":"approve","contentDigest":"<contentDigest>","nonce":"<nonce>"}'

# 4) 실행.
curl -sS -X POST "$CP/v1/operations/kill-switch" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d '{"expectedVersion":<version>,"reasonCode":"incident","approvalId":"<approvalId>"}'
```

`reasonCode`는 `maintenance`·`incident`·`operator_request` 중 하나다. `requiredApprovals`는 **2**로 고정이고, 같은 사람의 두 번째 표는 받아들여지지 않는다.

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

측정 시각 **2026-10-02 21:0x~21:4x (+09:00)**, 측정 tree는 이 branch의 base(train 25 후보)다. **아래는 과거 측정이고 현재 상태의 주장이 아니다** — 판정은 §1의 명령을 사용자가 실행한 출력이다.

| 확인 | 방법 | 결과 |
|---|---|---|
| §4의 SQL 10개 전부 | **disposable migrated DB**(alembic head)에 psycopg로 **실제 실행**(placeholder만 psycopg 형식 `%(tenant)s`로 바꾸고 `LIKE 'inv.build.%'`의 `%`를 psycopg 규칙대로 두 번 적었다 — 문장과 열 이름은 위와 같다) | 10/10 실행 성공(행 0개 — 아직 dispatch가 없다). 표·열 이름이 그 head에 존재함을 확인 |
| §3-1의 YAML 한 줄 | `docker-compose.prod.yml` 사본에 넣고 `yaml.safe_load` | parse 성공, `control-plane`의 `environment`에 그 이름이 들어온다 |
| §1-A·B·D·E의 `grep` 명령 | 이 checkout에서 실제 실행 | A는 두 파일에서 줄이 나왔다. **B는 "선언 없음"**, D의 (1)·(2)는 "없음", E는 "없음" — 즉 이 tree에서는 §3-1이 선행이다 |
| §1-D (3)의 PR 루프 | `gh pr view` + `git merge-base --is-ancestor` 실제 실행 | `#311`·`#312`·`#318`·`#323`·`#327`은 **IN-TREE**, `#331`은 **NOT-IN-TREE**(모두 `OPEN`) |
| 셸 블록 문법 | 이 문서의 모든 bash 블록을 추출해 `bash -n` | exit 0 |
| `tools/run_buildkit_rootless_roundtrip.py --help` | 실제 실행 | 사용법이 출력된다(§2-3의 명령이 존재함을 확인) |

**확인하지 못한 것** — 모두 사내망 노드가 필요하고, 이 PC에서 실행하면 거짓이 된다:

- §2의 노드 명령(`docker ps`·`openssl`·`buildctl debug workers`·`systemctl --user`) — **노드에서만** 의미가 있다. 문법만 확인했다.
- §3의 재시작과 §3-2의 환경 파일 쓰기 — 운영 조치이므로 실행하지 않았다.
- §5의 `curl` 호출 — 살아 있는 CP와 두 사람의 토큰이 필요하다. **요청 본문의 필드는 저장소의 정본 schema(`contracts/v1alpha1/core.schema.json`의 `ContainmentProposalInput`·`ContainmentDecisionInput`·`ContainmentInput`)에서 읽어 적었고**, 호출 자체는 하지 않았다.
- **제품 dispatch 한 번의 실제 관측** — `#331`이 배포본에 없고 transport wiring도 없으므로(§7의 표) 이 tree에서는 **켜도 dispatch가 일어나지 않는다**. §4는 그 경로가 생긴 뒤 **처음 켜는 사람이 실행할 쿼리**이고, 쿼리 자체는 위에서 실제로 돌려 확인했다.

---

## 8. 다음 첫 행동

1. **Codex**: 이 절차의 검토. 특히 §3-1(배포 설정에 변수를 선언하는 PR의 소유자)과 §1-D의 PR 목록이 이 경로의 실제 전제 집합인지.
2. **배포 설정 담당**: `docker-compose.prod.yml`의 `control-plane`(그리고 worker 서비스가 생길 때 그 서비스)에 `INV_BUILDKIT_PRODUCT_ENABLED=${INV_BUILDKIT_PRODUCT_ENABLED:-0}` 한 줄. 그것이 없으면 사용자는 켤 수 없다.
3. **사용자**: §1을 실행해 A~G의 출력을 남긴다. 그 출력이 "무엇이 막고 있는가"의 정본이고, 이 문서를 다시 쓰게 만드는 입력이다.
4. **Claude**: `#331`이 착지하면 §1-D·§4를 그 tree에서 다시 돌려 이 문서를 갱신한다(쿼리는 그대로일 것이고, 바뀌는 것은 §7의 측정이다).
