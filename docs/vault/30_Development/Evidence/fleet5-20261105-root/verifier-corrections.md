---
doc_id: "EVIDENCE-FLEET5-20261105-ROOT-VERIFIER-CORRECTIONS"
title: "FLEET5 운영 검증기 정정과 실패 보존"
version: "1.0.2"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-05T20:43:53+09:00"
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
