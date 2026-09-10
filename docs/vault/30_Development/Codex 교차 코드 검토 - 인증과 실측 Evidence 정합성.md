---
doc_id: "REVIEW-CROSS-CONTRACT-001"
title: "Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:30:12+09:00"
source_of_truth: "Git"
---

# Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성

판정: **request_changes**. Codex가 다른 저자의 아래 고정 commit과 11개 파일을 직접 읽고 수행한 한정 검토다. Claude/Gemini가 Codex 코드를 검토했다고 표시하지 않는다. 다른 Agent의 최신 전체 코드·브라우저·운영망을 검증하거나 배포 승인을 한 기록이 아니다. 해당 owner 작업 트리는 수정하지 않았다.

입력: GUIDE-001/GOV-AGENT-001/PLAN-BACKEND-001 v1.0.0, ADR-INDEX-001 v1.6.0, CONTROL-INTEGRATION-CONTRACT-001 v1.0.1. base 31f423679107ddc55c9d05566959d6aa69a36e2d, task control-integration / cross-contract-review. engineering:code-review Skill의 correctness/security 기준 적용. 재현 command exit 0은 결함이 없다는 뜻이 아니라 아래 관측을 성공적으로 수집했다는 뜻이다.

| 소유자 | 검토 SHA | 범위 |
|---|---|---|
| Gemini | c323f551068b469e73fb8e84608c2a323c7ee98e | release/recovery engine, Login, release-candidate test |
| Gemini | 251b00ab8218a58307270432972e9900bdf3d2a8 | deployment engine, intranet-deployment test |
| Claude | 4fa551da59e05731b2a4b92976d62b1eb6a60e8a | Node route/service, pilot, API deps/app |

## 수정 요청

| ID / 우선순위 | 위치 | 재현·영향 | owner 다음 행동과 합격 조건 |
|---|---|---|---|
| CR-INT-01 / P1 | Claude `src/saintvision/api/v1/nodes.py:125` | post_heartbeat는 X-Inv-Tenant 및 node_id에서 권한 scope를 만들고 Depends(get_now)만 요구한다. app middleware는 trace만 처리한다. 노출하면 자격 증명 없이 해당 Node의 heartbeat/resource snapshot 갱신 경로에 진입할 수 있다. 코드·의존성 검토이며 운영망 공격 시험은 아니다. | Claude: 현재 Node credential/tenant/node/epoch를 검증하거나 이 경로를 차단하고 Codex의 mTLS probe adapter를 사용. 무자격·다른 Node·폐기된 채널의 갱신 0건 통합 시험. |
| CR-INT-02 / P1 | Claude `src/saintvision/services/nodes.py:139` 및 `:174` | heartbeat는 unlocked read→sequence 비교→write다. 두 transaction이 같은 과거 sequence를 읽고 늦은 작은 sequence가 덮으면 관측 순서가 역행할 수 있다. sweep의 unlocked scan도 갱신과 경쟁한다. 정적 동시성 검토이며 실제 DB race 재현은 다음 owner 검증이다. | Claude: Node 행 잠금/조건부 UPDATE로 최신값 재확인, applied를 같은 원자 변경 결과에서 계산. barrier를 둔 heartbeat/sweep/상태 변경 경쟁 시험. Codex observation은 별도 schema에서 이 경계를 검증했다. |
| CR-INT-03 / P1 | Claude `src/saintvision/services/pilot.py:121` | 정확한 verify_backup 함수와 fake Session으로 `g` 64자를 입력했을 때 verified=True. 길이/lowercase만 검사해 non-hex를 허용한다. 실제 bytes 검증도 함수에 없으며 checksum 문자열을 받는 것만으로 integrity proof가 되지 않는다. | Claude: hex 검사 및 trusted worker의 실제 bytes/hash/Evidence 확인을 분리하고 비검증 입력은 assertion으로 기록. non-hex·실제 손상·다른 backup hash·검증 중 파일 교체 거절. |
| CR-INT-04 / P1 | Gemini `apps/web/src/features/release/releaseEngine.ts:3`, `:57`, `:137` | 생성자만 실행해 SLO 7개 met, 접근성 5개 pass를 얻는다. rollbackToVersion은 메모리 flag만 바꿔 rollbackVerified=True. 배포/측정 없이 합격이 생성된다. | Gemini: demo를 명시하고 실제 측정 전 unknown으로 표시. read-only Evidence API의 SHA/측정 조건/시각/실제 배포 결과로만 pass 전이. 상수 검사 대신 누락·실패·stale Evidence 브라우저 시험. |
| CR-INT-05 / P1 | Gemini `apps/web/src/features/recovery/recoveryEngine.ts:17` | 현재 epoch=1/seq=100에 future epoch=99/seq=1 및 same epoch/seq=999 둘 다 true. UUID recovery epoch equality와 allocation별 정확한 token 계약에 맞지 않는다. | Gemini: canonical generated 계약 사용, 클라이언트 비교를 실행 권한으로 사용하지 않음. 새 epoch 설치는 trusted control 경계에서만 수행. 다른 epoch/미발급 token의 결과·쓰기 0건. ADR-020/027을 따른다. |
| CR-INT-06 / P1 | Gemini `apps/web/src/features/auth/Login.tsx:18` | timeout 뒤 hardcoded cluster:admin persona로 전환한다. 실제 OIDC 인증은 호출하지 않는다. 코드에는 simulation 설명이 있으므로 UI demo로만 인정하며 운영 로그인 완료로 승인하지 않는다. | Gemini: 검증된 access token과 현재 서버 grant 결과로 화면 연결. server auth 실패/만료/철회에서 persona fallback 금지. 실제 IdP PKCE 브라우저 시험은 구성 후 수행. |
| CR-INT-07 / P1 | Gemini `apps/web/src/features/deployment/deploymentEngine.ts:64`, `:127`, `:226` | 트래픽 없이 5 Node passed 및 9/11/14/16/18ms, 교육 4개 completed를 생성한다. arbitrary-actor 문자열로 signoff=true. CA/IP/GPU 정보도 상수다. SHA-256 문자열은 형식에 맞지만 실제 image 내용으로부터 계산한 증거는 없다. | Gemini: 실제 인벤토리·TLS 검사·Smoke 원시 로그·image digest provenance·검증된 운영자 승인과 연결. 미확인 장비/CA는 unknown. frontend 문자열 입력을 인수 서명으로 취급하지 않음. |
| CR-INT-08 / P2 | Gemini `apps/web/src/features/release/releaseEngine.ts:69` | #30363d / #0d1117의 sRGB 계산 대비는 약 1.551:1이고 선언된 4.8:1과 다르다. 전체 UI WCAG 판정이나 실제 브라우저 배경 조합 검사 결과는 아니다. | Gemini: 실제 DOM 대비·키보드·포커스 검사를 실행하고 원시 결과 저장. 잘못된 상수 assertion을 교체. |
| CR-INT-09 / P2 | Claude `src/saintvision/api/app.py:93` | 응답 traceparent의 span ID를 16자리 0으로 설정하고 입력은 최소 3조각만 검사한다. invalid parent가 정상 trace처럼 전파된다. | Claude: Codex tracing adapter 또는 검증된 Trace Context 구현 사용. 0/중복/길이/header 오류의 새 trace 생성, 정상 trace 유지 및 nonzero server span 검증. |
| CR-INT-10 / P2 | Gemini `apps/web/src/features/deployment/deploymentEngine.ts:178` | 생성 config의 location /는 SPA fallback index.html에도 1년 immutable cache를 적용한다. index.html no-cache라는 routing metadata와 다르다. 실제 Nginx 구동은 하지 않았다. | Gemini: index.html 재검증과 digest asset immutable을 별도로 설정하고 nginx -t 및 업그레이드/롤백 후 HTML·asset 응답 헤더를 실제 HTTPS로 확인. 실제 project/run SSE path도 계약에 연결. |

추가 확인 대상: Claude `api/deps.py:81`의 replay_or_reserve는 row를 예약하지 않고 읽기만 하며 actor/epoch를 key/hash에 포함하지 않는다. 동시 요청, TTL, 현재 project 권한을 포함한 해당 업무 route 검토가 더 필요하다. 이 한정 검토만으로 cross-project 데이터 유출이 재현됐다고 주장하지 않는다. `pilot.py`의 ERR-DESIGN-006 대기 설명은 ADR-020의 새 recovery UUID epoch 결정으로 갱신해야 한다.

## 실제 재현

`python tools/reproduce_handoff_review.py --typescript C:/Project/SaintVision-Invion/apps/web/node_modules/typescript/lib/typescript.js` (프로젝트 requirements 환경) exit 0. Git show로 고정 소스를 읽고 TypeScript를 메모리에서 실행했다. Python은 정확한 verify_backup 함수에 fake Session을 제공했다. 실제 Node 연결, 사용자 인증, 배포, 브라우저 접근성, 원격 메시지 전송은 이 재현에 포함되지 않는다. 원시 관측과 11개 source SHA-256은 [[cross-contract-review-provenance.json]]. 재현 도구는 tools/reproduce_handoff_review.py 및 .mjs에 보존했다.

위 finding은 수정 owner의 commit에서 다시 검증해야 닫는다. Git/Obsidian 검토 문서로 인계 자료를 공개하며 실제 수신 확인은 pending이다. [[Codex Control API 인증과 Node 관측 계약]]과 [[Codex 잔여 개발 작업과 합격 증거]]를 함께 읽는다.

