import type { ModelLineage } from '@/contracts/types';

// Test-only mock fixtures for local gate/conformance unit tests (never used as real production state)
export const TEST_FIXTURE_LINEAGES: ModelLineage[] = [
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
