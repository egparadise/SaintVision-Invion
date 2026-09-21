import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ApprovalReviewView } from '../../../../packages/contracts-ts/src';

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

const source = getFixturePath('../../../../contracts/fixtures/approval-review-response.json');
export const approvalReviewFixture = JSON.parse(readFileSync(source, 'utf8')) as ApprovalReviewView;
