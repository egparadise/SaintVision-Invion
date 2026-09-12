---
doc_id: "HIST-STORAGE-COMMIT-20260912"
title: "2026-09-12 STORAGE-COMMIT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T13:23:04+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-COMMIT Codex 검증보고

구현 `fd0c081b8065dde85d3b41092768c2fe78c20158` / base ea54634 / agent/codex/workspace-bridge / CX-02 owner Codex / reviewer Claude pending / PR19 draft. [[2026-09-12_STORAGE-COMMIT_Codex_착수]], [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.3.0 / ADR-090.

## 작업한 것

0037_storage_sample_commit과 inv.storage_commit.StorageSampleStore를 추가했다. 기존 kernel inv.evidence/public.storage_checks가 기록 정본이며 새 requests/consumptions는 challenge 및 중복 소비 참조만 보존한다. Run/project가 실제 존재하고 현재 kernel can_request, linked business project/user/member 권한, 해당 contribution 등록 소유자를 모두 확인한다. 단순 프로젝트 요청 권한만으로 다른 사람의 폴더를 점검할 수 없다.

발급은 Run 버전/attempt·현재 recovery epoch/channel·contribution 경로/버전·정렬된 최대32개 catalog 항목을 고정하고 request UUID/nonce/digest를 불변 보존한다. 같은 request의 sample_limit/scope 변경·조용한 nonce 갱신은 거부한다. 네트워크 호출은 DB transaction 밖에서 한다. 수신 시 같은 현재 권한·Run·root·catalog·channel을 다시 잠그고 실제 TLS leaf와 서명/만료/hash를 검사한다. Evidence·StorageCheck·consumption·outbox를 한 transaction으로 기록하며 마지막 쓰기 후에도 DB 시각으로 만료를 재검사한다.

같은 request/응답 bytes replay는 기존 ID만 반환하고 다른 응답은 IDEM-0001로 거부한다. replay도 현재 권한/owner/channel 검사는 통과해야 한다. inv.evidence 입력/출력 hash가 저장된 challenge/서명 payload와 연결된다. StorageCheck.detail에는 raw envelope, certificate DER, request/evidence ID, 표본 범위와 운영 인수 미평가가 남는다. 점검 일치/실패는 Run의 실행 완료/실패로 바꾸지 않는다. policyDecisionId의 storage-owner-v1은 이 요청의 현재 소유권 검사 식별자이며 실행 승인 토큰이 아니다.

DB는 tenant RLS/최소 컬럼 SELECT 및 고정 true sentinel의 UPDATE 권한만 부여한다. 잠금용 UPDATE가 경로·소유자·catalog 변경 권한을 주지 않는다. request/consumption 및 서명 scope의 StorageCheck UPDATE/DELETE는 기존 immutable_record trigger로 차단한다. 새 SECURITY DEFINER 함수는 없고 definer-policy의 기대 head만0037로 갱신했다.

## 확인한 증거

- Windows의 실제 disposable PostgreSQL 새 시험22개 통과(exit0). 제품 commit 전 검증이며 운영 DB가 아니다.
- clean `fd0c081b8065dde85d3b41092768c2fe78c20158` Linux 실제 Go daemon/mTLS/파일/격리 PostgreSQL 통합 **156 passed/0 skipped/exit0**. 신규 DB22, Node20, 기존 provisioning21/서명68/파일25. [실행 SHA·개별 case·image/hash·cleanup](../Evidence/storage-commit-linux-fd0c081.json). Windows와 중복 합산하지 않는다.
- 정상·동시 같은 응답·다른 응답 재소비·현재 권한/소유자/채널/폴더/catalog 변경·서명 오류·tenant 읽기/쓰기 격리·불변 기록·마지막 쓰기 실패/만료 후 전체 rollback을 검증했다. 만료 후 rollback 시험은 verifier clock 입력을 주입한 결정론적 경계 시험이며 실제30초 대기를 했다는 뜻이 아니다.
- git push origin agent/codex/workspace-bridge exit0. [같은 SHA CI6개](../Evidence/storage-commit-fd0c081-ci.json)는 결제/한도 제한으로 job 미시작 failure. 로컬 통과를 CI 통과로 대체하지 않는다.
- 첫 시험19개 중3개 실패는 테스트 fixture가 contribution 회수 시각/channel CAS/Run 상태 전이 규칙을 지키지 않았기 때문이다. fixture 수정 후22개 및 clean Linux156개 통과. [[2026-09-12_STORAGE-COMMIT_오류와 해결]].

## 화면 문제 해결

사용자 이미지의 Studio는 서버 중단이 아닌 로그인 세션 없음에 따른401 안내였다. 실제 운영 중 PID22076/port18100 서버를 재시작하지 않고 기존 agent-codex-dev-environment launcher를 사용했다. 현재 Windows 바탕화면 `C:/Users/egpar/OneDrive/바탕 화면/SaintVision 개발 시작.lnk`를 복구하고 실행했다. 2026-09-12T13:07:17+09:00 새 session 생성/유효 session1/미소비 loginlink0을 SQLite read-only 집계로 확인했다. 브라우저 화면을 직접 확인한 것은 아니다. 비밀 URL/토큰을 출력하지 않았다.

앞으로 바탕화면 바로가기를 실행하면 새 일회용 로그인 링크로 Studio가 열린다. 로그인 세션8시간/일회용 링크120초 제한은 유지한다. 주소만 직접 열었을 때 쿠키가 없거나 만료되면 다시 로그인해야 한다. 인증 우회나 영구 세션은 적용하지 않았다.

## 이어서 할 첫 행동

Codex: 승인된 호출 경로의 request/result 조회·권한 재검사 및 운영 sample 설치 계약을 연결한다. 현재 모듈은 내부 trusted service이며 공개 HTTP/UI 경로가 아니다. 만료된 collect 요청의 자동 재발급/오래된 응답 자동 복구를 주장하지 않는다. 저장된 동일 응답의 accept replay만 지원한다. 운영 .225 프로필·storage-policy 설치, 실제7개 원격 업무 시험, Windows 네이티브 수집/다중 root·5대/GPU는 남아 있다.

Claude: fd0c081/0037 최소권한·RLS·잠금 순서·기존 StorageCheck와의 관계/ADR-090 독립 검토. Gemini: 표본 점검 정상과 운영 인수/전체 디스크 정상/Run 완료를 구분하고 새 query 계약 이후 표시한다. 기존 ResultView 실행 결과 정본은 유지하며 이번 sample Evidence가 이미 결과 UI에 연결됐다고 표시하지 않는다.

전체 성숙도 **2775/4800=57.81% 완료,42.19% 잔여 유지**. 이번 내부 기록 구현만으로 S12 운영 인수 단계를 올리지 않는다. 공식 registry done0은 CI/독립 검토/실장비 인수 gate가 남았다는 뜻이며 구현0%가 아니다.


전달 검증: `.work/cx01_local.py upgrade` exit0, 기존23개 prior→0037 head/replay/최소권한/definer audit 통과. [DB 업그레이드](../Evidence/storage-commit-upgrade-fd0c081.json). 종료 시 문서 보고 작성 중이라 harness dirty=true이며 제품 소스는 fd0c081에서 변경하지 않았다. [Windows22](../Evidence/storage-commit-windows-20260912.json)는 commit 전 시험으로 구분한다. check_docs.py exit0(원문24/문서321/작업48), check_ontology.py exit0, diff --check exit0. PR19 설명 갱신/draft 유지. 보고 commit/push 후 Obsidian check→apply→check를 진행한다.
