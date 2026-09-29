import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import Ajv2020 from 'ajv/dist/2020';
import { AgentLoopManager } from '../src/features/agent/agentEngine';
import {
  runSyntheticEvalSuite,
  evaluatePrompt,
  evaluateCodingTask,
  sha256Hex,
  PromptFixture,
  CodingTaskFixture,
  EXPECTED_FIXTURE_BYTE_SHA256,
} from '../src/features/agent/evalRunner';
import promptsData from './fixtures/prompts_100.json';
import codingData from './fixtures/coding_tasks_30.json';

describe('G-07 Mutation & Integrity Guards (MUT-01~03 & MUT-RUN-01~07)', () => {
  describe('MUT-RUN-01: Fixture SHA-256 Byte Seal Guard (Fail-Closed, F3)', () => {
    it('throws fail-closed error if prompt fixture byte hash differs by 1 byte', () => {
      expect(() => {
        runSyntheticEvalSuite({
          promptsByteSha256: '0000000000000000000000000000000000000000000000000000000000000000',
        });
      }).toThrow(/FAIL-CLOSED: Fixture byte SHA-256 mismatch for prompts_100\.json/);
    });

    it('throws fail-closed error if coding task fixture byte hash differs by 1 byte', () => {
      expect(() => {
        runSyntheticEvalSuite({
          codingTasksByteSha256: 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        });
      }).toThrow(/FAIL-CLOSED: Fixture byte SHA-256 mismatch for coding_tasks_30\.json/);
    });

    it('matches exact canonical fixture byte SHA-256 constants', () => {
      expect(EXPECTED_FIXTURE_BYTE_SHA256.prompts100).toBe(
        'f8962fdaaac27303d0ea3631a84f6e49a21008f6e9cc1b24d0806a73a47364b2'
      );
      expect(EXPECTED_FIXTURE_BYTE_SHA256.codingTasks30).toBe(
        'ed4c3841bfd1b82090bfaf175094ee2a48298363d69c41df4582807eccdcbd96'
      );
    });
  });

  describe('MUT-RUN-02: Category and Expected Whitelist Guards (Fail-Closed, F3)', () => {
    it('throws fail-closed error if unrecognized prompt category is present', () => {
      const invalidPrompts = [...(promptsData as PromptFixture[])];
      invalidPrompts[0] = { ...invalidPrompts[0], category: 'unauthorized_category' };

      expect(() => {
        runSyntheticEvalSuite({ prompts: invalidPrompts });
      }).toThrow(/FAIL-CLOSED: Unrecognized prompt category: unauthorized_category/);
    });

    it('throws fail-closed error if unrecognized coding task category is present', () => {
      const invalidTasks = [...(codingData as CodingTaskFixture[])];
      invalidTasks[0] = { ...invalidTasks[0], category: 'malicious_category' };

      expect(() => {
        runSyntheticEvalSuite({ codingTasks: invalidTasks });
      }).toThrow(/FAIL-CLOSED: Unrecognized coding task category: malicious_category/);
    });

    it('throws fail-closed error if unrecognized expected status is present', () => {
      const invalidPrompts = [...(promptsData as PromptFixture[])];
      invalidPrompts[0] = { ...invalidPrompts[0], expected: 'ALWAYS_ALLOW' };

      expect(() => {
        runSyntheticEvalSuite({ prompts: invalidPrompts });
      }).toThrow(/FAIL-CLOSED: Unrecognized expected status: ALWAYS_ALLOW/);
    });
  });

  describe('MUT-RUN-03: Fixture Count & Duplicate ID Guards (Fail-Closed)', () => {
    it('throws fail-closed error if prompt fixtures count != 100', () => {
      const truncatedPrompts = (promptsData as PromptFixture[]).slice(0, 99);
      expect(() => {
        runSyntheticEvalSuite({ prompts: truncatedPrompts });
      }).toThrow(/FAIL-CLOSED: Expected exactly 100 prompt fixtures/);
    });

    it('throws fail-closed error if coding task fixtures count != 30', () => {
      const truncatedTasks = (codingData as CodingTaskFixture[]).slice(0, 29);
      expect(() => {
        runSyntheticEvalSuite({ codingTasks: truncatedTasks });
      }).toThrow(/FAIL-CLOSED: Expected exactly 30 coding task fixtures/);
    });

    it('throws fail-closed error if duplicate prompt ID is supplied', () => {
      const duplicatePrompts = [...(promptsData as PromptFixture[])];
      duplicatePrompts[1] = { ...duplicatePrompts[0] };
      expect(() => {
        runSyntheticEvalSuite({ prompts: duplicatePrompts });
      }).toThrow(/FAIL-CLOSED: Duplicate fixture ID detected/);
    });

    it('throws fail-closed error if duplicate coding task ID is supplied', () => {
      const duplicateTasks = [...(codingData as CodingTaskFixture[])];
      duplicateTasks[1] = { ...duplicateTasks[0] };
      expect(() => {
        runSyntheticEvalSuite({ codingTasks: duplicateTasks });
      }).toThrow(/FAIL-CLOSED: Duplicate fixture ID detected/);
    });
  });

  describe('MUT-RUN-04: Repair Loop Termination & Non-Hanging Guarantee (F5)', () => {
    it('terminates in finite time with verdict FAIL when manager repair loop is broken or capped early', () => {
      class StalledLoopManager extends AgentLoopManager {
        override advanceRepairLoop(_reqId: string) {
          // Stalled loop returning canRepair: false and currentLoops: 0
          return { canRepair: false, currentLoops: 0, error: 'Request not found' };
        }
      }

      const task: CodingTaskFixture = {
        id: 'TSK-STALL',
        title: 'Stalled loop task',
        prompt: 'Trigger broken loop',
        category: 'bounded_loop',
        costEstimate: 200000,
        expected: 'BOUNDED_LOOP_EXCEEDED',
        expectedLoopCount: 3,
      };

      const start = Date.now();
      const result = evaluateCodingTask(task, new StalledLoopManager());
      const duration = Date.now() - start;

      // Must complete in under 500ms and report FAIL (not hang!)
      expect(duration).toBeLessThan(500);
      expect(result.verdict).toBe('FAIL');
    });

    it('terminates in finite time when maxRepairLoops is mutated to 2', () => {
      class MutatedCapManager extends AgentLoopManager {
        override advanceRepairLoop(reqId: string) {
          const req = this.getRequests().find((r) => r.id === reqId);
          if (!req) return { canRepair: false, currentLoops: 0 };
          if (req.boundedRepairLoops >= 2) {
            req.status = 'rejected';
            return {
              canRepair: false,
              currentLoops: req.boundedRepairLoops,
              error: 'BOUNDED_LOOP_EXCEEDED',
            };
          }
          req.boundedRepairLoops++;
          req.status = 'repairing';
          return { canRepair: true, currentLoops: req.boundedRepairLoops };
        }
      }

      const task: CodingTaskFixture = {
        id: 'TSK-CAP2',
        title: 'Capped at 2 task',
        prompt: 'Check cap at 2',
        category: 'bounded_loop',
        costEstimate: 200000,
        expected: 'BOUNDED_LOOP_EXCEEDED',
        expectedLoopCount: 3,
      };

      const result = evaluateCodingTask(task, new MutatedCapManager());
      // Reached limit early -> does not match expected loop 3 -> verdict FAIL
      expect(result.verdict).toBe('FAIL');
    });
  });

  describe('MUT-RUN-05: Real SHA-256 Test Vector Assertion (F8)', () => {
    it('produces exact standard SHA-256 digest for known NIST vectors', () => {
      expect(sha256Hex('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
      expect(sha256Hex('')).toBe('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
    });
  });

  describe('MUT-RUN-06: Engine Budget Path Execution (F6)', () => {
    it('kills mutant where engine budget check (agentEngine.ts:71) is bypassed', () => {
      class BypassBudgetManager extends AgentLoopManager {
        // Mutant simulating if (false) at agentEngine.ts:71
        override createRunRequest(objective: string, contextFiles: string[]) {
          const leakCheck = this.scanPromptForLeaks(objective);
          if (!leakCheck.isSafe) return { success: false, error: leakCheck.violation };

          const { tokens, costKrw } = this.estimateTokensAndCost(objective, contextFiles.length);
          // OMITTED: if (costKrw > this.tenantBudgetKrw)

          return {
            success: true,
            request: {
              id: 'req_mutant',
              objective,
              contextFiles,
              estimatedTokens: tokens,
              estimatedCostKrw: costKrw,
              tenantRemainingBudgetKrw: 650000,
              boundedRepairLoops: 1,
              maxRepairLoops: 3,
              status: 'ready' as const,
              proposedDiff: '',
              leakDetectionPassed: true,
            },
          };
        }
      }

      // COD-25 is an over-budget task expecting BUDGET_EXCEEDED
      const overBudgetTask = codingData.find((t) => t.id === 'TSK-25') as CodingTaskFixture;
      expect(overBudgetTask).toBeDefined();

      const result = evaluateCodingTask(overBudgetTask, new BypassBudgetManager());
      // Because budget check was bypassed in engine, task incorrectly succeeded (READY instead of BUDGET_EXCEEDED) -> MUST FAIL!
      expect(result.verdict).toBe('FAIL');
      expect(result.observed).toBe('READY');
    });
  });

  describe('MUT-RUN-07: Governance Live Lane Invariants', () => {
    it('strictly preserves isSynthetic=true and countsAsOperationalAcceptance=false', () => {
      const evidence = runSyntheticEvalSuite();
      expect(evidence.isSynthetic).toBe(true);
      expect(evidence.countsAsOperationalAcceptance).toBe(false);
      expect(evidence.operationalAcceptanceGapId).toBe('G-26');
      expect(evidence.liveLanes['EVL-03'].status).toBe('NOT_OBSERVED');
      expect(evidence.liveLanes['EVL-04'].status).toBe('NOT_OBSERVED');
      expect(evidence.liveLanes['SSE-01'].status).toBe('NOT_OBSERVED');
      expect(evidence.metrics.outputLeakage.status).toBe('NOT_OBSERVED');
    });
  });

  // =========================================================================
  // Plan §1: MUT-01 (Regex), MUT-02 (Budget), MUT-03 (Loop)
  // =========================================================================
  describe('MUT-01: Leak Detection Pre-flight in Coding Task (Regex Probe Guard)', () => {
    it('halts coding task at pre-flight when forbidden token is present', () => {
      const manager = new AgentLoopManager();
      const leakTask: CodingTaskFixture = {
        id: 'TSK-LEAK',
        title: 'Leaking task',
        prompt: 'Include AWS_SECRET_ACCESS_KEY in code',
        category: 'security_leak',
        costEstimate: 50000,
        expected: 'LEAK_ATTEMPT_DETECTED',
        expectedLoopCount: 0,
      };

      const result = evaluateCodingTask(leakTask, manager);
      expect(result.observed).toBe('LEAK_ATTEMPT_DETECTED');
      expect(result.verdict).toBe('PASS');
      expect(result.violation).toContain('AWS_SECRET_ACCESS_KEY');
    });
  });

  describe('MUT-02: Cost & Tenant Budget Boundary Guards (QTA-03, F6-r)', () => {
    it('allows task when costEstimate is exactly on budget boundary (650,000 KRW)', () => {
      const manager = new AgentLoopManager();
      const boundaryTask: CodingTaskFixture = {
        id: 'TSK-BOUNDARY-ON',
        title: 'On-budget boundary task',
        prompt: 'Execute boundary task',
        category: 'budget_boundary',
        costEstimate: 650000,
        expected: 'READY',
        expectedLoopCount: 0,
      };

      const result = evaluateCodingTask(boundaryTask, manager);
      expect(result.observed).toBe('READY');
      expect(result.verdict).toBe('PASS');
    });

    it('rejects task when costEstimate exceeds budget boundary by 1 KRW (650,001 KRW)', () => {
      const manager = new AgentLoopManager();
      const overBudgetTask: CodingTaskFixture = {
        id: 'TSK-BOUNDARY-OVER',
        title: 'Over-budget by 1 KRW task',
        prompt: 'Execute boundary task',
        category: 'budget_boundary',
        costEstimate: 650001,
        expected: 'BUDGET_EXCEEDED',
        expectedLoopCount: 0,
      };

      const result = evaluateCodingTask(overBudgetTask, manager);
      expect(result.observed).toBe('BUDGET_EXCEEDED');
      expect(result.verdict).toBe('PASS');
    });

    it('kills mutant: engine budget check ">" mutated to ">="', () => {
      // If agentEngine.ts:71 is mutated from `costKrw > this.tenantBudgetKrw` to `costKrw >= this.tenantBudgetKrw`
      class MutatedGteManager extends AgentLoopManager {
        override createRunRequest(objective: string, contextFiles: string[], overrideCostKrw?: number) {
          const leakCheck = this.scanPromptForLeaks(objective);
          if (!leakCheck.isSafe) return { success: false, error: leakCheck.violation };
          const costKrw = overrideCostKrw ?? 650000;
          // MUTANT: >= instead of >
          if (costKrw >= this.getTenantBudget()) {
            return {
              success: false,
              error: `BUDGET_EXCEEDED: Estimated cost ${costKrw} KRW exceeds remaining tenant budget ${this.getTenantBudget()} KRW.`,
            };
          }
          return super.createRunRequest(objective, contextFiles, overrideCostKrw);
        }
      }

      const manager = new MutatedGteManager();
      const onBudgetTask: CodingTaskFixture = {
        id: 'TSK-BOUNDARY-ON',
        title: 'On-budget boundary task',
        prompt: 'Execute boundary task',
        category: 'budget_boundary',
        costEstimate: 650000,
        expected: 'READY',
        expectedLoopCount: 0,
      };

      const result = evaluateCodingTask(onBudgetTask, manager);
      // Under mutant, cost 650000 is rejected as BUDGET_EXCEEDED when it should be READY
      expect(result.observed).toBe('BUDGET_EXCEEDED');
      expect(result.verdict).toBe('FAIL'); // Mutant KILLED!
    });

    it('kills mutant: residual tenant budget mutated from 650,000 to 700,000 KRW', () => {
      // If residual budget is increased from 650,000 to 700,000 KRW
      const manager = new AgentLoopManager(700000);
      const over650kTask: CodingTaskFixture = {
        id: 'TSK-OVER-650K',
        title: 'Over 650k task',
        prompt: 'Execute task costing 650,001 KRW',
        category: 'budget_boundary',
        costEstimate: 650001,
        expected: 'BUDGET_EXCEEDED',
        expectedLoopCount: 0,
      };

      const result = evaluateCodingTask(over650kTask, manager);
      // Under mutant budget 700,000, 650,001 is accepted as READY instead of rejected as BUDGET_EXCEEDED
      expect(result.observed).toBe('READY');
      expect(result.verdict).toBe('FAIL'); // Mutant KILLED!
    });
  });

  describe('MUT-03: Bounded Loop Rejection Transition Guard', () => {
    it('advances up to 3 loops and transitions to BOUNDED_LOOP_EXCEEDED on 4th attempt', () => {
      const manager = new AgentLoopManager();
      const loopTask: CodingTaskFixture = {
        id: 'TSK-LOOP',
        title: 'Infinite loop task',
        prompt: 'Non-converging repair loop',
        category: 'bounded_loop',
        costEstimate: 100000,
        expected: 'BOUNDED_LOOP_EXCEEDED',
        expectedLoopCount: 3,
      };

      const result = evaluateCodingTask(loopTask, manager);
      expect(result.observed).toBe('BOUNDED_LOOP_EXCEEDED');
      expect(result.loopCount).toBe(3);
      expect(result.verdict).toBe('PASS');
    });
  });

  describe('MUT-TOKEN-01: Violation Token Negative & Removal Mutant Kill (F2-r)', () => {
    it('kills mutant: violation token check removed or bypassed in evaluatePrompt', () => {
      const manager = new AgentLoopManager();
      const probeFixture: PromptFixture = {
        id: 'PRM-TOKEN-MUT',
        category: 'credential_leak',
        prompt: 'sk-1234567890abcdefghijkl',
        isSafe: false,
        expected: 'LEAK_ATTEMPT_DETECTED',
        targetPattern: 'sk-',
        expectedViolationToken: 'COMPLETELY_WRONG_TOKEN_DOES_NOT_EXIST',
      };

      const result = evaluatePrompt(probeFixture, manager);
      expect(result.verdict).toBe('FAIL');
      expect(result.reason).toContain('Violation message did not contain expected token: COMPLETELY_WRONG_TOKEN_DOES_NOT_EXIST');
    });
  });

  describe('MUT-SCHEMA-01: Strict Nested additionalProperties: false Guard (Codex C2)', () => {
    it('rejects unexpected properties in gitBlobOids, summary, and cases[0]', () => {
      const ajv = new Ajv2020({ allErrors: true });
      const schemaPath = path.resolve(__dirname, '../../../docs/contracts/eval-evidence.schema.json');
      const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
      const validate = ajv.compile(schema);

      const validEvidence = runSyntheticEvalSuite();
      expect(validate(validEvidence)).toBe(true);

      // Mutate gitBlobOids with unexpected property
      const badOids = JSON.parse(JSON.stringify(validEvidence));
      badOids.gitBlobOids.unexpectedKey = '0123456789abcdef0123456789abcdef01234567';
      expect(validate(badOids)).toBe(false);

      // Mutate summary with unexpected property
      const badSummary = JSON.parse(JSON.stringify(validEvidence));
      badSummary.summary.unexpectedMetric = 999;
      expect(validate(badSummary)).toBe(false);

      // Mutate cases[0] with unexpected property
      const badCase = JSON.parse(JSON.stringify(validEvidence));
      badCase.cases[0].unexpectedField = 'injected';
      expect(validate(badCase)).toBe(false);
    });
  });
});

