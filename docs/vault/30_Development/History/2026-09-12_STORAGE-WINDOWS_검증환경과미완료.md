---
doc_id: "ERR-STORAGE-WINDOWS-20260912"
title: "2026-09-12_STORAGE-WINDOWS_검증환경과미완료"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:41:40+09:00"
source_of_truth: "Git"
---

# 실제 경로 검증 한계

본 서버의 wsl --list에는 docker-desktop/docker-desktop-data만 있다. Ubuntu를 임의 설치하거나 운영 Node를 정지하지 않았다. Windows launcher는 실제 PowerShell+모사 WSL, Linux bridge는 실제 Docker로 분리 검증했다. 드라이브 경로 변환 및 Docker inspect Source의 정확한 표현은 실제 원격 Ubuntu에서 확인해야 한다.

준비 기록은 동일 request hash만 재사용한다. source/policy가 달라지거나 request가 손상된 경우 덮어쓰기/초기화하지 않는다. prepare는 필요한 image와 private 준비 파일을 생성할 수 있지만 Node 교체는 Apply 단계다. CI는 결제 제한으로 미시작, 원격 배포·서버 인수는 [[2026-09-12_STORAGE-WINDOWS_Codex_검증보고]]의 다음 Codex 작업으로 남긴다.
