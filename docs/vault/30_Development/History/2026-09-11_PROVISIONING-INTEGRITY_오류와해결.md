---
doc_id: "ERROR-PROVISIONING-INTEGRITY-20260911"
title: "PROVISIONING-INTEGRITY 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:19:43+09:00"
source_of_truth: "Git"
---

# 발견·해결·남은 경계

Claude c6ed473 기준 독립 검토에서 확인한 사항이다. 통합 수정의 reviewer는 Claude 대기다.

- P1: tools/provision_account.py의 apply는 public.users.external_subject를 교체하고 business_projects.enabled를 다시 true로 만든다. inspect/apply 사이 잠금이 없고 apply 자체는 identity 충돌을 재검증하지 않으며, 없는 epoch를 생성한다. 반복 실행으로 disabled 정책/로그인 연결을 바꾸지 않도록 insert-only·현재 DB lock·원자 audit·epoch 별도 준비로 정정했다.
- P1: 도구에 inv.project_grants 생성/검증이 없어 연결 후 실제 kernel request가 거부된다. 명시적 grant 범위, 현재 멤버십 교집합, 실제 JWT로 draft 생성하는 통합 시험을 연결했다.
- P1: 0028_subject_kernel_link는 현재 계정 상태/external_subject 일치를 검사하지 않는다. 최신 Codex 0028과 적용 순서에 따라 검사 약화가 생기므로 두 공개 이력을 그대로 보존하고 0030의 최종 정의로 고정했다.
- P1: 새 business raw outputs는 public Run 존재를 전제하고 current kernel grant/Evidence까지 동일 transaction에서 확인하지 않는다. canonical 결과/다운로드와 중복 공개하지 않고 0030에서 alternate inv_app definer 실행 권한을 회수했다. 기존 canonical 성공/실패/취소/복구·다운로드 검증을 유지한다.
- Claude의 migration head 동적 계산과 standalone src 경로 수정은 채택했다. 기존 Codex 격리 runner는 패키지가 설치된 환경에서 통과했으므로 저자의 '매 실행 실패' 문구를 과거 전체 테스트 실패로 소급 해석하지 않는다. 이번에는 14개 공개 prior upgrade/replay를 검사한다.
- Git cherry-pick의 API/문서 add-add 충돌은 최신 canonical 동작을 유지해 해결했다. 원 저자 검토는 별도 보존하며 수정 부분을 Claude가 검토했다고 표시하지 않는다.
- 작업 도구 오류: 동일 파일 delete/add 한 patch는 적용 전에 거부되어 분리 적용했다. PowerShell 기본 pipe 인코딩으로 한글 문서 경로가 ?로 바뀐 쓰기는 실패했고, UTF-8 OutputEncoding을 명시해 복구했다. 제품 상태·원문 파일은 변경하지 않았다.

최종 테스트·코드 SHA·CI·Obsidian 결과는 후속 검증보고에 기록한다. 운영 계정/원격 profile은 변경하지 않았다.
