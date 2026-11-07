import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createContext, runInContext } from 'node:vm';
import { describe, expect, it } from 'vitest';
import { checkedNodeCertificateObservation } from '../src/shared/api/nodeCertificateObservation';

const webRoot = fileURLToPath(new URL('..', import.meta.url));
const generated = join(webRoot, 'src/contracts/node-certificate-validator.cjs');
const fixture = () => JSON.parse(readFileSync(new URL('../../../contracts/fixtures/project-node-certificate-observation-response.json', import.meta.url), 'utf8'));
const now = Date.parse('2026-11-04T04:00:00+00:00');

// Every JS dependency executes in the SAME realm with string and Wasm generation disabled.
// Supplying a host require would leave format/helper imports outside this regression's boundary.
function loadWithoutCodeGeneration() {
  const context = createContext({}, { codeGeneration: { strings: false, wasm: false } });
  const modules = new Map<string, { exports: any }>();
  const load = (filename: string): any => {
    if (modules.has(filename)) return modules.get(filename)!.exports;
    const module = { exports: {} };
    modules.set(filename, module);
    const require = (id: string) => {
      const resolved = createRequire(filename).resolve(id);
      if (!resolved.endsWith('.js') && !resolved.endsWith('.cjs')) throw new Error(`Unexpected validator dependency: ${id}`);
      return load(resolved);
    };
    const body = readFileSync(filename, 'utf8');
    const execute = runInContext(`(function(require,module,exports,__filename,__dirname){${body}\n})`, context, { filename });
    execute(require, module, module.exports, filename, dirname(filename));
    return module.exports;
  };
  return { context, validate: load(generated) as (value: unknown) => boolean };
}

describe('CR-CSP-01 canonical standalone validator', () => {
  it('imports and validates with string-code generation forbidden, including imported format helpers', () => {
    const { context, validate } = loadWithoutCodeGeneration();
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
      const path = join(directory, 'node-certificate-validator.cjs');
      const manifestPath = join(directory, 'node-certificate-validator.manifest.json');
      const first = readFileSync(path);
      const manifest = readFileSync(manifestPath, 'utf8');
      expect(first.equals(readFileSync(generated))).toBe(true);
      const metadata = JSON.parse(manifest);
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
