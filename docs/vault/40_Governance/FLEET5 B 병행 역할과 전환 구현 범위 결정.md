---
doc_id: "GOV-FLEET5-B-BOOTSTRAP-SCOPE-20261106"
title: "FLEET5 B 병행 역할과 전환 구현 범위 결정"
version: "1.4.5"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-06T22:47:40+09:00"
source_of_truth: "Git"
---

# 실제 검토 이후의 범위 결정

통합72028은 실제255cfa37 source/packet ACCEPT와8개CI/12job 성공을 받았다. 배포 전 C-L1 검토시각 정정 문서를 포함한 최종 납품·작은 독립 검토가 필요하며 별도 시험 보완을72028CI로 차용하지 않는다. 제품 전체·운영 인수는 아니다.

전환5d0753은 실제a81f7330에서 이전 Low/Info를 닫았고 V3-L1~L3의 cohort target·nonproof join·복원 head/epoch 정합성 조건을 남겼다. 기존 Codex를 이후 계약·고난도 구현 owner로 지정하되 현재 작업은 v4 문서/schema/fixture 보완이다. 실제 보완 검토 전 canonical 등록·helper/API/runtime 구현은 허용하지 않는다.

BroadB100f는 실제2bb959a3에서 B1 High/B2~B5 Medium 수정 필요다. Root는 B-FRESH1과 B-MIG1 DESIGN-FIRST를 선택했다. 새5Node 동일 병행 역할을 유지하며 Windows 물리CP의 새 역할은 Linux-native 파일시스템·지원 Docker Engine/default socket을 가진 별도 CP-colocated Linux context를 설계 대상으로 한다. 관리 Linux VM/WSL2 guest의 identity·실행 adapter·소스 containment·독립 kernel 측정·API·접속 capability를 계약으로 닫는다. 실제 guest가 준비됐거나 설치됐다는 뜻이 아니다. Windows drive mapping 또는 mixed cohort로 자동 대체하지 않는다. CP 겸임5번의 S05/S07 독립 장애 영역 제외는 그대로다.

D2는 operator-only role-admission 증거 ABI와 현재(C,R,policy,exe/root/instance) join 무효화·전체caller 분류, D3는 pin전 side-effect-free 검증과 부분 pin exact-config forward replay, D4는 intent부터 전cohort final 증거까지 격리, 당시 D5는 fence→sorted nodes→sorted contributions→sorted channels→admission/nonce/evidence의 B lock순서 제안, D6는 Codex owner/별도 Claude 실제 검토다. policyB 승인·revoke 변화·추가 floor·workload mount검사와 A1~A16 증거를 revised contract로 닫는다.

이 문서 1.0.0의 당시 B 승인 범위는 revised DOCS였다. 코드·ABI/ADR 등록·장비 작업은 실제 수정 검토 뒤 gate에 따라 진행한다. guest/context의 물리 준비는 검토 가능한 구체 계획과 실제 권한·환경 증거가 필요하다. 기존 WindowsDocker/파일럿/업무 컨테이너를 변경하거나 키를 이동하지 않았다. 이미 받은 프로젝트 승인을 반복 요청하지 않는다.

정확한 Root 지시·원본 review refs·reply ID는 implementation-scope-decision-root.json Evidence에 보존했다. 모든 실제 binding NULL/HOLD, B/전환 실제 Go·crypto·Engine·장비 검증0, future40case NOTRUN이며 원래48-task/VFCL 집계는 바꾸지 않는다.


## 실제 rev2 검토 후 rev3 결정

실제 ac9182c3e3d606ec027c0be2e90e049ff50d54f1의 R1~R7 Medium과 Low를 읽었다. Docs42095556156과 Portal42095515359의 exact head·ref·전체 job 성공을 Root가 대조했다. 02cfd260은 수정 필요이고 부분 동결도 하지 않는다. Root reply msg_f7caf4c96b16의 구체 rev3는 DOCS/schema/static fixture 범위이며 B 코드·운영 등록 권한이 아니다.

D1을 관리되는 별도 커널 Linux VM과 자체 Engine으로 좁힌다. WSL2는 Desktop과 커널을 공유하므로 별도 검토되지 않은 대안이며 자동 fallback을 허용하지 않는다. 게스트 CPU·메모리·디스크와 호스트 여유 자원은 원시 측정값·관측 시각·장비 identity·계획 예산으로 확인한다. 계획 기본값 2 vCPU/4 GiB/20 GiB와 호스트 여유 2 GiB/10 GiB는 실제 확보 증거가 아니다. 현재 자원 부족은 RESOURCE_UNAVAILABLE이고 실제 budget·binding은 NULL/HOLD다.

D5는 mandatory Database.transaction의 epoch guard를 존중하여 control_epoch를 첫 잠금으로 정정한다. 이후 routing/fence, 정렬된 inv.nodes, 정렬된 public node/contribution, channels, role/current, 명시된 business/run/grant/nonce/evidence/ledger 순서다. 실제 모든 callsite·FK·RLS·외부 transaction의 잠금 모드를 조사하고 discovery 뒤 재검증한다. DB row lock을 잡은 채 Node I/O를 하지 않으며 bounded timeout/abort와 실제 PG 검증을 별도로 요구한다.

rev3는 protected operator-release authority와 제한된 online use key 분리, Node-visible release/delegation chain, 별도 authenticated observe/reconcile/safety lane, released steady-state per-Node READMIT_SAME_CONFIG, named DB principals/grants, 부분 변경 중 revoke/epoch/expiry의 QUARANTINE, generation-bound memory replay와 닫힌 HostConfig allowlist를 명시해야 한다. 자세한 원문과 실제 reply는 b-rev2-root-revision3-decision.json이다. 기존 승인 재요청은 하지 않는다.

전환 v5의 실제 6b12d3ab 독립 검토와 별도 Root 설계 등록은 [[FLEET5 전환 v5 계약 동결과 구현 범위]]에 기록한다. B 미수락 범위와 전환 K1 구현 범위를 구분하며 실제 장비·전체 제품 인수는 여전히 미완료다.


## 실제 rev3 판정과 per-Node 승인 갱신 결정

최종 e9932f30은 실제638109ab 검토/Docs42108948613의 판정에서 REVISION REQUIRED다. R1~R7의 방향과 기존 Low는 닫혔으나 누락된 transitive lock/ORM census, 24시간 승인 갱신 경로, 새 gate/key-delivery/ObservationScope 규격의3Medium과6Low를 남겼다. Root가 actual review와 exact head/ref/alljobs를 확인하고 reply msg_94ff5bb7a0e6로 좁은 rev4 DOCS/schema/static 범위를 지정했다. B 부분 동결·코드·등록·실장비 인수는 아직 허용하지 않는다.

같은 고정 설정의 승인은 PC별 protected APPROVAL_RENEW_SAME_CONFIG로 갱신한다. 과거 서명 승인은 불변으로 남기고 새 priorApprovalHash·정확한 Node/cohort/config/epoch/C/R/root/image/executable/policy/floors·최대24시간 유효기간을 가진 새 승인을 current protected operator authority가 만든다. 다른 PC의 새 증거는 요구하지 않는다. 첫/cohort mutation 활성화만 전체5대 조건이다. 기존 승인 시각 만료만 발생한 경우에는 새 protected REAPPROVE_SAME_CONFIG를 별도로 정의하며 REFRESH/READMIT이 만료 승인을 재사용하지 않는다. 실제 operator grant/certificate/trust는 유효해야 하고 revoke·quarantine·부분변경·epoch/config/floor 변화·mutation fence는 이 경로로 우회하지 않는다. 계획의 역사적 설정 설명과 현재 실행 권한을 구분한다.

새 PC별 release/delegation·gate 전환·activation ledger·postcommit key delivery/possession receipt의 순서와 UNKNOWN 상태를 닫는다. ARM ack와 key challenge/PoP/보호된 delivery receipt는 닫힌 schema·목적/domain·writer/grant·fixture가 필요하다. ObservationScope는 CP-local nonbusiness 결과이며 ChannelProof나 admission이 되지 않는다. 실제 key custody/crypto/원격원자성이 증명됐다는 뜻은 아니다.

rev4 census는 helper/import/session alias의 transitive caller와 누락된 ORM 잠금까지 확대하고 known callsite를 빼면 실제 검사가 실패해야 한다. 권한 테이블에 runtime lock_sentinel UPDATE를 주는 방식은 철회하고 fixed-scope SECURITY DEFINER lock-only procedure로 정한다. 실제 role/RLS/search_path·canonical order와 writer별 EXECUTE matrix를 명시한다. context budget은 별도 protected context-budget-approver 역할/키/목적으로 제한하고 실제 key는 NULL이다. host·guest clockOffsetMillis와 uncertainty/source/freshness를 측정해 최대30초 skew 안인지 확인해야 하며 실제 clock은 변경하지 않는다.

NOT-YET-CASed member revoke의 C target alias, exact ledger reread 전후 lost response, 모든 writer/grant 검사와 실제 approval interval, READMIT의 새 generation 조건도 닫는다. 단순 counter/boolean·없는 ledger·상징적 서명은 진척이나 운영 성공의 근거가 아니다. delegation expiry와 acknowledged gate invalidation이 Node 측 use-key 권한의 실제 한계이며 CP300초 lease와 같다고 주장하지 않는다. 자세한 원문 지시는 b-rev4-root-decision.json이고 [실제 독립 검토 원문](https://github.com/egparadise/SaintVision-Invion/blob/638109ab211bdfab7646a07b375003a636b3a33b/docs/vault/30_Development/History/2026-11-06_06-00-00_KST_FLEET5_B_contract_rev3_e9932f30_%EB%8F%85%EB%A6%BD%EA%B2%80%ED%86%A0_Claude.md)은 고정 Git source다.


## 실제 rev4 판정과 rev5 쓰기·잠금·복구 결정

2a08284a의 실제 독립 검토14c7c936은 B4-M1/M2와 L1–L4의 수정 필요다. Root는 Docs42124324426의 exact head/ref/전체 job 성공과 실제 원문을 대조하고 reply msg_03544733c9f3로 rev5를 정했다. 이전 승인 갱신·gate/키 전달/scope의 닫힌 부분은 설계 증거로 보존하되 전체 B 계약의 부분 동결·코드·등록을 수락하지 않는다. 현재 범위는 고유 DOCS/schema/static/source-analysis 보완이다.

M1은 실제 SQL/ORM writer별로 procedure/principal/pool/column/전이 조건/transaction/잠금 계획을 전부 연결한다. 향후 공유 권한 테이블은 plain과 B 온라인 경로 모두 고정 범위 procedure를 통하며 broad legacy DML/SET ROLE로 우회하지 않는다. plain의 기존 동작과 일회용 bootstrap·Node 소유자 권한은 실제 DB profile을 확인하는 별도 wrapper로 보존한다. 지금 권한이나 제품을 변경한 것은 아니며 실제 refactor·두 경로 PG 검증은 설계 수락 이후의 별도 의무다.

실제 runtime quarantine은 인증된 해당 tenant/Node/epoch/operation의 거부만 증가시키는 좁은 procedure에 연결한다. 이를 허용하기 위해 quarantine 해제·claim 해제·물리 중지 성공을 허용하지 않는다. channel 최초 provision·revoke/C+1/audit와 다섯 evidence append의 실제 원자 경계도 빠짐없이 연결한다. enrollment/cert binding/heartbeat/lost/retirement를 구분하고 observation의 online 전이는 quarantine/draining/retired를 해제할 수 없다. storage contribution의 create/pending/activate/revoke/revoked_at는 실제 등록 소유자의 folder 동의·철회 권리를 보존한다. 일반 operator/project 등급이 소유자를 대신하지 않으며 기존 활성화는 별도 B storage admission이 아니다. 철회는 catalogue/folder를 삭제하거나 C/R/policy를 재설정하지 않는다.

M2의 진입점은 helper뿐 아니라 모든 canonical/matrix row locker다. constructor/instance/dotted import/SQL 상수는 실제 edge/table/mode로 해석하거나 UNKNOWN/BLOCK으로 남긴다. 필요한 알려진 경로에는 함수별 발견 대상·잠금·outer transaction·재검증·외부 I/O 경계를 명시한다. 순서는 control_epoch → tenant_controls → routing/fence → 정렬 transaction advisory key → 정렬 inv.nodes → public.nodes → contributions → channels → role/current → inv.projects → project_resource_limits → storage_budgets → shard_plans → approval_requests → runs → operator_grants → 명시 resource/claim/transfer/model/terminal → nonce/evidence/ledger/audit다. 늦게 발견한 앞 rank는 abort/replan하며 offline bootstrap/maintenance는 동시 B traffic 없는 별도 phase다.

NO KEY UPDATE/SHARE/KEY SHARE와 ORM read/key_share/skip_locked/nowait, advisory를 실제 PostgreSQL 모드로 구분한다. 고정 SQLAlchemy dialect의 격리 compile fixture와 진짜 source mutation으로 semantic record/edge/mode/계획 검출을 시험한다. 이전 stored JSON 비교 negative는 comparator 검사로 보존하며 실제 source 변조 시험으로 바꾸어 부르지 않는다. 실제 PG trace/동시성 시험은 여전히 미실행이다.

L1은 승인 계보의 어느 조상이든 명시적으로 revoke되면 모든 후손의 append/ARM/activation/delivery/refresh/token/current 경계에서 거부한다. 과거 조상의 시각 만료만으로 적법한 새 승인을 만료시키지는 않는다. L2는 invalidated gate ID와 release를 해당 Node/generation에서 terminal로 보존하고 release generation·expected prior record/hash·증가 sequence를 확인한다. 정확한 중복은 아직 일치하는 원래 ack를 반환할 수 있으나 과거 gate를 부활시키지 않는다. observe lane은 원래 durable record/ack와 nonce를 가진 새 서명 readback을 읽을 뿐 business를 허가하지 않는다. ack가 없거나 60초를 넘겨 정상 전이 증명이 안 되면 fenced/UNKNOWN의 B-RECOVERY1이다. 원래 ack에 새 시각을 붙이거나 자동 재ARM·일반 renew로 복구하지 않는다.

L3은 기존 protected operator-release anchor 뒤에 caller/purpose/scope를 강제하는 signing service를 둔다. delivery controller는 raw operator private key를 갖지 않으며 실제 postcommit/ARM/key/recipient/challenge에 결속된 KEY_DELIVERY_PREPARE/RECEIPT만 요청할 수 있다. APPROVAL/RELEASE/DELEGATION/GATE 요청은 서명 전에 거부한다. 별도 budget key와 실제 custody는 NULL이다. L4는 golden manifest 비교와 별도로 실제 writer/소유자/권한 불변식, oneOf branch별 부정 입력, 시간이 흐르는 expiry/revoke/fence/stale/lost ack 전이를 검사한다. 서명은 SYMBOLIC이며 실제 새 B Go/crypto/PG/Docker/crash/장비0, A1–A16 PENDING과 모든 real binding NULL/HOLD를 유지한다.

구체 지시 원문은 b-rev5-root-decision.json이며 실제 판정은 [고정 rev4 독립 검토](https://github.com/egparadise/SaintVision-Invion/blob/14c7c936e056c685e85ee8f34f6185aa27ed9a2c/docs/vault/30_Development/History/2026-11-06_07-45-00_KST_FLEET5_B_contract_rev4_2a08284a_%EB%8F%85%EB%A6%BD%EA%B2%80%ED%86%A0_Claude.md)다. K1의 새 temporal 코드/CI는 별도 카드이고 B 검증을 대신하지 않는다.


## 실제 rev5 판정과 rev6의 닫힌 상태·권한 결정

228e2a20은 실제8bac0838/Docs42137554199에서 B5-M1/M2와 L1–L5 수정 필요다. 현재34 writer/46 surface·335검사의 재현된 부분은 보존한다. Root는 원문과 exact head/ref/전체job을 확인하고 reply msg_17afe2db8b82로 좁은 rev6 DOCS/schema/static 범위를 지정했다. 부분 동결·B 코드·운영 등록은 아직 아니다.

PRE_IO obligation은 tenant/Node/epoch/operation별로 닫는다. 등록이 실제 I/O보다 먼저 commit되고 기존 signed body/nonce에 결속된 CP/adapter handle이 이를 증명한다. 보통 성공의 정확한 typed receipt는 원래 evidence/receipt transaction에서 CONFIRMED_OUTCOME으로 닫을 수 있다. ACTIVE receipt는 자원 claim을 유지하고, 이 상태만으로 cleanup·claim 해제·containment 해제를 허가하지 않는다. 오류/불명확은 PENDING 또는 UNCERTAIN으로 거부를 유지하고 UNCERTAIN은 보호된 physical proof 복구만 허용한다. 실제13개 plain reader와 B reader의 목적/동작을 명시하며 observe/safety는 별도 인증 아래 유지한다. 다른 Node의 obligation이 이 Node를 막지 않는다. draining·quarantine 등의 독립 거부 사실을 보존해 상태 projection 변경으로 더 강한 거부가 지워지지 않게 한다.

5426개의 name-collision BLOCK은 호출자의 타입·실제 import·DB 기록·transaction owner를 구분해 정정한다. 남은 unknown을 각 plan에 직접 연결하고 알려진 critical plan이 지원됨과 BLOCK됨을 동시에 주장하지 않는다. getattr·상태 전이 역전·ORM insert/setattr·동적/비정규 table SQL·사라진 stale rule도 인과 source fixture로 검사한다. 모든 새 B table과 anchor/child/tombstone/outbox의 rank/mode·키 순서를 같은 canonical 데이터로 닫는다.

Signing service 자체가 ARM/RELEASE/DELEGATION 등의 현재 승인·계보·tombstone·epoch/fence를 확인한다. 외부 signer가 있으면 준비 intent 뒤 조건부 issuance publication을 검증하며 DB lock을 네트워크 너머 유지하지 않는다. CP tombstone은 권한 있는 DB principal과 causal evidence/audit로 인증하는 unsigned record로 정한다. 존재하지 않는 Node tombstone consumer·별도 domain 주장을 제거하고, authoritative outbox와 기존 signed INVALIDATE/gate ACK/expiry 경계를 명시한다. SAFE caller는 보호된 service에서 정확한 INVALIDATE만 요청하며 ARM을 요청할 수 없다.

Root의 앞선 folder-confirmation 문구를 정정한다. 실제 plain activation은 등록 소유자와 revoked 여부만 확인하므로 그 동작을 보존한다. 새 folder/root 관측은 B-only readonly-root 승인에 추가하며 필요한 closed artifact/producer/rights/서명·검증자를 제안으로 명시한다. 사전 root identity 관측은 설치 후 readonly mount 증거를 대신하지 않는다. 실제72028에 이미 확인 artifact가 있다고 쓰지 않는다. 상세 지시는 b-rev6-concrete-root-decision.json이며 모든 실제 binding NULL/HOLD와 A1–A16 미실행을 유지한다.


## rev6 실제 검토 후 rev7의 효과 유형과 차단 범위 선택

실제 Claude ecbdaa3b/Docs42154177711는 B6-M1/M2와L1–L4를 남겼다. 서명 service 내부의 조건부 공개·unsigned CP tombstone와 기존 INVALIDATE outbox·B-only folder 관측의 authority/model은 설계상 닫혔다. Root는 msg_8b52dd815cae로 같은 담당자에게 한 번의 좁은 rev7 문서·schema·정적 source-plan 수정만 지시했다. 제품 구현·부분 동결·운영 인수는 허용하지 않았다.

기존의 모든 IO에 동일한 불확실성 복구를 적용하던 규칙을 이 절의 **효과 유형 A**로 정정한다. SIDE_EFFECT는 불확실하면 독립된 보호 복구를 유지한다. IDEMPOTENT_SAFETY는 현재 권한 아래 정확한 원래 command hash의 독립 검증된 durable ACK/readback으로만 별도 제한된 복구 경로에서 닫을 수 있다. READ_ONLY는 실패한 관측 시도를 NO_EFFECT_ABANDONED로 일반 종료하고, 업무 차단이나 authority version 상승을 일으키지 않는다. read 실패 종료는 이전 실행 불확실성·quarantine·drain을 지우지 않으며 heartbeat/offline의 실제 상태 규칙도 유지한다. 효과 유형은 실제 method/path/handler와 등록 binding에 고정하며 caller가 낮출 수 없다.

알려진 SIDE_EFFECT PENDING은 인증된 run/claim/resource/role footprint가 겹치는 새 admission만 차단한다. 불확실한 실행은 해당 tenant/Node/epoch를 보수적으로 차단하고, 범위 자체가 불명확한 PENDING도 그 operation에 한해 Node 범위를 유지한다. 정상적인 서로 다른 자원 claim의 동시 실행은 기존 capacity 규칙을 보존한다. 정확히 claim된 terminal은 DRAIN 중에도 원래 continuation 정책을 적용하며 새 R03 selection으로 바꾸지 않는다. 관측·복구는 각 kind의 목적과 parent handle로 평가한다.

completion fuse의 한 operation 실패를 다른 Node의 정상 capability까지 전파하지 않는다. 실제 verifier process/incarnation 소실은 별도로 다루며 effectClass별로 안전하게 복구한다. 단순 IO ledger 기록과 보안 authority 변경의 version을 구분해 read 등록이 준비된 서명을 굶기지 않게 한다. 실제 revoke·expiry·drain·겹치는 claim 변경의 조건부 publication 검사는 유지한다.

미해결 호출의 기본 분류는 UNRESOLVED이며 영향받는 entry에 인과적으로 연결한다. NONAUTHORITY는 실제 타입·import·source provenance가 있어야 한다. tuple/injected database/runtime transaction·dynamic dispatch를 닫고, 모든 미해결 항목의 scope/binding/futureWork/blocksGrant를 기록한다. 각 entry의 procedure와 감싼 원본 body lock을 합쳐 같은 row의 가장 강한 mode를 한 번에 전체 순서로 획득하며 SHARE→UPDATE 승격을 금지한다. 632개는 source plan 집계이고 실제 procedure join은39개라는 차이를 보존한다. 상세 반례·선택·합격 조건은 Root Evidence b-rev7-concrete-root-decision.json에 고정했다.

실제 검토 재현은547 schema/authority·R4와 bounded stream·작은 source subset까지다. 메모리 부족으로 full source-analysis/reconcile/source-fixtures/link-plans는 재실행하지 않았다. 이를 전체1905 독립 재현으로 쓰지 않는다. 원래74MB ledger는 불변 Git에 보존하며 관리/공유 vault에 복제하지 않는다. 실제 B runtime·A1–A16·장비 인수는 미완료다.


## rev7 실제 검토 후 rev8의 안전 복구 조건과 작은 분석 경로

실제 Claude97bb2f67/Docs42172425569는 B7-M1/M2 및 L1/L2를 남겼다. 기존 merged lock·실제 caller/Go anchor·plain owner-only 문구는 정적 축에서 닫혔고, sound default UNRESOLVED도 확인됐다. 다만 CANCEL/RECEIPT_OBSERVE가 TERMINAL_FRAME의 현재 실행 lease·containment 조건을 상속해 정상 복구를 막고, 분석상 미해결757개 참조를 구체 runtime port와 구분하지 못했다. B 코드·port·부분 동결은 허용하지 않는다.

Root는 msg_aca0d787de3d로 같은 담당자에게 좁은 rev8을 지시했다. CANCEL과 실제 reconcile 부작용이 있는 RECEIPT_OBSERVE는 정확한 원래 parent/claim/run/command와 유효한 현재 identity/epoch/generation/channel C/DER·관측 인증을 검사한다. 실행 lease/activation lease 만료·quarantine·offline heartbeat만으로 이 복구 경로를 막지 않는다. 실제 인증 channel/키/cert의 만료·폐기·epoch 변경은 계속 거부한다. TERMINAL_FRAME은 기존 live lease와 목적 조건을 유지한다.

불확실한 EXECUTE는 안전 취소 ACK만으로 일반 정리하지 않는다. 정확한 NodeStopReceipt는 보호된 quiescence 재조정의 입력이며 다른 claim·denial·UNKNOWN을 지우지 않는다. 현재 인증이 남은 원래 작업의 복구와 실제 인증 폐기를 구분하고, 사업상 RETIRE 사실이 새 권한을 만들어 주지 않게 한다. R01/R05 hint는 DB가 찾은 후보 footprint별로 계산하며 scope 없는 입력을 전체 Node 사업상 거부로 바꾸지 않는다.

시범 경로는 inv.node_channels.revoke_channel이다. 기존3개 미해결은 DomainError와 이미 기록된 DB call의 cursor 결과라 분석 근거를 닫는 대상이다. A1–A8의 타입·import·body provenance 규칙과 변형 반례를 작은 sidecar로 증명하고 다른 경로의 byte/reference를 유지한다. 전체644MB급 assembler를 반복 실행하지 않는다. T1 DB transaction/자격증명 역할·T2 기존 IO catalog 연결·T3 보호된 로컬 읽기는 기존 인터페이스의 설계 계약으로 묶되 실제 연결은 미제공이다. P-INJECT-BUILD/P-DBFUNC/P-API-DI/P-GETATTR/P-LOCKRANK/P-SQLSCOPE는 구체 미래 계약으로 이름만 정하며 구현·등록하지 않는다.

ORM session.delete/merge writer 누락과 ServeHTTP/rawPath anchor·선택 hook 부재·39 source lock plan 중33 procedure join이라는 차이도 바로잡는다. Runtime crypto/PG/role/race·실장비 증거는 아직0이고 A1–A16은 PENDING이다. 실제 rev8 독립 판정 뒤에만 Root가 다음 한정 계약·구현 범위를 결정한다. 상세 조건은 Root Evidence b-rev8-revoke-pilot-root-decision.json에 있다.


## Rev8 실제 판정과 작은 Rev9-T1 범위

Root는 실제0440d1cabcb74ce24d9b43c95970dae795957952 검토와 exact Docs42183423923/job127778067293/19단계 성공·remote·고유 검토 문서18개를 대조했다. B7의 CANCEL/RECEIPT 복구·시범 revoke 분석·writer389와 authority34·후보별 hint·I1–I4는 실제로 닫혔다. 그러나 이미 해제된 같은 claim의 터미널 frame을 다른 live claim 때문에 허용하는 B8-M1 Medium과 A1/A2 mutation 시험·분류 정확도·hint 인증 guard의 Low가 남아 전체 Rev8은 한정 수정 필요다.

Root는 같은 B Codex에게 msg_78b82487362a로 docs/static/symbolic Rev9-T1만 지시했다. TERMINAL_FRAME은 같은 원래 EXECUTE parent가 PENDING/LIVE/current-incarnation이고 같은 claimVersion·activeClaim·실행 중 workload·유효한 해당 run lease·now+5 deadline을 모두 만족해야 한다. 다른 Node claim의 bool은 대체하지 못한다. 원래 typed terminal receipt가 맞는 claim만 release/tombstone/version 갱신하며 원래 UNKNOWN·durable recovery identity는 보존한다. DRAIN 예외는 그대로고 준비 뒤 release된 frame도 거부한다.

공유 predicate였던 BUILD_CLEANUP_READ는 별도 기존 목적의 protected build evidence read로 분리한다. 원래 BUILD_DISPATCH와 정확한 admitted session/request/approval/decision/daemon/lease/resource/fencing descriptor, 현재 인증과 소유 protected transport root가 필요하다. 물리 종료 뒤에도 cleanup 증거를 읽을 수 있어야 하므로 terminal의 실행 중·lease/now+5 조건을 그대로 이식하지 않는다. 읽기만으로 claim·UNKNOWN·capability·거부 상태를 바꾸지 않고 원래 _commit_consequences와 typed physical receipt/CAS·duplicate 규칙만 적용한다. 보호된 read binding이 입증되지 않으면 T3/HOLD로 남고 새 wire/port 권한을 만들지 않는다.

같은 delta에서 hint의 channel/key/cert/epoch 독립 인증 guard와 span을 다시 계산하는 A1/A2 mutation 시험을 보완한다. cursor/Connection monkeypatch·metaclass·dataclass/Exception/constructor shadowing을 실제 producer/span provenance로 거부하며 오래된 span hash 불일치를 음성 증거로 쓰지 않는다. 분류 정밀화는 T1 대상 edge와 실제6개 오분류의 작은 sidecar로 한정하고 나머지는 원본 hash·blocksGrant로 보존한다.

다음 정적 시범은 inv.observation.NodeObservation.mark_offline과 Database.transaction이다. 필요한 A1c는 Connection/_ObservedConnection union과 원래 execute 결과를 증명하고 A3 ContextVar·A5 local container·좁은 A8 production NodeObservation.db constructor·T1 observability를 닫는다. 실제12개 공유 critical entry 집합을 이름으로 고정하고 다른 entry 상태는 올리지 않는다. A7 tools runtime import는 이 경로에 필요 없어 후속 snapshot/deliver로 미룬다. 출력 t1-mark-offline-closure.json은 SOURCE_STATIC_CLOSED_RUNTIME_PENDING이며 권한이 아니다.

P-DBROLE/실제 PG role·READ COMMITTED·SET LOCAL·두 세션 lock·DB clock·logging handler·현재 인증·B cutover는 계속 NULL/HOLD다. statement_observer는 잠금 안에서 호출되므로 in-process/nonblocking/no-network/예외 격리 계약이 필요하고 현재 production observer/sink None의 출처를 증명한다. 전체523파일/3485계획을 다시 생성하지 않는다. pending_contracts 뒤 edge_categories의 두 producer 순서·fresh canonical state 해시를 기록하고 기존46면/R4/C2/C-P-R·signer/outbox/root/owner 권리와 미실행 증거를 보존한다. 실제 독립 Rev9 검토 전 B 제품 코드/port/freeze/runtime grant는 없다. 정확한 범위와 원문은 b-rev9-t1-root-scope.json에 둔다.


## 실제 후속 검토와 제한된 다음 수정

실제 a7e9f9d7/Docs42196493024는 Rev9의 matched-claim·cleanup 분리·hint 인증·한정 category 보완은 닫았으나 terminal Node/tenant 상태 parity와 누락된 ObservationWorker production root의2Medium·새 mutation escape Low를 남겼다. Root는 msg_b6b4813cb5c2로 같은 Codex에게3daf 기반 Rev9b fix-only를 지시했다. 실제 require_execution 및 online/draining parity, 모든 constructor root census와 lan_pilot.runtime local helper, 보호된 receiver use-site allowlist/alias·post-construction patch 거부를 보강한다. 고정19edge/12entry·전체598/757/1071/21·외부573/218·NULL bindings는 유지한다. A7은 실제 Rev9b 수락 뒤 snapshot만 선택할 후속 제안이며 deliver는 아직 범위가 아니다. 정확한 지시는 b-rev9b-root-scope.json에 있다.


## Rev9b 실제 Low 판정과 Rev9c 수정 범위

aa3387/Docs42224817650의 실제 검토는 M1·actual72028 T1/A8를 닫았지만 reflection constructor census/forwarding caller fixedpoint/owner-instance escape의 Low3건을 남겼다. Root msg_8f20f55b48dc는 exact870 기반 새 고유 문서·bounded분석·targeted회귀만 Rev9c로 허용한다. modelbytes와 기존집계·NULLHOLD를 보존하고 A7 NodeChannels.snapshot/제품/port/runtime는 아직 허용하지 않는다. 실제 좁은 delta 수락 뒤 다음 A7 cut을 정한다. 전체 Python ownership/reflective completeness로 주장하지 않는다. 상세는 b-rev9c-fix-only-root-scope.json이다.
