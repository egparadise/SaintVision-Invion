---
doc_id: "HIST-STORAGE-SIGNED-SAMPLE-START-20260912"
title: "2026-09-12 STORAGE-SIGNED-SAMPLE Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T12:12:44+09:00"
source_of_truth: "Git"
---

# 서명된 폴더 sample 수집과 검증

Base19475870b40b823996618b3264dc2ff07150a62a / agent/codex/workspace-bridge / PR19. CX-02 무결성 하위 작업, S12-ST 원 owner Claude 유지, 이번 구현 owner Codex/reviewer Claude pending. GUIDE-001/GOV-AGENT-001/GOV-GIT-001 v1.1.0, PLAN-STORAGE-001 v1.0.0, CONTRACT-STORAGE-SAMPLE-001 v1.0.1, 진행판 v1.0.30, agent-delivery v1.1.0/core-reliability v1.0.0 확인.

기존 mTLS probe는 재검증 가능한 결과 서명이 없다. 기존 ReadRoot/hash_file/local collector를 재사용해 허용 root 설정 버전, ChannelProof, 실제 Run/project, catalog 항목과 digest, nonce/유효기간을 고정한 sample을 Node 인증서의 Ed25519 키로 서명하고 같은 challenge/인증서로 검증한다. 실제 파일 손상·scope 교체·만료·서명 위조·결과 누락·과대 파일을 시험한다. 운영 키·장비·DB 변경 없음.

이번 전달 단위는 내부 수집/검증 모듈이다. 실제 Go endpoint/프로필 연결, durable challenge 소비와 StorageCheck/inv.evidence 원자 기록은 후속이며 새 원장·가짜 Run을 만들지 않는다. 서명 확인은 DB의 현재 권한·epoch·nonce 재사용 방지·운영 인수가 아니다. 완료율은 운영 게이트 확인 전 올리지 않는다.
