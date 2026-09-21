import { readFileSync } from 'node:fs';
import type { ApprovalReviewView } from '../../../../packages/contracts-ts/src';

const source = new URL('../../../../contracts/fixtures/approval-review-response.json', import.meta.url);
export const approvalReviewFixture = JSON.parse(readFileSync(source, 'utf8')) as ApprovalReviewView;
