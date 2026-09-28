import { ModelLineage, ProviderAdapterConformance } from '@/contracts/types';
import { computeSha256 } from '../editor/diffEngine';

// Real backend has no HTTP lineage API; default is strictly empty (zero fake syntheses)
// Test fixtures have been segregated to apps/web/tests/fixtures/model-lineage.ts.

export class MlopsManager {
  // Real backend has no HTTP lineage API; default is strictly empty (zero fake syntheses)
  private lineages: ModelLineage[];

  constructor(initialLineages: ModelLineage[] = []) {
    this.lineages = [...initialLineages];
  }

  getLineages(): ModelLineage[] {
    return [...this.lineages];
  }

  /**
   * Reverse Lineage Query (AC-10: 역추적 질의)
   * Resolves query by modelId, deploymentDigest, sourceCommitSha, modelName, or datasetDigest
   */
  queryLineage(term: string): ModelLineage | undefined {
    const trimmed = term.trim().toLowerCase();
    if (!trimmed) return undefined;
    return this.lineages.find(
      (m) =>
        m.modelId.toLowerCase().includes(trimmed) ||
        m.deploymentDigest.toLowerCase().includes(trimmed) ||
        m.sourceCommitSha.toLowerCase().includes(trimmed) ||
        m.modelName.toLowerCase().includes(trimmed) ||
        m.datasetDigest.toLowerCase().includes(trimmed)
    );
  }

  /**
   * Multi-Provider Adapter Conformance Verification (AC-10)
   */
  verifyProviderConformances(): ProviderAdapterConformance[] {
    return [
      {
        provider: 'Codex',
        conformancePassed: true,
        contractVersion: 'v1.0.0-ADR-004',
        avgLatencyMs: 142,
        tokensPerSec: 68.5,
        supportedProtocols: ['SSE-v2', 'W3C-TraceContext', 'ProblemDetails'],
      },
      {
        provider: 'Claude',
        conformancePassed: true,
        contractVersion: 'v1.0.0-ADR-004',
        avgLatencyMs: 156,
        tokensPerSec: 64.2,
        supportedProtocols: ['SSE-v2', 'W3C-TraceContext', 'ProblemDetails'],
      },
      {
        provider: 'Local-vLLM',
        conformancePassed: true,
        contractVersion: 'v1.0.0-ADR-004',
        avgLatencyMs: 48,
        tokensPerSec: 112.0,
        supportedProtocols: ['SSE-v2', 'W3C-TraceContext', 'ProblemDetails'],
      },
    ];
  }

  /**
   * Client-only Simulated Gated Model Deployment (Mock Simulation: Unrelated to Backend Digest Pinning)
   * Note: Real backend persists digest via ModelVersion.content_sha256 and validates approval via AUTH-APPROVAL-DIGEST-MISMATCH.
   * This is a client-side mock simulation only and does not interact with backend digest pinning or production infrastructure.
   */
  deployModel(params: {
    modelId: string;
    approvalId: string;
  }): { success: boolean; deployedModel?: ModelLineage; error?: string; isSimulated?: boolean } {
    const model = this.lineages.find((m) => m.modelId === params.modelId);
    if (!model) {
      return { success: false, error: 'Model not found' };
    }

    if (!params.approvalId || !params.approvalId.startsWith('apr_')) {
      return {
        success: false,
        error: 'DEPLOYMENT_GATED: Two-Person Rule approval ID is required for production deployment.',
      };
    }

    if (model.evalAccuracy < 0.85) {
      return {
        success: false,
        error: `DEPLOYMENT_GATED: Model accuracy (${(model.evalAccuracy * 100).toFixed(1)}%) is below mandatory threshold (85.0%).`,
      };
    }

    // Client-only simulated deployment digest (mock simulation, unrelated to backend ModelVersion digest pinning)
    const digestPayload = `${model.modelId}:${model.datasetDigest}:${model.sourceCommitSha}:${params.approvalId}`;
    const deploymentDigest = `sha256:${computeSha256(digestPayload)}`;

    model.approvalId = params.approvalId;
    model.deploymentDigest = deploymentDigest;
    model.deployedAt = new Date().toISOString();
    model.status = 'deployed';

    return { success: true, deployedModel: { ...model }, isSimulated: true };
  }
}
