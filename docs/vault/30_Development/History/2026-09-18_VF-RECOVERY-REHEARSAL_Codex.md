---
doc_id: "HIST-VF-RECOVERY-20260918-001"
title: "승인 후 VF 운영 복원 리허설과 원격 선행조건"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-18T10:10:18+09:00"
source_of_truth: "Git"
---

# 승인 후 VF 운영 복원 리허설과 원격 선행조건

- 사용자 Codex영역 승인 후, 로그인통합 다음ready인 VF-CX-05 선행검증을 연속 수행했다. owner Codex/reviewer Claude 미수신. base54f3206, code325554c, branch agent/codex/vf-browser-auth-integration. 운영변경 허용 여부와 실제 검증 합격은 별도다.
- 시작시각은 Evidence각 report.startedAt/observedAt이며 UTC에9시간을 더하면KST다. 보고종료2026-09-18T10:10:18+09:00. agent-delivery/core-reliability 적용.

## 실제 수행과 결과

1. storage inventory/plan: 각exit1(차단조건있음). 원본DB0023→후보0043, pending26개. tenant kill switch=true, node status untrusted/fresh=false, 마지막스냅샷9월13일. 사용자승인 부족이라는 뜻이 아니다.
2. `.225:18443` TCP실제3회 각2초timeout. 원격실행/관측갱신 불가. 기존key/journal/kill switch는 보존했다.
3. `tools/rehearse_lan_upgrade.py --state ... --output ...`: 메모리스냅샷 일관복원→0043→재실행 및 원래열row해시 보존, runtime접근검사 exit0. 임시DB제거. 원본schema/data변경없음.
4. `--retain-directory` 새비공개폴더로 보관백업을 생성하고 저장파일재읽기 복원/업그레이드 exit0. 경로 `C:/Users/egpar/AppData/Local/SaintVision/backups/pilot-20260918-7a6fd27d66194be584ac4eca8acabfc6`. Git과공유Obsidian에는 dump/credential을 넣지 않았다. archive 3012574bytes, SHA256 `8a015f905580c2c0f14b2e915685c0f65d405a1c78613abef3ae35cd056276b6`.
5. `tools/rehearse_independent_restore.py --backup ... --expected-sha256 ...`: 첫실행exit2, create-owned-cluster 준비단계 RuntimeError, 소유컨테이너제거. 동일백업 재시도는exit0. 진단은 연결오류종류만수집(7회 일시 OperationalError), 비밀값/예외원문미공개. 최초실패의세부원인을 확정하지 않았다.
6. 최종 독립cluster복원: 130table/45183row,0043, 기존row보존/replay일치/NOLOGIN역할안전/definer검사/runtime접근/타tenant노드0/백업불변/소유컨테이너제거통과. 원본DB접속과원래credential재사용없음. report.sourceHashes 전체가현재325554c입력과일치; 최초report의dirty는동시frontend/docs작업때문이며 복원도구/migration변경없음.

## 남은 gate와 다음 담당

- 보관backup과독립cluster복원은 완료했다. 같은PC Docker기반으로 **외부보관/off-device/PITR/실제5대복구 인수는 아니다**. private백업은암호화하지않았으며사용자/SYSTEM/관리자ACL로제한했다.
- 사용자 승인은 OK이며 반복요청하지 않는다. 원격접속실패, CI billing, 새코드독립review, 운영SSO/연속WAL/PITR·보관매체가 남은기술/외부조건이다. 원본migration은실행하지않았다.
- 다음첫행동: 운영owner는.225전원/WSL/경로복구; Claude는고정migration0043/backup·restore실측을독립검토; Gemini는로그인통합PR32검토. Codex는접속복구후fresh mTLS/profile 확인, 안전한실행전환을진행한다. 기존57.81%/VF운영0/5를임의승격하지않는다.

- 문서484/ontology/YAML/diff 검사통과. 전체sync check는외부편집충돌로미적용. base54f3206 확인 scoped17파일 hash일치/pending0/conflict0; 일반Codex공유본보존. 최종receipt와보고를같은state로재동기화한다.
