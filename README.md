# Saint Vision INV

5대 Windows/Linux PC의 제공 자원을 연결하는 내부망 AI 개발 플랫폼의 **개발 지침 기준선**입니다. 제품 구현은 아직 시작 전입니다.

- [최종 개발 계획](docs/vault/00_Index/최종%20개발%20계획%20-%20모든%20개발의%20지침.md)
- [Agent 시작 지침](AGENTS.md)
- [24주 실행 계획](docs/vault/30_Development/24주%20통합%20실행%20계획.md)
- [원문 반영 목록](docs/vault/00_Index/원문%20분석%20및%20반영%20목록.md)
- Git origin: https://github.com/egparadise/SaintVision-Invion.git

## 검증·동기화

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-docs.txt
python tools/check_docs.py
.venv/Scripts/python tools/check_ontology.py
python tools/sync_obsidian.py --check
python tools/sync_obsidian.py --apply
```

CI는 같은 문서·Ontology 검증과 문서 Artifact build를 실행합니다. 제품 코드·실장비 성공을 검증하는 CI가 아닙니다.

`docs/sources`는 원문 bytes, `docs/vault`는 Git 정본입니다. Obsidian 미관리 파일과 설정은 동기화하지 않으며 외부 수정 충돌은 중단합니다. 대상은 `docs/source-manifest.json`의 vault 경로이며 `--vault`로 다른 환경 경로를 지정할 수 있습니다.
