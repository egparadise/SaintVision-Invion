import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createContext, runInContext, SourceTextModule } from 'node:vm';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';
import { checkedNodeCertificateObservation } from '../src/shared/api/nodeCertificateObservation';

const webRoot = fileURLToPath(new URL('..', import.meta.url));
const generated = join(webRoot, 'src/contracts/node-certificate-validator.mjs');
const fixture = () => JSON.parse(readFileSync(new URL('../../../contracts/fixtures/project-node-certificate-observation-response.json', import.meta.url), 'utf8'));
const now = Date.parse('2026-11-04T04:00:00+00:00');

// Parse/link/evaluate the actual ESM in one realm with string/Wasm generation
// disabled. Any residual external dependency is an error, never a host require.
async function loadWithoutCodeGeneration() {
  const context = createContext({}, { codeGeneration: { strings: false, wasm: false } });
  const module = new SourceTextModule(readFileSync(generated, 'utf8'), { context, identifier: generated });
  await module.link(id => { throw new Error(`Unexpected validator dependency: ${id}`); });
  await module.evaluate();
  return { context, validate: (module.namespace as { default: (value: unknown) => boolean }).default };
}

describe('CR-CSP-01 canonical standalone validator', () => {
  it('imports and validates with string-code generation forbidden, including bundled format helpers', async () => {
    const { context, validate } = await loadWithoutCodeGeneration();
    expect(() => runInContext('new Function("return 1")()', context)).toThrow(/Code generation from strings disallowed/);
    expect(() => runInContext('eval("1")', context)).toThrow(/Code generation from strings disallowed/);
    expect(validate(fixture())).toBe(true);
    for (const field of ['observedAt', 'certificateNotAfter', 'earliestCertificateNotAfter', 'renewalWindowStartsAt']) {
      const value = fixture();
      const owner = field === 'certificateNotAfter' ? value.items[0]
        : field === 'observedAt' ? value : value.trust;
      // Date.parse accepts this non-RFC3339 date. Canonical Ajv date-time MUST reject it.
      owner[field] = 'November 4, 2026 04:00:00 GMT';
      expect(validate(value), field).toBe(false);
    }
    const invalid = fixture();
    invalid.items[0].nodeId = 'nod_invalid';
    expect(validate(invalid)).toBe(false);
    invalid.items = Array.from({ length: 201 }, () => fixture().items[0]);
    expect(validate(invalid)).toBe(false);
  });

  it('has a real default ESM export and loads natively without CommonJS globals or external imports', () => {
    const code = readFileSync(generated, 'utf8');
    const source = ts.createSourceFile(generated, code, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
    const commonJS: string[] = [];
    const visit = (node: ts.Node) => {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'require') commonJS.push('require()');
      if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression) &&
          node.expression.text === 'module' && node.name.text === 'exports') commonJS.push('module.exports');
      if (ts.isElementAccessExpression(node) && ts.isIdentifier(node.expression) &&
          node.expression.text === 'module' && ts.isStringLiteral(node.argumentExpression) &&
          node.argumentExpression.text === 'exports') commonJS.push('module[exports]');
      ts.forEachChild(node, visit);
    };
    visit(source);
    expect(commonJS).toEqual([]);
    const nativeImport = spawnSync(process.execPath, ['--input-type=module', '-e',
      `import { readFileSync } from 'node:fs';
       const module = await import(${JSON.stringify(pathToFileURL(generated).href)});
       const fixture = JSON.parse(readFileSync(${JSON.stringify(fileURLToPath(new URL('../../../contracts/fixtures/project-node-certificate-observation-response.json', import.meta.url)))}, 'utf8'));
       if (typeof module.default !== 'function' || !module.default(fixture)) process.exit(1);`],
    { encoding: 'utf8' });
    expect(nativeImport.status, nativeImport.stderr).toBe(0);
  });

  it.each([
    ['extra property', (v: any) => { v.healthy = true; }],
    ['invalid project ID format', (v: any) => { v.projectId = 'bad'; }],
    ['invalid node ID format', (v: any) => { v.items[0].nodeId = 'bad'; }],
    ['invalid observedAt format', (v: any) => { v.observedAt = 'November 4, 2026 04:00:00 GMT'; }],
    ['invalid certificate date', (v: any) => { v.items[0].certificateNotAfter = '2026-11-31T04:00:00Z'; }],
    ['non-boolean channel', (v: any) => { v.items[0].channelEnabled = 'true'; }],
    ['unknown trust enum', (v: any) => { v.trust.state = 'healthy'; }],
    ['fractional seconds summary', (v: any) => { v.trust.secondsUntilEarliestExpiry = 604800.5; }],
    ['false trust summary', (v: any) => { v.trust.secondsUntilEarliestExpiry -= 1; }],
    ['false renewal window', (v: any) => { v.trust.renewalWindowStartsAt = v.observedAt; }],
    ['microsecond precision overflow', (v: any) => { v.items[0].certificateNotAfter = '2026-11-11T04:00:00.0000001Z'; }],
  ])('preserves wire/semantic rejection: %s', (_label, mutate) => {
    const value = fixture();
    mutate(value);
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now)).toThrow();
  });

  it('retains project binding, freshness and incomplete/disabled trust rejection', () => {
    const value = fixture();
    expect(() => checkedNodeCertificateObservation(value, 'another-project', now)).toThrow();
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now + 60001)).toThrow();
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now - 5001)).toThrow();
    value.complete = false;
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now)).toThrow();
    value.complete = true;
    value.items[0].channelEnabled = false;
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now)).toThrow();
  });

  it('generates deterministic canonical output and detects missing/tampered output and manifest drift', () => {
    const directory = mkdtempSync(join(tmpdir(), 'sv-validator-drift-'));
    const run = (mode: string) => spawnSync(process.execPath,
      ['scripts/node-certificate-validator.mjs', mode, directory], { cwd: webRoot, encoding: 'utf8' });
    try {
      expect(run('--check').status).toBe(1);
      expect(run('--write').status).toBe(0);
      const path = join(directory, 'node-certificate-validator.mjs');
      const manifestPath = join(directory, 'node-certificate-validator.manifest.json');
      const first = readFileSync(path);
      const manifest = readFileSync(manifestPath, 'utf8');
      expect(first.equals(readFileSync(generated))).toBe(true);
      const metadata = JSON.parse(manifest);
      expect(metadata.format).toBe('esm');
      expect(metadata.selfContained).toBe(true);
      const schemaBytes = readFileSync(new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url));
      expect(metadata.schemaSHA256).toBe(createHash('sha256').update(schemaBytes).digest('hex'));
      expect(run('--check').status).toBe(0);
      writeFileSync(path, first + '\n// stale');
      expect(run('--check').status).toBe(1);
      writeFileSync(path, first);
      writeFileSync(manifestPath, manifest + '\n');
      expect(run('--check').status).toBe(1);
      expect(run('--write').status).toBe(0);
      expect(readFileSync(path).equals(first)).toBe(true);
      expect(readFileSync(manifestPath, 'utf8')).toBe(manifest);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
