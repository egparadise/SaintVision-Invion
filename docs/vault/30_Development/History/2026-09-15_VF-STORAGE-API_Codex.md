---
doc_id: "HIST-VF-STORAGE-API-001"
title: "VF 저장소 조회 API 연결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T14:59:30+09:00"
source_of_truth: "Git"
---

# VF 저장소 조회 API 연결

- VF-CX-01/02 후속. owner Codex/reviewer Claude pending. branch agent/codex/vf-storage-api,base58f0370.
- INDEX-PROGRESS-0011.0.80,WORKBOARD-VF-CODEX-0011.0.9,최종GUIDE/역할/Git운영1.0.0,보강로드맵/연속정책1.0.0 및 기존 ADR/Backend/DB/Storage 계획. agent-delivery1.1.0/core-reliability1.0.0 재사용.
- 범위: 기존 저장소 목록 및 inv:// resolver를 canonical business dispatch에 조회전용 연결. 사용자별 등록자 소유권과 활성contribution 검사, GET과 mutation 경계, verified identity/tenant/RLS 시험.
- 공개 메타데이터 조회는 등록자 본인 폴더로 제한. 프로젝트 공유/관리자 전체조회는 권한 계약이 별도 확정되기 전 열지 않는다. 등록자 소유권이 물리파일 접근/실행허가/현재바이트 검증을 대체하지 않는다.
- 합격: configured factory·실JWT·non-ownerPG에서 자기목록/URI, 같은tenant 타사용자/다른tenant/폐기폴더/무인증/가짜토큰/POST 우회 거부. 응답값/tenant를 caller가 지정해 권한을 바꿀 수 없음.
- 운영DB/장비/credential/공개배포 변경 없음. 이전PR23 독립검토/CI billing/실5대 인수는 대기.


## 작업과 검증

- 기존3개 GET catalog API를 canonical business dispatch에 연결. GET path의 partial match로 POST가 business의 등록함수에 도달하지 않도록 Match.FULL로 한정했다.
- 목록/URI resolver에 검증된 reader_user_id를 전달. contribution 등록자 및 active 조건을 명시적 tenant/RLS와 교차 검사. 같은tenant 타등록자도 숨긴다. 사용자입력 URI오류는 generic422/404로 노출값을 줄였다.
- 초기시험10passed/1failed: 모든요청거부는 통과했으나 DB의 전체행수를3으로 고정한 시험이24를 관측했다. session fixture가 이전case의 public행을 보존하는 환경이라 요청전후count 비교로 정정했다. 제품 권한실패로 기록하지 않는다.
- 관련78passed, 이어 route/deployment 도구 포함123passed/0skip/0failure,exit0. 실제RS256/JWKS와 configured factory, 격리PostgreSQL16의inv_app non-owner role. 실제운영IdP/실장비인수 아님.
- mutation2개: method match를 기존partial 허용으로 되돌리면 POST거부시험1failed, 공개 reader필터제거 시 소유권시험1failed. 각exit1,finally로 원본bytes복원 확인. 원본복구후123/123 검증.
- 이미지build exit0: saintvision-backend-candidate:vf-storage-api / sha256:ddea890640066d5dfa7ddaaaf252f075e30046ba344a35e66e42e53ba39353a1. 실제컨테이너권한/설정/조회/쓰기거부 시험8passed/0skip/0failed,47.84초,exit0. UID65532·설정readonly·정본JWT·inv_app 분리·business-enabled목록200/무인증401/쓰기404·405 확인.
- [[저장소 카탈로그 조회와 URI 해석 계약]]1.0.0. 새migration없음(0043유지), 레지스트리/replica dispatch 실행/다운로드/프로젝트공유를 구현했다고 주장하지 않는다.

## 다음 담당

Codex: 같은SHA commit/push/CI·Obsidian·인계. Claude: 등록자scope·메서드dispatch·공개오류재검토. Gemini: 위3개 API를 실제FileExplorer조회/URI입력에 연결 후브라우저검증. CI billing·운영IdP/PITR/5대는운영owner. 기존57.81%/VF운영0/5 유지.
