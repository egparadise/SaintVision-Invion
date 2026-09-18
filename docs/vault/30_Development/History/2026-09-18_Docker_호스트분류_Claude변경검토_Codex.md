---
doc_id: "HIST-DOCKER-HOST-REVIEW-001"
title: "Docker 호스트 실패 분류와 Claude 변경 검토"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T12:01:19+09:00"
source_of_truth: "Git"
---

# Docker 호스트 실패 분류와 Claude 변경 검토

- owner Codex/reviewer Claude, base7f8d7f5, branch agent/codex/docker-host-review, 착수2026-09-18T12:01:19+09:00. 공통/개인판·agent-delivery1.1.0/core-reliability1.0.0 적용. 사용자 요청: 분류 정정 및83c0163/911aed8/9e69dcc 검토. Claude 소유 분류기/재시도 구현을 중복하지 않는다.

## 원인 분류 정정

- 사용자 clean worktree 9e69dcc 동일digest 실행 보고: runner의 docker inspect가3221225794(0xC0000142, signed -1073741502) 종료. Microsoft NTSTATUS 정본은 STATUS_DLL_INIT_FAILED로 정의한다. https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55
- 이를 **host-process-initialization-failure**로 별도 수신한다. DLL 초기화 실패를 daemon I/O timeout으로 분류하지 않는다. Codex가 같은 NTSTATUS를 직접 재현한 것은 아니다.
- 기존 `Error response from daemon: i/o timeout`은 **daemon-response-io-timeout**: 관측된 응답의 종류일 뿐 daemon 자체 고장이나 근본 원인 확정이 아니다. Python90초 TimeoutExpired는 **docker-operation-timeout**이며 NTSTATUS 확인 없는 상태다. 과거 raw기록은 변경하지 않고 최신 image-tests.json에 분류 보충한다.
- **docker-stream-upgrade-http500**: business-workspace의 `unable to upgrade to tcp, received 500`은 CLI가 실행돼 응답을 받은 단계다. 같은 호스트 압박 가설과 양립하지만 DLL 초기화 실패와 동일 원인이라고 입증하지 못했다. 해당 initializer 컨테이너가 created로 남았다는 점에서 작업은 부분 수행됐으며 docker run을 무조건 재시도하면 중복 자원을 만들 수 있다.
- 사용자 측정380프로세스/RAM가용2224MB/OneDrive463776핸들/System7682핸들 및 직후inspect10/10성공을 출처와 함께 보존한다. 핸들 수 급증은 의심 근거다. 시간별 증가·핸들 유형·환경 조치 전후 재검증이 없으므로 OneDrive 누수나 커널 자원 고갈을 확정 진단으로 올리지 않는다. OneDrive 조치는 사용자 담당이며 프로세스 종료/동기화 설정 변경을 하지 않았다.
- 재시도 검토 입력: 읽기 전용inspect/version의 명시적NTSTATUS 실패는 횟수 제한·원래 exit/status 기록을 유지한 재시도를 검토할 수 있다. HTTP500/timeout이 발생한 create/run은 먼저 고유명/ID로 실제 생성 여부를 확인해야 한다. 구현 결정과 시험은 Claude owner다.
- 최신 직접 image 결과는4pass/4fail 그대로다. **business-kernel-role의 잘못된 DB role 거부 단언 미검증**을 유지한다.

## Claude 커밋 검토 판정

| 커밋 | 판정 | 근거 |
|---|---|---|
| 83c0163 | 검토 History 채택(1b0d8ee) | 작성자 독립 검토 기록 수신. 당시 자원고갈 단정 표현은 위 최신 분류로 한정 |
| 911aed8 | 보류, 수정 필요 | 아래 R2-01/R2-02/R2-03 |
| 9e69dcc | 보류, 수정 필요 | 아래 R2-03 및 cleanup 결과 관측 보완 필요 |

- **VF-CL-R2-01, P1 동시 실행 자원 삭제**: prune은 전역 kernel-test label에 status created/dead/exited를 열거하고 재검사 없이 `docker rm -f` 실행한다. 다른 실행이 생성 직후인 컨테이너도 후보이며 열거 후running으로 바뀌어도 강제삭제된다. 새 자원을 자신의 prune 뒤에 생성해도 다른 Agent의 prune과 경합한다. 공유호스트에서 안전하지 않아 원안 착지를 보류한다. 활성 run 소유권/보존기간·잠금 등 조정과 비강제 삭제가 필요하다. 기존 hygiene 시험은 다른 label의running만 검사해 이 경합을 검증하지 않는다.
- **VF-CL-R2-02, P2 best-effort 불일치**: 사전 prune은 try/finally 밖이며 run()의 TimeoutExpired/OSError를 잡지 않는다. 모의 TimeoutExpired가 밖으로 전파됨을 확인했다. 기존 본문/정리 오류 가림 문제를 다른 위치에 재도입할 수 있다.
- **VF-CL-R2-03, P2 진단 비밀 마스킹 불완전**: 양쪽 함수는 URL user:password@만 가리고 libpq `password=...`는 남긴다. kernel 실제 DSN 형태와 다른 형태도 처리해야 하며 stderr/예외가 인증정보를 반사하지 않도록 회귀 필요. 합성 sentinel로 두 함수의 노출을 확인했고 실제 비밀은 출력하지 않았다.
- image cleanup의 원래 실패 보존 방향은 타당하다. 다만 모든 예외를 pass하면 정상 시험에서도 cleanup 실패/잔재를 보고서에서 알 수 없으므로 별도 cleanup 상태 수령증을 남기는 편이 맞다. 본문 성공과 자원 정리 성공은 분리해야 한다.
- `Evidence/docker-host-review/review-probes.json`: 원격 코드의 함수만 로드, 모든 prune subprocess를 mock해 created 후보 강제삭제 명령·timeout 전파·양쪽 마스킹 실패를 확인했다. **실제 prune/컨테이너 생성/삭제는 실행하지 않았다.** 사용자 시스템에 광역삭제를 수행하는 기존 hygiene시험도 실행하지 않았다.

## 인계 및 상태

- 구현은 Claude 담당 유지. Codex는83c0163 문서 수신과 근거·분류만 공유 반영한다. 두 fix커밋은 결함 해소 후 Claude 후속SHA를 받아 재검토한다. 사용자 재승인 요청 없이 안전한 부분을 먼저 착지한다.
- 다음 Claude: R2-01/02/03 + Windows NTSTATUS 분리/읽기 전용 재시도 검토. 다음 Codex: 수정본 검토·같은digest security lane 재실행. CI billing·운영mTLS/5대인수 미완. Docker daemon 다운/제품보안결함/OneDrive 근본원인 어느 것도 현재 결과로 단정하지 않는다.

- 후속 사용자 시계열 정정 수신: [[2026-09-18_Workspace_아카이브무결성_Codex]]. 쓰기구간+17853/조용한90초-29, 일정누수 아닌 버스트상관. 환경조치 전후 인과는 미확정 유지.
