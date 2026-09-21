import { readFileSync } from 'node:fs';
import type { ContributionPageResponse } from '../../src/contracts/contribution-page-response';
import type { DataLocationPageResponse } from '../../src/contracts/data-location-page-response';

function fixture<T>(filename: string): T {
  const url = new URL(`../../../../contracts/fixtures/${filename}`, import.meta.url);
  return JSON.parse(readFileSync(url, 'utf8')) as T;
}

export const storageContributionsFixture = fixture<ContributionPageResponse>(
  'storage-contributions-response.json',
);
export const storageLocationsFixture = fixture<DataLocationPageResponse>(
  'storage-locations-response.json',
);
