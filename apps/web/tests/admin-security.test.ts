import { describe, it, expect } from 'vitest';
import { SecurityControlManager } from '../src/features/admin/securityEngine';

describe('S08-FE: Security Controls, Isolation, Audit Ledger & GPU Benchmark (AC-08)', () => {
  describe('Docker Socket Isolation (AC-08 Zero Exposure)', () => {
    it('strictly forbids mounting Docker socket and permits legitimate volumes', () => {
      const sec = new SecurityControlManager();

      // Prohibited attempts
      const attempt1 = sec.validateMountPath('/var/run/docker.sock', 'usr_attacker');
      expect(attempt1.allowed).toBe(false);
      expect(attempt1.reason).toContain('Docker socket exposure is prohibited');

      const attempt2 = sec.validateMountPath('//./pipe/docker_engine', 'usr_attacker');
      expect(attempt2.allowed).toBe(false);

      const attempt3 = sec.validateMountPath('/var/run/docker/containerd.sock', 'usr_attacker');
      expect(attempt3.allowed).toBe(false);

      // Invariant: Status reports 0 docker socket exposure
      expect(sec.getStatus().dockerSocketExposed).toBe(false);

      // Legitimate volume allowed
      const valid = sec.validateMountPath('/data/datasets/medical_pacs', 'usr_developer');
      expect(valid.allowed).toBe(true);
    });
  });

  describe('Approval Bypass Prevention (AC-08 Zero Bypass)', () => {
    it('blocks unapproved L2 and L3 executions and permits L1 executions', () => {
      const sec = new SecurityControlManager();

      // L1 allowed without approval
      const l1 = sec.validateExecutionApproval('L1', undefined, 'usr_developer');
      expect(l1.allowed).toBe(true);

      // L2 blocked without approval
      const l2 = sec.validateExecutionApproval('L2', undefined, 'usr_attacker');
      expect(l2.allowed).toBe(false);
      expect(l2.reason).toContain('APPROVAL_REQUIRED');

      // L3 blocked without approval
      const l3 = sec.validateExecutionApproval('L3', undefined, 'usr_attacker');
      expect(l3.allowed).toBe(false);
      expect(l3.reason).toContain('APPROVAL_REQUIRED');

      // L2 allowed with valid approval token
      const l2Approved = sec.validateExecutionApproval('L2', 'apr_01JABCDEF', 'usr_developer');
      expect(l2Approved.allowed).toBe(true);

      // 20 simulated automated bypass attempts all blocked
      for (let i = 0; i < 20; i++) {
        const res = sec.validateExecutionApproval('L2', undefined, `usr_bot_${i}`);
        expect(res.allowed).toBe(false);
      }
      expect(sec.getStatus().approvalBypassesBlocked).toBeGreaterThanOrEqual(22);
    });
  });

  describe('Synthetic GPU Capability Benchmark (AC-08)', () => {
    it('executes synthetic GPU GEMM benchmark with exit code 0 and valid evidence', () => {
      const sec = new SecurityControlManager();

      // Run on RTX 4090 node
      const res4090 = sec.runSyntheticGpuBenchmark('nod_01JABCDEF01', 'NVIDIA RTX 4090');
      expect(res4090.exitCode).toBe(0);
      expect(res4090.computeThroughputTflops).toBeGreaterThan(50);
      expect(res4090.vramAllocatedBytes).toBe(4 * 1024 ** 3);
      expect(res4090.evidenceId).toMatch(/^evi_gpu_/);

      // Run on A4000 node
      const resA4000 = sec.runSyntheticGpuBenchmark('nod_01JABCDEF04', 'NVIDIA A4000');
      expect(resA4000.exitCode).toBe(0);
      expect(resA4000.computeThroughputTflops).toBeGreaterThan(15);
      expect(resA4000.evidenceId).toMatch(/^evi_gpu_/);
    });
  });

  describe('Immutable Audit Ledger & Hash Chaining', () => {
    it('verifies append-only SHA-256 hash chaining across all logged events', () => {
      const sec = new SecurityControlManager();

      sec.logEvent({
        actor: 'usr_admin',
        action: 'test_action_1',
        target: 'res_01',
        outcome: 'allowed',
        details: 'first dynamic event',
      });

      sec.logEvent({
        actor: 'usr_admin',
        action: 'test_action_2',
        target: 'res_02',
        outcome: 'denied',
        details: 'second dynamic event',
      });

      const verification = sec.verifyLedgerIntegrity();
      expect(verification.isValid).toBe(true);
      expect(verification.checkedRecords).toBeGreaterThanOrEqual(6);
    });
  });

  describe('Emergency Kill Switch', () => {
    it('activates emergency kill switch and logs security intervention', () => {
      const sec = new SecurityControlManager();
      expect(sec.getStatus().emergencyKillSwitchActive).toBe(false);

      const activated = sec.toggleEmergencyKillSwitch('usr_security_officer', 'Threat containment protocol');
      expect(activated).toBe(true);
      expect(sec.getStatus().emergencyKillSwitchActive).toBe(true);

      const latestLog = sec.getAuditLogs()[0];
      expect(latestLog.action).toBe('kill_switch_activated');
      expect(latestLog.details).toContain('Threat containment protocol');
    });
  });
});
