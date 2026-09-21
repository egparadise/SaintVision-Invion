import type { RunArtifactList } from '@/contracts/types';
import { apiClient } from './client';
import { calculateSha256 } from '@/shared/utils/crypto';

export interface ArtifactDownloadVerification {
  blob: Blob;
  fileName: string;
  calculatedSha256: string;
  expectedSha256: string | null;
  integrity: 'verified' | 'mismatch' | 'unverified';
}

export async function fetchRunArtifacts(projectId: string, runId: string): Promise<RunArtifactList> {
  if (!projectId) throw new Error('프로젝트 정보가 없습니다.');
  const result = await apiClient<RunArtifactList>(
    `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/artifacts`
  );

  if (!result || typeof result !== 'object') {
    throw new Error('RunArtifactList 응답 형식 불일치');
  }

  if (result.source !== 'execution-kernel') {
    throw new Error(`RunArtifactList source 계약 불일치: expected 'execution-kernel', got '${(result as any).source}'`);
  }

  if (typeof result.runId !== 'string' || !result.runId) {
    throw new Error('RunArtifactList runId 누락');
  }

  if (!Array.isArray(result.artifacts)) {
    throw new Error('RunArtifactList artifacts 배열 누락');
  }

  if (typeof result.count !== 'number') {
    throw new Error('RunArtifactList count 계약 불일치');
  }

  if (typeof result.verifiedCount !== 'number') {
    throw new Error('RunArtifactList verifiedCount 계약 불일치');
  }

  if (result.completedAt !== undefined && result.completedAt !== null && typeof result.completedAt !== 'string') {
    throw new Error('RunArtifactList completedAt 계약 불일치');
  }

  return result;
}

export function getArtifactDownloadUrl(projectId: string, runId: string, path: string): string {
  return `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/artifacts/content?path=${encodeURIComponent(path)}`;
}

/**
 * Downloads artifact content from kernel endpoint and verifies its SHA-256 against X-Content-SHA256 header.
 * Strictly implements tri-state integrity verification:
 * - 'verified': Header exists and matches calculated SHA-256
 * - 'mismatch': Header exists and does NOT match calculated SHA-256 (corrupted/tampered)
 * - 'unverified': Header is missing (cannot verify)
 */
export async function downloadAndVerifyArtifact(
  projectId: string,
  runId: string,
  path: string,
  fallbackFileName?: string,
  authToken?: string | null
): Promise<ArtifactDownloadVerification> {
  if (!projectId) throw new Error('프로젝트 정보가 없습니다.');
  if (!runId) throw new Error('실행 ID가 없습니다.');
  if (!path) throw new Error('아티팩트 경로가 없습니다.');

  const headers: Record<string, string> = {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const url = getArtifactDownloadUrl(projectId, runId, path);
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }

  // 1. Determine final filename using Content-Disposition if present
  let fileName = fallbackFileName || path.split('/').pop() || 'artifact.bin';
  const disposition = res.headers.get('content-disposition');
  if (disposition) {
    const match = disposition.match(/filename\*?=['"]?(?:UTF-\d['"]*)?([^;\r\n"']*)['"]?/i);
    if (match && match[1]) {
      try {
        fileName = decodeURIComponent(match[1].trim());
      } catch {
        fileName = match[1].trim();
      }
    }
  }

  // 2. Read bytes and compute WebCrypto SHA-256
  const blob = await res.blob();
  const arrayBuffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);
  const calculatedSha256 = await calculateSha256(bytes);

  // 3. Extract X-Content-SHA256 header
  const headerSha = res.headers.get('x-content-sha256') || res.headers.get('X-Content-SHA256');
  const expectedSha256 = headerSha ? headerSha.trim().toLowerCase() : null;

  // 4. Determine tri-state integrity
  let integrity: 'verified' | 'mismatch' | 'unverified';
  if (!expectedSha256) {
    integrity = 'unverified';
  } else if (expectedSha256 === calculatedSha256.toLowerCase()) {
    integrity = 'verified';
  } else {
    integrity = 'mismatch';
  }

  return {
    blob,
    fileName,
    calculatedSha256,
    expectedSha256,
    integrity,
  };
}
