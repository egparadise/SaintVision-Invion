---
doc_id: "RES-TRANSPORT-001"
title: "RES-TRANSPORT-001 엄격한 인증서와 원 socket 기한 집행"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:56:38+09:00"
source_of_truth: "Git"
---

# RES-TRANSPORT-001 엄격한 인증서와 원 socket 기한 집행

합성 CA와 leaf에 SKI/AKI를 추가했고 Python VERIFY_X509_STRICT를 유지했다. Go httptest fixture에 테스트용 서버 인증서를 명시해 기본 인증서 주입을 피했다. production TLS 검증을 약화하지 않았다. 명시적 port 0은 거절하고 연결 원 socket을 timer가 보유해 response 이전 후에도 shutdown한다. OneConnection은 암묵적 재연결을 거절하고 명시적 SSLContext는 환경 변수로 TLS key log를 만들지 않는다.

수정 구현 59baad93cbe2f11c7b758b0ee668b8fbd67ce8ac, Core CI #34379287327 success. Python 237 tests / failures 0 / errors 0 / skipped 0, Go race detector 22 top-level / 55 leaf cases / failures 0 / test skips 0. 느린 응답·잘못된 CA/URI/EKU/pin·폐기·회전·TLS 연결 재사용·timeout·관찰 복구·DB 권한 변경 경쟁을 검증했다. 원본 [[transport-59baad9-tests.xml]], [[transport-59baad9-unit.jsonl]], [[transport-59baad9-provenance.json]].

실제 Linux/PostgreSQL/Docker와 일회 합성 CA 시험이다. 운영 인증서·IdP·장비·Windows ACL·GPU 검증을 주장하지 않는다. [[ERR-TRANSPORT-001 TLS fixture와 연결 종료 경계 검토]]의 대응이다.
