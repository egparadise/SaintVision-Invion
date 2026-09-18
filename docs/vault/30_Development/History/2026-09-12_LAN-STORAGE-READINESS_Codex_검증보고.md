---
doc_id: "HIST-LAN-STORAGE-READINESS-REPORT-20260912"
title: "2026-09-12 LAN-STORAGE-READINESS Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:55:31+09:00"
source_of_truth: "Git"
---

# 작업·검증·다음 행동

CX-02/S12-ST, owner Codex / reviewer Claude pending. base548bcfd → 코드f2a7fbcc5d4880e09e8973aeaa702ba45d581006, agent/codex/workspace-bridge, origin push exit0. [[2026-09-12_LAN-STORAGE-READINESS_Codex_착수]].

## 구현과 실제 관측

`tools/check_lan_storage_readiness.py`는 PostgreSQL REPEATABLE READ/READ ONLY와 tenant 설정·명시적 Node 조건으로 현재 epoch, kill switch, 관측 freshness/profile, 관계 존재와 현재 관측 역할 SELECT 허용 여부를 조사한다. 원본 경로/DSN/키 출력 없음. public zip은 추출 없이 hash와 필수 파일의 정확한 root 이름/중복을 확인한다. SHA 일치는 코드 버전·서명·설치 성공 증거가 아니다. 성공 exit0도 deploymentAuthorized=false/operationalAcceptanceAssessed=false이며 전체 인수 판정이 아니다.

실제 관측 2026-09-12T07:54:30.061951+00:00 (KST +9시간): .225 1대 online/fresh, lan-observe-v1/0.1.0, epoch 일치. kill switch 활성. inv.storage_sample_requests와 inv.storage_sample_consumptions 없음. public.storage_contributions/storage_checks/data_locations는 있으나 관측 계정 SELECT 불허. 이는 등록 데이터가 없다는 뜻이 아니며 관측 계정의 권한을 확대할 근거도 아니다. 공개 worker/workspace-worker 둘 다 SHA 일치하지만 저장소 교체 관련 5개 파일 모두 없음.

Evidence: [[lan-storage-readiness-f2a7fbc.json]], [[lan-storage-readiness-f2a7fbc-tests.xml]], [[lan-storage-readiness-f2a7fbc-ci.json]].

## 명령과 결과

- 동일 코드 SHA에서 `python -m pytest tests/core/test_lan_storage_readiness.py -q --junitxml=.work/lan-storage-readiness-tests.xml`: exit0, 6 passed. 누락/구형/잘못된 checksum/중복 파일/완전 묶음과 독립 차단 사유 시험. 실제 원격 실행 시험 아님.
- `python tools/check_lan_storage_readiness.py --state <운영 pilot> --output .work/lan-storage-readiness.json`: exit1, 관측 성공·차단 조건 5개. exit2는 점검 자체 오류로 구분. 실제 운영 DB/파일 read only; 운영 Node·DB·공개 묶음 변경 없음.
- `python tools/check_docs.py`, `python tools/check_ontology.py`: exit0 (착수 시 문서341/48 tasks). 최종 보고 후 재검사.
- CI 16:54:38 KST, 같은 코드 SHA의 6개 run 모두 account billing 이유로 job 미시작/failure. 로컬6개는 CI 대체·통합 성공이 아니다.

## 다음 담당과 순서

1. Codex: 운영용 서비스 DB 연결 대상과 migration 이력을 읽어 0037까지의 의존성/기존 데이터 정합성을 검토하고, 백업/복원 증거와 연결한 적용 계획 작성. 단독 관측 역할에 광범위 GRANT 하지 않는다.
2. Claude: 실제 등록 owner/project/Node/contribution 연결과 운영 서비스 역할 확인, migration/점검 도구 독립 검토. 관측 계정에서 조회 불가한 내용을 미등록으로 오판하지 않는다.
3. Codex: 검증된 정확한 Node 이미지·policy/root/channel 버전으로 별도 후보 묶음 생성, 원격 Ubuntu와 실제 허용 폴더 경로 확인 → 명시적 교체 request → 서버 mTLS/서명 Evidence. storage READ ONLY 설정과 lan-workspace-v1 작업 프로필은 별도 조건이며 교체 스크립트 하나로 둘 다 완료되지 않는다.
4. Codex: workspace 프로필 설치와 서버 admission 조건 확인 후 제한된 실제7개 실행/취소/복구 시험. kill switch는 시험 준비가 끝난 뒤 승인된 운영 절차로 전환한다.
5. Gemini: 실제 관측 전용/준비 미완료 상태 표시, 이후 스케줄링 가능 상태와 브라우저 실행 검증. Orca 운영 기록 담당은 카드/branch/담당 추적 유지.

정식 done/PR19 merge 미완료. 전체48행 근거 기준 2775/4800=57.8125%, 잔여42.1875% 유지. 이 도구 추가로 실장비 인수 진척을 올리지 않는다. Obsidian 동기화 결과는 후속 기입.

## 동기화와 최종 검사

343문서/48task 검사와 ontology exit0. 외부3개 편집을 원본 hash로 보존한 뒤 동일 bytes adopt, 2026-09-12T16:56:46 KST/2758297에서 로컬 Obsidian664파일 hash 일치, pending0/conflicts0. [[lan-storage-readiness-obsidian-20260912.json]]. OneDrive cloud 업로드 미확인. 이 영수증 추가 후 최종 commit/push와 동기화를 다시 수행한다.
