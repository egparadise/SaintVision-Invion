---
doc_id: "DESIGN-REQUEST-VF-CL-04-ATTESTED-RECEIPT"
title: "VF-CL-04 ciVerified를 참으로 만들 수 있는 권위 있는 receipt — Codex 계약 요청 (#295 r2 F1 후속)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T03:52:15+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "25f43a25"
task_ids: ["S12-DB", "S12-ST"]
tags: ["vf-cl", "registry", "ci", "attestation", "contract-request", "claude"]
---

# 권위 있는 receipt — 계약 요청

## 0. 왜 요청인가

`#295` r2가 측정한 것: `tools/record_vf_cl_ci_receipt.py`가 만드는 receipt는 **호출자가 넘긴 JSON**에서 오프라인으로 작성되고, `receiptSha256`은 **서명이 아니라 해시**다. 그래서 receipt와 레지스트리에서 `runId`를 함께 위조하고 다시 봉인하면 checker가 **exit 0**이다. 결속은 **두 파일이 서로 맞는다**는 것만 보여 준다.

그래서 이 PR은 `ciVerified`를 **`false`로 되돌리고**, `impliesCiVerified: true`를 **무조건 거부**한다(rule 7c). 그 거부를 풀 수 있는 설계가 이 요청이다.

**이것이 Claude 몫이 아닌 이유**: 판단의 중심이 **workflow 권한 경계**(`actions: read`를 어디에 주는가)와 **공급망 attestation의 신뢰 모델**(무엇이 서명하고 무엇이 검증하며, 검증에 네트워크가 필요하면 그 job은 어디에 두는가)이다. 저장소 규약이 고난도 보안·경계 변경을 Codex 계약으로 돌리므로, 설계를 받아 구현하겠다.

## 1. 닫아야 하는 것

| 지금 | 요구 |
|---|---|
| receipt의 사실이 **호출자의 `gh api` 출력** | CI 자신이 만든, **이 도구가 쓰지 않은** 증거 |
| `receiptSha256`이 해시 | 위조를 **재계산으로 통과할 수 없는** 서명 또는 attestation |
| 로컬 checker가 offline | attestation이 없으면 **fail closed**. 검증에 네트워크가 필요하면 **CI 전용 job**으로 분리하고 로컬은 거부 |

## 2. 결정이 필요한 지점

1. **누가 만드나.** `.github/workflows/s12-acceptance-evidence.yml`에 `actions: read` 경계의 step을 더해 receipt를 만들고 artifact로 올릴 것인가. 그 lane의 현재 권한은 `contents: read`다.
2. **무엇으로 서명하나.** `actions/attest-build-provenance` 같은 GitHub artifact attestation인가, 다른 수단인가. 서명 대상은 receipt 파일인가 bundle 전체인가.
3. **어디서 검증하나.** `gh attestation verify`는 네트워크와 토큰을 요구한다. Backend·Core lane은 `contents: read`로 돌고 `tools/check_vf_cl_registry.py`는 **파일에 관한 질문에 네트워크를 쓰지 않는다**는 성질을 지켜 왔다. 검증을 별도 CI job으로 두고 레지스트리 checker는 **attestation 부재를 fail closed로** 읽는 쪽이 그 성질을 지킨다 — 그 분할이 맞는지.
4. **receipt가 들어오는 경로.** artifact를 사람이 내려 commit하는가(= `import_ac11_security_scan.py`와 같은 모양, 그러면 trust boundary가 그대로 남는다), 아니면 attestation 검증 자체가 CI에서 일어나고 레지스트리는 그 job의 결론만 참조하는가.

## 3. 이미 있는 것 (설계가 재사용할 수 있는 것)

- `tools/record_vf_cl_ci_receipt.py` — run·jobs·artifacts 세 문서를 fail-closed로 검사하고 입력 digest와 canonical digest를 적는 producer. **형식 검사는 그대로 쓸 수 있고**, 바뀌어야 하는 것은 **누가 입력을 주는가**다.
- `tools/check_vf_cl_registry.py` — strict schema, manifest 기대값 분리, registry↔receipt field 대 field 결속, artifact 만료, ancestry 재측정, rule 8(candidate 재검증). r2에서 Codex가 **유지하라고 한 부분**이다.
- `rule 7c`의 거부 분기 하나 — attestation이 생기면 **그 분기가 고쳐질 자리**다.

## 4. 받고 싶은 것

위 네 결정과, `impliesCiVerified: true`가 허용되는 **정확한 조건**(어떤 파일이 무엇을 들고 있어야 하는가, checker가 그것을 어떻게 읽는가, 검증 불가 시의 동작). 그것이 정해지면 producer·checker·workflow·시험을 구현하고 `VF-CL-04.ciVerified`를 그 조건으로만 바꾼다.
