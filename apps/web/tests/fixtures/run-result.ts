import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ArtifactContentResponse, RunResultView, RunArtifactList } from '../../../../packages/contracts-ts/src';

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

const resultPath = getFixturePath('../../../../contracts/fixtures/run-result-view.json');
export const runResultViewFixture = JSON.parse(readFileSync(resultPath, 'utf8')) as RunResultView;

const artifactListPath = getFixturePath('../../../../contracts/fixtures/run-artifact-list.json');
export const runArtifactListFixture = JSON.parse(readFileSync(artifactListPath, 'utf8')) as RunArtifactList;

const artifactContentPath = getFixturePath('../../../../contracts/fixtures/artifact-content-response.json');
export const artifactContentResponseFixture = JSON.parse(readFileSync(artifactContentPath, 'utf8')) as ArtifactContentResponse;
