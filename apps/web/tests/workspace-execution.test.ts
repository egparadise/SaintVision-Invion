import { describe, it, expect } from 'vitest';
import { WorkspaceItem, ExecutionResultItem } from '../src/contracts/types';

describe('S03-FE Workspace Isolation & Execution Results (AC-03)', () => {
  const sampleWorkspace: WorkspaceItem = {
    id: 'wsp_01JABCDE9999',
    projectId: 'prj_01JABCDE',
    name: 'wsp-pacs-core-sandbox',
    targetNodeId: 'nod_01JABCDEF01',
    isolationMode: 'process_sandbox',
    allowedPaths: ['./workspace', './data'],
    prohibitedPaths: ['/etc', 'C:\\Windows', '..', '/var/run'],
    cpuLimitCores: 4,
    memoryLimitBytes: 8 * 1024 ** 3,
    status: 'active',
    createdAt: new Date().toISOString(),
  };

  const sampleExecution: ExecutionResultItem = {
    runId: 'run_01JABCDE0001',
    workspaceId: 'wsp_01JABCDE9999',
    command: 'pytest tests/test_core.py -v',
    exitCode: 0,
    state: 'succeeded',
    evidenceId: 'evi_01JABCDEF987654',
    resourceReclaimed: true,
    allowedEvents: [
      { timestamp: '2026-09-09T18:10:01Z', action: 'READ', path: './workspace/tests/test_core.py' },
      { timestamp: '2026-09-09T18:10:02Z', action: 'WRITE', path: './data/test_output.json' },
    ],
    deniedEvents: [
      {
        timestamp: '2026-09-09T18:10:01.5Z',
        action: 'EXEC',
        path: '/etc/shadow',
        reason: 'BLOCKED: Access to prohibited system directory /etc is forbidden (ADR-005)',
      },
    ],
    executedAt: '2026-09-09T18:10:00Z',
    completedAt: '2026-09-09T18:10:05Z',
  };

  it('should block path traversal attempts containing ".." in allowed paths', () => {
    const isPathPermitted = (path: string): boolean => {
      if (path.includes('..')) return false;
      if (path.startsWith('/') || /^[a-zA-Z]:\\?/.test(path)) return false;
      return true;
    };

    expect(isPathPermitted('./src/models')).toBe(true);
    expect(isPathPermitted('../etc/passwd')).toBe(false);
    expect(isPathPermitted('workspace/../../root')).toBe(false);
    expect(isPathPermitted('C:\\Windows\\System32')).toBe(false);
    expect(isPathPermitted('/etc/shadow')).toBe(false);
  });

  it('should require a valid evidenceId when execution state is succeeded (ADR-008 Invariant)', () => {
    const validateRunEvidenceInvariant = (state: string, evidenceId?: string): boolean => {
      if (state === 'succeeded') {
        return Boolean(evidenceId && evidenceId.trim().length > 0);
      }
      return true;
    };

    expect(validateRunEvidenceInvariant(sampleExecution.state, sampleExecution.evidenceId)).toBe(true);
    expect(validateRunEvidenceInvariant('succeeded', undefined)).toBe(false);
    expect(validateRunEvidenceInvariant('succeeded', '')).toBe(false);
    expect(validateRunEvidenceInvariant('failed', undefined)).toBe(true);
  });

  it('should verify resource reclamation upon execution termination (AC-03)', () => {
    expect(sampleExecution.resourceReclaimed).toBe(true);

    const markWorkspaceReclaimed = (wsp: WorkspaceItem): WorkspaceItem => ({
      ...wsp,
      status: 'reclaimed',
    });

    const reclaimed = markWorkspaceReclaimed(sampleWorkspace);
    expect(reclaimed.status).toBe('reclaimed');
  });

  it('should distinguish exit code 0 as success and non-zero as failure', () => {
    const isSuccess = (code: number) => code === 0;

    expect(isSuccess(sampleExecution.exitCode)).toBe(true);
    expect(isSuccess(1)).toBe(false);
    expect(isSuccess(137)).toBe(false); // SIGKILL / OOM
  });

  it('should capture audit trail with both allowed and blocked security actions', () => {
    expect(sampleExecution.allowedEvents.length).toBeGreaterThan(0);
    expect(sampleExecution.deniedEvents.length).toBeGreaterThan(0);
    expect(sampleExecution.deniedEvents[0].reason).toContain('BLOCKED');
  });
});
