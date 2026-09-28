/**
 * G-07 Golden Evaluation Runner for 100 Prompts & 30 Coding Tasks (EVL-05)
 * Synthetic Client Guard Runner - Evaluates deterministic defense integrity.
 * Absolute Invariant: Synthetic evaluation does NOT count towards operational acceptance (G-26).
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { AgentLoopManager } from './agentEngine';

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
  inputText: string;
  inputSha256: string;
  expected: string;
  observed: string;
  verdict: 'PASS' | 'FAIL' | 'ERRORED' | 'KNOWN_FALSE_POSITIVE';
  violation?: string;
  reason?: string;
  loopCount?: number;
}

export interface EvalEvidenceSummary {
  promptsTotal: number;
  promptsSafe: number;
  promptsAdversarial: number;
  promptsPass: number;
  promptsFail: number;
  promptsKnownFalsePositive: number;
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
  metrics: {
    outputLeakage: { status: 'NOT_OBSERVED'; reason: string };
  };
  liveLanes: {
    'EVL-03': { status: 'NOT_OBSERVED'; reason: string };
    'EVL-04': { status: 'NOT_OBSERVED'; reason: string };
    'SSE-01': { status: 'NOT_OBSERVED'; reason: string };
  };
}

export const EXPECTED_FIXTURE_BYTE_SHA256 = {
  prompts100: 'f8962fdaaac27303d0ea3631a84f6e49a21008f6e9cc1b24d0806a73a47364b2',
  codingTasks30: '549710ce589c37533e727d6f5d69242cff080668ff6652281e38c8151b3dbdb9',
};

export const ALLOWED_PROMPT_CATEGORIES = new Set([
  'angiography', 'artifact_removal', 'audit', 'cardiology', 'compliance', 'compression', 'coronary',
  'densitometry', 'detection', 'dicom_pipeline', 'dicom_scu', 'diffusion', 'echocardiography',
  'endocrinology', 'feature_extraction', 'file_validation', 'filtering', 'governance', 'hemodynamics',
  'image_processing', 'indexing', 'interpolation', 'jailbreak', 'leak_api_keys', 'leak_aws', 'leak_key',
  'leak_probe_api_keys', 'leak_probe_aws', 'leak_probe_jailbreak', 'leak_probe_key', 'leak_probe_openai',
  'leak_probe_shadow', 'leak_shadow', 'leak_token', 'meshing', 'morphometry', 'multimodal', 'navigation',
  'nephrology', 'neuro', 'neuroimaging', 'neurology', 'nuclear', 'obstetrics', 'oncology', 'ophthalmology',
  'orthopedics', 'pacs_sync', 'parsing', 'perfusion', 'planning', 'privacy', 'pulmonology', 'radiotherapy',
  'reconstruction', 'registration', 'rendering', 'reporting', 'rheumatology', 'security', 'segmentation',
  'spectral_ct', 'steatosis', 'stroke', 'synthesis', 'texture', 'thoracic', 'tissue_segmentation',
  'tracking', 'trauma', 'triage', 'vascular', 'viewing', 'visualization', 'volumetry', 'worklist',
]);

export const ALLOWED_CODING_CATEGORIES = new Set([
  'analysis', 'bounded_loop', 'dicom', 'frame', 'geometry', 'heavy_compute', 'image', 'lut',
  'ortho', 'parsing', 'query', 'radiotherapy', 'rendering', 'security', 'security_leak',
  'statistics', 'validation', 'viewer',
]);

export const ALLOWED_EXPECTED_STATUSES = new Set([
  'READY', 'REPAIRING', 'BOUNDED_LOOP_EXCEEDED', 'BUDGET_EXCEEDED', 'LEAK_ATTEMPT_DETECTED',
]);

/**
 * Hash input string or buffer to SHA-256 hex (Fail-closed)
 */
export function sha256Hex(content: string | Buffer): string {
  if (typeof crypto !== 'undefined' && crypto.createHash) {
    return crypto.createHash('sha256').update(content).digest('hex');
  }
  throw new Error('FAIL-CLOSED: crypto.createHash is unavailable');
}

/**
 * Compute real Git Blob OID: sha1("blob <len>\0" + buffer)
 */
export function computeGitBlobOid(buf: Buffer): string {
  if (typeof crypto !== 'undefined' && crypto.createHash) {
    return crypto.createHash('sha1').update(`blob ${buf.length}\0`).update(buf).digest('hex');
  }
  throw new Error('FAIL-CLOSED: crypto is unavailable for gitBlobOid calculation');
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

    if (fixture.expectedViolationToken && scan.violation) {
      const normViolation = scan.violation.replace(/\\/g, '');
      const normToken = fixture.expectedViolationToken.replace(/\\/g, '');
      const tokenMatches = scan.violation.includes(fixture.expectedViolationToken) || normViolation.includes(normToken);
      if (!tokenMatches) {
        return {
          id: fixture.id,
          category: fixture.category,
          inputText: fixture.prompt,
          inputSha256,
          expected: fixture.expected,
          observed,
          verdict: 'FAIL',
          violation: scan.violation,
          reason: `Violation message did not contain expected token: ${fixture.expectedViolationToken}`,
        };
      }
    }

    if (fixture.knownFalsePositive && fixture.isSafe && observed === 'LEAK_ATTEMPT_DETECTED') {
      return {
        id: fixture.id,
        category: fixture.category,
        inputText: fixture.prompt,
        inputSha256,
        expected: fixture.expected,
        observed,
        verdict: 'KNOWN_FALSE_POSITIVE',
        violation: scan.violation,
        reason: 'Known false positive: benign medical imaging prompt triggers unanchored firewall filter',
      };
    }

    const isMatch = observed === fixture.expected;
    return {
      id: fixture.id,
      category: fixture.category,
      inputText: fixture.prompt,
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
      inputText: fixture.prompt,
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
    // 1. Pass fixture.costEstimate directly so engine budget check (agentEngine.ts:71) evaluates exact fixture cost
    const contextFiles = ['file:///src/pipeline.ts'];
    const runRes = manager.createRunRequest(fixture.prompt, contextFiles, fixture.costEstimate);
    if (!runRes.success || !runRes.request) {
      const isBudget = runRes.error?.includes('BUDGET_EXCEEDED');
      const isLeak = runRes.error?.includes('LEAK_ATTEMPT_DETECTED');
      const observed = isBudget ? 'BUDGET_EXCEEDED' : isLeak ? 'LEAK_ATTEMPT_DETECTED' : 'ERRORED';
      const statusMatch = observed === fixture.expected;
      const loopMatch = 1 === fixture.expectedLoopCount;
      const pass = statusMatch && loopMatch;
      return {
        id: fixture.id,
        category: fixture.category,
        inputText: fixture.prompt,
        inputSha256,
        expected: fixture.expected,
        observed,
        loopCount: 1,
        verdict: pass ? 'PASS' : 'FAIL',
        violation: isLeak ? runRes.error : undefined,
        reason: pass ? undefined : (runRes.error || 'Failed to create run request'),
      };
    }

    let currentLoops = 1;
    let observedStatus = runRes.request.status.toUpperCase(); // 'READY'

    // 2. Advance repair loop with Fail-Closed boundary termination (F5)
    if (fixture.expectedLoopCount > 1) {
      let iterations = 0;
      while (currentLoops < fixture.expectedLoopCount && currentLoops < 3 && iterations++ < 10) {
        const adv = manager.advanceRepairLoop(runRes.request.id);
        if (!adv.canRepair || adv.currentLoops <= currentLoops) {
          if (adv.error && !adv.error.includes('BOUNDED_LOOP_EXCEEDED')) {
            observedStatus = 'ERRORED';
          } else {
            observedStatus = 'BOUNDED_LOOP_EXCEEDED';
          }
          currentLoops = adv.currentLoops;
          break;
        }
        currentLoops = adv.currentLoops;
        observedStatus = runRes.request.status.toUpperCase();
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
      inputText: fixture.prompt,
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
      inputText: fixture.prompt,
      inputSha256,
      expected: fixture.expected,
      observed: 'ERRORED',
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
  promptsByteSha256?: string;
  codingTasksByteSha256?: string;
}

/**
 * Execute the 130-case G-07 Synthetic Evaluation Suite (EVL-05)
 */
export function runSyntheticEvalSuite(options: RunSyntheticSuiteOptions = {}): EvalEvidence {
  let prompts: PromptFixture[];
  let promptsByteSha: string;
  if (options.prompts) {
    prompts = options.prompts;
    promptsByteSha = options.promptsByteSha256 || EXPECTED_FIXTURE_BYTE_SHA256.prompts100;
  } else {
    const pPath = path.resolve(__dirname, '../../../tests/fixtures/prompts_100.json');
    if (!fs.existsSync(pPath)) {
      throw new Error(`FAIL-CLOSED: Prompt fixture file not found: ${pPath}`);
    }
    try {
      const raw = fs.readFileSync(pPath, 'utf-8').replace(/\r\n/g, '\n');
      promptsByteSha = options.promptsByteSha256 || sha256Hex(raw);
      prompts = JSON.parse(raw) as PromptFixture[];
    } catch (err) {
      throw new Error(`FAIL-CLOSED: Failed to read or parse prompt fixture file: ${(err as Error).message}`);
    }
  }

  let codingTasks: CodingTaskFixture[];
  let codingByteSha: string;
  if (options.codingTasks) {
    codingTasks = options.codingTasks;
    codingByteSha = options.codingTasksByteSha256 || EXPECTED_FIXTURE_BYTE_SHA256.codingTasks30;
  } else {
    const cPath = path.resolve(__dirname, '../../../tests/fixtures/coding_tasks_30.json');
    if (!fs.existsSync(cPath)) {
      throw new Error(`FAIL-CLOSED: Coding tasks fixture file not found: ${cPath}`);
    }
    try {
      const raw = fs.readFileSync(cPath, 'utf-8').replace(/\r\n/g, '\n');
      codingByteSha = options.codingTasksByteSha256 || sha256Hex(raw);
      codingTasks = JSON.parse(raw) as CodingTaskFixture[];
    } catch (err) {
      throw new Error(`FAIL-CLOSED: Failed to read or parse coding tasks fixture file: ${(err as Error).message}`);
    }
  }

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

  // Fail-Closed Guard 3: Fixture Byte SHA256 integrity seal (F3)
  if (promptsByteSha !== EXPECTED_FIXTURE_BYTE_SHA256.prompts100) {
    throw new Error(
      `FAIL-CLOSED: Fixture byte SHA-256 mismatch for prompts_100.json (expected ${EXPECTED_FIXTURE_BYTE_SHA256.prompts100}, got ${promptsByteSha})`
    );
  }
  if (codingByteSha !== EXPECTED_FIXTURE_BYTE_SHA256.codingTasks30) {
    throw new Error(
      `FAIL-CLOSED: Fixture byte SHA-256 mismatch for coding_tasks_30.json (expected ${EXPECTED_FIXTURE_BYTE_SHA256.codingTasks30}, got ${codingByteSha})`
    );
  }

  // Fail-Closed Guard 4: Category and Expected Whitelists (F3)
  for (const p of prompts) {
    if (!ALLOWED_PROMPT_CATEGORIES.has(p.category)) {
      throw new Error(`FAIL-CLOSED: Unrecognized prompt category: ${p.category} in ${p.id}`);
    }
    if (!ALLOWED_EXPECTED_STATUSES.has(p.expected)) {
      throw new Error(`FAIL-CLOSED: Unrecognized expected status: ${p.expected} in ${p.id}`);
    }
  }
  for (const c of codingTasks) {
    if (!ALLOWED_CODING_CATEGORIES.has(c.category)) {
      throw new Error(`FAIL-CLOSED: Unrecognized coding task category: ${c.category} in ${c.id}`);
    }
    if (!ALLOWED_EXPECTED_STATUSES.has(c.expected)) {
      throw new Error(`FAIL-CLOSED: Unrecognized expected status: ${c.expected} in ${c.id}`);
    }
  }

  const factory = options.managerFactory || (() => new AgentLoopManager());
  const cases: CaseVerdictResult[] = [];

  // Evaluate 100 prompts
  let promptsBlocked = 0;
  let promptsFalsePositives = 0;
  let promptsPass = 0;
  let promptsFail = 0;
  let promptsKnownFalsePositive = 0;

  for (const promptFixture of prompts) {
    const isolatedManager = factory();
    const result = evaluatePrompt(promptFixture, isolatedManager);
    cases.push(result);

    if (result.verdict === 'PASS') {
      promptsPass++;
    } else if (result.verdict === 'KNOWN_FALSE_POSITIVE') {
      promptsKnownFalsePositive++;
    } else {
      promptsFail++;
    }

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

  // Compute or obtain real Git Blob OIDs and sourceHeadSha (F1)
  const sourceHeadSha = options.sourceHeadSha || (() => {
    try {
      const { execSync } = require('child_process');
      return execSync('git rev-parse HEAD', { encoding: 'utf-8' }).trim();
    } catch (err) {
      throw new Error(`FAIL-CLOSED: sourceHeadSha must be provided or retrievable via git rev-parse HEAD: ${(err as Error).message}`);
    }
  })();

  const gitBlobOids = options.gitBlobOids || (() => {
    try {
      const { execSync } = require('child_process');
      return {
        agentEngine: execSync(`git rev-parse ${sourceHeadSha}:apps/web/src/features/agent/agentEngine.ts`, { encoding: 'utf-8' }).trim(),
        evalRunner: execSync(`git rev-parse ${sourceHeadSha}:apps/web/src/features/agent/evalRunner.ts`, { encoding: 'utf-8' }).trim(),
        mutationTools: execSync(`git rev-parse ${sourceHeadSha}:apps/web/src/features/agent/mutationTools.ts`, { encoding: 'utf-8' }).trim(),
        promptsFixture: execSync(`git rev-parse ${sourceHeadSha}:apps/web/tests/fixtures/prompts_100.json`, { encoding: 'utf-8' }).trim(),
        codingTasksFixture: execSync(`git rev-parse ${sourceHeadSha}:apps/web/tests/fixtures/coding_tasks_30.json`, { encoding: 'utf-8' }).trim(),
      };
    } catch (err) {
      throw new Error(`FAIL-CLOSED: Unable to resolve canonical gitBlobOids for commit ${sourceHeadSha}: ${(err as Error).message}`);
    }
  })();

  const evidence: EvalEvidence = {
    $schema: 'docs/contracts/eval-evidence.schema.json',
    evalRunId: 'eval-s09-g07-static',
    sourceHeadSha,
    gitBlobOids,
    isSynthetic: true,
    countsAsOperationalAcceptance: false,
    operationalAcceptanceGapId: 'G-26',
    fixturesSha256: {
      prompts100: promptsByteSha,
      codingTasks30: codingByteSha,
    },
    casesDigest,
    summary: {
      promptsTotal: 100,
      promptsSafe: prompts.filter((p) => p.isSafe).length,
      promptsAdversarial: prompts.filter((p) => !p.isSafe).length,
      promptsPass,
      promptsFail,
      promptsKnownFalsePositive,
      promptsBlocked,
      promptsFalsePositives,
      codingTasksTotal: 30,
      codingTasksPass,
      codingTasksFail,
      guardConformanceRate,
      skipCount: 0,
    },
    cases,
    metrics: {
      outputLeakage: {
        status: 'NOT_OBSERVED',
        reason: '실제 LLM completion 부재 (클라이언트 가드 시뮬레이션)',
      },
    },
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
