import { readFileSync } from 'node:fs';
import type { ApprovalChallenge } from '../../../../packages/contracts-ts/src';

const source = new URL('../../../../contracts/fixtures/approval-challenge-response.json', import.meta.url);
export const approvalChallengeFixture = JSON.parse(readFileSync(source, 'utf8')) as ApprovalChallenge;
