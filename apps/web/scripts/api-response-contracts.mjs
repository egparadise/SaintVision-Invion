import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compileFromFile } from 'json-schema-to-typescript';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, '../../..');
const contracts = [
  {
    schema: 'discovery-candidates-response',
    output: 'discovery-candidates-response',
  },
  {
    schema: 'contribution-page-response',
    output: 'contribution-page-response',
  },
  {
    schema: 'data-location-page-response',
    output: 'data-location-page-response',
  },
  {
    schema: 'project-workspaces-response',
    output: 'project-workspaces-response',
  },
  {
    schema: 'workspace-summary-response',
    output: 'workspace-summary-response',
  },
  {
    schema: 'execution-readiness-check-response',
    output: 'execution-readiness-check-response',
  },
  {
    schema: 'workspace-execution-readiness-response',
    output: 'workspace-execution-readiness-response',
  },
];
const mode = process.argv[2];

if (!['--check', '--write'].includes(mode) || process.argv.length !== 3) {
  process.stderr.write('Usage: node scripts/api-response-contracts.mjs (--check|--write)\n');
  process.exit(2);
}

const drift = [];
for (const contract of contracts) {
  const schemaPath = resolve(repoRoot, `contracts/${contract.schema}.schema.json`);
  const outputPath = resolve(repoRoot, `apps/web/src/contracts/${contract.output}.ts`);
  const generated = await compileFromFile(schemaPath, {
    bannerComment: `/* Generated from contracts/${contract.schema}.schema.json. Do not edit by hand. */`,
    style: { singleQuote: true, semi: true },
  });

  if (mode === '--write') {
    await writeFile(outputPath, generated, 'utf8');
    process.stdout.write(`WROTE: ${outputPath}\n`);
    continue;
  }

  let current;
  try {
    current = await readFile(outputPath, 'utf8');
  } catch {
    current = undefined;
  }
  if (current !== generated) drift.push(contract.output);
}

if (mode === '--write') process.exit(0);
if (drift.length) {
  process.stderr.write(`FAIL: stale generated API response type(s): ${drift.join(', ')}. Run npm run contracts:generate.\n`);
  process.exit(1);
}
process.stdout.write(`PASS: ${contracts.length} API response TypeScript types match their JSON Schemas.\n`);
