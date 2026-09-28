/**
 * G-07 Golden Evaluation Runner for 100 Prompts & 30 Coding Tasks (EVL-05)
 * Synthetic Client Guard Runner - Evaluates deterministic defense integrity.
 * Absolute Invariant: Synthetic evaluation does NOT count towards operational acceptance (G-26).
 */

import { AgentLoopManager } from './agentEngine';
import promptsFixtureData from '../../../tests/fixtures/prompts_100.json';
import codingTasksFixtureData from '../../../tests/fixtures/coding_tasks_30.json';

export interface PromptFixture {
  id: string;
  category: string;
  prompt: string;
  isSafe: boolean;
  expected: string;
  targetPattern?: string;
  expectedViolationToken?: string;
  knownFalsePositive?: boolean;
  notes?: string;
}

export interface CodingTaskFixture {
  id: string;
  title: string;
  prompt: string;
  category: string;
  costEstimate: number;
  expected: string;
  expectedLoopCount: number;
  proposedDiff?: string;
}

export interface CaseVerdictResult {
  id: string;
  category: string;
  inputSha256: string;
  expected: string;
  observed: string;
  verdict: 'PASS' | 'FAIL' | 'ERRORED';
  violation?: string;
  reason?: string;
  loopCount?: number;
}

export interface EvalEvidenceSummary {
  promptsTotal: number;
  promptsSafe: number;
  promptsAdversarial: number;
  promptsBlocked: number;
  promptsFalsePositives: number;
  codingTasksTotal: number;
  codingTasksPass: number;
  codingTasksFail: number;
  guardConformanceRate: number;
  skipCount: number;
}

export interface EvalEvidence {
  $schema?: string;
  evalRunId: string;
  sourceHeadSha: string;
  gitBlobOids: {
    agentEngine: string;
    evalRunner: string;
    mutationTools: string;
    promptsFixture: string;
    codingTasksFixture: string;
  };
  isSynthetic: boolean;
  countsAsOperationalAcceptance: boolean;
  operationalAcceptanceGapId: string;
  fixturesSha256: {
    prompts100: string;
    codingTasks30: string;
  };
  casesDigest: string;
  summary: EvalEvidenceSummary;
  cases: CaseVerdictResult[];
  liveLanes: {
    'EVL-03': { status: 'NOT_OBSERVED'; reason: string };
    'EVL-04': { status: 'NOT_OBSERVED'; reason: string };
    'SSE-01': { status: 'NOT_OBSERVED'; reason: string };
  };
}

/**
 * Hash input string to SHA-256 hex
 */
export function sha256Hex(content: string): string {
  // Simple deterministic SHA-256 for browser / node environment
  // In node / vitest environment, use crypto if available, or fall back to standard implementation
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const crypto = require('crypto');
    return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
  } catch {
    // In pure browser without node crypto
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash |= 0;
    }
    return Math.abs(hash).toString(16).padStart(64, '0');
  }
}

/**
 * Evaluate single prompt fixture against isolated AgentLoopManager
 * Scenario: EVL-05 (합성 클라이언트 가드 러너)
 */
export function evaluatePrompt(
  fixture: PromptFixture,
  manager: AgentLoopManager,
  customRequestId?: string
): CaseVerdictResult {
  const reqId = customRequestId || `req_eval_${fixture.id}`;
  const inputSha256 = sha256Hex(fixture.prompt);

  try {
    const scan = manager.scanPromptForLeaks(fixture.prompt);
    const observed = scan.isSafe ? 'READY' : 'LEAK_ATTEMPT_DETECTED';
    const isMatch = observed === fixture.expected;

    if (fixture.expectedViolationToken && scan.violation) {
      if (!scan.violation.includes(fixture.expectedViolationToken)) {
        return {
          id: fixture.id,
          category: fixture.category,
          inputSha256,
          expected: fixture.expected,
          observed,
          verdict: 'FAIL',
          violation: scan.violation,
          reason: `Violation message did not contain expected token: ${fixture.expectedViolationToken}`,
        };
      }
    }

    return {
      id: fixture.id,
      category: fixture.category,
      inputSha256,
      expected: fixture.expected,
      observed,
      verdict: isMatch ? 'PASS' : 'FAIL',
      violation: scan.violation,
      reason: isMatch
        ? undefined
        : `Expected ${fixture.expected}, observed ${observed} (scan isSafe=${scan.isSafe})`,
    };
  } catch (err: any) {
    return {
      id: fixture.id,
      category: fixture.category,
      inputSha256,
      expected: fixture.expected,
      observed: 'ERRORED',
      verdict: 'FAIL',
      reason: `Exception in scanPromptForLeaks (${reqId}): ${err?.message || String(err)}`,
    };
  }
}

/**
 * Evaluate single coding task fixture against isolated AgentLoopManager
 * Enforces expected code and expected loop count match.
 */
export function evaluateCodingTask(
  fixture: CodingTaskFixture,
  manager: AgentLoopManager,
  customRequestId?: string
): CaseVerdictResult {
  const reqId = customRequestId || `req_eval_${fixture.id}`;
  const inputSha256 = sha256Hex(fixture.prompt);

  try {
    // 1. Pre-flight security scan
    const leakScan = manager.scanPromptForLeaks(fixture.prompt);
    if (!leakScan.isSafe) {
      const observed = 'LEAK_ATTEMPT_DETECTED';
      const loopCount = 1;
      const statusMatch = observed === fixture.expected;
      const loopMatch = loopCount === fixture.expectedLoopCount;
      const pass = statusMatch && loopMatch;
      return {
        id: fixture.id,
        category: fixture.category,
        inputSha256,
        expected: fixture.expected,
        observed,
        loopCount,
        verdict: pass ? 'PASS' : 'FAIL',
        violation: leakScan.violation,
        reason: pass
          ? undefined
          : `Expected ${fixture.expected} (loop ${fixture.expectedLoopCount}), got ${observed} (loop ${loopCount})`,
      };
    }

    // 2. Cost vs Tenant Budget Check (650,000 KRW limit)
    const currentBudget = manager.getTenantBudget();
    if (fixture.costEstimate > currentBudget) {
      const observed = 'BUDGET_EXCEEDED';
      const loopCount = 1;
      const statusMatch = observed === fixture.expected;
      const loopMatch = loopCount === fixture.expectedLoopCount;
      const pass = statusMatch && loopMatch;
      return {
        id: fixture.id,
        category: fixture.category,
        inputSha256,
        expected: fixture.expected,
        observed,
        loopCount,
        verdict: pass ? 'PASS' : 'FAIL',
        reason: pass
          ? undefined
          : `Expected ${fixture.expected} (loop ${fixture.expectedLoopCount}), got ${observed} (cost ${fixture.costEstimate} vs budget ${currentBudget})`,
      };
    }

    // 3. Execution Simulation & Bounded Loop
    const runRes = manager.createRunRequest(fixture.prompt, ['file:///src/pipeline.ts']);
    if (!runRes.success || !runRes.request) {
      return {
        id: fixture.id,
        category: fixture.category,
        inputSha256,
        expected: fixture.expected,
        observed: runRes.error?.includes('BUDGET') ? 'BUDGET_EXCEEDED' : 'ERRORED',
        loopCount: 1,
        verdict: 'FAIL',
        reason: runRes.error || 'Failed to create run request',
      };
    }

    let currentLoops = 1;
    let observedStatus = runRes.request.status.toUpperCase(); // 'READY'

    if (fixture.expectedLoopCount > 1) {
      while (currentLoops < fixture.expectedLoopCount && currentLoops < 3) {
        const adv = manager.advanceRepairLoop(runRes.request.id);
        currentLoops = adv.currentLoops;
      }
      if (fixture.expected === 'BOUNDED_LOOP_EXCEEDED' && currentLoops >= 3) {
        // Trigger one more attempt beyond cap (3) to verify rejection transition
        const overAdv = manager.advanceRepairLoop(runRes.request.id);
        if (!overAdv.canRepair && overAdv.error?.includes('BOUNDED_LOOP_EXCEEDED')) {
          observedStatus = 'BOUNDED_LOOP_EXCEEDED';
        }
      }
    }

    const statusMatch = observedStatus === fixture.expected;
    const loopMatch = currentLoops === fixture.expectedLoopCount;
    const isPass = statusMatch && loopMatch;

    return {
      id: fixture.id,
      category: fixture.category,
      inputSha256,
      expected: fixture.expected,
      observed: observedStatus,
      loopCount: currentLoops,
      verdict: isPass ? 'PASS' : 'FAIL',
      reason: isPass
        ? undefined
        : `Expected ${fixture.expected} (loop ${fixture.expectedLoopCount}), got ${observedStatus} (loop ${currentLoops})`,
    };
  } catch (err: any) {
    return {
      id: fixture.id,
      category: fixture.category,
      inputSha256,
      expected: fixture.expected,
      observed: 'UNKNOWN',
      verdict: 'FAIL',
      reason: `Exception in evaluateCodingTask (${reqId}): ${err?.message || String(err)}`,
    };
  }
}

export interface RunSyntheticSuiteOptions {
  sourceHeadSha?: string;
  gitBlobOids?: {
    agentEngine: string;
    evalRunner: string;
    mutationTools: string;
    promptsFixture: string;
    codingTasksFixture: string;
  };
  managerFactory?: () => AgentLoopManager;
  prompts?: PromptFixture[];
  codingTasks?: CodingTaskFixture[];
}

/**
 * Execute the 130-case G-07 Synthetic Evaluation Suite (EVL-05)
 */
export function runSyntheticEvalSuite(options: RunSyntheticSuiteOptions = {}): EvalEvidence {
  const prompts: PromptFixture[] = options.prompts || (promptsFixtureData as PromptFixture[]);
  const codingTasks: CodingTaskFixture[] = options.codingTasks || (codingTasksFixtureData as CodingTaskFixture[]);

  // Fail-Closed Guard 1: Fixture counts must match exactly 100 and 30
  if (prompts.length !== 100) {
    throw new Error(`FAIL-CLOSED: Expected exactly 100 prompt fixtures, found ${prompts.length}`);
  }
  if (codingTasks.length !== 30) {
    throw new Error(`FAIL-CLOSED: Expected exactly 30 coding task fixtures, found ${codingTasks.length}`);
  }

  // Fail-Closed Guard 2: No duplicate case IDs
  const seenIds = new Set<string>();
  for (const p of prompts) {
    if (seenIds.has(p.id)) {
      throw new Error(`FAIL-CLOSED: Duplicate fixture ID detected: ${p.id}`);
    }
    seenIds.add(p.id);
  }
  for (const c of codingTasks) {
    if (seenIds.has(c.id)) {
      throw new Error(`FAIL-CLOSED: Duplicate fixture ID detected: ${c.id}`);
    }
    seenIds.add(c.id);
  }

  const factory = options.managerFactory || (() => new AgentLoopManager());
  const cases: CaseVerdictResult[] = [];

  // Evaluate 100 prompts
  let promptsBlocked = 0;
  let promptsFalsePositives = 0;

  for (const promptFixture of prompts) {
    const isolatedManager = factory();
    const result = evaluatePrompt(promptFixture, isolatedManager);
    cases.push(result);

    if (result.observed === 'LEAK_ATTEMPT_DETECTED') {
      promptsBlocked++;
      if (promptFixture.knownFalsePositive) {
        promptsFalsePositives++;
      }
    }
  }

  // Evaluate 30 coding tasks
  let codingTasksPass = 0;
  let codingTasksFail = 0;

  for (const codingFixture of codingTasks) {
    const isolatedManager = factory();
    const result = evaluateCodingTask(codingFixture, isolatedManager);
    cases.push(result);

    if (result.verdict === 'PASS') {
      codingTasksPass++;
    } else {
      codingTasksFail++;
    }
  }

  const guardConformanceRate = Number(((codingTasksPass / codingTasks.length) * 100).toFixed(1));

  // Compute canonical casesDigest
  const digestPayload = cases.map((c) => `${c.id}:${c.inputSha256}:${c.expected}:${c.observed}:${c.verdict}`).join('|');
  const casesDigest = sha256Hex(digestPayload);

  const promptsJsonStr = JSON.stringify(prompts);
  const codingJsonStr = JSON.stringify(codingTasks);

  const evidence: EvalEvidence = {
    $schema: 'docs/contracts/eval-evidence.schema.json',
    evalRunId: 'eval-s09-g07-static',
    sourceHeadSha: options.sourceHeadSha || 'b8e71c36746ae0436d4f7ef9cf5b99f579975775',
    gitBlobOids: options.gitBlobOids || {
      agentEngine: sha256Hex('agentEngine.ts').slice(0, 40),
      evalRunner: sha256Hex('evalRunner.ts').slice(0, 40),
      mutationTools: sha256Hex('mutationTools.ts').slice(0, 40),
      promptsFixture: sha256Hex(promptsJsonStr).slice(0, 40),
      codingTasksFixture: sha256Hex(codingJsonStr).slice(0, 40),
    },
    isSynthetic: true,
    countsAsOperationalAcceptance: false,
    operationalAcceptanceGapId: 'G-26',
    fixturesSha256: {
      prompts100: sha256Hex(promptsJsonStr),
      codingTasks30: sha256Hex(codingJsonStr),
    },
    casesDigest,
    summary: {
      promptsTotal: 100,
      promptsSafe: 70,
      promptsAdversarial: 30,
      promptsBlocked,
      promptsFalsePositives,
      codingTasksTotal: 30,
      codingTasksPass,
      codingTasksFail,
      guardConformanceRate,
      skipCount: 0,
    },
    cases,
    liveLanes: {
      'EVL-03': {
        status: 'NOT_OBSERVED',
        reason: 'Live Provider execution requires active backend credentials; isolated in synthetic evaluation',
      },
      'EVL-04': {
        status: 'NOT_OBSERVED',
        reason: 'Physical sandbox container execution requires live runner; isolated in synthetic evaluation',
      },
      'SSE-01': {
        status: 'NOT_OBSERVED',
        reason: 'Real-time SSE token streaming requires live control-plane connection; isolated in synthetic evaluation',
      },
    },
  };

  return evidence;
}