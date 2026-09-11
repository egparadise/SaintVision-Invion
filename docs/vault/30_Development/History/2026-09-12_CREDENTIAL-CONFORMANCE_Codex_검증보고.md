---
doc_id: "HIST-CREDENTIAL-CONFORMANCE-REPORT-20260912"
title: "2026-09-12 CREDENTIAL-CONFORMANCE Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T00:47:43+09:00"
source_of_truth: "Git"
---

# CREDENTIAL-CONFORMANCE 검증보고

CX-02 / owner Codex / reviewer Claude pending. base34d457c, 구현·검증 **8222f0b6432a7aada7d6b65add260f806fc7ffd2**, branch agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_CREDENTIAL-CONFORMANCE_Codex_착수]], [[Codex 자격증명 보안 검증 인계]].

## 작업한 것

`saintvision.credentials.contract`에 CredentialContext·CredentialResolver·CredentialHandle·CredentialDenied Protocol을 추가했다. 이 타입이 인증/인가를 대신 수행하지 않는다. 기존 adapter를 수정하거나 두 번째 runtime resolver를 구현하지 않았다.

`tests/credential_conformance.py`는 구현별 fixture에 적용할39개 공통 보안 사례다. tenant/project/subject/run 및 용도/목적지, invalid reference의 read 전 거부, resolve 전 및 resolve→use 사이 회수/만료/삭제/재바인딩, 매 use 재검사, old version 고정, 파일 경계9종, handle 표현·오류/trace/log 비밀 비노출, callback 실패 비재시도를 검사한다.

합성 모델39개와 검출력 확인8개를 별도 `credential_model`로 구분했다. 결함8개는 context 검사 누락, 인가 전 read, revoke 무시, symlink 허용, old reference 재지정, repr 비밀 노출, 자동 callback 재시도, 비밀이 섞인 exception cause 노출이다. 검출 assertion이 실패함을 확인하는 시험이며 잘못된 구현이 합격했다는 뜻이 아니다.

## 확인한 증거

- clean8222f0b에서 `python -m pytest tests/test_credential_conformance.py -q --junitxml=.work/credential-conformance-8222f0b.xml`: **47 passed, 0 skipped, exit0**, Windows Python. [개별 case와 scope](../Evidence/credential-conformance-8222f0b.json).
- `python -m pytest tests/test_credential_conformance.py -m credential_backend -q`: **47 deselected, 실제 child exit5**. 모델을 실제 backend 시험으로 선택하지 않는 것을 확인했다. PowerShell 전체 명령 결과가 exit1로 보였으므로 subprocess.returncode로5를 직접 확인했다. 의도한 빈 집합 판정이며 제품 결함이 아니다.
- `git push origin agent/codex/workspace-bridge`: 8222f0b, exit0. [동일 SHA CI](../Evidence/credential-conformance-8222f0b-ci.json)는 계정 제한으로 job 시작 전 실패, CI 합격 아님. 원인/대응은 [[2026-09-12_PTY-INTENT_오류와해결]]을 따른다.

**실제 secret provider, Linux 파일 시스템, DB 권한, 외부 API, Windows ACL을 실행한 시험이 아니다.** 실제 backend fixture는 아직 없다. 모델은 파일 경계를 상태로 표현하며 OS 검증을 대체하지 않는다. 기존 PTY61/core25/migration21은 이번47개에 합산하지 않는다.

## 인계와 다음 첫 행동

Claude는 공통 suite를 실제 resolver/registry/Linux backend에 연결하고 합성 secret을 사용한39개 실제 case를 제출한다. 변경된 owner/mode/symlink/inode/oversize는 실제 OS 조작이어야 하며 guard를 monkeypatch해 성공시키지 않는다. 제공되지 않은 fixture, skip/xfail, 0개 선택을 합격 처리하지 않는다.

Codex는 실제 구현의 scope/회수/descriptor 경계를 독립 검토하고 open→read 파일 교체와 다중 프로세스 회수/dispatch 장벽 시험을 추가한다. 현재39개는 resolve→use 전이 검증이며 모든 동시성 interleaving의 증거가 아니다. 호출 후 외부 효과 회수/메모리 완전 소거를 보장하지 않는다. Gemini는 model/observed/verified 상태를 구분한다.

CX-02와 실제 운영 인수는 진행 중이다. 전체 추정 **57.29% 완료 /42.71% 잔여(표시55%/45%) 유지**. 실제 backend가 없어 점수를 올리지 않는다. 다음 작업/검증/담당을 공통 진행판과 Codex 작업판에 기록한다.

## 전달 검사

문서/ontology·최종 push 및 Obsidian 영수증은 아래에 기록한다.

- 2026-09-12T00:48:13+09:00: `check_docs.py` exit0(24 원본hash/281 versioned docs/48tasks), `check_ontology.py` exit0, 변경Python4개 `black --check` exit0, `git diff --check` exit0. Obsidian 사전check455개/변경9개/충돌0, exit0.
