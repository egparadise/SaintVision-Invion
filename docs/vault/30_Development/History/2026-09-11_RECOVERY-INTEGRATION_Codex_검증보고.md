---
doc_id: "HIST-RECOVERY-INTEGRATION-REPORT-20260911"
title: "2026-09-11 RECOVERY-INTEGRATION Codex 검증보고"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-11T18:58:38+09:00"
source_of_truth: "Git"
---

# 2026-09-11 RECOVERY-INTEGRATION Codex 검증보고

최종 구현은 **869d74b**, clean 검증 SHA는 **b5aef8a23bd4d8baf69db58d83366637e65c8126**다. 초회 구현/검증 5fc1116은 아래에 이력으로 보존했다. CX-01/CX-07의 이번 구현 단위는 전달하며 전체 카드/운영 인수는 진행 중이다. owner Codex, reviewer Claude pending. 착수 base d14db0a, branch agent/codex/workspace-bridge, PR19. [[2026-09-11_RECOVERY-INTEGRATION_Codex_착수]]와 [[Codex DB 함수 감사와 복원 판정 검토]] v1.1.0/ADR-073을 따른다.

## 작업한 것

Claude dee31e5의 recovery_drill(0581964 권한/RLS/서비스 probe 포함)을 같은 파일명으로 이어받았다. DB 함수 감사 정본은 Codex b9a53f8의 `check_definer_functions.py`+9개 versioned policy이며, SQL 패턴 감사 구현을 두 번째 합격 판정기로 추가하지 않았다. 일반 복원 서비스 owner는 Claude, 이번 고위험 판정 통합 owner는 Codex다.

- nonzero pg_restore, target에서 사라진 table, 읽기 실패·권한/소유자/RLS·definer 불일치를 거부한다. 원래 객체 owner/권한을 보존한다.
- public/inv 양쪽에서 두 tenant와 빈 scope를 검사하고 seed transaction을 전부 rollback한다.
- RPO는 복원 시작 시점 기준이며 RTO는 모든 검증 종료까지다. 미래/미상/음수/비수치 측정을 거부하고, DB 기록은 실제 서비스 인자와 올림한 초를 사용한다.
- 복원 도중 source에서 발급된 상한과 target의 is_called를 반영해 다음 fencing 값 재사용을 막는다. sequence를 자동 변경하지 않는다.
- CLI/하위 pg client의 password argv와 예외 원문 출력을 방지한다. `operationalRecoveryVerified=false`와 미검증 범위를 보고서/DB notes에 유지한다.

## 확인한 증거

| 실행 | 코드/환경 | 결과 |
|---|---|---|
| `python tools/check_kernel_docker.py --prepared .work/sv-kernel-8c70955143a6/prepared.json --tests tests/integration/test_recovery_drill.py tests/integration/test_definer_audit.py tests/test_pilot.py` | clean 5fc1116, 격리 Linux runner + 일회용 PostgreSQL 16 | **64 passed, 0 skipped, exit 0** |
| `python -m pytest tests/core/test_recovery_verdict.py -q` | 같은 5fc1116, Windows Python | **22 passed, 0 skipped, exit 0** |
| Linux용 Go supervisor 시험 바이너리의 `TestTerminal*` 3개 | 5fc1116, network none/read-only 시험 컨테이너 | **3 passed, exit 0** |
| docs / ontology / black | 코드 commit 전후 관련 검사 | exit 0, 최종 보고서 검사는 아래 전달 기록에서 갱신 |
| `git push origin agent/codex/workspace-bridge` | d14db0a→5fc1116 | exit 0 |
| 같은 SHA GitHub CI | 6 workflow | **job 시작 전 failure — 계정 결제/한도** |

64개는 새 실제 복원 12개+기존 함수 감사 22개+pilot 서비스 30개다. 22개는 판정/시간/argv/오류 경계다. 총 89개는 서로 다른 세 집합이며, 앞선 Windows PostgreSQL 준비 시험 12개를 중복 가산하지 않았다. 과거 402/304/43 시험을 이번 SHA의 전체 회귀 수로 합산하지 않는다. migration/함수 policy 정의는 바꾸지 않았으므로 이전 20개 upgrade 경로를 재실행한 것으로 쓰지 않는다.

복원 시험은 실제 dump/restore·부정 DB mutation·미래 백업 시각·복원 도중 토큰 발급·DB 기록을 포함한다. SQLAlchemy/libpq DSN 두 경로와 900.01초→901초·met_targets=false를 실제 저장/조회했다. 생성한 복원 DB와 격리 runner/DB 컨테이너는 정리됐다. 운영 DB/Node/계정/제출 gate를 변경하지 않았다.

[Linux 64 원본](../Evidence/recovery-5fc1116-linux.json), [판정/검사 원본](../Evidence/recovery-5fc1116-checks.json), [Go 3개](../Evidence/recovery-5fc1116-supervisor.json), [CI ID/annotation](../Evidence/recovery-5fc1116-ci.json). 대표 [Core CI 34586022626](https://github.com/egparadise/SaintVision-Invion/actions/runs/34586022626). 로컬 성공은 CI/peer/운영 인수를 대체하지 않는다.

## 전체 완료율

이전과 같은 **48개 task 동일 가중·0/25/50/75/100** 기준이다. S06-BE는 이전 평가 이후 c5f2154에서 최신 kernel 통합과 로컬 실제 편집/PTY 시험을 확보해 50→75로 갱신했다. 이번 복원 단위는 이미 부분 구현으로 평가한 S11-DB/S12-DB 내부 진척이므로 도구/시험 건수만큼 별도 점수를 추가하지 않는다.

**2750 / 4800 = 57.29% 진척, 42.71% 잔여. 기존 5% 단위 보고는 약 55% 진척 / 45% 잔여**다(이전 계산 56.77%). 대형 과제별 노력/기간은 동일하지 않으므로 일정 추정이나 공식 합격률이 아니다. registry의 공식 done 0/48은 유지하며, 코드 0%라는 뜻은 아니다. [48개 점수와 근거](../Evidence/development-progress-recovery-20260911.json).

Gemini 858763c의 64.58%는 작성자 보고로 보존하되 공통 승인 수치로 채택하지 않는다. `deploy_intranet.ps1`은 Compose config 검증 뒤 `up -d --build`를 안내문으로 출력한다. 이 명령 실행을 TLS 운영 배포·실제 rollback 성공으로 계산할 수 없다. 487a42c의 drain은 local Set, PTY ticket은 문자열 생성이며 서버 승인/발급 API를 호출하지 않는다. 실제 결과 header/Authorization 불일치도 남는다. 3c1850b의 로그인 실패 시 관리자 fallback 제거는 개선으로 인정한다. 전체 실장비/정본 API 여정 및 12개 FE task 일괄 75점은 아직 근거 부족이다.

## 새 검토 수신과 이어서 할 일

- **Codex CX-01 첫 행동**: Claude cdf98ad F1의 두 번 lease snapshot 문제를 실제 함수 경합 시험으로 고정하고 단일 snapshot의 자원별 held 분배로 수정한다. 원본 0031은 보존하고 필요한 경우 새 forward migration/정본 policy를 함께 갱신한다. F1은 Claude가 SQL 문장 순서를 재생한 재현이며 이번 Codex가 전체 함수 경합을 새로 실행한 것은 아니다.
- **Codex/Claude F2**: 서버 frame 감사는 Node 호출 후다. 다만 supervisor가 mutex 안에서 sequence/hash를 검사하고 write 전에 sequence를 소비한다. 이번 Linux 3개 회귀가 통과했으므로 '다른 내용이 실제 두 번 실행됐다'는 주장은 입증되지 않았다. 전송 전 intent 기록과 응답 유실 시 감사 정합성은 후속으로 검토하고, 감사 행을 미실행 완료 증거로 바꾸지 않는다.
- **Claude CL-01/03**: 5fc1116/ADR-073의 독립 검토와 단일 감사 도구 수렴. 별도 클러스터 role/실제 로그인·object bytes·Node journal/epoch·PITR/운영 재개 시험이 남는다. cdf98ad 검토는 d14db0a에 대한 findings이며 최신 복원 구현 승인으로 간주하지 않는다.
- **Gemini GM-01/03/05/06**: 실제 결과 Authorization/hash, 서버 발급 PTY ticket, ADR-053~056의 2인 승인 drain을 정본 API에 연결한다. fixture smoke/Compose 설정 검사와 실제 2-PC/TLS/rollback 증거를 나눠 보고한다.
- **Codex CX-02**: credential/Storage/IdP·허용 폴더 입력 계약을 이어 확정한다. CX-03 원격 설치 receipt 수신→실제 7개 시험. CI 계정은 운영 책임자 선행이며 이 때문에 다른 구현을 중지하지 않는다.

18:42:48 읽기 조회에서 worker .225는 여전히 lan-observe-v1이다. [GitHub/LAN 관측 원본](../Evidence/recovery-runtime-snapshot-20260911.json). 실제 원격 7개/5대/GPU/운영 복원은 이번 합격 항목에 없다.

## Obsidian/전달

공통 진행판·4개 owner 카드와 검증/오류/근거를 갱신한다. 외부 변경 3문서는 원본 bytes/hash와 Git858763c 대응을 [제안 원문](../Evidence/recovery-sync-proposals-20260911.json)에 보존했다. Claude/Gemini의 새 작성자 보고를 수신하고 Codex의 기존 최신 이력과 독립 판정을 유지한다. Claude 문서의 19:xx/20:40 표기는 원저자의 표기이며 실제 수신·검토 시각으로 인용하지 않는다.

최종 docs/ontology/build/push/CI/Obsidian hash 영수증은 후속 전달 commit에서 기록한다. 현재 main 병합·독립 승인·전체 운영 인수는 완료하지 않았다.

### 최종 기록 보강

869d74b에서 JSON 보고서의 `scope/operationalRecoveryVerified/notVerified`를 DB notes에도 보존하도록 보강하고 실제 저장/조회 assertion을 추가했다. 앞 표의 64/22/3은 정확히 5fc1116의 증거다. 이 후속 변경을 포함한 clean b5aef8a에서 Linux64/core22가 다시 통과했다. DB notes의 범위와 미검증 조건 저장/조회도 실제 시험에 포함했다.

### 최종 고정 SHA 검증·전달

- **b5aef8a / 구현 869d74b**: Linux 통합 **64 pass/0 skip**, core **22 pass/0 skip**, exit0. 5fc1116 때의 같은 64/22를 다시 더하지 않는다. Node 소스는 5fc1116 이후 바뀌지 않았으며 Go3 증거는 원래 SHA로 보존했다.
- [최종 Linux 원본](../Evidence/recovery-b5aef8a-linux.json), [최종 판정 검사](../Evidence/recovery-b5aef8a-checks.json), [최종 CI 원본](../Evidence/recovery-b5aef8a-ci.json). b5aef8a CI6은 계정 제한으로 job 시작 전 failure다.
- docs268/원문24/task48/outcome12, ontology, black, 문서 ZIP build exit0. 제품 전체 build나 물리 장비 시험 합격을 뜻하지 않는다.
- b5aef8a push exit0. 18:56:07 Obsidian 관리430개 전부 hash 일치, pending0/conflict0, 외부 원문3개 보존. 이번 최종 증거/영수증 추가 후 같은 sync 절차를 다시 수행한다. OneDrive cloud upload는 별도 확인하지 않았다.
- 다음 첫 행동/owner는 변함없다: Codex F1 경합 수정/F2 감사 검토→CX-02; Claude는 최신 b5aef8a/ADR-073 독립 검토. 원격 설치·운영 인수·CI 차단은 미해소다.

### 최종 동기화 영수증

2026-09-11T18:59:44+09:00에 전달 commit `3c74d13c7ee568b6fe970b683add0fe42b8ff1ef` 기준 Obsidian **433개** 관리 파일의 모든 SHA-256 일치, pending0/conflict0, check→apply→check 모두 exit0을 확인했다. PR19의 제목/본문도 최종 Workspace·복원 범위와 실제 검증/미해결 finding으로 갱신했다. 이 영수증 반영 후 최종 commit/push와 동일 guarded sync를 수행하며 제품 소스는 검증 b5aef8a와 일치한다. 동기화 범위는 로컬 Obsidian 사본이고 OneDrive cloud upload는 별도다.
