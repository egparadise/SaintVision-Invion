---
doc_id: "RES-WORKSPACE-API-001"
title: "WORKSPACE-API 통합 검증 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T12:18:00+09:00"
source_of_truth: "Git"
---

# WORKSPACE-API 통합 검증 해결

[[WORKSPACE-API 통합 검증 오류]]의 원인을 동작 계약에 맞춰 수정했다. 승인 거절의 403을 유지하고 fixture 기대값을 바로잡았다. migration graph는 누락된 부모/중복 ID/cycle/미합류 head를 거부하며, 0019에서 두 공개 이력을 연결한다. CI는 각 선행 head에서 실제 임시 DB를 upgrade하고 반복 upgrade와 runtime 역할의 금지 권한을 확인한다. Frame/UI는 원래 타입을 사용하도록 최소 빌드 수정했다.

`d4861095ab7e637999118b27f320455f132bc969`의 Core push 34432297511/artifact 10135051861을 2026-09-10 12:17:34 KST에 직접 확인했다. 전체 Python 920 tests, failure/error/skip 0. 선행 Workspace 18개는 전체에도 포함되므로 중복 합산하지 않는다. Go race 40 top-level/94 leaf case. artifact archive SHA-256 `807064de86cf9fa94bdc0e0ecf215d511f7884284e3a964ac56a28438481218e`. 배포용 image build, 비root UID, 설정 없는 시작 거절, 실제 PostgreSQL·mTLS·Docker·Git 시험을 포함한다.

이후 응답 schema 검증, policy 거절 뒤 frozen attempt rollback, 프로젝트 Node 소속 회수 경계를 추가했다. 최종 SHA의 별도 CI·보고서로 이 추가분까지 확인해야 이번 delivery를 완료할 수 있다. 이전 SHA의 성공을 최신 코드 전체의 성공으로 대신 사용하지 않는다. 독립 reviewer Claude는 pending이다.

최신 코드 `e9dd3419f04f20d729cdb28cf93387028dd9e292`도 Core 34432676544에서 전체 922개/Workspace 선행 20개/Go 94 leaf case를 failure/error/skip 없이 통과했다. 공개 API 9개에는 정책 거절 후 frozen rollback과 관측 중 Node 프로젝트 소속 회수도 포함된다. artifact `10135184510`, 확인 `2026-09-10T12:24:01+09:00`. [[2026-09-10_12-24-16_KST_WORKSPACE-API_Codex_검증보고]]에 원본 증거와 인계를 연결했다.
