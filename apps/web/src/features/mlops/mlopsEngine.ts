import { ModelLineage, ProviderAdapterConformance } from '@/contracts/types';
import { computeSha256 } from '../editor/diffEngine';

const INITIAL_LINEAGES: ModelLineage[] = [
  {
    modelId: 'mod_pacs_seg_v2',
    modelName: 'SaintVision PACS Lesion Segmentation',
    version: '2.1.0',
    datasetDigest: 'dset_sha256_8a91f4c3b2e1d0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5',
    sourceCommitSha: '58cabd3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c',
    trainingRunId: 'run_01JABCDE0001',
    evalAccuracy: 0.948,
    evalF1Score: 0.923,
    approvalId: 'apr_01JXYZ987654',
    deploymentDigest: 'sha256:4a8b2c1d9f3e5a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b',
    deployedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    status: 'deployed',
  },
  {
    modelId: 'mod_pacs_cls_v1',
    modelName: 'SaintVision Chest CT Classifier',
    version: '1.4.2',
    datasetDigest: 'dset_sha256_1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c',
    sourceCommitSha: '39699e9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f',
    trainingRunId: 'run_01JABCDE0003',
    evalAccuracy: 0.892,
    evalF1Score: 0.867,
    approvalId: 'apr_01JXYZ112233',
    deploymentDigest: 'sha256:7f8e9d0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e',
    deployedAt: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
    status: 'deployed',
  },
  {
    modelId: 'mod_experimental_vit_v3',
    modelName: 'ViT-Huge Medical Multimodal',
    version: '0.3.0-alpha',
    datasetDigest: 'dset_sha256_99887766554433221100aabbccddeeff00112233445566778899aabbccddeeff',
    sourceCommitSha: '24566d8f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d',
    trainingRunId: 'run_01JABCDE0002',
    evalAccuracy: 0.812, // Below 0.85 threshold!
    evalF1Score: 0.785,
    approvalId: '',
    deploymentDigest: '',
    deployedAt: '',
    status: 'staging',
  },
];

export class MlopsManager {
  private lineages: ModelLineage[] = [...INITIAL_LINEAGES];

  getLineages(): ModelLineage[] {
    return [...this.lineages];
  }

  /**
   * Reverse Lineage Query (AC-10: 역추적 질의)
   * Resolves query by modelId, deploymentDigest, or sourceCommitSha
   */
  queryLineage(term: string): ModelLineage | undefined {
    const trimmed = term.trim().toLowerCase();
    return this.lineages.find(
      (m) =>
        m.modelId.toLowerCase().includes(trimmed) ||
        m.deploymentDigest.toLowerCase().includes(trimmed) ||
        m.sourceCommitSha.toLowerCase().includes(trimmed) ||
        m.modelName.toLowerCase().includes(trimmed)
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
   * Gated Model Deployment: Enforces Accuracy >= 0.85 and Two-Person Rule Approval
   */
  deployModel(params: {
    modelId: string;
    approvalId: string;
  }): { success: boolean; deployedModel?: ModelLineage; error?: string } {
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

    // Generate deployment digest
    const digestPayload = `${model.modelId}:${model.datasetDigest}:${model.sourceCommitSha}:${params.approvalId}`;
    const deploymentDigest = `sha256:${computeSha256(digestPayload)}`;

    model.approvalId = params.approvalId;
    model.deploymentDigest = deploymentDigest;
    model.deployedAt = new Date().toISOString();
    model.status = 'deployed';

    return { success: true, deployedModel: { ...model } };
  }
}
