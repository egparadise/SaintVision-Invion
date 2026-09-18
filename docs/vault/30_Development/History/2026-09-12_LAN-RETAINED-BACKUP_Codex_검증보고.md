---
doc_id: "HIST-LAN-RETAINED-BACKUP-REPORT-20260912"
title: "2026-09-12 LAN-RETAINED-BACKUP Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T19:46:57+09:00"
source_of_truth: "Git"
---

# 보관 백업과 실제 복원

CX-02 Codex 무결성 지원 / Claude reviewer pending. 상위 S12-ST Claude owner 유지. base4ef821b → 코드7a0a25bc0e7be701c42ed751cbc7e09f3c8a13c5, agent/codex/workspace-bridge. commit/push exit0. [[2026-09-12_LAN-RETAINED-BACKUP_Codex_착수]].

## 구현

기존 리허설의 `--retain-directory` 옵션을 추가했다. 기존 부모의 링크/reparse를 거부하고 새 디렉터리를 배타 생성한 뒤 private ACL/권한을 적용한다. dump와 manifest를 배타 생성/flush/fsync하고 저장된 manifest·크기·SHA256를 검증해 읽은 bytes를 pg_restore 입력으로 사용한다. 기존 디렉터리·파일을 덮어쓰지 않고 파일 누락/변조/하드링크를 거부한다. 코드 worktree/public 아래 저장은 거부한다. 실패한 보관 파일은 자동 삭제하지 않으며 복원 합격 여부는 별도 report로 판정한다.

원본 파일은 `C:/Users/egpar/AppData/Local/SaintVision-Recovery/snapshot-7ff48f5651a64acfb0e003390ca8a386`의 snapshot.dump/manifest.json이다. Git/Obsidian/public에는 dump를 복사하지 않았다. Windows ACL 상속 차단과 현재 사용자 소유, OWNER RIGHTS/current user/SYSTEM/Administrators 규칙을 확인했다. 로컬 비암호화 보관이며 다른 관리자·동일 사용자 악성 프로세스·서버 디스크 손실에 대한 보호를 의미하지 않는다. Windows 디렉터리 metadata 전원 장애 내구성은 시험하지 않았다.

## 동일 clean SHA 실제 검증

- `python -m pytest tests/core/test_lan_restore_upgrade.py -q --junitxml=.work/lan-retained-backup-tests.xml`: exit0,11 passed. 기존 행 보존5 + 보관 파일 경계6(정상/내용변조/manifest변조/누락/하드링크/기존디렉터리) 통과.
- `python tools/rehearse_lan_upgrade.py --state <pilot> --retain-directory <새 private directory> --output .work/lan-retained-backup.json`: exit0. 19:45:12~19:45:44 KST. 실제 파일2,167,833bytes를 재검증한 후 복원,130개 테이블 조회 행 합계28,726 보존,0037 upgrade/전체 replay 일치,definer9 unsafe0/runtime DB transaction 통과,폐기용 DB 정리. 파티션 부모/자식 조회 중복 가능하므로 고유 행 수로 해석하지 않는다.
- CI 같은 코드 SHA 19:45:38 KST:5개 billing 실패(job 미시작),Core34689268865 queued. CI 합격 아님.

Evidence: [[lan-retained-backup-7a0a25b.json]], [[lan-retained-backup-7a0a25b-tests.xml]], [[lan-retained-backup-7a0a25b-ci.json]], [[lan-retained-backup-acl.json]]. 파일 hash는 변조 검출 기준이며 별도 서명/독립 보관을 대체하지 않는다. read_snapshot은 신뢰한 생성 시 manifest를 전달받는 내부 helper이며 임의 업로드 archive 복원 API가 아니다.

## 운영 서비스 확인과 다음 담당

실제 listener: loopback18100 PID22076의 `C:/Project/SaintVision-Invion/agent-codex-dev-environment/tools/dev_studio.py`. 해당 소스는 ThreadingHTTPServer/SQLite 기반 로컬 Windows 작업대이며 운영 Node Run admission과 별개라고 명시한다. 18081 PID23428은 기존 LAN 묶음 서버다. 현재 Codex branch의 src/saintvision/server.py는 create_configured_app 위임, Dockerfile은 `saintvision.server:create_app --factory`다. DB만 upgrade해도 로컬 작업대가 최신 운영 서버로 전환되지는 않는다. 실제 process 환경의 자격증명/명령줄 전체는 출력하지 않았다.

다음 Codex: 기존 로컬 작업대와 별도 포트의 정본 서버 candidate를 구분해 운영 설정·인증·실제 DB 연결 검증 및 구체적 적용/복구 계획을 만든다. Claude: 보관 백업과 상위 복구 훈련/독립 검토. Gemini: 정본 candidate에 대한 화면 계약·실제 로그인 여정 확인. 운영 DB upgrade/kill switch 해제/Node 교체는 아직 수행하지 않았다.

off-device/독립 클러스터/역할 복원/PITR/HTTP 로그인/Node journal/원격7개 시험은 미완료. 현재 DB 리허설은 같은 클러스터 기존 역할 재사용이다. 전체2775/4800=57.8125%,잔여42.1875% 유지. PR19 draft/독립 검토/CI/운영 인수 미완료. 최종 문서 검사와 Obsidian 영수증은 후속 기록한다.


## 2026-09-12 RETAINED-BACKUP 외부 보고와 우선순위 정정

Evidence/obsidian-proposals-20260912-retained-backup의 원문3개와hash를 보존했다. Gemini는 Idempotency-Key/route404 판별·WebTerminal apiClient와Vitest114를 보고했다. 작성자 보고이며 실제 커널의 idempotency 저장·응답 계약과 운영 인수는 검토 대기다.

Claude는 저장소의 기본 시험 credential로 운영DB 로그인이 가능하다고 보고했다. Codex가 실제 READ ONLY metadata를 확인한 결과 inv_app LOGIN=true,superuser=false,bypassrls=false,inv_kernel LOGIN=false이며 조회 순간 해당 그룹과inv_lan_runtime active session은0이었다(상시 미사용 증거 아님). 실제 password 인증은 이번 Codex 확인에서 재시도하지 않았다. deploy/init-db.sql의 고정 password LOGIN 생성뿐 아니라 tests/conftest.py의 기존 app_engine fixture에도 공용 inv_app 역할을 고정 password LOGIN으로 바꾸는 코드가 있어 재발 경로다. 폐기용 DB라도 역할은 클러스터 전역이라는 점을 반드시 수정해야 한다.

최우선 다음 Codex: init SQL/compose 고정 로그인 제거, 테스트별 난수 login 역할 생성·정리로 공용 그룹 역할 변경 금지, 해당 회귀 검증. 그 뒤 실제 서비스 의존성과 권한 확인을 마치고 운영 inv_app NOLOGIN/password 폐기 조치를 별도 critical 운영 변경으로 제시한다. 현재 사용자 지침에서 critical 변경은 자동 승인 범위에서 제외되어 있으므로 이번에는 운영 credential/역할을 변경하지 않았다. 기존 정본 서버 candidate 작업보다 이 항목을 먼저 수행한다. 미래KST 원문은 현재 실측 시각으로 채택하지 않으며 전체57.81% 유지한다.

## 최종 전달

문서352개/48 task 및 ontology 검사 exit0. 외부 변경을 두 번 원문 보존 후 동일bytes adopt했다. 19:49:18 KST/9837ec5 로컬 Obsidian708개 hash 일치/pending0/conflicts0. [[lan-retained-backup-obsidian-20260912.json]]. OneDrive cloud 미확인. 영수증 추가 후 최종 commit/push/sync를 수행한다.
