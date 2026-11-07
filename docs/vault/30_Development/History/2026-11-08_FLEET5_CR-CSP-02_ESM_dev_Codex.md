---
doc_id: "HISTORY-FLEET5-CSP02-ESM-DEV-COMPAT-R1-CODEX"
title: "FLEET5 CR-CSP-02 ESM dev Codex"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-08T02:44:28+09:00"
source_of_truth: "Git"
---

# CR-CSP-02 bounded correction

작업한 것: actual Claude4a29의 soundR1은 상속하고, Root가 unchanged428e AC11에서 확인한 CJS default-export dev 부팅 실패만 한정 수정한다. exact428e에서 새 ordinary branch를 만들고 canonical standalone을 locked esbuild로 self-contained ESM 생성하여 dev/build가 같은 모듈을 쓰게 했다. 기존14회귀를 actual ESM VM 로더로 보존하고 native ESM/default export/CommonJS 부재 시험1건을 추가한다. AC11 workflow·30min timeout·normalizer·assertion은 불변이다.

확인한 것: Root526/41c3e18의 최신 공통/자기판과 public R1/baseline42396627296 failure를 읽고 새 full canonical baseline 529870B/43600e1941cb3527e80adc2daac2064c53a44d129094da53869e6f50d46e334e를 복사했다. Main에서는 source/AST/data/hash/docs만 검사하고 실제 generation/lint/Vitest/build/strictCSP/AC11은 exact hosted workflows에 귀속한다. 각8 gate 명령·즉시 exit·실패 disposition·최종SHA·공식 job/step/artifact·full-state before/end/afterCI 비교는 자기 Evidence의 delivery.json과 receipts가 정본이다. 오래된 branch pending exports는 전체 canonical sync 성공이나 APPLY 권한이 아니다.

다음 첫 행동/담당: Root가 published exact source·Frontend/Docs/AC11 결과·dist/manifest/hash를 대조하고 실제 Claude 한 명에게 bounded delta review를 시작한다. 수락 뒤 Root만 PC3 strict-CSP 재배포·실로그인·no-blink/resources/API 및 진짜 승인·Run/output/all5를 검증한다. 코드/CI/문서 성공으로 실제 운영 수락을 대신하지 않는다. Root만 canonical APPLY를 수행하며 이 오래된 전체 vault는 export하지 않는다.

[[30_Development/Evidence/fleet5-csp02-esm-dev-compat-r1-20261108-codex/README]]

첫 수정본8e3fdbd0 Frontend42398028486는1350pass/1fail/0skip으로 VM 회귀1건이 실패했다. SourceTextModule 플래그가 Vitest worker에 전달되지 않은 실제 시험 실행 설정 오류를 보존하고, 공식 --execArgv 전달만 교정한다. ESM 제품 코드·15시험·negative controls·timeout은 불변이며 새 exactSHA에서 Frontend/Docs/AC11 모두 새 실행이 필요하다.

3bd660b5의 Frontend/Docs는 성공했으나 AC11 job 결론과 달리 원본은4pass/2fail, canonical journey1fail을 기록했다. Node/Vite 직접 fixture가 predev 전 App 모듈을 요청하므로 같은 canonical generator를 browser Vite config 시작에 연결한다. 모든 실제 여섯 case/아홉 invariant의 자동실패0을 최종 artifact로 확인하며, manual acceptance 누락1은 정직한 real-device gate로 보존한다. 기존 AC11 workflow/normalizer/assertion/timeout은 변경하지 않는다.
