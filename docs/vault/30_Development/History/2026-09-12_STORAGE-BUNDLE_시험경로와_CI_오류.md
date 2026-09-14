---
doc_id: "ERR-STORAGE-BUNDLE-20260912"
title: "2026-09-12 STORAGE-BUNDLE 시험경로와 CI 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:40:43+09:00"
source_of_truth: "Git"
---

# 시험 경로 오류와 해결

실제 Docker 최초 설치 시험 exit1: daemon volume의 /var/lib/docker 하위 bind source는 rprivate를 허용하지 않았다. 시험 harness만 전용 .work 호스트 폴더로 변경하여 실제 설치2개 exit0 확인. 운영 데이터 변경·격리 완화 없음. 테스트 파일은 증거와 함께 전용 폴더에 보존한다.

Windows Ubuntu WSL 조회는 WSL_E_DISTRO_NOT_FOUND: Windows launcher는 문법만 확인했고 Ubuntu를 자동 설치하지 않았다. 원격 PC 검증은 별도다. CI6개는 계정 결제/한도로 시작되지 않았다. 반복 rerun/병합 없이 [[2026-09-12_STORAGE-BUNDLE_Codex_검증보고]]에 상태와 다음 Codex 작업을 인계한다.
