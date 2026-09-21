import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { RunLogView } from '../../../../packages/contracts-ts/src';

function getFixturePath(relativePath: string): string {
  try {
    if (typeof import.meta?.url === 'string' && import.meta.url.startsWith('file:')) {
      return fileURLToPath(new URL(relativePath, import.meta.url));
    }
  } catch {
    // Fall back to path resolution
  }
  const cleanRelative = relativePath.replace(/^(\.\.\/)+/, '');
  const candidateFromCwd = resolve(process.cwd(), cleanRelative);
  try {
    readFileSync(candidateFromCwd);
    return candidateFromCwd;
  } catch {
    return resolve(process.cwd(), '../..', cleanRelative);
  }
}

const logPath = getFixturePath('../../../../contracts/fixtures/run-log-view.json');
export const runLogViewFixture = JSON.parse(readFileSync(logPath, 'utf8')) as RunLogView;
