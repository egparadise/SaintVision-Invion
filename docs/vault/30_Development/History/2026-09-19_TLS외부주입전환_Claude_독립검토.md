---
doc_id: "FIND-TLS-EXTERNAL-INJECTION-REVIEW-001"
title: "TLS 외부 주입 전환(7c804ed·e7e3b3e·15e81ff) VF-CL-05 독립 검토 — finding·재현·판정. 값 미기록"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-20T00:30:00+09:00"
branch: "agent/claude/vf-cl-cx01"
task: "VF-CL-05"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "tls", "compose", "deploy", "no-values"]
---

# TLS 외부 주입 전환 VF-CL-05 독립 검토

Codex의 TLS 외부 주입 3연속 커밋(모두 integration; 내 branch HEAD 미포함이라 커밋/`<ref>:파일`로 검토)에 대한 독립 검토다. **값은 옮기지 않고 경로·성격·짧은 해시만 기록**한다. 대상: `7c804ed`(compose cert bind→`SAINTVISION_DEV_CERT_DIR:?` fail-closed), `e7e3b3e`(추적 dev 인증서 2파일 삭제 + `.gitignore` + README 절차), `15e81ff`(`tests/core/test_vf_deployment.py`에 합성 변수 1줄).

사용자 실측 전제(재확인 안 함): 전체 회귀 1273 passed→1 failed가 15e81ff로 2 passed 해소; 삭제 후 `generate_tls_cert.py` 재생성 동작·git status clean; tip raw URL 404이나 과거 SHA raw는 200(이력 노출 회수 불가); `compose config`는 호스트 경로 미생성. Compose v2.15.1의 `create_host_path=false` 미준수도 사용자가 재현.

## 각도 1 — 15e81ff 합성 값이 시험을 무의미화하는가: **아니오 (sound)**
`test_vf_deployment.py`의 `test_internal_services_are_not_published_on_all_interfaces`는 `docker compose config --format json`을 돌려 control-plane·postgres·minio의 **모든 포트 `host_ip=='127.0.0.1'`**(전 인터페이스 미공개)을 단언한다. 이 단언은 **cert dir 값과 무관**하다(포트 바인딩에 영향 없음). 7c804ed가 변수를 required(`:?`)로 만든 뒤 **unset이면 config가 실패**해 `assert returncode==0`에서 단언 도달 전 에러가 난다 — 15e81ff의 합성값은 config를 통과시켜 **실제 포트 단언에 도달**시킬 뿐이며, 기존 합성 DSN/password와 동일 성격(fixture: "Explicitly replace every deployment input")이다. **검사 대상(인터페이스 노출)을 가리지 않는다.**

- **부수 finding(커버리지 gap, 권고)**: `POSTGRES_PASSWORD`의 fail-closed는 음성 시험(`test_missing_database_password_cannot_fall_back_to_a_default`)이 있으나, 7c804ed가 새로 도입한 **`SAINTVISION_DEV_CERT_DIR:?` fail-closed에는 대응 음성 시험이 없다**. 권고: unset(또는 빈 값) 시 `compose config`가 non-zero + stderr에 `SAINTVISION_DEV_CERT_DIR`를 담는지 확인하는 평행 음성 시험 추가(내 테스트 영역). *내 branch에 compose `:?` 변경이 없어(분기) 여기서 유의미 검증 불가 → integration 착지 상태에서 추가 권고.*

## 각도 2 — 잔여: 변수 설정됐으나 경로 부재 시 (Compose v2.15.1)
7c804ed의 `:?`는 **unset만** 막는다. **설정됐으나 경로 부재**면 Compose v2.15.1이 `create_host_path=false`를 무시하고 빈 호스트 디렉터리를 만들어 컨테이너가 **디렉터리를 인증서 파일로 마운트**한다(사용자 재현).
- **현재 완화**: README(e7e3b3e)가 이 잔여를 **명시 경고**하고 "직접 Compose 실행 말고 `deploy_intranet.ps1`의 leaf·키 일치 preflight 선통과"를 안내한다. **문서화는 됐다.**
- **판정(문서 vs preflight)**: 직접 `docker compose up`은 어떤 호스트측 preflight도 우회하고 Compose 2.15.1이 깨끗이 실패하지 않으므로, 강건한 검사는 **승인된 경로(`deploy_intranet.ps1`)에 있어야** 한다. 그러나 그 스크립트의 인증서 검사(`Test-Path`, line 17)는 **존재 확인뿐 — 디렉터리도 통과**한다(leaf가 파일인지·crt/key 쌍이 맞는지 미검증). 즉 **README가 안내하는 "leaf·키 일치 preflight"가 스크립트에 실제로는 없다(문서-구현 불일치)**.
- **처리·권고**: `deploy_intranet.ps1`은 **Gemini 소유**이므로 내가 수정하지 않는다. 권고: 그 스크립트의 preflight를 **leaf가 정규 파일인지(`Test-Path -PathType Leaf`) + crt/key 쌍 검증**으로 강화해 README 주장과 일치시킨다. 직접 compose 경로의 footgun은 문서 경고 유지가 현실적 상한(compose 네이티브 강제 불가). 값 미기록.

## 각도 3 — 실사용 영향 / 문서: **대체로 충족**
README@integration이 clone→`requirements-core` 설치→`generate_tls_cert.py --output-dir <외부>`→`$env:SAINTVISION_DEV_CERT_DIR` 설정→`deploy_intranet.ps1` 실행을 문서화하고, "이전 `./deploy/certs` 폴백 제거로 직접 compose 개발자도 변수 필요"·구형 Compose 디렉터리 생성 경고까지 담는다. **절차 반영됨.**
- **부수(소규모)**: `deploy_intranet.ps1` line17이 변수 미설정 시 `deploy/certs`로 **폴백 생성**하나, compose는 `:?`로 변수를 요구하므로 이 폴백은 이제 **모순적**(certs는 deploy/certs에 생겼는데 compose는 변수 없어 실패). 문서 예시는 변수를 먼저 설정하므로 정상 경로는 동작. 이 vestigial 폴백 정리 권고(Codex/Gemini).

## 판정 (커밋별)
- **7c804ed sound**: unset fail-closed(`:?`) 타당, create_host_path 미준수를 주석으로 인지. 단 set-but-부재는 미차단(각도2).
- **e7e3b3e sound**: 추적 인증서 삭제 + gitignore + README 절차. (이력 노출은 회수 불가 — 사용자 기록, 회전 권고는 SEC-PUBLIC-EXPOSURE-CLAUDE-ANGLE-001.)
- **15e81ff sound**: 시험 무의미화 아님(각도1). 단 새 변수 fail-closed 음성 시험 커버리지 gap.

## 권고 요약 (구현은 담당 영역/승인)
1. `SAINTVISION_DEV_CERT_DIR:?` fail-closed 음성 시험 추가(테스트 영역; integration 상태에서).
2. `deploy_intranet.ps1` preflight를 leaf-파일 + crt/key 쌍 검증으로 강화(Gemini)해 README의 "leaf·키 일치" 주장과 일치.
3. line17 `deploy/certs` 폴백 정리(모순 제거; Codex/Gemini).
Claude는 검토·기록까지 수행. 교차 영역/분기 구현은 하지 않는다.
