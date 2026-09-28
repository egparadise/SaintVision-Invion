// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import {
  isModelVerifyResponse,
  isEvalRunResponse,
  startEvalRun,
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

  const setInputValue = (input: HTMLElement, val: string) => {
    if (input instanceof HTMLSelectElement) {
      input.value = val;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
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
      adapter: 'codex-cli',
      contractVersion: '1.0.0',
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

      // Accepts payload with endedAt: null
      expect(isEvalRunResponse({ ...validEvalRunResponse, endedAt: null })).toBe(true);

      // M1: Accepts payload with 35 componentVersions keys (32 user keys + 3 server keys)
      const bigComponentVersions: Record<string, string> = {
        adapter: 'codex-cli',
        contractVersion: '1.0.0',
        modelPinned: 'false',
      };
      for (let i = 0; i < 32; i++) {
        bigComponentVersions[`user_component_${i}`] = `ver_${i}`;
      }
      expect(Object.keys(bigComponentVersions).length).toBe(35);
      expect(isEvalRunResponse({ ...validEvalRunResponse, componentVersions: bigComponentVersions })).toBe(true);

      // Rejects non-string values in componentVersions
      expect(isEvalRunResponse({ ...validEvalRunResponse, componentVersions: { adapter: 12345 as any } })).toBe(false);

      // Rejects extra keys on root (additionalProperties: false)
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

      const successBanner = container.querySelector('[data-testid="registry-verify-success"]');
      expect(successBanner).toBeTruthy();
      expect(successBanner?.textContent).toContain('새로 검증됨');
      expect(successBanner?.textContent).toContain('mvm_01JABCDEF1234567890ABCDEFG');

      // Check W3 badge in header
      const w3Badge = container.querySelector('[data-testid="badge-w3-verify-seam"]');
      expect(w3Badge).toBeTruthy();
      expect(w3Badge?.textContent).toContain('W3 검증: 검증 완료 (측정: mvm_01JABCDEF1234567890ABCDEFG)');
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

    it('handles 409 GRAPH-0002 snapshot drift error honestly using exact server detail string', async () => {
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
                detail: 'The measurement does not match the current storage snapshot of the model version.',
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
      expect(alert?.textContent).toContain('The measurement does not match the current storage snapshot of the model version.');
    });

    it('fails closed when canApprove is false or undefined (both button and handler level)', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      // 1. canApprove = false
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

      // Attempt form submit programmatically to test handler guard
      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });
      expect(mockFetch).not.toHaveBeenCalledWith(expect.stringContaining('/verify'), expect.anything());
      const alert = container.querySelector('[role="alert"]');
      expect(alert?.textContent).toContain('승인 권한(canApprove)이 없는 계정은 모델 버전을 검증할 수 없습니다.');

      // 2. canApprove undefined (fail-closed)
      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_test"
            version="1.0.0"
          />
        );
      });
      const submitBtn2 = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );
      expect(submitBtn2?.hasAttribute('disabled')).toBe(true);
    });

    it('W3 idempotency lifecycle: keeps key on retry, rotates on success, rotates on input change', async () => {
      let capturedKeys: string[] = [];
      let returnSuccess = false;
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          const key = getHeader(init, 'Idempotency-Key');
          if (key) capturedKeys.push(key);
          if (!returnSuccess) {
            return Promise.resolve(
              new Response(
                JSON.stringify({
                  type: 'about:blank',
                  title: 'SYS-0001',
                  status: 503,
                  code: 'SYS-0001',
                  category: 'transient',
                  detail: 'The model measurement observation could not be read.',
                  retryable: true,
                  traceId: '0123456789abcdef0123456789abcdef',
                  causeRef: null,
                  evidenceId: null,
                }),
                { status: 503, headers: { 'Content-Type': 'application/problem+json' } }
              )
            );
          }
          return Promise.resolve(new Response(JSON.stringify(validVerifyResponse), { status: 200 }));
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

      // (a) Attempt 1: fails 503
      await act(async () => {
        submitBtn?.click();
      });

      // (b) Attempt 2 (retry after failure): must use SAME key
      await act(async () => {
        submitBtn?.click();
      });

      expect(capturedKeys.length).toBe(2);
      expect(capturedKeys[0]).toBeTruthy();
      expect(capturedKeys[0]).toBe(capturedKeys[1]); // Idempotency-Key preserved on retry!

      // (c) Attempt 3: successful response
      returnSuccess = true;
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(3);
      expect(capturedKeys[2]).toBe(capturedKeys[0]); // same key used for retry that succeeded

      // (d) Attempt 4: next submission after success must rotate key (M2)
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(4);
      expect(capturedKeys[3]).not.toBe(capturedKeys[2]); // Key rotated on success!

      // (e) Change measurementId: must rotate key
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF1234567890ABCDEFH');
      });
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(5);
      expect(capturedKeys[4]).not.toBe(capturedKeys[3]); // Key rotated on input change!
    });

    it('H2 Zero Fake Verification: resets verifyResult when model/version/inputs change or on failure', async () => {
      let shouldFail = false;
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          if (shouldFail) {
            return Promise.resolve(
              new Response(
                JSON.stringify({
                  type: 'about:blank',
                  title: 'GRAPH-0002',
                  status: 409,
                  code: 'GRAPH-0002',
                  category: 'business_rule',
                  detail: 'The measurement does not match the current storage snapshot of the model version.',
                }),
                { status: 409, headers: { 'Content-Type': 'application/problem+json' } }
              )
            );
          }
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

      // Switch to verify tab and submit
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

      // Verification active
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeTruthy();
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toContain('W3 검증: 검증 완료');

      // Change version input to '2.0.0' -> must immediately reset verifyResult (H2)
      const versionInput = container.querySelector('#reg-version') as HTMLInputElement;
      await act(async () => {
        setInputValue(versionInput, '2.0.0');
      });

      // Must be flushed: badge shows unverified, success card disappears
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeNull();
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toContain('W3 검증: 미검증');

      // Change back to '1.0.0' and re-verify
      await act(async () => {
        setInputValue(versionInput, '1.0.0');
      });
      await act(async () => {
        submitBtn?.click();
      });
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeTruthy();

      // Subsequent failure flushes verifyResult
      shouldFail = true;
      await act(async () => {
        submitBtn?.click();
      });
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeNull();
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toContain('W3 검증: 미검증');
    });

    it('discards late responses when request is superseded (generation/abort guard)', async () => {
      let resolveFirst: ((val: Response) => void) | null = null;
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          const body = JSON.parse(init?.body as string);
          if (body.measurementId === 'mvm_01JABCDEF01234567890123451') {
            return new Promise((resolve) => {
              resolveFirst = resolve;
            });
          }
          return Promise.resolve(new Response(JSON.stringify({
            ...validVerifyResponse,
            verifiedMeasurementId: body.measurementId,
          }), { status: 200 }));
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

      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      await act(async () => {
        verifyTab?.click();
      });

      const measurementInput = container.querySelector('#mvm-measurement-id') as HTMLInputElement;
      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );

      // Submit slow request with valid 26-char Crockford ULID (N2 fix)
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF01234567890123451');
      });
      await act(async () => {
        submitBtn?.click();
      });

      expect(resolveFirst).not.toBeNull();
      const verifyCallsBeforeFast = mockFetch.mock.calls.filter(([url]: [string]) => url.includes('/verify'));
      expect(verifyCallsBeforeFast.length).toBe(1);

      // Submit new fast request before slow one resolves
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF01234567890123452');
      });
      await act(async () => {
        submitBtn?.click();
      });

      // Fast request succeeded
      expect(container.querySelector('[data-testid="verified-measurement-id"]')?.textContent).toBe('mvm_01JABCDEF01234567890123452');

      // Now slow request resolves late with obsolete data
      const obsoleteResponse: ModelVerifyResponse = {
        ...validVerifyResponse,
        verifiedMeasurementId: 'mvm_01JABCDEF01234567890123451',
      };
      await act(async () => {
        resolveFirst?.(new Response(JSON.stringify(obsoleteResponse), { status: 200 }));
      });

      // Must NOT be overwritten by superseded request!
      expect(container.querySelector('[data-testid="verified-measurement-id"]')?.textContent).toBe('mvm_01JABCDEF01234567890123452');
    });

    it('W3 N1 guard: input change while verify request is in-flight aborts controller and unlocks loading button', async () => {
      let resolveSlow: ((val: Response) => void) | null = null;
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          return new Promise((resolve) => {
            resolveSlow = resolve;
          });
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

      const verifyTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 검증')
      );
      await act(async () => {
        verifyTab?.click();
      });

      const measurementInput = container.querySelector('#mvm-measurement-id') as HTMLInputElement;
      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );

      // Start slow request
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF01234567890123451');
      });
      await act(async () => {
        submitBtn?.click();
      });

      expect(resolveSlow).not.toBeNull();
      const loadingBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('검증 처리 중...')
      );
      expect(loadingBtn).toBeDefined();
      expect(loadingBtn?.disabled).toBe(true);

      // User changes input while in-flight
      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF01234567890123452');
      });

      // Button MUST be unlocked and re-enabled immediately (N1 fix)
      const unlockedBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );
      expect(unlockedBtn).toBeDefined();
      expect(unlockedBtn?.disabled).toBe(false);

      // Now slow request arrives late
      await act(async () => {
        resolveSlow?.(new Response(JSON.stringify(validVerifyResponse), { status: 200 }));
      });

      // Verification result must NOT be shown
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeNull();
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toBe('W3 검증: 미검증 (커널 계측 검증 대기)');
      expect(unlockedBtn?.disabled).toBe(false);
    });

    it('W5 N1 guard: input change while eval run request is in-flight aborts controller and unlocks loading button', async () => {
      let resolveSlowEval: ((val: Response) => void) | null = null;
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/eval/suites/')) {
          return new Promise((resolve) => {
            resolveSlowEval = resolve;
          });
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
        setInputValue(suiteInput, 'ste_news_v1');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );

      // Submit slow eval request
      await act(async () => {
        submitBtn?.click();
      });

      expect(resolveSlowEval).not.toBeNull();
      const loadingBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('평가 실행 중...')
      );
      expect(loadingBtn).toBeDefined();
      expect(loadingBtn?.disabled).toBe(true);

      // User changes adapter or suiteId while in-flight
      await act(async () => {
        setInputValue(suiteInput, 'ste_news_v2');
      });

      // Button MUST be re-enabled immediately (N1 fix)
      const unlockedBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      expect(unlockedBtn).toBeDefined();
      expect(unlockedBtn?.disabled).toBe(false);

      // Now slow response arrives late
      await act(async () => {
        resolveSlowEval?.(new Response(JSON.stringify(validEvalRunResponse), { status: 201 }));
      });

      // Eval result must NOT be shown
      expect(container.querySelector('[data-testid="registry-eval-success"]')).toBeNull();
      expect(unlockedBtn?.disabled).toBe(false);
    });

    it('W5 N2 supersession guard: discards late eval run response when a newer request was submitted', async () => {
      let resolveFirstEval: ((val: Response) => void) | null = null;
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/eval/suites/')) {
          const body = JSON.parse(init?.body as string);
          if (body.adapter === 'codex-cli') {
            return new Promise((resolve) => {
              resolveFirstEval = resolve;
            });
          }
          return Promise.resolve(new Response(JSON.stringify({
            ...validEvalRunResponse,
            evalRunId: 'evr_01JABCDEF01234567890123452',
            suiteId: 'ste_fast',
          }), { status: 201 }));
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
        setInputValue(suiteInput, 'ste_slow');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );

      // Start slow eval run
      await act(async () => {
        submitBtn?.click();
      });
      expect(resolveFirstEval).not.toBeNull();

      // Change input to new suite & fast adapter
      const adapterSelect = container.querySelector('#eval-adapter') as HTMLSelectElement;
      await act(async () => {
        setInputValue(suiteInput, 'ste_fast');
        setInputValue(adapterSelect, 'claude-code');
      });

      // Submit fast request
      const fastSubmitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      await act(async () => {
        fastSubmitBtn?.click();
      });

      // Fast request displays
      expect(container.querySelector('[data-testid="registry-eval-success"]')?.textContent).toContain('evr_01JABCDEF01234567890123452');

      // Now slow request arrives late
      await act(async () => {
        resolveFirstEval?.(new Response(JSON.stringify({
          ...validEvalRunResponse,
          evalRunId: 'evr_01JABCDEF01234567890123451',
          suiteId: 'ste_slow',
        }), { status: 201 }));
      });

      // Fast result must NOT be overwritten by obsolete slow request!
      expect(container.querySelector('[data-testid="registry-eval-success"]')?.textContent).toContain('evr_01JABCDEF01234567890123452');
      expect(container.querySelector('[data-testid="registry-eval-success"]')?.textContent).not.toContain('evr_01JABCDEF01234567890123451');
    });

    it('H2 guard: changing projectId prop resets verify & eval results and does not bind results to wrong project or model', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          return Promise.resolve(new Response(JSON.stringify(validVerifyResponse), { status: 200 }));
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_AAA"
            modelId="mdl_01JLLAMA30000000000000000"
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
      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W3 커널 측정 검증 제출')
      );

      await act(async () => {
        setInputValue(measurementInput, 'mvm_01JABCDEF01234567890123451');
      });
      await act(async () => {
        submitBtn?.click();
      });

      // Successfully verified for prj_AAA
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toContain('W3 검증: 검증 완료');
      expect(container.querySelector('[data-testid="registry-verify-success"]')).not.toBeNull();

      // Now rerender with different projectId prop (prj_BBB)
      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_BBB"
            modelId="mdl_01JLLAMA30000000000000000"
            version="1.0.0"
            canApprove={true}
          />
        );
      });

      // Must be reset to unverified!
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toBe('W3 검증: 미검증 (커널 계측 검증 대기)');
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeNull();

      // Now change modelId input to different model
      const modelInput = container.querySelector('#reg-model-id') as HTMLInputElement;
      await act(async () => {
        setInputValue(modelInput, 'mdl_DIFFERENT');
      });
      expect(container.querySelector('[data-testid="badge-w3-verify-seam"]')?.textContent).toBe('W3 검증: 미검증 (커널 계측 검증 대기)');
      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeNull();
    });

    it('displays contract error alert when server returns invalid verify response', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/verify')) {
          // Missing required field newlyVerified
          return Promise.resolve(
            new Response(
              JSON.stringify({
                modelVersionId: 'mdv_01JABCDEF1234567890ABCDEFG',
                modelId: 'mdl_01JLLAMA30000000000000000',
                version: '1.0.0',
                stage: 'draft',
              }),
              { status: 200 }
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
            modelId="mdl_01JLLAMA30000000000000000"
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

      expect(container.querySelector('[data-testid="registry-verify-success"]')).toBeNull();
      const alert = container.querySelector('[role="alert"]');
      expect(alert?.textContent).toContain('응답 계약 불일치');
    });
  });

  describe('W5 Eval Run Business Route', () => {
    it('successfully calls eval runs endpoint and renders gate results and scores (H1 adapter options & M5 details)', async () => {
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
            adapter: 'claude-code',
            requireModelPinning: true,
            componentVersions: {
              prompt: 'pmt_01J11111111111111111111111',
              context: 'ctx_01J22222222222222222222222',
            },
          });

          return Promise.resolve(
            new Response(
              JSON.stringify({
                ...validEvalRunResponse,
                componentVersions: {
                  adapter: 'claude-code',
                  contractVersion: '1.0.0',
                  prompt: 'pmt_01J11111111111111111111111',
                },
              }),
              { status: 201 }
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

      // Fill in Suite ID and component versions, and select claude-code adapter (H1)
      const suiteInput = container.querySelector('#eval-suite-id') as HTMLInputElement;
      const adapterSelect = container.querySelector('#eval-adapter') as HTMLSelectElement;
      const promptInput = container.querySelector('#eval-prompt-ver') as HTMLInputElement;
      const ctxInput = container.querySelector('#eval-ctx-ver') as HTMLInputElement;

      await act(async () => {
        setInputValue(suiteInput, 'evs_01JABCDEF1234567890ABCDEFG');
        setInputValue(adapterSelect, 'claude-code');
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
      const passBadge = container.querySelector('[data-testid="eval-gate-badge"]');
      expect(passBadge).toBeTruthy();
      expect(passBadge?.textContent).toBe('GATE PASS');

      const scoreText = container.textContent;
      expect(scoreText).toContain('통과: 25 / 25 케이스 (위반 0건)');

      // M5: componentVersions are rendered
      const cvText = container.querySelector('[data-testid="eval-component-versions"]')?.textContent;
      expect(cvText).toContain('adapter=claude-code');
      expect(cvText).toContain('contractVersion=1.0.0');
    });

    it('honestly renders aborted status, GATE FAIL badge, and NOT_OBSERVED endedAt (M5)', async () => {
      const failedEvalResponse: EvalRunResponse = {
        evalRunId: 'evr_01JABCDEF1234567890ABCDEFG',
        suiteId: 'evs_01JABCDEF1234567890ABCDEFG',
        status: 'aborted',
        passedGate: false,
        totalCases: 25,
        passedCases: 22,
        violations: 3,
        componentVersions: {
          adapter: 'codex-cli',
          contractVersion: '1.0.0',
        },
        startedAt: '2026-09-28T12:00:00Z',
        endedAt: null, // NOT_OBSERVED
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

      // Honest rendering of status title and GATE FAIL badge
      const failBadge = container.querySelector('[data-testid="eval-gate-badge"]');
      expect(failBadge).toBeTruthy();
      expect(failBadge?.textContent).toBe('GATE FAIL');
      expect(container.textContent).toContain('⚠️ 평가 스위트 중단됨 (Status: aborted)');
      expect(container.textContent).toContain('통과: 22 / 25 케이스 (위반 3건)');

      // EndedAt null -> NOT_OBSERVED rendered
      const endedAtElem = container.querySelector('[data-testid="eval-ended-at"]');
      expect(endedAtElem?.textContent).toBe('NOT_OBSERVED');
    });

    it('W5 idempotency lifecycle: preserves key on retry, rotates on success, rotates on input change', async () => {
      let capturedKeys: string[] = [];
      let returnSuccess = false;
      const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/eval/suites/')) {
          const key = getHeader(init, 'Idempotency-Key');
          if (key) capturedKeys.push(key);
          if (!returnSuccess) {
            return Promise.resolve(
              new Response(
                JSON.stringify({
                  type: 'about:blank',
                  title: 'SYS-0001',
                  status: 503,
                  code: 'SYS-0001',
                  category: 'SYS',
                  detail: 'The resource is locked by another request; retry.',
                  retryable: true,
                }),
                { status: 503, headers: { 'Content-Type': 'application/problem+json' } }
              )
            );
          }
          return Promise.resolve(new Response(JSON.stringify(validEvalRunResponse), { status: 201 }));
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
      await act(async () => {
        setInputValue(suiteInput, 'evs_01JABCDEF1234567890ABCDEFG');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );

      // (a) Attempt 1: fails 503
      await act(async () => {
        submitBtn?.click();
      });

      // (b) Attempt 2 (retry): must use SAME key
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(2);
      expect(capturedKeys[0]).toBeTruthy();
      expect(capturedKeys[0]).toBe(capturedKeys[1]); // Idempotency-Key preserved on failure retry!

      // (c) Attempt 3: successful response
      returnSuccess = true;
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(3);
      expect(capturedKeys[2]).toBe(capturedKeys[0]);

      // (d) Attempt 4: next submission after success must rotate key (M2)
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(4);
      expect(capturedKeys[3]).not.toBe(capturedKeys[2]); // Key rotated on success!

      // (e) Change suiteId: must rotate key
      await act(async () => {
        setInputValue(suiteInput, 'evs_01JABCDEF1234567890ABCDEFH');
      });
      await act(async () => {
        submitBtn?.click();
      });
      expect(capturedKeys.length).toBe(5);
      expect(capturedKeys[4]).not.toBe(capturedKeys[3]); // Key rotated on input change!
    });

    it('fails closed when canApprove is false or undefined for W5 eval run', async () => {
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

      const evalTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행')
      );
      await act(async () => {
        evalTab?.click();
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      expect(submitBtn?.hasAttribute('disabled')).toBe(true);
      expect(submitBtn?.getAttribute('aria-disabled')).toBe('true');

      // Test handler guard via form submit
      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });
      expect(mockFetch).not.toHaveBeenCalledWith(expect.stringContaining('/runs'), expect.anything());
      const alert = container.querySelector('[role="alert"]');
      expect(alert?.textContent).toContain('승인 권한(canApprove)이 없는 계정은 평가 스위트를 실행할 수 없습니다.');
    });

    it('rejects invalid adapter format client-side in startEvalRun before network call', async () => {
      await expect(
        startEvalRun('prj_1', 'evs_1', { adapter: 'invalid adapter with spaces!' })
      ).rejects.toThrow('유효한 어댑터 이름');
    });

    it('M4: displays contract error alert when server returns invalid eval run response', async () => {
      const mockFetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('/lineage')) {
          return Promise.resolve(new Response(JSON.stringify(validTraceResponse), { status: 200 }));
        }
        if (url.includes('/eval/suites/')) {
          // Invalid status 'INVALID_STATUS'
          return Promise.resolve(
            new Response(
              JSON.stringify({
                ...validEvalRunResponse,
                status: 'INVALID_STATUS',
              }),
              { status: 201 }
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
        setInputValue(suiteInput, 'ste_news_v1');
      });

      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행 시작')
      );
      await act(async () => {
        submitBtn?.click();
      });

      const errorAlert = container.querySelector('[role="alert"]');
      expect(errorAlert?.textContent).toContain('EvalRunResponse 응답 계약 불일치');
      expect(container.querySelector('[data-testid="registry-eval-success"]')).toBeNull();
    });

    it('M4: fail-closed guard blocks W5 eval run submission when canApprove is undefined', async () => {
      const mockFetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(validTraceResponse), { status: 200 })
      );
      globalThis.fetch = mockFetch;

      await act(async () => {
        root.render(
          <ModelLineageView
            projectId="prj_demo"
            modelId="mdl_01JLLAMA30000000000000000"
            version="1.0.0"
            canApprove={undefined}
          />
        );
      });

      const evalTab = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('W5 평가 실행')
      );
      await act(async () => {
        evalTab?.click();
      });

      const submitBtn = container.querySelector('[data-testid="btn-start-eval-run"]') as HTMLButtonElement;
      expect(submitBtn).not.toBeNull();
      expect(submitBtn.disabled).toBe(true);

      const form = submitBtn.closest('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      const errorAlert = container.querySelector('[role="alert"]');
      expect(errorAlert?.textContent).toContain('승인 권한(canApprove)이 없는 계정은 평가 스위트를 실행할 수 없습니다.');

      // Zero eval network calls
      const evalCalls = mockFetch.mock.calls.filter(([url]: [string]) => url.includes('/eval/'));
      expect(evalCalls.length).toBe(0);
    });
  });
});
