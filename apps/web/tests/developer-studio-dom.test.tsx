// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as client from '../src/shared/api/client';
import type { ProjectItem, RunItem, NodeStopReceipt } from '../src/contracts/types';

const sampleReceipt: NodeStopReceipt = {
  receiptId: 'rcp_fb03',
  runId: 'run_fb03',
  nodeId: 'nod_01JABCDEF01',
  commandId: 'cmd_01',
  exitCode: 0,
  physicallyStopped: true,
  resourceReclaimed: true,
  verified: true,
  stoppedAt: '2026-09-21T10:00:05Z',
};

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
    window.URL.createObjectURL = vi.fn(() => 'blob:mock');
    window.URL.revokeObjectURL = vi.fn();
    window.alert = vi.fn();
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

describe('handleDownloadArtifact route-404 fallback and non-route error guards (UI-FB-03 Download Probe)', () => {
  let container: HTMLDivElement;
  let root: Root;

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

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    window.URL.createObjectURL = vi.fn(() => 'blob:mock');
    window.URL.revokeObjectURL = vi.fn();
    window.alert = vi.fn();
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

  it('Download Scenario 1: 401 Unauthorized during download probe -> NO fallback to /artifacts (0 calls)', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
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
        if (initialMount) {
          return result200 as any;
        }
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    // User triggers download action
    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // MUST NOT call /artifacts when /result fails with 401
    expect(artifactsCalls).toBe(0);
    // User must be alerted of authorization failure; stale cache MUST NOT be downloaded
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('산출물 검증 및 다운로드 요청 실패 (NET-401): User session expired or invalid token')
    );
    expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('Download Scenario 1b: 403 Forbidden during download probe -> NO fallback to /artifacts, alerts user, NO silent cache download', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
    const err403 = {
      problem: {
        status: 403,
        code: 'SEC-403',
        title: 'Forbidden',
        detail: 'Insufficient permissions to export artifacts',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        if (initialMount) {
          return result200 as any;
        }
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('산출물 검증 및 다운로드 요청 실패 (SEC-403): Insufficient permissions to export artifacts')
    );
    expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('Download Scenario 2: 500 Internal Server Error during download probe -> NO fallback to /artifacts (0 calls), alerts user, NO silent cache download', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
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
        if (initialMount) {
          return result200 as any;
        }
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('산출물 검증 및 다운로드 요청 실패 (NET-500): Database connection failed')
    );
    expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('Download Scenario 3: Network rejection during download probe -> NO fallback to /artifacts (0 calls), alerts user, NO silent cache download', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
    const errNetwork = new Error('Network request failed');

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        if (initialMount) {
          return result200 as any;
        }
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('산출물 검증 및 다운로드 요청 실패 (ERR): Network request failed')
    );
    expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('Download Scenario 4: App-level 404 (RES-RUN-404) during download probe -> STRICTLY NO fallback to /artifacts (0 calls), alerts user, NO silent cache download', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
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
        if (initialMount) {
          return result200 as any;
        }
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(0);
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('산출물 검증 및 다운로드 요청 실패 (RES-RUN-404): Specified run does not exist or has been purged')
    );
    expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('Download Scenario 5: Route-only 404 (detail=Not Found) during download probe -> triggers fallback to /artifacts (1 call) and downloads manifest', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
    const errRoute404 = {
      problem: {
        status: 404,
        detail: 'Not Found',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        if (initialMount) {
          return result200 as any;
        }
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // Route-only 404 must trigger fallback to /artifacts exactly once
    expect(artifactsCalls).toBe(1);
    expect(window.alert).not.toHaveBeenCalled();
    expect(window.URL.createObjectURL).toHaveBeenCalled();
  });

  it('Download Scenario 6: Route-only 404 but legacy fallback ALSO fails -> alerts user, NO silent cache download', async () => {
    let artifactsCalls = 0;
    let initialMount = true;
    const errRoute404 = {
      problem: {
        status: 404,
        detail: 'Not Found',
      },
    };
    const errFallback500 = {
      problem: {
        status: 500,
        detail: 'Storage volume unmounted',
      },
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        if (initialMount) {
          return result200 as any;
        }
        throw errRoute404;
      }
      if (endpoint.endsWith('/artifacts')) {
        artifactsCalls++;
        throw errFallback500;
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

    initialMount = false;
    artifactsCalls = 0;

    const downloadBtn = container.querySelector('[data-testid="artifact-meta-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(false);

    await act(async () => {
      downloadBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(artifactsCalls).toBe(1);
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('레거시 아티팩트 목록 조회 실패: Storage volume unmounted')
    );
    expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('Receipt Scenario 1: Missing receipt in liveRun and /result -> triggers alert, modal & reclaim notice NOT rendered', async () => {
    const { stopReceipt: _unused, ...noReceiptResult } = result200;
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        return noReceiptResult as any; // stopReceipt is strictly undefined
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any; // stopReceipt is undefined
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

    const inspectBtn = container.querySelector('[data-testid="inspect-receipt-btn"]') as HTMLButtonElement;
    expect(inspectBtn).not.toBeNull();
    expect(inspectBtn.disabled).toBe(false);

    await act(async () => {
      inspectBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // Alert must be called with failure explanation
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('물리 정지 영수증(NodeStopReceipt) 조회 실패')
    );

    // Modal and fake reclaim notice must NOT be rendered
    expect(container.querySelector('[data-testid="receipt-modal"]')).toBeNull();
    expect(container.querySelector('[data-testid="reclaim-notice-banner"]')).toBeNull();
  });

  it('Receipt Scenario 2: Valid receipt in /result -> opens receipt-modal and renders reclaim-notice-banner', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        return {
          ...result200,
          stopReceipt: sampleReceipt,
        } as any;
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

    const inspectBtn = container.querySelector('[data-testid="inspect-receipt-btn"]') as HTMLButtonElement;
    expect(inspectBtn).not.toBeNull();

    await act(async () => {
      inspectBtn.click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // Modal and reclaim notice must be rendered
    expect(container.querySelector('[data-testid="receipt-modal"]')).not.toBeNull();
    const banner = container.querySelector('[data-testid="reclaim-notice-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('NodeStopReceipt 수신을 확인하고 Lease 자원을 회수하였습니다');
  });

  it('Raw File Download Scenario: Server failure during raw download -> triggers honest alert, no fake local content synthesized', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith('/result')) {
        return result200 as any;
      }
      if (endpoint.includes('/workspaces')) {
        return { projectId: sampleProject.id, workspaces: [] } as any;
      }
      if (endpoint.includes('/runs/')) {
        return sampleRun as any;
      }
      return {} as any;
    });

    // Mock global fetch to simulate 500 error
    const originalFetch = window.fetch;
    window.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    } as any);

    try {
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

      const rawDownloadBtn = container.querySelector('[data-testid="artifact-raw-download-btn"]') as HTMLButtonElement;
      expect(rawDownloadBtn).not.toBeNull();
      expect(rawDownloadBtn.disabled).toBe(false);

      await act(async () => {
        rawDownloadBtn.click();
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      // Honest alert must be invoked
      expect(window.alert).toHaveBeenCalledWith(
        expect.stringContaining('산출물 파일 바이트 다운로드 실패: HTTP 500: Internal Server Error')
      );
      // createObjectURL should NOT have been called to synthesize a fake blob from local file
      expect(window.URL.createObjectURL).not.toHaveBeenCalled();
    } finally {
      window.fetch = originalFetch;
    }
  });
});

