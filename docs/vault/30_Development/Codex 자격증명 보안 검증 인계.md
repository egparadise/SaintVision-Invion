---
doc_id: "CODEX-CREDENTIAL-CONFORMANCE-001"
title: "Codex 자격증명 보안 검증 인계"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-12T01:14:28+09:00"
source_of_truth: "Git"
---

# 자격증명 보안 검증 인계

CX-02, owner Codex(공통 경계/검증), reviewer Claude. 사용자 후속 지시에 따른 runtime resolver/backend owner Codex, 독립 reviewer Claude. 실제 Provider Adapter 연결 owner Claude, reviewer Codex. [[Codex 운영 자격증명과 Storage 계약]] ADR-075를 executable contract로 옮긴다. 같은 개념의 두 resolver를 만들지 않는다.

## 정본 파일과 실행

- `src/saintvision/credentials/contract.py`: CredentialContext / CredentialResolver / CredentialHandle / CredentialDenied. 인증된 context와 내부 callback용 Protocol이며 인가 구현이나 공개 HTTP 요청 모델이 아니다.
- `tests/credential_conformance.py`: CredentialConformance, 현재 **39개** parametrized 보안 사례. 구현별로 subclass하고 `credential_harness` fixture를 제공한다. 공통 suite 자체에는 기본 fixture가 없다. 실제 Linux/PostgreSQL fixture는 `tests/integration/test_credential_backend.py`에 구현됐다.
- `tests/test_credential_conformance.py`: 합성 모델39개와 의도적인 결함8개 검출 시험. `credential_model` marker이며 실제 OS/DB/Provider 안전을 입증하지 않는다.
- `credential_backend` marker는 실제 구현의 독립 harness에만 붙인다. release 검증은 `pytest -m credential_backend`를 별도로 실행해 필요한39개 사례가 실제 수집·실행됐는지 확인한다. 0개(exit5)·skip·xfail·오류는 합격이 아니다. marker 선언만으로 실제 backend임을 증명하지 못하므로 reviewer는 fixture를 검토해야 한다.

기존 Linux backend39+추가9개는74012b3/0f5f4e8에서 실제 통과했다. [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]]. Claude는 이를 독립 검토하고 기존 resolver를 Provider에 연결한다. 아래는 새 backend를 추가할 때 사용하는 확장 형태이며 두 번째 Linux resolver를 요청하는 것이 아니다:

```python
from credential_conformance import CredentialConformance
import pytest

pytestmark = pytest.mark.credential_backend

class TestLinuxCredentialBackend(CredentialConformance):
    pass

# credential_harness fixture는 실제 resolver와 격리 Linux 파일/registry를 준비한다.
```

모든 파일/계정/키는 격리된 합성 시험용이다. 운영 키·개인 HOME·브라우저 로그인 cache를 읽거나 Provider에 과금 요청을 보내는 fixture를 만들지 않는다. Fixture 생성/정리 실패를 skip으로 바꾸지 않는다.

## Harness 계약

Fixture는 `resolver`, `reference`, `context`, `purpose='llm.invoke'`, `destination='provider-fixture'`, synthetic `secret: bytes`, `backend_reads`, `other_context_values`, `mutate(action)`을 제공한다. reference는 ADR-075 문법의 registry에 등록된 exact version이다. 다른 context 값은 문법상 유효하지만 허용되지 않은 tenant/project/subject/run이다. backend_reads는 실제 secret byte read 시도 수이며 실제 syscall/저장 backend 접점에서 계측한다. 인가 함수를 통과하도록 monkeypatch하거나 단순 flag로 실제 backend 결과를 대체하지 않는다.

| action | 실제 fixture가 수행할 것 |
|---|---|
| revoke / disable / revoke_grant | 실제 registry 또는 grant 변경; 이미 얻은 handle의 사용과 새 resolve 모두 거부 |
| expire | 주입 가능한 검증 clock을 실제 만료 이후로 이동하거나 실제 만료된 registry 상태를 구성 |
| remove_version | 기존 immutable version을 해석할 수 없게 만들되 새 version으로 묵시 대체 금지 |
| rebind_destination | 현재 허용 destination binding을 회수하여 old handle 권한 재검사를 검증 |
| rotate_keep_old | 새 버전을 추가하고 활성 binding을 변경하되 old version은 유효하게 유지; old ref가 원래 secret을 읽어야 함 |
| root_symlink / root_replaced | resolve 뒤 실제 root 링크 또는 inode 교체; 기존 경계와 다른 경로를 사용하지 못해야 함 |
| file_symlink / file_replaced | resolve 뒤 실제 파일 symlink 또는 다른 inode로 교체 |
| wrong_owner / public_mode | 실제 소유권 또는 그룹/타인 읽기 권한 변경; 권한 있는 격리 시험 helper 필요 |
| non_regular / oversize / outside_root | 정규 파일 아닌 대상, 65536bytes 초과 파일, root 밖 locator를 실제 구성 |
| backend_error_with_secret | 하위 backend 오류에 합성 secret을 넣어 전달하고 public 예외/trace/log/stdout/stderr 비노출 확인 |

`resolve` 직후의 mutation은 **해석→사용 사이** 재검사를 검증하며 동시 요청의 모든 interleaving을 증명하지 않는다. 각 use 때 재검사하는 시험도 별도로 있다. 파일 descriptor open→read 사이 바꿔치기, 다중 프로세스 revoke 경합과 실제 회수 commit/dispatch 시점은 실제 backend에 추가 fault hook/장벽 시험이 필요하다. 이39개만으로 완전한 TOCTOU/linearizability 검증을 선언하지 않는다.

## 판정 경계

정상 callback은 한 번 호출되고 결과가 반환돼야 한다. 잘못된 scope/참조는 secret read 이전에 거부한다. 회수/만료/파일 경계 실패는 callback을 실행하지 않는다. old version은 자동으로 최신에 연결하지 않는다. handle의 str/repr/JSON은 secret을 공개하지 않는다. Python 내부 introspection이나 신뢰 callback의 악의적 저장을 차단하는 메모리 sandbox라고 주장하지 않는다.

callback이 TimeoutError를 내면 성공으로 반환하거나 내부에서 재시도하지 않는다. 안전한 오류로 매핑할 수 있지만 외부 side effect 중단 여부는 별도이다. callback 자체가 비밀을 로그에 쓰지 않을 의무는 Adapter redaction/attestation conformance에서도 확인한다.

검출력용 결함8종: context 검사 누락, 인가 전 secret read, revoke 무시, file symlink 허용, old ref를 새 secret에 연결, repr 비밀 노출, 실패 callback 자동 재시도, 비밀을 담은 예외 cause 전파. 모델 시험은 이 결함들이 assertion으로 검출됨을 증명한다. 실제 Linux provider가 아직 없으면 backend 합격은 **미검증**이다.

## 다음 담당

Claude는 위 fixture를 실제 registry/Linux backend와 연결하고 합성 시험 evidence·코드 SHA·39개 case/skip0을 제출한다. Codex는 descriptor/권한/회수 구현을 독립 검토하고 실제 concurrent/TOCTOU fault 시험을 추가한다. Gemini는 verified/observed/unknown을 구분하며 모델 시험 결과를 운영 readiness로 표시하지 않는다. CI/독립 리뷰/운영 인수는 각각 기록한다.
