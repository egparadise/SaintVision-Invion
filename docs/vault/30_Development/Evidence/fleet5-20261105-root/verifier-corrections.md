---
doc_id: "EVIDENCE-FLEET5-20261105-ROOT-VERIFIER-CORRECTIONS"
title: "FLEET5 운영 검증기 정정과 실패 보존"
version: "1.0.6"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-06T05:25:06+09:00"
source_of_truth: "Git"
---

# 운영 검증기 정정

- CA 생성 명령은 exit0이었으나 첫 로컬 검증기가 CA 최상위에 key 파일이 있다고 가정해 assert/exit1이었다. 실제 `_paths`는 root/intermediate/private 하위다. 생성물을 보존하고 source의 명시적 role로 다시 읽어 암호화 header·CA/chain/CRL 서명과 이전 public CA24개와의 구분을 확인했다. 키·암호를 재생성하거나 출력하지 않았다.
- 두 번째 ACL 검증기는 current-user만을 허용한다고 가정해 exit1이었다. 검토된 `private_directory/private_file`은 current operator·SYSTEM·Administrators를 명시적으로 허용한다. 실제 전체21개 항목의 ACL을 그 source 정책과 대조해 비특권 다른 사용자 허용0을 확인했다. DACL을 넓히거나 기존 키 권한을 바꾸지 않았다. rootOffline=false를 그대로 기록한다.
- sudo 결과 분류 v1은 영어 interactive-authentication 문구와 한국어 암호 필요 문구를 놓쳤다. 실제 exit1과 원문 private stderr는 보존됐고, 새 인증 시도 없이 v2에서 세 장비 모두 operator authentication 필요로 정정했다.
- 기존 inventory 슬롯 번호는 사용자의 물리 PC 번호가 아니다. 주소·계정과 직접 SSH 결과로 legacyworker1=PC2, legacyworker2=PC4, legacyworker3=PC3를 확인했다. 이전 관측은 원래 슬롯 기준 기록으로 보존하고 새 ledger를 만들었다. 원래 inventory/r5 ID·CA·예약·pins를 덮지 않았다.

실제 증거/현재 상태는 `physical-setup-checkpoint.json`과 [[2026-11-05_기존5대_오케스트레이션_착수_Codex]]를 따른다. 이 정정은 제품 검증 실패를 PASS로 바꾸는 처리가 아니다. 기존 source 실패와 새 verifier 성공을 구분한다.

- 합본9a8 bool probe의 첫 실행은 고정 Git object 대신 작성자의 변경 중인 checkout을 읽었다. 그 checkout은 이미 isTrue 수정으로 numeric1을 거부해 Python0, expected-red wrapper1이었다. 실제9a8을 pass/fail로 판정하지 않고 exact Gitblob의 caller assert만 다시 실행해 numeric1 수락을 확인했다. source/키/운영상태 변경 없이 fixedrevision과 mutabletree 결과를 나눠 기록했다.

- r5 읽기 전용 snapshot의 첫 수집기는 각 host에 실행 Node가 하나라고 가정했으나 실제6개를 만나 unknown으로 중단했다. 원래r5 source03의 정확한 두Node identity/port로 대상을 고정해 재관측했다. 다른Node를 선택·정리하거나 어떤runtime도 재시작하지 않았으며 첫unknown과 다음의 일관된 snapshot을 나눠 보존한다.

## 2026-11-06 시험 입력·격리와 로그 읽기

- 4a의 canonical Unicode fixture 생성 경로에서 일부 문자가 물음표로 바뀌었다. 실제 signature/두 cycle은 suppliedbytes 범위에서만 유효하며 전체Unicode증거로 수락하지 않는다.500은 ASCII-escaped fixture와 명시적 codepoint/UTF8/NFC 비정규화 검사를 추가했고 실제 새 Go는 아직 필요하다.
- 4a standalone 시험이 sys.modules의 다섯 helper를 지운 뒤 복구하지 않아 후속 clock monkeypatch와 verifier가 서로 다른 module을 읽었다. Backend 양버전과 Core의 같은5 실패를 보존했다.46은 성공/실패·present/absent/None을 finally로 복구한 source fix이며315 독립 검토 수락/새 전체CI는 별도다. freshness나 원래 assertion을 완화하지 않았다.
- Root의 첫 Core 실패 요약은 PowerShell redirect의 UTF16을 UTF8로 읽어 빈 결과였다. BOM으로 encoding을 식별해 원문 rawbytes/hash를 보존한 채 읽어5fail9075pass를 확인했다. 빈 요약을 PASS로 간주하지 않았고 실제 실패를 지우지 않았다.
- 기존 installed standalone fixture PASS와 새 T3 generic default pinned dispatcher의 미검증은 다르다. Owner의 과거 stage-order 오독은 source에 정정 예정이며 wholeBackend/Core의 FAIL도 그대로다.

- Root의 첫4f artifact 검증기는 installerSourceSHA256를 단일 hash로 가정해 assert/exit1이었다. 실제 필드는7개 파일의 closed hash map이며 각각 exact4f Git blob과 비교해 모두 일치했다. 원본 artifact/프로그램/값은 바꾸지 않았고 verifier의 필드 해석만 정정했다.

- 집계 draft에서 shared Card150의 네 tool pointer가 새 소스로 바뀌었으나 Root checkout 제품은 구59f이므로 잘못된 pin 조합이다. private 사본과 exact4필드 비교를 남기고 이 파일만 coordinator HEAD의 바이트로 복구했다. 새 도구 pin은 실제 결합 후보 담당자가 원래 metadata와 함께 검증하며 집계 보고가 제품 반영을 대신하지 않는다. 위 Unicode/격리의 당시 미확인 상태는 역사 관측으로 보존하고 최신4f 실제 코드 수락/전체CI 성공은 별도 receipt로 확정했다.

- 최종 stage 검사에서 새로 집계한 과거 pytest traceback 두 원문에 E-line 후행 공백3개가 있어 exit2였다. 앞선 working-tree diff 검사는 untracked 파일을 포함하지 않았다. 원문 hash/바이트를 그대로 보존하고 해당 두 basename에만 blank-at-eol 예외를 명시했다. 다른 파일이나 whitespace 규칙은 바꾸지 않았으며 최종 staged 검사 성공을 별도로 확인한다.

- Root414 첫 path ratchet은 집계한 B History의4f source 경로2개가 구59f 제품 checkout에 없어 exit1이었다. 원래100f는4f 계열 source에서 유효하다.4f Git object의 실제142/192·144/149행을 읽고 집계 사본만 immutable GitHub 링크로 정정했으며 source bytes hash와 wrapper hash/1.0.1을 기록했다. 제품 파일을 보고 branch로 복사하거나 baseline을 올리지 않았고 원래 제안과 검토 대상100f는 그대로다.

- Root417 첫 docs검사는 새 v4 reviewer History가 집계하지 않은 v3 History를 wiki로 가리켜 exit1이었다. 원래 v3 source는 connection-like fixture를 포함해 별도 immutable source에 보존했다. a81f Git객체 존재를 확인한 고정 링크로 집계 wrapper1.0.1의 참조 하나만 바꾸고 원본/집계hash를 기록했다. 실제 검토판정·원본d2fa/a81f·제품·baseline은 바꾸지 않았다.

- Root418 path-ratchet는 old59f 관리 branch에 없는 e50 시험4개를 새 review History가 local path로 인용해 exit1이었다. 실제 e50 Git 객체를 확인해 집계 wrapper1.0.1의 인용4개를 immutable source 링크로만 바꿨다. 최초 실패log와 원본/집계hash를 보존했고 제품·검토 원문·baseline은 변경하지 않았다.
