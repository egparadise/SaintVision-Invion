# Saint Vision INV

5대 Windows/Linux PC의 제공 자원을 연결하는 내부망 AI 개발 플랫폼의 **개발 지침 기준선**입니다. Codex 핵심 기반 코드는 `services/control-plane`에서 개발 중이며, 장비·인증·Frontend 통합은 후속 단계입니다.

- [최종 개발 계획](docs/vault/00_Index/최종%20개발%20계획%20-%20모든%20개발의%20지침.md)
- [공통 개발 진행판 — 작업·검증·다음 담당](docs/vault/00_Index/전체%20개발%20진행%20현황.md)
- [Agent 지속 개발 운영 규칙](docs/vault/40_Governance/Agent%20지속%20개발%20운영%20규칙.md)
- [Agent 시작 지침](AGENTS.md)
- [24주 실행 계획](docs/vault/30_Development/24주%20통합%20실행%20계획.md)
- [원문 반영 목록](docs/vault/00_Index/원문%20분석%20및%20반영%20목록.md)
- Git origin: https://github.com/egparadise/SaintVision-Invion.git

## 개발 TLS 인증서

개발 인증서는 저장소 외부 디렉터리에 둡니다. clone 후 `requirements-core.txt`를 설치하고 인증서를 준비한 다음 `SAINTVISION_DEV_CERT_DIR`를 설정해야 합니다. Compose는 이 변수가 없으면 시작하지 않습니다.

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-core.txt
.\\.venv\\Scripts\\python.exe tools/generate_tls_cert.py --output-dir C:\\SaintVision\\secrets\\saintvision-dev
$env:SAINTVISION_DEV_CERT_DIR = 'C:\\SaintVision\\secrets\\saintvision-dev'
powershell -ExecutionPolicy Bypass -File tools/deploy_intranet.ps1
```

전환·검증·롤백의 전체 절차는 [개발 TLS 인증서 외부 주입 전환 준비](docs/vault/30_Development/History/2026-09-18_TLS_%EC%99%B8%EB%B6%80%EC%A3%BC%EC%9E%85_%EC%A0%84%ED%99%98%EC%A4%80%EB%B9%84_Codex.md)를 따른다.

## 검증·동기화

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-docs.txt
python tools/check_docs.py
.venv/Scripts/python tools/check_ontology.py
python tools/sync_obsidian.py --check
python tools/sync_obsidian.py --apply
```

CI는 같은 문서·Ontology 검증과 문서 Artifact build를 실행합니다. 별도 Core Build는 핵심 코드·PostgreSQL·언어별 계약·패키지를 검증합니다. 실장비 성공을 의미하지 않습니다.

`docs/sources`는 원문 bytes, `docs/vault`는 Git 정본입니다. Obsidian 미관리 파일과 설정은 동기화하지 않으며 외부 수정 충돌은 중단합니다. 대상은 `docs/source-manifest.json`의 vault 경로이며 `--vault`로 다른 환경 경로를 지정할 수 있습니다.
