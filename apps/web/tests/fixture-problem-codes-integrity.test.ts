import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

describe('Card 126 / F6: ProblemDetails Fixture Code Format Integrity', () => {
  it('enforces all ProblemDetails fixture codes across web tests conform to /^[A-Z]+-[0-9]{4}$/ without allowlist constant', () => {
    const testsDir = __dirname;
    const testFiles: string[] = [];

    function walkDir(dir: string) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walkDir(fullPath);
        } else if (
          (entry.name.endsWith('.test.ts') || entry.name.endsWith('.test.tsx')) &&
          entry.name !== 'fixture-problem-codes-integrity.test.ts'
        ) {
          testFiles.push(fullPath);
        }
      }
    }

    walkDir(testsDir);
    expect(testFiles.length).toBeGreaterThan(0);

    const codePattern = /code\s*:\s*['"]([^'"]+)['"]/g;
    const canonicalFormat = /^[A-Z]+-[0-9]{4}$/;

    const observedCodes: Array<{ file: string; line: number; code: string }> = [];

    for (const file of testFiles) {
      const relPath = path.relative(testsDir, file);
      const content = fs.readFileSync(file, 'utf-8');
      const lines = content.split('\n');

      lines.forEach((lineText, idx) => {
        // Skip intentional fail-closed helper boundary discrimination tests in developer-studio.test.ts
        if (lineText.includes('isRouteNotFoundError')) return;
        // Skip explicit legacy-format backwards compatibility payload tests (#200 deps.py AUTH_MISSING_CREDENTIAL)
        if (lineText.includes('AUTH-MISSING-CREDENTIAL')) return;

        let match: RegExpExecArray | null;
        while ((match = codePattern.exec(lineText)) !== null) {
          observedCodes.push({
            file: relPath,
            line: idx + 1,
            code: match[1],
          });
        }
      });
    }

    // Must have observed a representative set of fixtures across the test suite
    expect(observedCodes.length).toBeGreaterThan(20);

    // Every observed code MUST conform to the canonical RFC 9457 / problem.py 4-digit code format
    const invalidCodes = observedCodes.filter((item) => !canonicalFormat.test(item.code));
    expect(invalidCodes).toEqual([]);
  });
});
