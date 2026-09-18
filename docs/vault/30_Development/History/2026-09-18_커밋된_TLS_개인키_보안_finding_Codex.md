---
doc_id: "SEC-FINDING-COMMITTED-TLS-KEY-20260918"
title: "커밋된 TLS 개인키 보안 finding"
version: "1.0.0"
status: "finding"
author: "Codex"
updated: "2026-09-18T23:59:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 커밋된 TLS 개인키 보안 finding

## 판정

**P1 보안·배포 경계 finding — 조치 선택 대기.** `deploy/certs/saintvision.key`가 Git에 존재하고 `-----BEGIN RSA PRIVATE KEY-----`로 시작한다. 현재 파일 크기는 1,679바이트이며, 이 문서에서는 키를 복사하거나 값을 재기록하지 않는다. 사용자가 보고한 인증서 분석에 따르면 짝 파일 `saintvision.crt`는 `CN=saintvision.internal` 자체 서명 인증서다.

Codex가 현재 고정 SHA에서 확인한 배선은 다음과 같다.

- `docker-compose.prod.yml:13-14`가 인증서와 키를 nginx 컨테이너의 `/etc/ssl` 아래 read-only로 마운트한다.
- `apps/web/nginx.conf:40-41`이 두 파일을 `ssl_certificate`와 `ssl_certificate_key`로 지정한다.
- `git log --all -- deploy/certs/saintvision.key`에서 과거 추가 커밋도 확인된다. 현재 파일만 삭제해도 이력에 남은 키가 자동으로 폐기되지는 않는다.

## 영향 범위와 한계

- 현재 저장소가 비공개이므로 공개 저장소 외부에 즉시 노출됐다고 단정하지 않는다. 다만 저장소 접근권한이 있는 주체는 키를 취득할 수 있다.
- 저장소를 공개로 전환하면 키가 즉시 외부에 노출되는 상태다.
- 내부망에서 개인키가 사용되면 TLS 종단 위장 또는 트래픽 복호화 위험이 있다. PACS 경로와의 연관 가능성은 위험 검토 대상이지만, 실제 의료 데이터 경로 사용 여부는 확인하지 않았다.
- 이 인증서가 실제 운영 배포에서 사용 중인지, 개발 전용인지, 운영은 별도 인증서를 쓰는지는 **미확인**이다. compose 정의가 참조한다는 사실은 실제 배포 사용 증거와 구분한다.

## 사용자 선택지

1. **키 폐기·재발급·저장소 외부 관리**: 기존 키를 폐기하고 새 인증서를 발급하며 secret/certificate provider 또는 배포 호스트에서 주입한다. `deploy/certs`의 비밀 파일을 `.gitignore`로 제외하고 배포 preflight에서 외부 파일 존재·권한·인증서/키 일치를 검사한다. 운영 재배포와 모든 사용처 교체가 필요하다.
2. **Git 이력 정리**: `git filter-repo` 등으로 모든 브랜치·원격에서 키를 제거한다. 협업 중인 브랜치와 clone을 강제 동기화해야 하며, 이력에서 제거해도 이미 취득한 키는 폐기·재발급해야 한다. 실행 비용과 협업 중단 위험이 크다.
3. **내부망 전용 위험 수용**: 내부망 전용·개발용이라는 근거와 공개 전환 금지, 접근권한 범위, 키 교체 주기와 사고 대응을 명시한 위험 수용 결정을 남긴다. 이 선택은 노출 위험을 제거하지 않는다.

## 상태

구현 변경, 키 삭제, 인증서 재발급, Git 이력 재작성은 이 finding에서 수행하지 않았다. 운영 사용 여부 확인과 세 선택지 중 결정은 사용자/운영 책임자에게 남긴다.
