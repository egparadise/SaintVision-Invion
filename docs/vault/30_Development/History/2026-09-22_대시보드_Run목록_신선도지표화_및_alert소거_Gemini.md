# 2026-09-22 대시보드(ClusterOverview) 및 Run 목록 신선도 지표화 및 alert() 소거 작업 기록 (Gemini)

- **작성자**: Gemini (Frontend & Design Lane)
- **일시**: 2026-09-22 00:43 KST
- **작업 브랜치**: `integration/all-agents-unified`
- **목표**: 화면 결함 6대 부류(시간 경과 묵인 및 신선도 은폐, 가짜 alert 다이얼로그, 실패 은폐) 치유 트랙 7차 완결.
  1. `ClusterOverview`: 노드 동기화 실패 시 정상 0대 은폐 원천 차단, 신선도 지표 및 Stale 경고 실장.
  2. `RunList`: Run 동기화 실패 시 정상 0건 빈 상태 둔갑 차단 및 전용 에러 뷰 분리, 신선도 지표 및 Stale 경고 실장.
  3. `RunDetail`: 브라우저 다이얼로그 `alert()` 전면 소거 및 정직한 DOM 피드백 배너 전환, 아티팩트 미노출 상태 정직 고지, 취소 실패 인라인 에러 실장.
  4. `App.tsx`: 신선도 타임스탬프 실배선 및 `onCreateRun`의 가짜 alert 창을 `DeveloperStudio` Step 3(코드 편집 & 실행) 실배선으로 전환.

---

## 1. 작업 배경 및 결함 구조

1. **대시보드 메인 화면 (`ClusterOverview.tsx`)**:
   - 서버 장애로 노드 조회가 실패했을 때(`nodesState === 'error'`), `nodes`가 빈 배열(`[]`)이 되어 `자원 합계를 확인할 수 없습니다. 미관측 정보가 있습니다. 표시된 노드 0대`라는 텍스트만 출력하고 있었음.
   - 이는 서버 네트워크 장애임에도 불구하고 마치 물리 노드가 실제로 0대이거나 단순 텔레메트리 결측인 것처럼 둘러대는 전형적인 "실패 은폐 / 미관측 둔갑" 결함이었음.
   - 또한 5초마다 노드가 폴링되고 있음에도 언제 수신된 텔레메트리인지 시각 지표가 없어 노드 장애 판단을 지연시킴.
2. **작업 목록 화면 (`RunList.tsx`)**:
   - 서버 에러 발생 시 `runs`가 빈 배열이 되면서 "해당 상태의 Run이 없습니다."라는 정상 0건 안내문으로 둔갑하여, 서버에서 고위험 배치 작업이 실행 중임에도 관리자가 안심하고 시스템을 방치하게 만듦.
   - 5초 주기 자동 갱신 및 최근 동기화 시각 부재, 폴링 실패 시 과거 캐시 침묵 유지.
   - `onCreateRun` 버튼이 브라우저 `alert('새 Run 요청 폼')` 창만 띄우는 가짜 핸들러로 방치되어 있었음.
3. **Run 상세 화면 (`RunDetail.tsx`)**:
   - 아티팩트 다운로드 버튼, 샤드 취소 실패, 영수증 조회 실패, 실행 취소 실패 시 화면에 상태를 남기지 않고 브라우저 팝업 `alert()`로만 띄워 스크린 리더(접근성) 및 DOM 단언에서 완전히 실종되는 문제 존재.

---

## 2. 변경 상세

### A. `ClusterOverview.tsx` (대시보드 장애 은폐 차단 및 신선도 지표화)
1. **장애 상태와 정상 0대 빈 상태 분리**:
   - `nodesState === 'error' && nodes.length === 0`:
     `cluster-overview-fetch-error` (`role="alert"`, `⚠️ 클러스터 노드 동기화 실패: 서버와 통신할 수 없어 노드 정보를 조회하지 못했습니다 (...). 이는 '노드 0대'(정상 0대 아님)이며, 물리 노드가 정상 가동 중일 수 있습니다.` 및 재시도 버튼 `cluster-error-retry-btn`) 전용 에러 섹션 표출.
   - `nodes.length === 0 && (nodesState === 'success' || nodesState === 'idle')`:
     `cluster-overview-empty-state` (`role="status"`, "등록된 노드가 없습니다 (정상 조회 결과: 0대)") 정직한 빈 상태 표출.
2. **신선도 지표 및 Stale 경고 배너**:
   - 상단 헤더에 `cluster-freshness-indicator` (`role="status"`, `🔄 자동 갱신 (5초 주기) · 최근 관측: HH:mm:ss`) 및 수동 `cluster-refresh-btn` 실장.
   - 폴링 실패 시 기존 캐시 노드가 있을 때 `cluster-stale-warning` (`role="alert"`, 과거 스냅샷 기준 시각 명시 및 처리 전 확인 안내) 표출.
   - `node.os` 결측 시 크래시 방지 방어 로직(`(node.os ? node.os.toUpperCase() : 'LINUX')`) 강화.

### B. `RunList.tsx` (Run 목록 에러 은폐 차단 및 신선도 지표화)
1. **장애 상태와 정상 0건 빈 상태 분리**:
   - `runsState === 'error' && runs.length === 0`:
     테이블 내부에 `run-fetch-error-state` (`role="alert"`, `⚠️ Run 작업 목록 동기화 실패: 서버와 통신할 수 없어 Run 작업 목록을 조회하지 못했습니다 (...). 이는 '작업 0건'(정상 0건 아님)이며, 실행 중인 작업이 서버에서 구동 중일 수 있습니다.` 및 재시도 버튼 `run-error-retry-btn`) 표출.
   - 정상 0건일 때만 `해당 상태의 Run이 없습니다.` 표출.
2. **신선도 지표 및 Stale 경고 배너**:
   - 상단 헤더에 `run-list-freshness-indicator` (`role="status"`, `🔄 자동 갱신 (5초 주기) · 최근 동기화: HH:mm:ss`) 및 수동 `run-list-refresh-btn` 실장.
   - 폴링 실패 시 기존 캐시 작업이 있을 때 `run-stale-warning` (`role="alert"`) 표출.

### C. `RunDetail.tsx` (alert() 소거 및 정직한 DOM 피드백 배너)
1. **DOM 피드백 배너 및 취소 에러 실장**:
   - 상단 헤더 위에 `run-action-${type}-notice` (`role={actionNotice.type === 'error' ? 'alert' : 'status'}`) 배너 실장.
   - 샤드 일괄 취소 실패 및 영수증 조회 실패 시 `setActionNotice`를 통해 DOM 인라인 배너로 안내.
   - 취소 모달 내부에 `cancel-modal-error` (`role="alert"`, `❌ 취소 요청 실패: ...`) 인라인 배너 실장.
2. **아티팩트 다운로드 미노출 상태 정직 고지**:
   - 930행의 허위 `alert` 다운로드 팝업을 소거하고 버튼 라벨을 `다운로드 (API 미노출)`로 정직화. 클릭 시 인라인 배너(`role="status"`, `ℹ️ [모의 고지] ... (서버 아티팩트 파일 스트림 다운로드 API 미노출 상태)`) 표출.
   - `run.artifacts`가 주입된 경우 우선 렌더링되도록 개선.

### D. `App.tsx` (신선도 결속 및 Studio 전환 실배선)
1. `lastRunsFetchedAt` 상태 및 타임스탬프를 `fetchRuns` 성공 시 갱신하도록 결속.
2. `ClusterOverview`에 `nodesState`, `nodeError`, `lastFetchedAt`, `onRefresh={fetchNodes}` 결속.
3. `RunList`에 `runsState`, `runError`, `lastFetchedAt`, `onRefresh={fetchRuns}` 결속.
4. `onCreateRun`: 가짜 alert 팝업을 제거하고 `handleOpenStudio({ step: 3 })`로 실배선하여 새 Run 생성 버튼 클릭 시 Developer Studio의 코드 편집 및 실행 단계로 직접 전환.

---

## 3. 검증 증거

1. **신규 단위 테스트 9종 작성 (`apps/web/tests/dashboard-runlist-freshness-wiring.test.tsx`)**:
   - Test 1: `ClusterOverview` 노드 0대일 때 동기화 실패 시 정상 빈 상태 은폐 차단 및 `cluster-overview-fetch-error` (`role="alert"`, 정상 0대 아님 명시) 표출 검증 (PASS).
   - Test 2: `ClusterOverview` 정상 조회 성공 시 노드가 0대이면 정상 0대 빈 상태(`role="status"`) 표출 검증 (PASS).
   - Test 3: `ClusterOverview` 상단에 신선도 표시기(`role="status"`, 5초 주기) 및 새로고침 버튼 호출 검증 (PASS).
   - Test 4: `ClusterOverview` 과거 캐시 보유 중 동기화 실패 시 `cluster-stale-warning` (`role="alert"`) 표출 검증 (PASS).
   - Test 5: `RunList` 작업 0건일 때 동기화 실패 시 허위 빈 상태 차단 및 `run-fetch-error-state` (`role="alert"`, 정상 0건 아님 명시) 표출 검증 (PASS).
   - Test 6: `RunList` 상단 헤더에 신선도 표시기(`role="status"`, 5초 주기) 및 새로고침 버튼 호출 검증 (PASS).
   - Test 7: `RunList` 과거 작업 목록 보유 중 동기화 실패 시 `run-stale-warning` (`role="alert"`) 표출 검증 (PASS).
   - Test 8: `RunDetail` 아티팩트 탭 다운로드 클릭 시 브라우저 alert 대신 인라인 고지(`role="status"`, API 미노출 명시) 표출 검증 (PASS).
   - Test 9: `RunDetail` 취소 요청 실패 시 취소 모달 내부에 `cancel-modal-error` (`role="alert"`) 인라인 표출 검증 (PASS).
2. **돌연변이 실측 사살 (Mutation Testing)**:
   - **M16 사살 (KILLED)**: `ClusterOverview`에서 노드 에러 발생 시 정상 0대 빈 상태로 둔갑시키는 돌연변이 실측 검출.
   - **M17 사살 (KILLED)**: `RunList`에서 서버 에러 발생 시 정상 0건 빈 상태로 둔갑시키는 돌연변이 실측 검출.
   - **M18 사살 (KILLED)**: `RunList`에서 Stale 경고 배너 렌더링을 억제하는 돌연변이 실측 검출.
   - **M19 사살 (KILLED)**: `RunDetail`에서 취소 실패 시 인라인 에러 배너를 누락하는 돌연변이 실측 검출.
3. **전체 단위 테스트 스위트 (Vitest)**:
   - 명령: `npx vitest run`
   - 결과: **66개 테스트 파일 597개 테스트 전수 통과 (100% PASS, exit code 0)**.
4. **프로덕션 빌드 (Vite & TypeScript)**:
   - 명령: `npm --prefix apps/web run build`
   - 결과: `tsc -b && vite build` 성공, exit code 0 (built in 3.55s).
5. **프론트엔드 무결성 검사**:
   - 명령: `python tools/check_frontend_integrity.py`
   - 결과: 80개 프로덕션 소스 파일 검사, 0 violations (PASS).
6. **문서 및 온톨로지 무결성 검사**:
   - 명령: `python tools/check_docs.py` & `.venv/Scripts/python tools/check_ontology.py`
   - 결과: PASS.
