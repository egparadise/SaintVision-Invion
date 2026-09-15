---
doc_id: "ERR-STORAGE-REPLACE-PREFLIGHT-20260912"
title: "2026-09-12_STORAGE-REPLACE-PREFLIGHT_오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:52:13+09:00"
source_of_truth: "Git"
---

# 실제 Docker에서 드러난 메타데이터 차이

최초 사전 점검 시험 exit1: docker cp tar는 mode에 파일 종류 비트(0100600)를 포함했다. mode==0600 비교를 mode & 07777==0600으로 고쳐 type 비트와 권한을 분리했다. 특수 파일/링크는 tar type 검사에서 계속 거부한다.

후속 exit1: Docker inspect의 Mounts 순서가 바뀌어 실제 변경으로 잘못 거부했다. Destination 정렬로 순서만 정규화하고 mount 모든 필드는 유지했다. 순서 변경은 통과, 실제 컨테이너/volume/상태 변경은 거부하는 결정론적 시험을 추가했다.

823b4b8 실제 Docker3/경계90 exit0. 키·journal 원문은 로그에 출력하지 않았다. CI6개는 결제 제한으로 시작되지 않았으며 [[2026-09-12_STORAGE-REPLACE-PREFLIGHT_Codex_검증보고]]에 다음 교체 executor/forward 재개를 인계한다.

