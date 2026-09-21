// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as client from '../src/shared/api/client';
import type { ProjectItem, RunItem } from '../src/contracts/types';

const sampleProject: ProjectItem = {
  id: 'prj_test_fb03',
  name: 'FB-03 Test Project',
};

const sampleRun: RunItem = {
  id: 'run_fb03',
  projectId: 'prj_test_fb03',
  status: 'succeeded',
  state: 'succeeded',
  targetNodeId: 'nod_01JABCDEF01',
  createdAt: '2026-09-21T10:00:00Z',
  startedAt: '2026-09-21T10:00:01Z',
  finishedAt: '2026-09-21T10:00:05Z',
};

const sampleFallbackArtifactList = {
  runId: 'run_fb03',
  outputHash: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  outputSizeBytes: 2048,
  verifiedEvidenceId: 'evi_legacy_fb03',
  items: [
    {
      name: 'model_output.bin',
      path: 'dist/model_output.bin',
      sizeBytes: 2048,
      sha256: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    },
  ],
};

describe('DeveloperStudio Artifact Route-404 Fallback DOM Harness (UI-FB-03)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it('Scenario 1: 401 Unauthorized -> NO fallback to /artifacts, displays error banner, suppresses fallback badge & verified banner', async () => {
    let artifactsCalls = 0;
    const err401 = {
      problem: {
        status: 401,
        code: 'NET-401',
        title: 'Unauthorized',
        detail: 'User session expired or invalid token',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw err401;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // 1. /artifacts endpoint must NOT be called
    expect(artifactsCalls).toBe(0);

    // 2. Error banner must be rendered with role="alert"
    const errorBanner = container.querySelector('[data-testid="artifact-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('User session expired or invalid token');

    // 3. Fallback badge must NOT be rendered
    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();

    // 4. Fallback or Verified text must NOT appear
    expect(container.textContent).not.toContain('404 호환 폴백: /artifacts');
    expect(container.textContent).not.toContain('Artifact Fallback');
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 2: 403 Forbidden -> NO fallback to /artifacts, displays error banner, suppresses fallback badge & verified banner', async () => {
    let artifactsCalls = 0;
    const err403 = {
      problem: {
        status: 403,
        code: 'NET-403',
        title: 'Forbidden',
        detail: 'Insufficient permissions to view run results',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw err403;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);

    const errorBanner = container.querySelector('[data-testid="artifact-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('Insufficient permissions to view run results');

    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();
    expect(container.textContent).not.toContain('404 호환 폴백: /artifacts');
    expect(container.textContent).not.toContain('Artifact Fallback');
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 3: 500 Internal Server Error -> NO fallback to /artifacts, displays error banner, suppresses fallback badge & verified banner', async () => {
    let artifactsCalls = 0;
    const err500 = {
      problem: {
        status: 500,
        code: 'NET-500',
        title: 'Internal Server Error',
        detail: 'Database connection failed',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw err500;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);

    const errorBanner = container.querySelector('[data-testid="artifact-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('Database connection failed');

    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();
    expect(container.textContent).not.toContain('404 호환 폴백: /artifacts');
    expect(container.textContent).not.toContain('Artifact Fallback');
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 4: Malformed JSON parse error -> NO fallback to /artifacts, displays error banner, suppresses fallback badge & verified banner', async () => {
    let artifactsCalls = 0;
    const errParse = {
      problem: {
        status: 500,
        code: 'NET-PARSE',
        title: 'Communication Failure',
        detail: 'Failed to parse error response from server.',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw errParse;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);

    const errorBanner = container.querySelector('[data-testid="artifact-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('Failed to parse error response from server.');

    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();
    expect(container.textContent).not.toContain('404 호환 폴백: /artifacts');
    expect(container.textContent).not.toContain('Artifact Fallback');
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 5: Network rejection -> NO fallback to /artifacts, displays error banner, suppresses fallback badge & verified banner', async () => {
    let artifactsCalls = 0;
    const errNetwork = new Error('Network request failed');

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw errNetwork;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);

    const errorBanner = container.querySelector('[data-testid="artifact-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('Network request failed');

    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();
    expect(container.textContent).not.toContain('404 호환 폴백: /artifacts');
    expect(container.textContent).not.toContain('Artifact Fallback');
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 6: App-level 404 (RES-RUN-404) -> STRICTLY NO fallback to /artifacts, displays error banner, suppresses fallback badge & verified banner', async () => {
    let artifactsCalls = 0;
    const errApp404 = {
      problem: {
        status: 404,
        code: 'RES-RUN-404',
        title: 'Run Not Found',
        detail: 'Specified run does not exist or has been purged',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw errApp404;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // 1. Strictly NO fallback to /artifacts (route exists, entity missing)
    expect(artifactsCalls).toBe(0);

    // 2. Error banner must be rendered with role="alert"
    const errorBanner = container.querySelector('[data-testid="artifact-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('Specified run does not exist or has been purged');

    // 3. Fallback badge must NOT be rendered
    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();

    // 4. Must NOT claim artifact fallback or output verified
    expect(container.textContent).not.toContain('404 호환 폴백: /artifacts');
    expect(container.textContent).not.toContain('Artifact Fallback');
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 7: Route-only 404 (unmapped route) -> triggers fallback to /artifacts (1 call), renders fallback badge & UNVERIFIED, NO error banner', async () => {
    let artifactsCalls = 0;
    const errRoute404 = {
      problem: {
        status: 404,
        detail: 'Not Found',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        throw errRoute404;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // 1. Fallback to /artifacts MUST be called exactly once
    expect(artifactsCalls).toBe(1);

    // 2. Error banner must NOT be present
    expect(container.querySelector('[data-testid="artifact-error-banner"]')).toBeNull();

    // 3. Fallback badge must be rendered
    const fallbackBadge = container.querySelector('[data-testid="artifact-fallback-badge"]');
    expect(fallbackBadge).not.toBeNull();
    expect(fallbackBadge?.textContent).toContain('404 호환 폴백: /artifacts');

    // 4. Status badge must display UNVERIFIED fallback
    expect(container.textContent).toContain('산출물 아티팩트 폴백 (Artifact Fallback / UNVERIFIED)');

    // 5. Output Verified must NEVER be shown when fallback was used
    expect(container.textContent).not.toContain('✓ 산출물 검증 완료 (Output Verified)');
  });

  it('Scenario 8: Canonical /result 200 OK -> NO fallback to /artifacts, renders Output Verified badge, NO fallback badge or error banner', async () => {
    let artifactsCalls = 0;
    const result200 = {
      runId: 'run_fb03',
      output: {
        sha256: 'sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        sizeBytes: 4096,
      },
      evidence: {
        evidenceId: 'evi_verified_canonical_01',
      },
      stopReceipt: {
        exitCode: 0,
      },
      completedAt: '2026-09-21T10:00:05Z',
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        return result200 as any;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        return sampleFallbackArtifactList as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[sampleRun]}
          initialStep={4}
          initialRunId="run_fb03"
        />
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);
    expect(container.querySelector('[data-testid="artifact-error-banner"]')).toBeNull();
    expect(container.querySelector('[data-testid="artifact-fallback-badge"]')).toBeNull();
    expect(container.textContent).toContain('✓ 산출물 검증 완료 (Output Verified)');
  });
});
