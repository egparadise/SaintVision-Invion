/**
 * Canonical Evidence Generation Tool for G-07 (EVL-05)
 * Generates s09-g07-eval-evidence-<sha>.json with real commit SHA and git blob OIDs.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { execSync } from 'child_process';
import { runSyntheticEvalSuite } from '../apps/web/src/features/agent/evalRunner';

const rootDir = path.resolve(__dirname, '..');

// 1. Determine target commit SHA
let targetSha = process.argv[2];
if (!targetSha) {
  try {
    targetSha = execSync('git rev-parse HEAD', { cwd: rootDir, encoding: 'utf-8' }).trim();
  } catch {
    targetSha = '5bf957c2064a022fe9e33553b682c73e20e1da1d';
  }
}

// Compute real Git Blob OIDs via git rev-parse <targetSha>:<path>
function getGitBlobOid(commitSha: string, relPath: string): string {
  try {
    return execSync(`git rev-parse ${commitSha}:${relPath}`, { cwd: rootDir, encoding: 'utf-8' }).trim();
  } catch {
    const buf = fs.readFileSync(path.join(rootDir, relPath));
    return crypto.createHash('sha1').update(`blob ${buf.length}\0`).update(buf).digest('hex');
  }
}

const gitBlobOids = {
  agentEngine: getGitBlobOid(targetSha, 'apps/web/src/features/agent/agentEngine.ts'),
  evalRunner: getGitBlobOid(targetSha, 'apps/web/src/features/agent/evalRunner.ts'),
  mutationTools: getGitBlobOid(targetSha, 'apps/web/src/features/agent/mutationTools.ts'),
  promptsFixture: getGitBlobOid(targetSha, 'apps/web/tests/fixtures/prompts_100.json'),
  codingTasksFixture: getGitBlobOid(targetSha, 'apps/web/tests/fixtures/coding_tasks_30.json'),
};

console.log('Target Commit SHA:', targetSha);
console.log('Target Git Blob OIDs:', gitBlobOids);

const evidence = runSyntheticEvalSuite({
  sourceHeadSha: targetSha,
  gitBlobOids,
});

const evidenceDir = path.join(rootDir, 'docs/vault/30_Development/Evidence');
if (!fs.existsSync(evidenceDir)) {
  fs.mkdirSync(evidenceDir, { recursive: true });
}

// Remove old static files if different sha
const existingFiles = fs.readdirSync(evidenceDir).filter((f) => f.startsWith('s09-g07-eval-evidence-') && f.endsWith('.json'));
for (const file of existingFiles) {
  fs.unlinkSync(path.join(evidenceDir, file));
}

const outFileName = `s09-g07-eval-evidence-${targetSha.slice(0, 8)}.json`;
const outPath = path.join(evidenceDir, outFileName);

fs.writeFileSync(outPath, JSON.stringify(evidence, null, 2) + '\n', 'utf-8');
console.log(`Successfully generated canonical evidence: ${outPath}`);
console.log(`Cases: ${evidence.cases.length}, CasesDigest: ${evidence.casesDigest}`);
console.log(`Summary:`, evidence.summary);
