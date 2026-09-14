---
doc_id: "HIST-CLI-OUTPUT-BOUNDARY-REPORT-20260914"
title: "2026-09-14 CLI-OUTPUT-BOUNDARY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T20:00:13+09:00"
source_of_truth: "Git"
---

# CLI 출력 수집 무결성 보완

CX-01/CX-08 지원, Codex 작성/Claude reviewer pending. 제품 `dcd5f791f50b5287c98910ed4888aed3d5af3306` commit/push 완료. 기존 Claude Adapter의 통합 검토 중 발견한 메모리·출력 관측 결함을 보완했다. 기존 run/cancel/collect 계약을 유지한다.

## 변경과 확인

- 기존 communicate는 전체 stdout/stderr를 메모리에 받은 뒤 자른다. 실행 직후 두 pipe를 각각 배수하며 설정한 bytes만 보관하도록 변경했다. Windows PeekNamedPipe와 Linux nonblocking read를 사용해 자손 프로세스가 pipe를 계속 열어도 reader를 종료할 수 있다.
- collect 시간초과는 RUN-TIMEOUT, EOF를 확인하지 못한 출력은 RUN-OUTPUT-INCOMPLETE로 분리한다. cancel은 기존 UNKNOWN을 유지한다. stderr만 넘쳐도 truncatedOutput=true로 보고한다. 상태 probe는 잘리거나 불완전한 출력의 접두사로 로그인 성공을 판정하지 않는다.
- [이전 코드 재현](../Evidence/cli-output-before-0790076.json): Git0790076의 모듈을 별도로 로드해 실제 Python stderr1000bytes/상한32을 실행했을 때 truncatedOutput=false였다. 수정 후 회귀시험 통과.
- Windows 새6개/8.11s, 기존18개/2.11s, Linux 합계24개/4.23s, 각각 exit0. [검증 범위](../Evidence/cli-output-validation-dcd5f79.json). 같은24개를 두 플랫폼에서 확인한 것이며 고유48개로 세지 않는다. 실제 CLI 정의/계정 검사5개는 명시적으로 제외했다.
- 대량 출력 시험은 stdout/stderr 각각16MiB를 생성하고 collect 전 프로세스 종료를 확인했다. 각 stream 보관1024bytes, Python tracemalloc peak<4MiB를 검사했다. 운영 전체 RSS나 동시 Run 부하 측정은 아니다.
- `python tools/check_docs.py`:388문서/48task exit0, `python tools/check_ontology.py`:exit0(착수 포함 시점). 보고 포함 최종 검사는 후속 기록한다.

## 제한과 다음 담당

호스트 로컬 CLI Adapter의 출력 수집 보완이다. OS sandbox/프로세스 트리 격리·원격 Node/실제 LLM 호출/운영 인수를 주장하지 않는다. 시간 제한은 기존 collect의 대기 제한이며 run 시작 시점의 전체 예산 집행은 별도다. 생성된 Run handle의 보존 개수 정책도 후속이다. 부작용 재시도는 cancel UNKNOWN을 보고 결정해야 한다.

Claude: process_output/CLI의 출력·취소·상태 판정 독립 검토. Codex: 실제 Node 실행/제한 Agent 루프와 연결할 때 예산·승인·Evidence 정본을 유지한다. 원격 .225/운영 OIDC/CI 계정 제한은 기존 차단이며 본 시험으로 해소되지 않는다. 전체 성숙도2775/4800=57.81% 유지. CI와 Obsidian은 실제 결과를 아래에 추가한다.

동일SHA CI6건은20:00:21 KST 확인 시 billing 제한으로 job 시작 전 실패했다. [CI 증거](../Evidence/cli-output-ci-dcd5f79.json). 로컬 시험과 CI 성공은 동등하게 표시하지 않는다.

최초 Obsidian check는 공통/Gemini 진행판 외부 편집2개 때문에 exit1/쓰기0으로 중단됐다. raw 원문과 SHA manifest를 보존하고 작성자 주장과 독립 검증을 구분해 수신 기록을 합친 후 재동기화한다. 신규 frontend 검토는 다음 CX-01이다.
