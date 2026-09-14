---
doc_id: "HIST-SHARD-OBSERVATION-FIX-REPORT-20260914"
title: "2026-09-14 SHARD-OBSERVATION-FIX Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T22:24:31+09:00"
source_of_truth: "Git"
---

# 샤드 관측 수정 후보

제품ea42657, branch agent/codex/frontend-mutations. 기존8037166과Gemini43640ee를3ad1530에서충돌없이병합한뒤수정했다. commit/push완료,공유integration/main에는미병합·미배포. Codex작성/Claude검토·GeminiUI인수pending.

- 샤드새로고침·전체취소후조회·자동회수상태조회가정본shards를같은변환으로적용한다. 다른parent응답과project누락을거부,flatfallback없음. Run변경시과거관측과알림을초기화한다.
- 실제receipt를조회하지않았는데receipt수신/모든자원반환을확인했다고표시하던문구제거. allPhysicallyStopped확인과자원반환을구분해후자는Run에서확인하도록표시한다.
- 개별샤드attempt/자원반환필드는정본뷰에없어추정하지않고optional/미관측처리. 실패Run에evidenceId가있다고합격표시하지않는다.
- 첫화면의가짜노드5개/Run/Workspace/승인/성공결과fixture제거,빈배열과null로시작. 빈nodes응답도적용한다. 응답누락시Node/승인매핑의임의수치및고정projectID는아직남아있어FE-M04전체종결아님.
- Gemini가이동한tests/kernel-mutations.test.ts와원래src쪽중복12개를정리했다. 동일시험을진척으로중복계산하지않는다.

`npm test -- --run`:최종22파일**140passed/3.63s**,exit0. 새샤드관측9개포함,API모사단위시험이며브라우저/원격증거아님. `npm run build`:TypeScript/Vite6.4.3 exit0,6.80s. build는제품수정후수행했으며이후변경은시험beforeEach수정과중복시험제거뿐이다. 운영배포없음.

첫시험은151passed/1failed였다(중복12개포함). beforeEach가mockReset()의반환함수까지반환해Vitest의정리함수로호출되면서403mock이추가호출된시험작성오류였다. 중괄호로반환하지않도록수정한뒤9개/전체140통과. 커널오류를우회한것은아니다.

다음Codex:응답누락값의unknown표시와실제project선택연결,최신후보브라우저검증. Gemini:ea42657통합·레이아웃/상태표시확인. Claude:관측·권한·실패처리독립검토. Gemini96191cc의외부IdP PKCE코드는이번merge에포함됐지만실운영IdP설정/로그인검증은미수행이다. 전체57.81%유지,CI/실장비인수별도.

CI동일SHA4건은22:24:38KST billing제한으로job시작전실패했다. [CI증거](../Evidence/shard-observation-fix-ci-ea42657.json).
