---
doc_id: "ERR-RPO-CAPABILITY-20260912"
title: "2026-09-12 RPO-CAPABILITY 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:46:04+09:00"
source_of_truth: "Git"
---

# 2026-09-12 RPO-CAPABILITY 오류와해결

[[2026-09-12_RPO-CAPABILITY_Codex_검증보고]]. owner Codex / reviewer Claude pending.

원본4b09dfc pure 함수에서 성공만 반환하는 /bin/true와 실패 /bin/false가 모두 timeout300→목표900 합격을 반환했다. 설정을 보관/복원 증거로 오인했다. 새 tool은 metadata와 실제 인수 증거를 분리한다. archive_command/library 원문은 SQL에서 marker로 축약한다.

08cd83d 실제 Linux67개 중66개 pass/1개 fail. CLI는 운영 목표를 거부했지만 pilot 서비스가 outcome failed + met_targets true를 기록했다. b49ecd3에서 서비스에 passed 전제를 추가하고0036 신규 쓰기 제약을 넣었다. 기존 측정값은 유지한다. 초기 raw 로그는 개인 작업 경로에만 두고 공용 Evidence에는 case·판정·hash만 기록한다.

로컬 migration graph 검사에서 새 파일의 PowerShell UTF-8 BOM을 AST가 거부했다(52pass/1fail). 파일을 BOM 없는 UTF-8로 저장해 수정했고 동일 최종 SHA의53개 기본 검사와23개 실제 upgrade/replay를 통과했다. migration parser를 우회하지 않았다.

기존 과거 실패/목표true 행은 자동 수정하지 않았다. NOT VALID 제약을 통해 과거 값 보존·신규 쓰기 차단을 실제0035→0036 시험으로 확인했다. 운영자는 해당 과거 행을 검토해야 한다. 동일 SHA CI6개는 계정 제한으로 시작 전 실패했고, 로컬 성공으로 대체하지 않는다.
