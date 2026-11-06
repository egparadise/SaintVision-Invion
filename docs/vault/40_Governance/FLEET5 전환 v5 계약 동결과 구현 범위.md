---
doc_id: "GOV-FLEET5-BOOTSTRAP-V5-FREEZE-CODE-SCOPE-20261106"
title: "FLEET5 전환 v5 계약 동결과 구현 범위"
version: "1.0.8"
status: "active"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-06T13:08:37+09:00"
source_of_truth: "Git"
---

Root는 source8874b2dfe0dda9a019bd5f334636668290702e13과 실제 reviewer6b12d3ab0e1f3e3cf623b62c528e0e096ba48af6의 검토 원문을 읽고 Docs42101121186/Portal42101121325의 exact SHA·ref·전체 job 성공을 대조했다. V4-M1/I1/I2/I3는 닫혔고 제안 수준 수락이다. 실제 Go·crypto·Engine·장비 실행은 이 설계 수락에 포함되지 않는다.

17개 schema와 11개 규범·synthetic fixture의 원본 SHA256/크기/source를 bootstrap-v5-design-contract-registration-root.json에 고정해 구현 기준으로 등록한다. $id가 없는 7개 schema는 원본 바이트를 바꾸지 않고 명시한 offline URI로 해석하며 전체 참조를 오프라인에서 닫는다. 거부된 v4 signed aggregate는 제외한다. 이는 설계 등록이며 live CP/worker trust 설치가 아니다. 실제 anchor/key/검토된 verifier artifact/binding은 NULL/HOLD다.

Codex task_38393b5d1865가 FLEET5-BOOTSTRAP-V5-K1-OFFLINE-VERIFIER-20261106의 구현 owner다. reply msg_a21df0511488로 승인된 첫 범위는 e50c148287779add421265868ef16909ed984650을 base로 삼은 새 branch의 독립 Go offline verifier package와 테스트·필요한 read-only 검증 CLI다. 오래된 v5 제품 branch를 구현 base로 사용하지 않으며 frozen e50 ref를 움직이지 않는다. 기존 Node launch·peer floor·transport·rotation·B·DB 구현은 변경 범위가 아니다.

K1은 strict UTF-8/closed schema/C2, 외부 고정 trust/role/scope, 실제 Ed25519 typed proof와 freshness/current binding, dependency 순서의 DAG, graph와 별도 role@scope policy, 두 원본 Node projection과 현재 lease/head/readback의 독립 인증 뒤 unsigned derived digest 재계산을 구현한다. bundle/plan은 trust를 설치하거나 verifier를 고르지 못한다. 115개 dummy signed-shape는 실제 서명 positive가 아니며 새 test key로 재생성한 실제 crypto fixture를 별도 표기한다.

K1은 효과 없는 검증 단계다. host root/journal/lock/Engine adapter·CP DB·SSH·Node/leaf 발급·guest 설치·live trust 등록·물리 운영은 별도 K2와 실제 코드 검토 이후 범위다. 구현자는 실제 Go 테스트·race 가능 여부·기존 Node suite/build·관련 게이트·정확한 CI를 기록하고 별도 Claude의 실제 코드 검토를 요청한다. 40개 future case는 수행한 항목별 증거가 생기기 전까지 NOT RUN이다. 이 지침은 반복 사용자 승인을 요구하지 않으며 이미 승인된 구현을 이어가도록 한다.

검토자의 I-a~I-e를 구현 제약으로 보존한다. 특히 112 proof-key swaps는 graph equality만으로 검증되지 않으므로 role@scope policy가 필수이며 rule-list 순서가 아닌 DAG 순서로 평가한다. 전체 제품 100%·5대 운영 인수·원래48-task/VFCL 완료율은 올리지 않는다. 원본 검토와 실행 기록은 [[2026-11-06_05-15-00_KST_FLEET5_bootstrap_contracts_v5_8874_검토_Claude]], [[2026-11-06_FLEET5_bootstrap_contracts_v5_unsigned_context_Codex]]에 있다.


## K1에서 발견한 실제 참조 증거 wire 공백과 추가 구현 범위

K1 구현자가 새 e50 기반 Orca worktree에서 strict parser/C2·17 offline schema·195 기존 shape/digest·4 vector의 Go 통과를 보고했다. Root는 해당 실행을 재실행한 것으로 쓰지 않으며 실제 crypto positive로 인정하지 않는다. 실제 v2 규범은 서명된 참조 원본 바이트를 요구하지만 77개 slot의 실제 contract/verifier pin은 NULL이고 112개 참조는 metadata/typedSubject뿐이다. Root는 이 공백을 실제 계약 한계로 기록하고 reply msg_b005ebff62ab로 새로운 package-local proof wire를 코드 검토 가능한 제안으로 승인했다. 기존 v5 설계·17개 schema·registry hash는 변경하지 않는다.

새 형식은 28개 계약 중 비-native 27개에만 적용한다. 닫힌 body와 signer 구조를 정의하고 서명은 고정 domain+단일 NUL 뒤 body와 signer의 role/SPKI hash를 포함한 C2 projection을 보호한다. 실제 raw 참조 바이트의 SHA256을 artifact identity로 사용하며 새 normalized envelope는 그 바이트가 full C2와 정확히 같아야 한다. subject 전체와 hash, metadata, 외부 role/scope/key/contract pin을 각각 검증한다. plan이나 bundle이 key·codec·verifier·producer 권한을 정하지 않는다.

fresh 계약만 migrationId/operationId를 서명 body에 요구한다. 과거 build/CI/image/review의 immutable provenance와 validity-bounded approval에는 해당 필드를 금지해 재서명이나 순환 참조를 만들지 않는다. fresh는 현재 clock/lease와 최대120초, approval은 현재 validity/plan expiry/nonrevocation, immutable provenance는 인증된 원래 event time과 현재 accepted publication/nonrevocation을 검증한다. 과거 증거는 현재 Node 관측으로 바뀌지 않는다.

native node-floor-v2 계약은 기존 M2 바이트·domain·Unix seconds·nodeSignature를 보존한 고정 codec만 사용한다. 실제 인증된 certificate의 DER/Node identity/SPKI와 fresh operation nonce를 대조한다. 원래 M2에 없는 validUntil은 관측시각+허용age·인증서·현재 plan·lease의 최소값으로 별도 계산해 검증하며 Node가 서명한 필드라고 쓰지 않는다. daemon/container/ExecID/plan join은 별도 인증 증거로 확인하고 normalized 재서명/fallback은 금지한다.

새 per-contract descriptor·schema·strict Ed25519·각 mode/native adapter·원본 바이트와 metadata attack은 실제 코드와 함께 별도 Claude 검토를 한 번 받는다. 새 wire 상태는 PROPOSED_CODE_REVIEW_REQUIRED이고 live trust·keys·설치 등록은 NULL/HOLD다. 이전 dummy 195 shape를 실제 crypto positive로 바꾸지 않으며 별도 test key로 올바르게 재생성한 fixture만 실제 서명 시험이라고 기록한다. 전체40 future case·실장비·전체 제품 완료를 뜻하지 않는다. 원문 결정은 k1-proof-wire-gap-decision-root.json에 보존한다.


## 실제 K1 코드 검토 후 current/history 시간 분리

c6f 코드와 새 proof wire는 실제 c2b15b70/Docs42119997927 검토에서 M1/M2와 L1~L5 수정 필요다. strict Ed25519·파서·C2·normalized wire·키 scope·native producer 바이트·원본 pin과 실제 테스트는 검토자가 검증했으나 전체 코드 수락이나 live 등록은 아니다. Root는 실제 원문과 exact head/ref/alljobs를 확인하고 msg msg_87002d358dbb로 좁은 수정 범위를 부여했다.

K1은 서로 다른 시점의 보존 이력을 검증해야 한다. 종료된 epoch1은 현재 active operation이나 120초 안의 proof로 다시 표현하지 않는다. 역사적 fresh proof는 원래 인증된 operation/HELD lease와 enclosing signed record/event의 당시 소비 시각·phase·key scope로 인증하고, 현재 시간 검사는 current derivation의 실제 live witnesses에 별도로 적용한다. Now를 과거로 바꾸거나 age를 늘리거나 과거 proof를 현재 권한으로 재분류하지 않는다. 과거 출력은 이전 상태를 인증하는 자료이며 현재 실행 허가가 아니다.

현재 projection set은 실제 trusted current operation의 정확한 HELD lease hash와 일치하고, 같은 cohort/migration의 authenticated RELEASED 종료나 더 높은 fence epoch에 의해 대체되지 않아야 하며 해당 operation의 최대 인과 sequence여야 한다. 양 Node 원본·현재 head/readback은 별도 actual current context와 일치해야 한다. 오래된 set의 모든 hash/SetID를 일관되게 맞춘 공격도 거부해야 한다. recoveryEpoch R과 fence epoch, 다른 tenant/cohort는 섞지 않는다. release된 snapshot은 역사 자료로만 읽는다.

추가로 malformed trusted SemanticInputs를 panic 대신 오류로 거부하고, native leaf의 명시적 ServerAuth EKU와 DigitalSignature, challenge issue/expiry 창, bounded packet byte snapshot과 최신 actual testcount를 보완한다. challenge는 IssuedAt-30초 이내 skew가 허용되므로 5초 전 관측을 잘못된 negative로 꾸미지 않으며 범위 밖/만료 경계를 시험한다. concurrent caller가 복사 중 입력을 바꾸는 것까지 안전하다고 주장하지 않는다. 새 multi-time crypto fixture에서 과거 lease 만료·120초 경과 뒤 current epoch2만 live인 정상/거부 경계를 실제로 확인해야 한다.

수정은 c6f 기반 별도 고립 branch의 migrationverify와 고유 테스트/문서로 제한한다. 기존 c6f/current Core를 취소·advance·재실행하거나 그 성공을 새 수정 SHA의 성공으로 쓰지 않는다. 수정 SHA·실제 CI·독립 delta review 전까지 K1/K2/live trust/40future runtime/실장비 수락은 보류한다.


## K1 temporal 코드의 실제 검토와 남은 CI 축

수정56651cba/package d8321059는 실제191b6f84 검토/Docs42132923864에서 code delta ACCEPT를 받았다. Root가 원문·exact head/ref/전체 job·remote·제품 diff0를 대조했다. M1/M2와 L1–L5는 실제 인과 반례·정상 사례로 닫혔다. 이는 구현 축의 한정 수락이고 전체Core42126222201은 Python rate-limit 시험1건으로 실패 상태다. K1 카드 완료·K2·설치 trust·운영/5대 인수로 바꾸지 않는다.

새 typed History는 현재 Operations/Challenges와 분리한 독립 입력이고 current NativeWitnesses는 현재의 원래 Node 증명이다. 현재 파생은 PRESENT인 인증된 inventory head가 있어야 한다. ABSENT의 초기 단계에는 인증된 expected-native-state 근거가 없어 현재 view를 내지 않고 거부하며 역사 Verify는 가능하다. 이 한계를 README에 다음 touch에서 명시하는 R1 Low를 저자에게 배정했다. Go/testdata/schema/28 source pin 변경 없이 설명만 추가한다. 정규화27+원래 native1 producer wire와 설계 등록 manifest는 바뀌지 않았다.

다른 migration 사이의 cohort fence, History/current native/challenge/상태·인증서/publication/설치 trust/artifact/CI/review 입력의 실제 독립 생성·인증은 K2 의무다. 서명 시각에 의존하는 offline 역사 검증의 backdating 잔여 한계와 caller-owned 동시성 조건을 보존한다. 이 타입이나 서명 fixture가 실시간 producer 구현을 대신하지 않는다.

실패 보고a413c0c2/Docs42133327925는 사실 보고로만 수락한다. 분 경계는 실제 실패 원인으로 미확정이다. 같은 Codex의 별도 TEST-clock 카드와 README-only 교정·고정 목적 hosted PG16 시험 경로를 허용했다. 기존 Core/Backend workflow·제품·Go는 그대로 두며 선택 시험의 성공은 fullCore가 아니다. Root가 실제 시험/README/CI delta와 실제 PG 결과를 검토하고 결합 SHA를 고른 뒤에만 새 전체Core/Docs를 진행한다. 현재 코드 수락을 근거로 실패 CI를 재실행하거나 K1 최종 worker_done을 하지 않는다. [실제 독립 코드 검토](https://github.com/egparadise/SaintVision-Invion/blob/191b6f843a643ee4989ce28c9ebf1816963ffe28/docs/vault/30_Development/History/2026-11-06_08-50-00_KST_FLEET5_K1_56651cba_temporal_delta_%EB%8F%85%EB%A6%BD%EA%B2%80%ED%86%A0_Claude.md)와 k1-temporal-actual-code-axis-root-decision.json에 근거를 보존했다.


## 실제 eb32 시험 교정 검토와 새 전체 CI

Root는 eb32b211의 TEST/README/고정 CI delta를 직접 읽고 source25개 허용 범위·Go/testdata/schema/pin/기존Core/Backend 불변을 대조해 수락했다. README R1도 닫혔다. 실제 PG16 Focus42137053588과 Docs42137296076은 exact source에서 성공했다. Root가 원본 artifact13466003560의13,493bytes/digest를 비교·다운로드해 XML/JSON을 직접 파싱했다. 원래 함수 같은 분1통과·강제 분 경계1의도된 실패·수정 파일30통과/0오류/0skip와 source의 모든 test 이름,3scope counter·2bucket5→1 및 원래56651 함수 hash를 확인했다. 이 반례는 과거 실패의 실제 시각 원인 확정은 아니다.

msg_4f741ef0872c로 고정 eb32를 검토된 결합 소스로 선택해 새 fullCore42138733821을 한 번 실행하도록 했다. 이미 성공한 동일 SHA Docs를 재사용하고 선택 proof input은 모두 false다. 과거56651/Core42126222201 실패는 유지한다. 현재 fullCore terminal·원본artifact·최종보고/ownDocs·Rootboundedhandoff가 남으며 source/선택PG 검토 수락을 전체 CI 성공으로 바꾸지 않는다. pending question msg_045f69f4caf4에는 고정 run만 확인하는 한정 one-shot monitor가 terminal 때 같은 ctx_ceecb3824e33에 실제 상태를 reply한다. inbox polling·새 Agent·CI 재실행이나 취소는 하지 않는다.


## K1 한정 인수 완료와 별도 K2 설계 카드

Root는 실제 eb32/Core42138733821 두 job·f28fb41d 최종 보고/Docs42142783600의 exact source/ref/correlation/runAttempt1/전체 성공을 검증했다. 두 원본artifact의 size/digest를 비교·다운로드하고 XML/Go JSON을 직접 파싱해 main9216pass/46declaredskip/0fail, 영향 file30pass·13함수/0skip, K142상위165PASS이벤트/0skip을 대조했다. 기존c6f와 실제46skip 이름도 동일했고, ELF 바이너리를 실행하지 않고 build info의 eb32/modified=false/Go1.27.1/CGO0와 hash를 읽었다. actual191b 코드 검토와 Root TEST/README/CI 검토, 10개 보고 gate0 및 실제 보고 CI가 모두 충족돼 msg_f96802b15040으로 K1 소스·검증·보고의 한정 납품을 수락했다. actual worker_done msg_6987f7ecdcb5/outcome succeeded를 수신했다.

후속 K2는 별도 task_a95ef3d8ccce/ctx_ed23b4a777d0다. 현재 범위는 trusted producer의 실제 출처·인증·신선도·설치 trust와 read-only acquisition/효과 실행 경계를 닫는 DESIGN-FIRST 문서·정적 사례다. 실제 40 runtime case·설치 trust·Node/PKI/Engine/DB 효과는 미실행이고 새 코드 권한도 아직 없다. 완료한 K1의 ref·보고·artifact·이전 실패를 보존한다. 새 불변 제안/ownDocs 이후 실제 별도 검토와 좁은 구현 grant를 진행하며 B rev6 설계와 병행한다. 새 source 배포 패킷 필요성도 확인해야 하며 이전 e50 패킷을 eb32 설치 증거로 쓰지 않는다. [고정 최종 K1 보고](https://github.com/egparadise/SaintVision-Invion/blob/f28fb41d6e566625d5feb27535d4c3d40fbc9100/docs/vault/30_Development/History/2026-11-06_FLEET5_K1_reviewed_combined_Core_delivery_Codex.md)에 세부 증거를 남겼다.


## K2 첫 계약 검토 후 Root의 rev2 설계 선택

실제 Claude 검토5623dc00/Docs42150131952는551d 제안을 K2-M1/M2/M3와L1–L5의 수정 필요로 판정했다. Root는 msg_6df22674ff19로 기존 K2 담당자에게 한 번의 문서·정적 계약 rev2만 지시했다. 현재 코드나 관측·서명·Engine 효과를 허용한 것은 아니다.

설계 선택은 독립 운영자가 사전 승인한 봉인 공개 registry, 보호된 CP 공통 cohort의 transactional authority, 최대1초 시간 불확실성 정책이다. 실제 registry·custody·모든 mutator 중재·시간 출처는 여전히 미설치/HOLD다. 초기 ABSENT 상태의 효과 보류를 유지하고, PRESENT 상태에서 witness가121초 지난 경우도 명시적인 별도 observation-refresh authority와 retry 계약이 닫히기 전까지 HOLD한다. terminal seal과 fresh common normal:3 lease는 기존 A36의 필요 조건을 보존하며 새로운 K1 current 기능으로 간주하지 않는다. UNKNOWN 관측은 새 challenge/실행/소유자 전환에 앞서 보호된 결과 확인과 quiescence를 요구한다.

TrustedContext.MigrationOperationID는 원래 계획·역사의 migration operation이며 현재 active operation으로 대체하지 않는다. facts와의 동일성 및 역사 HELD lease의 인증을 요구한다. 40개 시험의 원래 문구는 그대로 두고 readonly 소비·거부와 producer·효과의 green 의무를 분리한다. 시간 양 끝점의 동일한 보안 결과와 모든 Now 조건의 convexity 증명, 하나의 오류 catalog, Go types 기반 inventory, internal·opaque DTO 경계, 실제 실행 중 verifier executable의 독립 설치 인증을 rev2에서 닫아야 한다.

상세 선택·반례·보류 조건은 Root Evidence의 k2-rev2-concrete-root-decision.json에 고정했다. 실제 rev2 독립 검토 이후에만 Root가 작은 K2A trust/history 읽기 전용 구현을 검토한다. 40 runtime·현재 view·관측/회전·설치·5PC 인수는 계속 미완료다.


## K2 rev2 한정 설계 수락과 readonly trust/history 구현 범위

실제 Claude fe7e1ea0/Docs42158896721는4ce63e8e를 K2A-TRUST/HISTORY readiness에 한해 수락했다. M1은 관측의 명시적 HOLD로, M2/M3/L2는 종결됐고 clock proof는 실제 clock·running stdlib 미확인의 HOLD를 유지한다. 이 판정은 관측·현재 상태 파생·효과·설치의 수락이 아니다.

Root는 msg_18271633c26c로 카드 FLEET5-K2A-TRUST-HISTORY-20261106의 구현을 같은 Codex 담당자에게 허용했다. 허용 제품 경로는 services/node-agent/internal/migrationcontext와 그 내부 시험·문서뿐이며, LoadInstalledPolicy/ReadHistory/ValidateHistory의 typed readonly ports·checked factories·closed refusals를 구현한다. 실제 registry/archive/status/clock/running-code 측정 연결은 null이며 근거가 없으면 거부해야 한다. 공개 constructor나 옵션으로 caller의 provider/Now/key/path/authenticated DTO를 주입해 인증을 우회하지 못한다. 테스트에서만 package 내부의 합성 port·임시 fixture를 사용할 수 있다.

ReadCurrent/현재 Assemble/DeriveCurrent/CurrentView/current SnapshotToken은 stub 없이 API 자체를 두지 않는다. K2B permit/attempt/nonce/challenge·저널/잠금/임시 파일·서명/Engine·entrypoint·실제 측정/packaging/설치는 이 범위에 없다. null running-code port의 오류는 기존 INSTALLATION_OR_RUNTIME_CAPABILITY_UNKNOWN으로 고정한다. 경계 검사는 저장소 전체 first-party Go module의 import/call/constructor를 검사하며, 기존 K1 내부 구현과 시험 fixture를 구분한 뒤 새 production 외부 구성은 k1_bridge.go만 허용한다.

K2R2-L1은 code gate에서 수정한다. 모든 non-test K1 파일을 실제 go/types로 검사하고 named map/slice/function의 underlying type을 포함한다. 기존 G01–G08과 R01–R03 변형을 검출하고 input stub으로 형태를 숨기지 않는다. 새 코드의 실제 로컬 검사·정확한 SHA의 새 Core/Docs·실제 Claude 코드 검토가 필요하며 이전 K1 CI를 차용하지 않는다.

K2R2-M1은 관측 계약 안의 Medium으로 계속 열려 있다. immutable attempt body와 method별 permit/step idempotency·합법 상태 전이·UNKNOWN 재조정·ExecCreate 후 만료·normal:3 별도 slot을 별도 문서 delta와 실제 계약 검토로 닫아야 한다. 이 보완은 readonly 구현의 선행 조건이 아니며, 현재 attempt/permit 코드를 허용하지 않는다. 상세 범위·오류·검사·차단 항목은 Root Evidence k2a-trust-history-root-implementation-grant.json에 고정했다. 실제 연결·40runtime·5PC 운영 인수·전체 개발은 미완료다.


## K2A 인증 형식 공백의 A 선택과 구현 범위 정밀화

담당자가 msg_e5157d3b1280에서 확인한 형식 공백에 Root는 msg_f4259ea0de6b로 A를 선택했다. 4ce의 trust-bootstrap-contract.json은 실제로 PROPOSED_HOLD·actualAcceptance=false·모든 deploymentBindings=null이다. 기존28개 proof slot은 새 registry/archive/status/clock/running-code port의 완전한 인증 형식을 제공하지 않는다.

따라서 이번 구현은 readonly 경계·null port·거부·binding/freeze/history selector/clock/K1 순수 검증 로직·권한 경계/Go type gate의 한정 단위다. 미등록 purpose/format의 근거는 hash·ACTIVE 표기·self-signed 자료가 일관돼도 인증으로 승격하지 않는다. 새 내부 proof 메시지·서명 domain/issuer·암호 검증 ABI를 이번 범위에 만들지 않으며 g2-planning-policy를 설치 인증으로 전용하지 않는다. 등록된 인증 형식과 실제 연결이 없으면 LoadInstalledPolicy와 후속 공개 경로는 계속 닫힌 오류로 거부한다. 이는 production positive authentication 또는 전체 K2A가 구현됐다는 뜻이 아니다.

후속 로직의 양성 단위 시험은 *_test.go 안에서만 명시적으로 이미 binding된 합성 fixture를 구성할 수 있다. 이 시험은 누락된 외부 인증 단계를 의도적으로 우회한 후속 binding/copy/selector/time/K1 로직의 시험임을 표기한다. 공개 constructor·옵션·callback·production helper·verify=true로 신뢰 DTO를 만들 수 있게 하지 않는다. 실제 positive 인증은 purpose별 별도 검토된 provisioning/attestation 계약과 실제 등록 anchor/port, 후속 Root 구현 범위 결정에 의존한다. 기존 새 코드 CI/독립 검토와 observation/current/effect/installation HOLD 조건은 유지한다. 상세 근거와 지시는 Root Evidence k2a-authentication-seam-root-scope-clarification.json에 보존했다.
