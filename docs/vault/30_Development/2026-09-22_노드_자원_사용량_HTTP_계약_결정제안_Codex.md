---
doc_id: "CODEX-NODE-USAGE-CONTRACT-PROPOSAL-001"
title: "노드 자원 사용량 HTTP 계약 결정 제안"
version: "1.1.0"
status: "accepted"
author: "Codex"
updated: "2026-09-22T16:05:00+09:00"
source_of_truth: "Git"
---

# 노드 자원 사용량 HTTP 계약 결정 제안

> 결정: 2026-09-22 코디네이터가 사용자 위임으로 **A capability별**을 승인했다. 미측정 값은 null, kind/unit 제한을 유지한다.

## 결정할 것

노드 상세 화면에 제공할 사용량 읽기 계약을 capability별 구조로 둘지, 평면 metric map으로 둘지 결정한다. 이 계약은 **커널 예약량 관측**이며 CPU/GPU 실제 utilization 퍼센트를 뜻하지 않는다. 현 정본은 heartbeat의 `usedQuantity`, `inv.resources`의 `capacity/offered`, pool capacity의 `spare/used/measured`다.

## 비교

| 안 | 장점 | 위험 |
|---|---|---|
| A. capability별 배열 | kind·unit을 함께 보내 CPU millicores, RAM bytes, GPU devices를 혼동하지 않는다. capability 추가가 명시적이고 `measured/observedAt`을 항목에 결속할 수 있다. | 화면이 배열을 kind별로 변환해야 한다. |
| B. 평면 metrics map | 기존 pool capacity의 `{cpuMillicores, ramBytes, gpuDevices}`와 가까워 단순하다. | 키 이름에 단위를 숨기고, kind별 신선도·측정 여부 표현이 약하다. network/storage 확장 때 임의 키가 늘어난다. |
| C. 신설 안 함 | 작업 없음. | 노드 상세 사용량 공백이 유지된다. |

## 권고: A

`GET /v1/projects/{projectId}/nodes/{nodeId}/resource-usage`와 strict `NodeResourceUsageResponse`를 둔다.

```json
{
  "nodeId": "nod_…",
  "stateAsOf": "2026-09-22T07:00:00Z",
  "resources": [
    {
      "resourceId": "res_…",
      "kind": "cpu",
      "unit": "millicores",
      "capacity": 8000,
      "offered": 6000,
      "reserved": 3000,
      "spare": 3000,
      "measured": true,
      "observedAt": "2026-09-22T07:00:00Z"
    }
  ]
}
```

불변식은 `0 <= reserved <= offered <= capacity`, `spare = offered - reserved`다. `measured=false`이면 값을 0으로 합성하지 않고 `observedAt=null`, `reserved/spare=null`로 둔다. 후보 discovery의 `claimedGpuCount`를 가용 GPU로 승격하지 않으며 등록된 Node만 응답한다. capability 종류와 unit 조합은 cpu/millicores, memory/bytes, gpu/devices, storage/bytes, network/bitsPerSecond로 제한한다.

## 승인 후 착지 범위

JSON Schema, 생성 Python/TypeScript/Go 타입, fixture와 negative invariant 시험을 먼저 착지한다. 실제 route/service는 계약 다음 카드로 분리하며, 계약만 추가하고 HTTP 구현 완료로 쓰지 않는다.

결정 요청: **A capability별(권고)** / **B 평면** / **C 신설 안 함**.
