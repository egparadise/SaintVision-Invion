import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compileFromFile } from 'json-schema-to-typescript';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, '../../..');
const schemaPath = resolve(repoRoot, 'contracts/discovery-candidates-response.schema.json');
const outputPath = resolve(repoRoot, 'apps/web/src/contracts/discovery-candidates-response.ts');
const mode = process.argv[2];

if (!['--check', '--write'].includes(mode) || process.argv.length !== 3) {
  process.stderr.write('Usage: node scripts/discovery-contracts.mjs (--check|--write)\n');
  process.exit(2);
}

const generated = await compileFromFile(schemaPath, {
  bannerComment: '/* Generated from contracts/discovery-candidates-response.schema.json. Do not edit by hand. */',
  style: { singleQuote: true, semi: true },
});

if (mode === '--write') {
  await writeFile(outputPath, generated, 'utf8');
  process.stdout.write(`WROTE: ${outputPath}\n`);
  process.exit(0);
}

let current;
try {
  current = await readFile(outputPath, 'utf8');
} catch {
  current = undefined;
}
if (current !== generated) {
  process.stderr.write('FAIL: generated discovery response type is stale. Run npm run contracts:generate.\n');
  process.exit(1);
}
process.stdout.write('PASS: discovery response TypeScript type matches the JSON Schema.\n');
