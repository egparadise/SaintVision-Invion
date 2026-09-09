---
doc_id: "ERR-TRANSPORT-001"
title: "ERR-TRANSPORT-001 TLS fixture와 연결 종료 경계 검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:56:38+09:00"
source_of_truth: "Git"
---

# ERR-TRANSPORT-001 TLS fixture와 연결 종료 경계 검토

개발 중 Python TLS 테스트 25개 중 4개가 최초 실행에서 실패했다(exit 1). strict certificate 검증에 필요한 합성 CA/leaf의 AKI가 누락되어 인증서 검증 오류 85가 발생했고, HTTPS origin의 명시적 port 0이 `port or 443` 계산으로 허용된 결함을 확인했다. Go TLS fixture에서도 httptest.StartTLS의 기본 인증서 주입 때문에 의도한 인증서가 선택되지 않아 실패했다. 실제 운영 장애 기록이 아니다.

별도 코드 검토에서 http.client가 Connection: close 응답의 socket을 response로 이전하면 conn.sock만 종료하는 timer가 느린 응답을 중단하지 못할 수 있음을 확인했다. deadline 후 암묵적 재연결과 SSLKEYLOGFILE 환경 변수의 영향도 차단했다. 이 검토를 수정 전 운영 공격 재현으로 표시하지 않는다.

CI artifact 조회 보조 스크립트는 전역 Python 3.14의 tzdata 부재로 한 차례 exit 1이었다. 프로젝트 requirements 환경의 Python으로 다시 실행해 KST 기록과 artifact 검증을 완료했다. 제품 시험 실패가 아니다.

[[RES-TRANSPORT-001 엄격한 인증서와 원 socket 기한 집행]]을 따른다.
