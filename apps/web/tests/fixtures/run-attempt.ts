import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { RunAttemptList } from '@/contracts/types';

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

const attemptPath = getFixturePath('../../../../contracts/fixtures/run-attempt-list.json');
export const runAttemptListFixture = JSON.parse(readFileSync(attemptPath, 'utf8')) as RunAttemptList;
