---
doc_id: "HIST-IMAGE-POSTOD-001"
title: "OneDrive 재시작 후 image lane 판별 수신"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T14:00:39+09:00"
source_of_truth: "Git"
---

# OneDrive 재시작 후 image lane 판별 수신

base f4b3f73, owner Codex(증거대조), 실행 사용자, branch agent/codex/model-registry-binding. agent-delivery1.1.0 적용. 사용자 고정harness f4b3f73/같은image b93b5ef1f944… 보고. JSON에는 harness SHA가 없어 그 부분은 사용자보고로 구분한다. .work/postod-quiet-determination-tests.xml 및 .json을 C:/vw에서 직접 파싱했다. 사설로그는 cleanup/NTSTATUS marker 수만 확인했고 원문은 게시하지 않는다.

## 케이스 판정

| 케이스 | 실제 결과 | 범주 / 보안 단언 |
|---|---|---|
| healthy | PASS | 이번케이스 통과 |
| unreadable | PASS | 이번케이스 통과 |
| writable | PASS | 이번케이스 통과 |
| business | PASS | 이번케이스 통과 |
| public-signing-key | FAIL | docker inspect의 daemon-response-io-timeout,케이스 전체 보안단언 미검증 |
| business-workspace | FAIL | docker inspect의 daemon-response-io-timeout,케이스 전체 보안단언 미검증 |
| workspace | SKIP | docker-operation-timeout90초,미검증 |
| business-kernel-role | SKIP | docker-operation-timeout90초,잘못된DB role거부 미검증 유지 |

합계4passed/2failed/2skipped,exit1. XML의3221225794/C0000142 각각0회,사설로그에서도0회. 제품보안단언 실패관측0을4미완케이스 합격으로 바꾸지 않는다. skip 이유가 명시된 것은 확인했으나 이 실행만으로 R5-01의 본문실패+cleanup실패 보존 시나리오를 새로 검증했다고 하지 않는다. 그 근거는 기존 회귀시험이다.

## 환경과 인과의 구분

사용자실측OneDrive핸들641442→2421,가용RAM896→938MB,동시image실행없는구간과과거sv-container2개제거 보고수신. 이번실행에서host-init 실패가 관측되지 않은 사실은 확인한다. 그러나 이전harness90c07c6/9e69dcc/b5f770a와현재f4b3f73가다르고,재시작외잔재/동시성조건도바뀌었다. 실패범주 변화도 이런교란에서자유롭지않다. 따라서 OneDrive가단일원인이었다거나지속적핸들누수임을확정하지않는다. 남은RAM부족은timeout원인후보이며 daemon자체I/O·기타요인을배제하지못했다.

unreadable은직전b5f770a에서host-init이아니라operation-timeout이었다. 이번통과를해당과거범주와대조하고 '이전모두host-init/이번최초통과'로일괄서술하지않는다. 서로다른실행의PASS를합쳐8/8로만들지않는다.

## cleanup과 현재 상태

JSON isolatedContainerRemoved=true는러너의격리PG컨테이너제거확인이다. XML/사설로그에VF cleanup incomplete marker0회이지만모든case의성공stdout/stderr와자원목록전수검사가없어전체자원정리확인으로승격하지않는다. 이전2/6정본은Evidence/docker-host-review/image-before-postod-quiet.json으로보존했고 최신image-tests.json은이번4/2/2와원본hash·관측한계를기록한다.

호스트환경조치및첫재판별은수신완료. 추가Docker사용금지는사용자가해제했으나현재timeout4케이스의미검증은남아있다. 새환경조치/진단근거없이동일lane반복실행하지않는다. VF운영인수0/5·business-kernel-role미검증·CI/실장비/AC-12대기는유지한다. 다음 Codex: Claude PITR준비안/격리리허설수신검토와새조건시timeout재판별. 이번작업의Docker/운영변경/시험재실행0건.
