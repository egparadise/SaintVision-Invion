import { readFileSync } from 'node:fs';
import type { DiscoveryCandidatesResponse } from '../../src/contracts/discovery-candidates-response';

const source = new URL('../../../../contracts/fixtures/discovery-candidates-response.json', import.meta.url);
export const discoveryCandidatesFixture = JSON.parse(
  readFileSync(source, 'utf8'),
) as DiscoveryCandidatesResponse;
