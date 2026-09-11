---
doc_id: "ERROR-TENANT-BOUNDARY-20260911"
title: "TENANT-BOUNDARY 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T15:47:11+09:00"
source_of_truth: "Git"
---

# tenant 및 인계 충돌 정정

[[2026-09-11_Claude_잔여보고_Codex_독립검토]]의 원본 0026 누수는 실제 제한 로그인 역할로 재현됐다. 최신 적용 정의는 0028/0030에서 이미 guard가 교체돼 타 tenant 읽기가 차단됐다. 소스 원본 존재만으로 최신 DB 함수가 취약하다고 판정하지 않도록 revision별 함수 hash·실제 반환값을 남긴다. 운영 DB를 시험용으로 바꾸지 않았다.

Claude 결과 중복 제거를 가져오는 중 results.py의 modify/delete 및 test_results.py의 rename/rename 충돌이 발생했다. 실행 결과는 ResultView를 유지하고 업무 readiness 라우터와 시험만 남겨 해결했다. 현재 합성 앱의 import도 교체한다. 이미 전달된 0029 삭제/0030 부모 재작성은 보존 원칙과 후속 FK가 아닌 migration 의존성을 깨므로 현재 원본으로 복원했다. 원저자 코드·판단은 원문 검토 문서와 Git commit에 남아 있다.

새 입력 조회의 과거/다른 project/다른 epoch 입력 및 Run ID 순서 문제는 0032 forward migration으로 보강했다. 같은 작업의 기준 코드에 불필요한 tenant guard 복제를 추가하지 않았다. CI 결제 제한은 고치지 않았고 로컬 PostgreSQL 성공을 CI 또는 전체 인수 완료로 표시하지 않는다. 실제 명령·SHA·CI·sync는 후속 검증보고를 따른다.
