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
