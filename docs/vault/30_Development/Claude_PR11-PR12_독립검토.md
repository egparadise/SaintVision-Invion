# PR #11·#12 독립 검토 — Claude

- 검토자: Claude (owner: Backend·DB·Context·Adapter·테스트·운영 문서)
- 대상: PR #11 `agent/codex/runtime-completion` (151 files, +12354), PR #12 `agent/codex/workspace-resume` (57 files, +3339, #11 위에 적층)
- 방법: 두 PR + `integration/all-agents-unified` + Claude 작업을 **한 트리에 병합하여 실행**
- 결과 브랜치: `review/claude-pr11-pr12` (`a3f98ca`)
- 검증: Backend Build **success**, Core Build **success**, Documentation Build **success**

## 검토 방법에 대하여

두 PR은 각자의 base 위에서 green이었다. 그 사실이 증명하는 것은 "각 PR이 자기가 올라선 코드와 충돌하지 않는다"까지다. **#11은 #12의 마이그레이션을 본 적이 없고, 둘 다 Claude의 마이그레이션을 본 적이 없으며, Claude의 것도 저 둘을 본 적이 없다.** 세 갈래가 같은 PostgreSQL에서 함께 돈 적은 한 번도 없었다.

그래서 검토는 읽기가 아니라 병합 후 실행으로 했다. 아래 지적 사항 중 세 개는 읽어서는 나오지 않았고, 병합해서 돌렸을 때만 나왔다.

---

## 지적 사항 (수정 완료)

### 1. 마이그레이션 체인이 갈라진다 — 병합 차단, 정적 검사로는 안 보임

두 갈래가 모두 `0006_control_api`에서 분기한다.

```
0006_control_api ─┬─ 0007_delivery_queue … 0018_workspace_resume   (실행 코어)
                  └─ 0008_node_certificate_lookup … 0010_…         (업무 표면)
```

병합하면 `alembic upgrade head`에 head가 둘이 되고, alembic은 **하나를 골라서 조용히 성공한다.** git이 볼 수 있는 충돌이 아니고, 파일 이름도 겹치지 않으며, 어느 쪽 CI도 이 상태를 겪은 적이 없다. 실제로 드러나는 시점은 배포가 스키마의 절반만 적용한 다음이다.

**조치**: 짧은 쪽이 움직인다. Claude의 세 revision을 `0019`·`0020`·`0021`로 번호를 다시 매기고 `0018_workspace_resume` 위로 재지정했다. 어느 쪽도 상대의 테이블에 의존하지 않아 순서는 자유로웠고, 이 선택은 **Codex 쪽 파일을 한 줄도 고치지 않는다.**

### 2. 역전 검사 단계에 DSN이 없다

```yaml
- name: Service migrations reverse; reliability migrations recover forward
  run: |
    python -m alembic upgrade 0007_locality_replicas
    python -m alembic downgrade base
    ...
```

이 단계는 `INV_MIGRATION_DSN`을 설정하지 않는다. job 전역 `INV_DATABASE_URL`에 기대는데, **그 전역 변수는 마이그레이션 단계가 주변 DSN을 실수로 잡는 일을 막으려고 일부러 제거된 것이다.** 합치면 이 단계는 DSN이 아예 없다.

**조치**: 대체된 세 검사(단일 head·빈 DB 적용·역전 가능한 꼬리만)를 복원하고 각 단계에 자기 DSN을 줬다. 이 단계가 갖고 있던 고유한 성질 하나 — **head에서 한 번 더 upgrade하면 아무 일도 없어야 한다** — 는 Claude 쪽 검사에 없던 것이라 그대로 가져왔다.

### 3. Backend Build가 반대쪽 절반의 테스트를 돌리지 않게 되어 있었다

`--ignore=tests/core --ignore=tests/integration`가 들어와 있었다. 그러면 **각 절반이 자기 컨테이너에서 통과하고 이음매는 아무도 시험하지 않는다** — 공용 PostgreSQL을 하나로 맞춘 이유가 바로 그것이었다.

되돌렸더니 **51개 error**가 났다. 전부 `CI must enable real Node execution tests` — Go 에이전트 바이너리와 빌드된 이미지를 필요로 하는 suite들의 정당한 거부다. 그런데 그 목록은 **손으로 유지할 수 없다.** 세 파일이었던 것이 이 병합 뒤 열세 파일이고, 대부분은 전이적으로 걸린다(`test_approvals`의 fixture → `test_node_runtime`의 fixture). 파일 이름만 봐서는 알 수 없다.

**조치**: `tools/node_dependent_tests.py`가 import 그래프에서 계산하고, CI가 제외한 목록을 출력한다. 이 저장소에서 하드코딩된 목록이 **이미 세 번 낡았고**, 매번 증상은 오류가 아니라 "테스트가 조용히 안 돌기 시작함"이었다.

병합 후 Backend Build: **774 passed, 0 skipped, 0 error**.

---

## 지적 사항 (소유자 판단 필요 — 고치지 않음)

### 4. `inv` 스키마에 GRANT가 하나도 없다 — 배포 차단

18개 inv 마이그레이션 전체에 `GRANT` 문이 **0개**다. 접근 권한은 테스트 fixture가 시험마다 만드는 임시 role에 부여한다.

`public`은 `inv_app`(NOLOGIN, **NOBYPASSRLS**)에게 자기 마이그레이션 안에서 권한을 준다. `inv`는 아무에게도 주지 않는다. 즉 배포에서 실행 코어가 동작하려면 **스키마 소유자로 접속하는 수밖에 없다.** 44개 테이블 전부에 `FORCE ROW LEVEL SECURITY`를 건 이유가 소유자를 신뢰하지 않기 위해서인데, 소유자로 붙으면 `ALTER TABLE … NO FORCE` 한 줄이 그 전부를 되돌린다.

이건 중복 개념 정리보다 **먼저** 풀어야 한다. 소유자: Codex.

### 5. `src/saintvision/server.py` — 인증 없는 두 번째 컨트롤 플레인

integration 브랜치에 배포 패키지 안으로 들어온 파일이다. 메모리 상태, 하드코딩 fixture, 서명 없는 토큰(`sv_jwt_` + `secrets.token_urlsafe`), 하드코딩 tenant `00000000-…-0001`.

문제는 변경 엔드포인트다:

```python
@app.post("/v1/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, request: Request):
    ...
    if nonce and apprv.get("nonce") != nonce:   # nonce를 안 보내면 검사 자체가 없다
```

**자격 증명 매개변수가 없다.** `/v1/runs/{id}/cancel`, `/reclaim-resources`, `/resume/enqueue`도 같다. Codex가 4개 테이블·nonce·정족수·RLS를 들여 만든 승인 결정에, 같은 패키지 안에 **무엇이든 승인하는 쌍둥이**가 있다.

현재 아무것도 import하지 않고 배포 대상도 아니다. 하지만 "지금 연결되어 있지 않다"는 오늘의 설정에 대한 사실이지 산출물에 대한 사실이 아니고, `src/saintvision/server.py`라는 이름은 운영자가 uvicorn을 겨눌 가능성이 가장 높은 파일이다.

웹 클라이언트용 mock으로서는 타당하다. 설치되는 패키지 안에 있는 것이 타당하지 않다. **삭제하지 않았다** — Gemini의 것이다. 대신 `tests/test_package_surface.py`가 경계를 명시한다: 패키지는 애플리케이션을 하나만 노출하고, 격리 목록에 있는 것은 사유·소유자와 함께 기록되며 실제 앱에서 도달 불가능해야 한다.

---

## 검토했고 문제 없음

지적만 나열하는 것은 검토가 아니므로 기록한다.

**잠금 순서에 순환이 없다.** 모든 용량 기록 경로가 하나의 문서화된 순서를 따른다: `run → project → ceiling → node → resource`. `shard_plans`는 항상 run보다 **먼저** 잡히고 다른 어디에서도 run 뒤에 잡히지 않는다. `node_channels`는 `nodes` 뒤에만, `approval_requests`는 `run` 뒤에만 잡힌다. 함수 18개의 잠금 획득 순서를 AST로 추출해 확인했다.

**RLS에 빠진 테이블이 없다.** inv 44개 테이블 전부가 `ENABLE` + `FORCE` + tenant 정책을 갖는다. 손으로 하나씩이 아니라 `FOREACH … EXECUTE format(...)` 루프로 적용하기 때문에 빠진 것이 없다 — 이 방식이 맞다. (처음에 정규식으로 세었을 때 30개가 누락으로 보였는데, 누락이 아니라 내 검출기가 루프를 못 읽은 것이었다.)

**두 Run 상태 기계가 일치한다.** `inv.guard_run()` 트리거의 허용 간선과 `saintvision.runs.state.TRANSITIONS`를 전수 비교했다. PR #11의 한 줄(`recovering → awaiting_approval`)이 들어오면 차이가 **0**이다. 하나의 개념에 두 구현이 있는 자리인데, 지금은 같은 말을 한다.

---

## 남은 것

- #4(GRANT)와 #5(두 번째 앱)는 각 소유자의 판단이 필요하다.
- `public`이 권위라는 결정에 따른 11개 중복 개념 재지정, 그리고 `inv`의 자원 어휘(`memory`/`storage`/`network`)·단위 미선언은 별도 인계 항목으로 남아 있다.
- 두 PR은 여전히 draft이며 main 병합·운영 배포는 하지 않았다.
