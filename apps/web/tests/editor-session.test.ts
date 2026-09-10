import { describe, it, expect } from 'vitest';
import {
  computeSha256,
  computeDiff,
  createGitCommit,
} from '../src/features/editor/diffEngine';
import { SessionRecoveryManager } from '../src/features/editor/sessionRecovery';

describe('S06-FE: Development Workspace, Monaco Diff & Session Recovery (AC-06)', () => {
  describe('Diff Engine & ETag Integrity', () => {
    it('generates deterministic SHA-256 ETag and accurate line-by-line diff', () => {
      const original = 'line 1\nline 2\nline 3\n';
      const modified = 'line 1\nline 2 modified\nline 3\nline 4 added\n';

      const origEtag = computeSha256(original);
      const modEtag = computeSha256(modified);

      expect(origEtag).toHaveLength(64);
      expect(modEtag).toHaveLength(64);
      expect(origEtag).not.toBe(modEtag);

      const diff = computeDiff('src/app.ts', original, modified);
      expect(diff.path).toBe('src/app.ts');
      expect(diff.originalEtag).toBe(origEtag);
      expect(diff.modifiedEtag).toBe(modEtag);
      expect(diff.additionsCount).toBeGreaterThan(0);
      expect(diff.deletionsCount).toBeGreaterThan(0);

      // Check line markers
      const addedLines = diff.lines.filter((l) => l.type === 'added');
      const removedLines = diff.lines.filter((l) => l.type === 'removed');
      const unchangedLines = diff.lines.filter((l) => l.type === 'unchanged');

      expect(addedLines.length).toBe(diff.additionsCount);
      expect(removedLines.length).toBe(diff.deletionsCount);
      expect(unchangedLines.length).toBeGreaterThan(0);
    });

    it('returns zero additions and deletions when content is unchanged', () => {
      const content = 'const x = 42;\nconsole.log(x);\n';
      const diff = computeDiff('src/math.ts', content, content);

      expect(diff.additionsCount).toBe(0);
      expect(diff.deletionsCount).toBe(0);
      expect(diff.lines.every((l) => l.type === 'unchanged')).toBe(true);
      expect(diff.originalEtag).toBe(diff.modifiedEtag);
    });
  });

  describe('Git Commit Creation & Chaining (AC-06)', () => {
    it('generates 40-char SHA commit records and chains parents correctly', () => {
      const files = {
        'src/main.ts': 'console.log("hello")',
        'contracts/spec.json': '{"version": "1.0.0"}',
      };

      // Root commit
      const rootCommit = createGitCommit({
        author: 'Alice <alice@saintvision.internal>',
        message: 'chore: initial commit',
        parentCommitId: null,
        stagedFiles: ['src/main.ts', 'contracts/spec.json'],
        fileContents: files,
      });

      expect(rootCommit.commitId).toMatch(/^[0-9a-f]{40}$/);
      expect(rootCommit.parentCommitId).toBeNull();
      expect(rootCommit.treeHash).toMatch(/^[0-9a-f]{40}$/);

      // Child commit
      const updatedFiles = {
        ...files,
        'src/main.ts': 'console.log("hello world v2")',
      };

      const childCommit = createGitCommit({
        author: 'Bob <bob@saintvision.internal>',
        message: 'feat: update greeting',
        parentCommitId: rootCommit.commitId,
        stagedFiles: ['src/main.ts'],
        fileContents: updatedFiles,
      });

      expect(childCommit.commitId).toMatch(/^[0-9a-f]{40}$/);
      expect(childCommit.parentCommitId).toBe(rootCommit.commitId);
      expect(childCommit.treeHash).not.toBe(rootCommit.treeHash);
    });
  });

  describe('PTY Terminal Resize (SIGWINCH)', () => {
    it('resizes within terminal boundaries and emits SIGWINCH event', () => {
      const mgr = new SessionRecoveryManager('wsp_test_01');

      const res1 = mgr.resizeTerminal(120, 40);
      expect(res1.cols).toBe(120);
      expect(res1.rows).toBe(40);
      expect(res1.event).toBe('SIGWINCH');

      // Clamping lower bound
      const resMin = mgr.resizeTerminal(10, 5);
      expect(resMin.cols).toBe(20);
      expect(resMin.rows).toBe(10);

      // Clamping upper bound
      const resMax = mgr.resizeTerminal(500, 200);
      expect(resMax.cols).toBe(240);
      expect(resMax.rows).toBe(100);
    });
  });

  describe('Session Recovery & Zero Duplicate Executions (AC-06)', () => {
    it('executes commands with sequence numbers and prevents duplicate executions with same nonce', () => {
      const mgr = new SessionRecoveryManager('wsp_test_01');
      const nonce1 = 'nonce_1001';
      const nonce2 = 'nonce_1002';

      const exec1 = mgr.executeCommand('git status', nonce1);
      expect(exec1.success).toBe(true);
      expect(exec1.isDuplicate).toBe(false);
      expect(exec1.entry.seq).toBe(1);

      const exec2 = mgr.executeCommand('npm test', nonce2);
      expect(exec2.success).toBe(true);
      expect(exec2.isDuplicate).toBe(false);
      expect(exec2.entry.seq).toBe(2);

      // Duplicate execution attempt with nonce1
      const dupExec = mgr.executeCommand('git status', nonce1);
      expect(dupExec.success).toBe(true);
      expect(dupExec.isDuplicate).toBe(true);
      expect(dupExec.entry.seq).toBe(1); // returned original entry
      expect(mgr.getState().duplicateExecutions).toBe(1);
    });

    it('simulates Control Plane restart, reconnects with token, and verifies checkpoint hash match', () => {
      const workspaceId = 'wsp_mission_critical';
      const mgr = new SessionRecoveryManager(workspaceId);

      mgr.executeCommand('export NODE_ENV=production', 'nonce_a');
      mgr.executeCommand('make build', 'nonce_b');
      mgr.executeCommand('pytest -v', 'nonce_c');

      const preRestartState = mgr.getState();
      expect(preRestartState.lastSeq).toBe(3);
      expect(preRestartState.status).toBe('connected');

      const initialCheckpointHash = preRestartState.checkpointHash;

      // 1. Simulate CP Crash / Restart
      mgr.simulateCpRestart();
      expect(mgr.getState().status).toBe('disconnected');

      // 2. Client attempts resume using token and lastSeq=2 (client missed seq=3 during drop)
      const resumeResult = mgr.resumeSession(preRestartState.reconnectToken, 2);

      expect(resumeResult.resumed).toBe(true);
      expect(resumeResult.hashMatches).toBe(true);
      expect(resumeResult.checkpointHash).toBe(initialCheckpointHash);
      expect(resumeResult.missedCommands).toHaveLength(1);
      expect(resumeResult.missedCommands[0].command).toBe('pytest -v');
      expect(mgr.getState().status).toBe('recovered');

      // Zero duplicate executions occurred during recovery
      expect(mgr.getState().duplicateExecutions).toBe(0);
    });
  });
});
