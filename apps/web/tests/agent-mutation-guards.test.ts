import { describe, it, expect } from 'vitest';
import { AgentLoopManager } from '../src/features/agent/agentEngine';
import {
  runSyntheticEvalSuite,
  evaluatePrompt,
  evaluateCodingTask,
  PromptFixture,
  CodingTaskFixture,
} from '../src/features/agent/evalRunner';
import promptsData from './fixtures/prompts_100.json';
import codingData from './fixtures/coding_tasks_30.json';

describe('G-07 Mutation & Integrity Guards (MUT-01~03 & MUT-RUN-01~04)', () => {
  describe('MUT-RUN-01: Fixture count integrity check (Fail-Closed)', () => {
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
  });

  describe('MUT-RUN-02: Duplicate fixture ID guard (Fail-Closed)', () => {
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

  describe('MUT-RUN-03: Engine crash or unknown status is recorded as verdict FAIL', () => {
    it('records fail-closed verdict FAIL when prompt evaluation throws an exception', () => {
      const manager = new AgentLoopManager();
      // Inject crashing scanner
      manager.scanPromptForLeaks = () => {
        throw new Error('Fatal scanner segmentation fault');
      };

      const result = evaluatePrompt(promptsData[0] as PromptFixture, manager);
      expect(result.verdict).toBe('FAIL');
      expect(result.observed).toBe('ERRORED');
      expect(result.reason).toContain('Fatal scanner segmentation fault');
    });

    it('records fail-closed verdict FAIL when coding task evaluation throws', () => {
      const manager = new AgentLoopManager();
      manager.createRunRequest = () => {
        throw new Error('Kernel communication panic');
      };

      const result = evaluateCodingTask(codingData[0] as CodingTaskFixture, manager);
      expect(result.verdict).toBe('FAIL');
      expect(result.observed).toBe('UNKNOWN');
      expect(result.reason).toContain('Kernel communication panic');
    });
  });

  describe('MUT-RUN-04: Governance live lane invariants', () => {
    it('strictly preserves isSynthetic=true and countsAsOperationalAcceptance=false', () => {
      const evidence = runSyntheticEvalSuite();
      expect(evidence.isSynthetic).toBe(true);
      expect(evidence.countsAsOperationalAcceptance).toBe(false);
      expect(evidence.operationalAcceptanceGapId).toBe('G-26');
      expect(evidence.liveLanes['EVL-03'].status).toBe('NOT_OBSERVED');
      expect(evidence.liveLanes['EVL-04'].status).toBe('NOT_OBSERVED');
      expect(evidence.liveLanes['SSE-01'].status).toBe('NOT_OBSERVED');
    });
  });

  describe('MUT-01: Cost & Tenant Budget Boundary Guards', () => {
    it('rejects task when costEstimate exceeds 650,000 KRW with BUDGET_EXCEEDED', () => {
      const manager = new AgentLoopManager();
      const overBudgetTask: CodingTaskFixture = {
        id: 'TSK-OVER',
        title: 'Over budget task',
        prompt: 'Execute high cost task',
        category: 'heavy',
        costEstimate: 650001,
        expected: 'BUDGET_EXCEEDED',
        expectedLoopCount: 1,
      };

      const result = evaluateCodingTask(overBudgetTask, manager);
      expect(result.observed).toBe('BUDGET_EXCEEDED');
      expect(result.verdict).toBe('PASS');
    });

    it('allows boundary task when costEstimate == 650,000 KRW (boundary probe O4)', () => {
      const manager = new AgentLoopManager();
      const boundaryTask: CodingTaskFixture = {
        id: 'TSK-BOUND',
        title: 'Boundary cost task',
        prompt: 'Execute exact budget task',
        category: 'boundary',
        costEstimate: 650000,
        expected: 'READY',
        expectedLoopCount: 1,
      };

      const result = evaluateCodingTask(boundaryTask, manager);
      expect(result.observed).toBe('READY');
      expect(result.verdict).toBe('PASS');
    });
  });

  describe('MUT-02: Bounded Loop Rejection Transition Guard', () => {
    it('advances up to 3 loops and transitions to BOUNDED_LOOP_EXCEEDED on 4th attempt', () => {
      const manager = new AgentLoopManager();
      const loopTask: CodingTaskFixture = {
        id: 'TSK-LOOP',
        title: 'Infinite loop task',
        prompt: 'Non-converging repair loop',
        category: 'loop',
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

  describe('MUT-03: Leak Detection Pre-flight in Coding Task', () => {
    it('halts coding task at pre-flight when forbidden token is present', () => {
      const manager = new AgentLoopManager();
      const leakTask: CodingTaskFixture = {
        id: 'TSK-LEAK',
        title: 'Leaking task',
        prompt: 'Include AWS_SECRET_ACCESS_KEY in code',
        category: 'security',
        costEstimate: 50000,
        expected: 'LEAK_ATTEMPT_DETECTED',
        expectedLoopCount: 1,
      };

      const result = evaluateCodingTask(leakTask, manager);
      expect(result.observed).toBe('LEAK_ATTEMPT_DETECTED');
      expect(result.verdict).toBe('PASS');
      expect(result.violation).toContain('AWS_SECRET_ACCESS_KEY');
    });
  });
});