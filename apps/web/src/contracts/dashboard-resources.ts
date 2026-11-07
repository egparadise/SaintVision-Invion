import type { ObservedNodeResourceUsage } from './kernel-observation';

/** Internal read model. Project binding is the requested scoped route, not a new wire field. */
export interface DashboardNodeResourceObservation {
  projectId: string;
  usage: ObservedNodeResourceUsage | null;
  issues: Array<{ kind: string; message: string }>;
  error: string | null;
  loading?: boolean;
}
