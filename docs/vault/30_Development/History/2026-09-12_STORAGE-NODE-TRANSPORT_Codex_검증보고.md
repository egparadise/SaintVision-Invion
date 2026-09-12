---
doc_id: "HIST-STORAGE-NODE-TRANSPORT-REPORT-20260912"
title: "2026-09-12 STORAGE-NODE-TRANSPORT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T12:57:44+09:00"
source_of_truth: "Git"
---

# 실제 Go Node 서명 sample 전송

2026-09-12T12:57:44+09:00 / 구현 `688678d510b676d59d80c69de08bc69569828dd5` / base9fe35b6 / agent/codex/workspace-bridge / PR19 draft. CX-02 owner Codex/reviewer Claude pending. S12-ST 원 owner Claude 유지. [[2026-09-12_STORAGE-NODE-TRANSPORT_Codex_착수]], [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.2.0/ADR-089.

## 바뀐 실제 경로

기존 Python 참조 구현124fe97에 공통 JSON Schema 6개(NodeStorageChannel/Item/Challenge/SampleInput/SignedSample/RootConfig)를 추가하고 Python/TS/Go 및 Node wire bundle을 같은 원본에서 생성했다. 단일 원본은 contracts/v1alpha1/core.schema.json이다.

Go daemon에 `--storage-policy <운영자가 승인한 보호 JSON 파일>`이 있을 때만 POST /v1/storage/sample을 활성화한다. 기본값은 비활성/인증된 호출에도503이다. v1은 Node당 한 contribution만 지원한다. 로컬 policy는 channel 전체·contribution_id·root_version·root를 갖고 request는 root/key 경로를 선택하지 못한다. 같은 Node/tenant/epoch인지 시작 시 확인하고, 수집 전후 policy의 정확한 bytes hash가 처음과 같아야 한다. 변경된 설정은 자동으로 반영하지 않고 통제된 재시작이 필요하다. 영속 root-policy rollback floor는 아직 구현하지 않았으며 설정 버전만으로 DB 현재 권한을 대체하지 않는다.

기존 Authority의 실제 mTLS/peer allowlist 검사 전후에 요청을 검사한다. 현재 TLS GetCertificate로 읽은 보호 Node Ed25519 키를 사용하며 SAN/EKU/유효기간/pin/키 일치를 검사한다. 수집 후 현재 인증서를 다시 읽어 교체를 감지한다. Node 키를 Control Plane에 복사하지 않는다. key/config가 작업 중 바뀌면 결과를 반환하지 않는다. heartbeat 슬롯과 별도1개 점검 슬롯이며 동시에 두 번째 점검은429다.

파일 읽기는 Linux에서만 활성화된다. root부터 모든 ancestor를 O_NOFOLLOW로 열고 root dev/inode를 고정한다. 상대 경로 component별 openat, 같은 device, regular single-link file, 열린 크기≤1MiB, bounded 두 번 읽기/hash 일치, 읽기 후 metadata/이름/루트 identity를 검사한다. 심볼릭 링크·하드링크·FIFO·과대 파일·루트 교체가 정상으로 관측되지 않는다. 실패 파일은 null hash/size로 서명해 verifier가 mismatch로 판정하며 root 교체는 전체 요청을 거부한다. Linux 밖의 Go root opener는 거부한다. Windows Docker/WSL의 Linux Node와 Windows 네이티브 지원은 구분한다.

32개/파일당1MiB/manifest 및 payload64KiB/발급30초 제한을 유지한다. Node 요청 context5초, client6초 상한이며 파일 chunk 사이 cancellation과 마지막 expiry/authority 검사를 수행한다. kernel/filesystem syscall 자체를 강제로 중단하는 deadline이나 일관 filesystem snapshot은 아니다.

Control Plane NodeTLSClient.storage_sample은 고정 challenge bytes를 base64로 전달하고 실제 TLS peer certificate DER와 서명 envelope를 반환한다. 이미 CA/hostname/URI/pin을 검증한 같은 연결의 인증서다. verifier는 기존 challenge와 서명/domain/hash/시각·개별 파일을 검사한다. UTF-8 한국어/emoji 경로도 실제 Go→Python digest가 일치했다.

## 검증 증거

| 환경/명령 | 실제 결과 | 기록 |
|---|---|---|
| clean688678d Windows pytest tests/test_node_storage_sample.py tests/test_contracts.py |**98 passed/0 skipped/exit0**|[Windows](../Evidence/storage-node-windows-688678d.json)|
| clean688678d Windows go test -json ./transport ./storage |exit0, transport22 pass events/20 leaf; storage는 플랫폼 구현 시험 없음|같은 Windows Evidence|
| clean688678d Linux standalone Go tests |storage9 pass events(부모 포함)/transport22 pass events, 모두 exit0, 격리 disposable container|[Linux Go](../Evidence/storage-node-linux-go-688678d.json)|
| clean688678d check_kernel_docker.py --tests test_node_storage_transport.py test_node_delivery.py test_node_storage_sample.py test_storage_check_integrity.py |**130 passed/0 skipped/exit0**, 실제 Go daemon·TLS·격리 PostgreSQL·파일, owned cleanup 성공|[Linux 통합](../Evidence/storage-node-linux-688678d.json)|
| git push origin agent/codex/workspace-bridge |688678d exit0|PR19|
| 같은 SHA Actions6개 |결제/한도 때문에 job 미시작 failure|[CI IDs](../Evidence/storage-node-688678d-ci.json)|

시험 중 fixture의 profile 빈 값 때문에 heartbeat response schema가503을 반환한1개 실패가 있었다. storage 슬롯 문제로 숨기지 않고 fixture profile을 유효하게 설정해 최종 성공을 확인했다. initial root cwd go test 및 존재하지 않는 test 경로의 실행 실패는 별도 오류 기록에 남겼다. Generator의 formatter future warning은 제품 테스트 실패가 아니다. 독립 reviewer를 실행했다고 주장하지 않는다.

실제 통합 신규19개는 수집/서명, 손상·누락·크기·checksum 없음·과대·symlink/hardlink/parent-link, Unicode, root/config 변경, client 폐기, 잘못된 scope/만료/중복/경로/추가필드 및 비활성 기본값을 확인한다. 기존 Node delivery18/서명68/storage25와 합쳐130이며 환경 간 같은 시험은 중복 합산하지 않는다. Windows 네이티브 Node 파일 수집·원격 .225·물리5대 운영 인수는 수행하지 않았다.

## 다음 DB 경계와 인계

**durable challenge 발급/nonce 소비 및 StorageCheck/inv.evidence 원자 쓰기는 아직 미구현이다.** API는 파일 sample을 서명할 뿐 운영 health나 Evidence를 기록하지 않는다. 실제 Node daemon이 응답해도 VerifySample.recorded=false/operational_acceptance_assessed=false다. 실제 Run 존재/인가·현재 contribution/catalog는 후속 trusted issuer의 일관 조회/잠금 책임이다. Node는 허용된 control peer와 로컬 root 범위에서 읽는다. 별도 tenant/workload 공개 API로 연결하지 않았다.

다음 Codex 첫 행동: public contribution/catalog와 kernel Run/channel을 같은 DB 권한 경계에서 고정하는 최소권한 발급·소비 계약을 구현한다. 기존 Evidence 원장/ResultView를 유지하고, 실제 Run/현재 project 권한·epoch·channel/config/catalog version·expiry를 transaction에서 재검사한다. 같은 nonce는 같은 결과 replay만 인정하고 다른 결과는 충돌, 실패 시 Evidence/StorageCheck/consumption 모두 rollback해야 한다. 먼저 disposable DB에서 동시 회수/만료/중복/부분 실패를 시험한 뒤 운영 연결한다.

Claude:688678d/공통 Schema/ADR-089·Go 경로/키 경계 독립 검토. Gemini: 이번은 운영 건강/5대 연결 완료를 표시할 근거가 아니다. 전체 성숙도 추정 **57.81% 완료/42.19% 잔여 유지**. CI·교차 검토·원격 프로필 및 업무7개 시험은 별도다.

## 외부 인계 수신

Obsidian Agent 인계 대기 목록에 Claude/Gemini 추가 절이 있어 --check exit1/쓰기0. [원문/hash](../Evidence/obsidian-proposals-20260912-storage-node/manifest.json)를 보존하고 수신 요약만 정본에 추가했다. Claude d14db0a/c5f2154 기준F1~F4 및 f17ad62 운영 질문, Gemini fa01d77 작성자106/133/63/5 주장이다. 이번에 그 소스/운영을 다시 검증하지 않았으므로 최신 결함 판정·실제2-PC/GPU 통과·독립 승인으로 표시하지 않는다. ADR-074 등 후속 Codex 수정은 기존 보고를 확인해야 한다. 수신 확인은 코드 승인과 다르다.

전달 준비: check_docs.py exit0(원문24/문서318/작업48), check_ontology.py exit0, git diff --check exit0. 생성 Schema/bundle/types 반영. PR19 설명 갱신/draft 유지. 원문 보존·commit/push 후 동일 bytes 인수 및 Obsidian 동기화를 진행한다.

최종 전달: 보고 commit `7f30fe7740f0620790df49909584ecf616b78ee9` push exit0; 인계 외부 원문1개는 Git blob/hash 동일성 확인 후 쓰기0으로 인수. 2026-09-12T12:58:43+09:00 로컬 Obsidian 574개 hash 일치, pending0/conflict0, check→apply→check exit0. [동기화 영수증](../Evidence/storage-node-obsidian-20260912.json). 영수증 포함 후속 commit도 push 후 다시 동기화한다. OneDrive 클라우드 업로드는 미검증. 다음 Codex는 durable challenge/nonce·기존 Evidence/StorageCheck 원자 DB 쓰기, Claude688678d 독립 검토 pending.
