---
doc_id: "HIST-VF-DEPLOYMENT-GUARD-001"
title: "VF 배포 레지스트리 승인과 동시성 검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T16:13:30+09:00"
source_of_truth: "Git"
---

# VF 배포 레지스트리 승인과 동시성 검토

## 착수

- VF-CL-03/05 후속 owner Codex/reviewer Claude pending. base0db07c8/agent/codex/vf-deployment-guard, 시작2026-09-15T16:13:30+09:00.
- INDEX-PROGRESS-0011.0.84/WORKBOARD-CODEX-0011.0.52/WORKBOARD-VF-CODEX-0011.0.13, 기존최종계획/ADR/역할/운영/보강로드맵/연속정책 및 agent-delivery1.1.0/core-reliability1.0.0 적용.
- Claude ad09e5e/1e4b25c 실제검토·시험2commit을원작성자유지cherry-pick. 기존resolver/replica하드닝은이미동일하여서비스중복수정없음. 검토범위는그두함수이며새관측API전체검토로승격하지않는다.
- 범위: record_deployment의승인시간구간·같은version/environment 동시등록및ORM캐시최신성. 원본시험통과/실패재현후수정·실제PG회귀.
- 이작업은S10 레지스트리metadata이며kernel실행permit/물리배포/ModelManifest결속을추가하지않는다. 현재HTTP표면미노출. 운영DB/migration/장비변경없음.


## 작업과 확인

- Claude원본모델registry/URI/replica 46시험pass. 새독립4시험은만료/미래/ORM캐시철회승인을수용하고동시등록이기존DB부분고유index에서UniqueViolation으로실패함을재현(exit1,4failure).
- 첫안내의active2잔존표현은잘못이었다. 0004의uq_deployments_one_active_per_environment가중복을이미거부한다. 고유제약은보존하고정상service동시호출이둘다성공·하나가superseded되도록수정했다.
- version FOR UPDATE→approval FOR SHARE 순서및populate_existing으로현재stage/digest/decision/time구간을읽는다. [decided_at,expires_at)에서만기록. 기존active UPDATE와새INSERT를같은transaction에둔다.
- 같은version/environment의최초등록경합에서실제pg_stat_activity Lock대기를확인하고두호출성공/active1+superseded1확인. 원시중복INSERT는기존DBconstraint로거부됨. 캐시된released→draft와철회approval도거부.
- fixture오류·정정은 [[2026-09-15_VF_오류와_해결]]. 최종관련82passed/0skipped/0failed exit0. record_deployment는신뢰내부호출자의기록시각을검사하는S10metadata이며현재물리배포permit이아니다.
- 실제candidate image sha256:bc1eaf277472f884b7afa444657556e937cb7e6c5276537e6c2ff7b7c97b9ced build exit0,컨테이너8case모두pass. 해당전체run은89pass/1fixturefail이었고8case부분결과를분리기록했다. fixture수정후위82pass. 이사이제품source변경없음.
- check_docs478/check_ontology/diff exit0. [[모델 레지스트리와 실행 Manifest 권한 경계]]1.2.0. DBmigration/새API/운영배포미수행.

## 다음 담당

Codex:commit/push/동일SHA CI·제한Obsidian인계. Claude:이번승인시각/잠금/ORM갱신독립재검토. 기존ad09e5e검토는resolver owner필터/replica잠금두함수의실제검토수신이며전체신규API검토로확장하지않는다. Gemini:storage/model관측API실화면·browser. 운영owner:CI/SSO/PITR/5대. 기존57.81%/VF운영0/5유지.


## 최종 전달

- code653aea06a8830cfa38dc60141cca41f36005464b commit/push exit0. draft PR28 https://github.com/egparadise/SaintVision-Invion/pull/28, basePR27.
- 동일SHA push CI34941182621/605/600 및PR CI34941208175/115/146 전부billing/spending limit으로시작전실패. 실제annotation8개ci.json.
- 전체sync --check exit1(기존외부/비관리충돌),0db07c8출처대조후제한15파일check→apply→check,15hash일치/pending0/conflict0. 일반Codex공유판은외부편집보존. 최종receipt포함16파일재동기화.
- 최종관련82pass와제품변경없는image8pass를확인. 독립재검토/CI/운영인수미완. 다음Claude PR28잠금/유효시간재검토, Gemini storage/model실화면, Codex finding통합. 운영owner CI/SSO/PITR/5대gate. 기존57.81%/VF운영0/5유지.
