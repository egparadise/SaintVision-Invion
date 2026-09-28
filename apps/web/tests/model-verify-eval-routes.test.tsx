// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import {
  isModelVerifyResponse,
  isEvalRunResponse,
  generateIdempotencyKey,
} from '../src/shared/api/modelRegistryObservation';
import type { ModelVerifyResponse } from '../src/contracts/model-verify-response';
import type { EvalRunResponse } from '../src/contracts/eval-run-response';
import type { ModelLineageTraceResponse } from '../src/contracts/model-lineage-trace-response';

describe('G-05 W3 Verify & W5 Eval Run Business Routes (Card 101)', () => {
  let container: HTMLDivElement;
  let root: Root;
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    act(() => {
      root?.unmount();
    });
    container?.remove();
    vi.restoreAllMocks();
  });

  const getHeader = (init?: RequestInit, name: string): string | undefined => {
    if (!init?.headers) return undefined;
    if (init.headers instanceof Headers) {
      return init.headers.get(name) ?? undefined;
    }
    if (Array.isArray(init.headers)) {
      const entry = init.headers.find(([k]) => k.toLowerCase() === name.toLowerCase());
      return entry ? entry[1] : undefined;
    }
    const rec = init.headers as Record<string, string>;
    return rec[name] ?? rec[name.toLowerCase()];
  };

  const setInputValue = (input: HTMLInputElement, val: string) => {
    const setNative = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
    setNative?.call(input, val);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };

  const validTraceResponse: ModelLineageTraceResponse = {
    modelVersionId: 'mdv_01JABCDEF1234567890ABCDEFG',
    version: '1.0.0',
    stage: 'draft',
    contentSha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    producedByRunId: 'run_01J9876543210',
    fullyTraceable: true,
    traceabilityLimitedByScope: false,
    detailedKinds: ['dataset_version'],
    countOnlyKinds: ['eval_run'],
    missing: [],
    unresolved: [],
    datasets: [],
    deployments: [],
  };

  const validVerifyResponse: ModelVerifyResponse = {
    modelVersionId: 'mdv_01JABCDEF1234567890ABCDEFG',
    modelId: 'mdl_01JLLAMA30000000000000000',
    version: '1.0.0',
    stage: 'draft',
    verifiedAt: '2026-09-28T12:00:00Z',
    verifiedMeasurementId: 'mvm_01JABCDEF1234567890ABCDEFG',
    contentSha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    newlyVerified: true,
  };

  const validEvalRunResponse: EvalRunResponse = {
    evalRunId: 'evr_01JABCDEF1234567890ABCDEFG',
    suiteId: 'evs_01JABCDEF1234567890ABCDEFG',
    status: 'completed',
    passedGate: true,
    totalCases: 25,
    passedCases: 25,
    violations: 0,
    componentVersions: {
      adapter: 'codex',
      prompt: 'pmt_01J11111111111111111111111',
    },
    startedAt: '2026-09-28T12:00:00Z',
    endedAt: '2026-09-28T12:01:30Z',
  };

  describe('Runtime Contract Guards (additionalProperties: false & format enforcement)', () => {
    it('isModelVerifyResponse accepts valid payload and rejects extra keys or bad formats', () => {
      expect(isModelVerifyResponse(validVerifyResponse)).toBe(true);

      // Rejects extra keys (additionalProperties: false)
      expect(isModelVerifyResponse({ ...validVerifyResponse, extraKey: 'forbidden' })).toBe(false);

      // Rejects missing keys
      const { newlyVerified, ...missingKey } = validVerifyResponse;
      expect(isModelVerifyResponse(missingKey)).toBe(false);

      // Rejects invalid measurementId prefix (must be mvm_ + 26 base32 chars)
      expect(isModelVerifyResponse({ ...validVerifyResponse, verifiedMeasurementId: 'bad_prefix_1234567890' })).toBe(false);
      expect(isModelVerifyResponse({ ...validVerifyResponse, verifiedMeasurementId: 'mvm_short' })).toBe(false);

      // Rejects invalid ISO 8601 date-time
      expect(isModelVerifyResponse({ ...validVerifyResponse, verifiedAt: '2026-02-30T12:00:00Z' })).toBe(false);
    });

    it('isEvalRunResponse accepts valid payload and rejects extra keys, bad formats, or bad status', () => {
      expect(isEvalRunResponse(validEvalRunResponse)).toBe(true);

      // Accepts payload without optional endedAt
      const { endedAt, ...withoutEndedAt } = validEvalRunResponse;
      expect(isEvalRunResponse(withoutEndedAt)).toBe(true);

      // Rejects extra keys (additionalProperties: false)
      expect(isEvalRunResponse({ ...validEvalRunResponse, unauthorizedKey: 123 })).toBe(false);

      // Rejects missing required keys
      const { passedGate, ...missingGate } = validEvalRunResponse;
      expect(isEvalRunResponse(missingGate)).toBe(false);

      // Rejects invalid evalRunId prefix (must be evr_ + 26 base32 chars)
      expect(isEvalRunResponse({ ...validEvalRunResponse, evalRunId: 'bad_id' })).toBe(false);

      // Rejects invalid status enum
      expect(isEvalRunResponse({ ...validEvalRunResponse, status: 'unknown_status' as any })).toBe(false);

      // Rejects negative case count
      expect(isEvalRunResponse({ ...validEvalRunResponse, totalCases: -1 })).toBe(false);
      expect(isEvalRunResponse({ ...validEvalRunResponse, passedCases: 30, totalCases: 25 })).toBe(false);
    });
  });

  describe('W3 Verify Model Business Route', () => {
    it('successfully calls verify endpoint and displays verification details', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          expect(init?.method).toBe('POST');
          expect(getHeader(init, 'Idempotency-Key')).toBeTruthy();
          expect(getHeader(init, 'Content-Type')).toContain('application/json');

          const body = JSON.parse(init?.body as string);
          expect(body).toEqual({
            measurementId: 'mvm_01JABCDEF1234567890ABCDEFG',
          });

          return Promise.resolve(new Response(JSON.stringify(validVerifyResponse), { status: 200 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_01JLLAMA30000000000000000"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      // Switch to W3 Verify tab
      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      expect(verifyTab).toBeTruthy();

      await act(async () => {
        verifyTab?.click();
      });

      // Fill in measurement ID
      const measurementInput = container.querySelector('#mvm-measurement-id') as HTMLInputElement;
      expect(measurementInput).toBeTruthy();

      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF1234567890ABCDEFG');
      });

      // Submit W3 Verify form
      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );
      expect(submitBtn).toBeTruthy();

      await act(async () => {
        submitBtn?.click();
      });

      // Check success banner and live region
      const liveRegion = container.querySelector('[aria-live="polite"]');
      expect(liveRegion?.textContent).toContain('W3 커널 측정 검증 완료: mdl_01JLLAMA30000000000000000:1.0.0 (새로 검증됨)');

      const successBanner = container.querySelector('.bg-emerald-950\\/40');
      expect(successBanner).toBeTruthy();
      expect(successBanner?.textContent).toContain('새로 검증됨');
      expect(successBanner?.textContent).toContain('mvm_01JABCDEF1234567890ABCDEFG');

      // Check W3 badge in header
      const w3Badge = Array.from(container.querySelectorAll('span')).find((el) =>
        el.textContent?.includes('W3 검증: 검증 완료')
      );
      expect(w3Badge).toBeTruthy();
      expect(w3Badge?.textContent).toContain('측정: mvm_01JABCDEF1234567890ABCDEFG');
    });

    it('rejects invalid measurementId format client-side before network call', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_test"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      await act(async () => {
        verifyTab?.click();
      });

      // Bad ID (not starting with mvm_)
      const measurementInput = container.querySelector('#mvm-measurement-id') as HTMLInputElement;
      await act(async () => {
        setInputValue(measurementInput, 'invalid_measurement_id');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );
      await act(async () => {
        submitBtn?.click();
      });

      // Should show client validation error and NOT call verify endpoint
      const alert = container.querySelector('[role="alert"]');
      expect(alert?.textContent).toContain('유효한 측정 ID 형식(mvm_... 26자리 Crockford Base32)이어야 합니다.');
      expect(mockFetch).not.toHaveBeenCalledWith(expect.stringContaining('/verify'), expect.anything());
    });

    it('handles 409 GRAPH-0002 snapshot drift / measurement mismatch error honestly', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                type: 'about:blank',
                title: 'GRAPH-0002',
                status: 409,
                code: 'GRAPH-0002',
                category: 'GRAPH',
                detail: 'Measurement digest does not match current model lineage snapshot.',
                retryable: false,
                traceId: '0123456789abcdef0123456789abcdef',
                causeRef: null,
                evidenceId: null,
              }),
              {
                status: 409,
                headers: { 'Content-Type': 'application/problem+json' },
              }
            )
          );
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_test"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      await act(async () => {
        verifyTab?.click();
      });

      const measurementInput = container.querySelector('#mvm-measurement-id') as HTMLInputElement;
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF1234567890ABCDEFG');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );
      await act(async () => {
        submitBtn?.click();
      });

      const alert = container.querySelector('[role="alert"]');
      expect(alert?.textContent).toContain('GRAPH-0002');
      expect(alert?.textContent).toContain('Measurement digest does not match');
    });

    it('fails closed when canApprove is false', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_test"
            version="1.0.0"
            canApprove={false}
          />
        );
      });

      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      await act(async () => {
        verifyTab?.click();
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );
      expect(submitBtn?.hasAttribute('disabled')).toBe(true);
      expect(submitBtn?.getAttribute('aria-disabled')).toBe('true');
    });

    it('preserves Idempotency-Key on retry across failures', async () => {
      let capturedKeys: string[] = [];
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          const key = getHeader(init, 'Idempotency-Key');
          if (key) capturedKeys.push(key);
          return Promise.resolve(
            new Response(
              JSON.stringify({
                type: 'about:blank',
                title: 'SYS-0001',
                status: 503,
                code: 'SYS-0001',
                category: 'SYS',
                detail: 'Kernel measurement worker temporarily overloaded',
                retryable: true,
                traceId: '0123456789abcdef0123456789abcdef',
                causeRef: null,
                evidenceId: null,
              }),
              { status: 503, headers: { 'Content-Type': 'application/problem+json' } }
            )
          );
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_test"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      await act(async () => {
        verifyTab?.click();
      });

      const measurementInput = container.querySelector('#mvm-measurement-id') as HTMLInputElement;
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF1234567890ABCDEFG');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );

      // Attempt 1
      await act(async () => {
        submitBtn?.click();
      });

      // Attempt 2 (retry)
      await act(async () => {
        submitBtn?.click();
      });

      expect(capturedKeys.length).toBe(2);
      expect(capturedKeys[0]).toBeTruthy();
      expect(capturedKeys[0]).toBe(capturedKeys[1]); // Idempotency-Key preserved!
    });
  });

  describe('W5 Eval Run Business Route', () => {
    it('successfully calls eval runs endpoint and renders gate results and scores', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/eval/suites/evs_01JABCDEF1234567890ABCDEFG/runs')) {
          expect(init?.method).toBe('POST');
          expect(getHeader(init, 'Idempotency-Key')).toBeTruthy();
          expect(getHeader(init, 'Content-Type')).toContain('application/json');

          const body = JSON.parse(init?.body as string);
          expect(body).toEqual({
            adapter: 'codex',
            requireModelPinning: true,
            componentVersions: {
              prompt: 'pmt_01J11111111111111111111111',
              context: 'ctx_01J22222222222222222222222',
            },
          });

          return Promise.resolve(new Response(JSON.stringify(validEvalRunResponse), { status: 201 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_01JLLAMA30000000000000000"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      // Switch to W5 Eval tab
      const evalTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행')
      );
      expect(evalTab).toBeTruthy();

      await act(async () => {
        evalTab?.click();
      });

      // Fill in Suite ID and component versions
      const suiteInput = container.querySelector('#eval-suite-id') as HTMLInputElement;
      const promptInput = container.querySelector('#eval-prompt-ver') as HTMLInputElement;
      const ctxInput = container.querySelector('#eval-ctx-ver') as HTMLInputElement;

      await act(async () => {
        setInputValue(suiteInput, 'evs_01JABCDEF1234567890ABCDEFG');
        setInputValue(promptInput, 'pmt_01J11111111111111111111111');
        setInputValue(ctxInput, 'ctx_01J22222222222222222222222');
      });

      // Submit W5 Eval Run form
      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      expect(submitBtn).toBeTruthy();

      await act(async () => {
        submitBtn?.click();
      });

      // Live region announcement
      const liveRegion = container.querySelector('[aria-live="polite"]');
      expect(liveRegion?.textContent).toContain('W5 평가 실행 완료: evr_01JABCDEF1234567890ABCDEFG');

      // Success card displays GATE PASS badge and score
      const passBadge = Array.from(container.querySelectorAll('span')).find((el) =>
        el.textContent?.includes('GATE PASS')
      );
      expect(passBadge).toBeTruthy();

      const scoreText = container.textContent;
      expect(scoreText).toContain('통과: 25 / 25 케이스 (위반 0건)');
    });

    it('honestly renders GATE FAIL badge and violation count when gate fails', async () => {
      const failedEvalResponse: EvalRunResponse = {
        evalRunId: 'evr_01JABCDEF1234567890ABCDEFG',
        suiteId: 'evs_01JABCDEF1234567890ABCDEFG',
        status: 'aborted',
        passedGate: false,
        totalCases: 25,
        passedCases: 22,
        violations: 3,
        componentVersions: {
          adapter: 'claude',
        },
        startedAt: '2026-09-28T12:00:00Z',
        endedAt: '2026-09-28T12:01:30Z',
      };

      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/eval/suites/')) {
          return Promise.resolve(new Response(JSON.stringify(failedEvalResponse), { status: 201 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_01JLLAMA30000000000000000"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      const evalTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행')
      );
      await act(async () => {
        evalTab?.click();
      });

      const suiteInput = container.querySelector('#eval-suite-id') as HTMLInputElement;
      await act(async () => {
        setInputValue(suiteInput, 'evs_01JABCDEF1234567890ABCDEFG');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      await act(async () => {
        submitBtn?.click();
      });

      // Honest rendering of GATE FAIL badge
      const failBadge = Array.from(container.querySelectorAll('span')).find((el) =>
        el.textContent?.includes('GATE FAIL')
      );
      expect(failBadge).toBeTruthy();
      expect(container.textContent).toContain('통과: 22 / 25 케이스 (위반 3건)');
    });

    it('rejects invalid adapter format client-side before network call', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_test"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      const evalTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행')
      );
      await act(async () => {
        evalTab?.click();
      });

      const suiteInput = container.querySelector('#eval-suite-id') as HTMLInputElement;
      const adapterInput = container.querySelector('#eval-adapter') as HTMLInputElement;
      await act(async () => {
        setInputValue(suiteInput, 'evs_01JABCDEF1234567890ABCDEFG');
        setInputValue(adapterInput, 'invalid adapter! spaces & symbols');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      await act(async () => {
        submitBtn?.click();
      });

      const alert = container.querySelector('[role="alert"]');
      expect(alert?.textContent).toContain('어댑터 식별자는 소문자, 숫자, 하이픈만 허용됩니다.');
      expect(mockFetch).not.toHaveBeenCalledWith(expect.stringContaining('/runs'), expect.anything());
    });
  });
});
