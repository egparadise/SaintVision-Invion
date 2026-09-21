/* Re-export API wire types generated from contracts/v1alpha1/core.schema.json. */
export type {
  ApprovalPage,
  ControlRunDetail,
  ControlRunPage,
  ControlRunView,
  RunState,
} from '../../../../packages/contracts-ts/src/index';

import type { ControlRunDetail, ControlRunPage, ControlRunView } from '../../../../packages/contracts-ts/src/index';
import type { RunItem } from './types';

/**
 * Projects a canonical wire run (ControlRunView | ControlRunDetail) into the UI RunItem ViewModel.
 * Fields absent from the wire remain undefined, rather than being synthesized.
 */
export function observedRun(view: ControlRunView | ControlRunDetail): RunItem {
  return {
    id: view.runId,
    projectId: view.projectId,
    state: view.state,
    version: view.version,
    attempt: view.attempt,
    resourceReleasePending: 'resourceReleasePending' in view ? Boolean(view.resourceReleasePending) : undefined,
  };
}

/**
 * Projects a canonical ControlRunPage wire response into UI RunItem array with pagination cursor.
 */
export function observedRunPage(page: ControlRunPage): { items: RunItem[]; nextCursor: string | null } {
  return {
    items: (page.items || []).map(observedRun),
    nextCursor: page.nextCursor ?? null,
  };
}

