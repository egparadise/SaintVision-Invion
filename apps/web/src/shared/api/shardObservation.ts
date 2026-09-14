import type { ShardExecutionItem, ShardObservation } from '@/contracts/types';
import { apiClient } from './client';

export async function fetchShardObservation(projectId: string, runId: string) {
  if (!projectId) throw new Error('프로젝트 정보가 없습니다.');
  const result = await apiClient<ShardObservation>(
    `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/shards`,
  );
  if (result?.parentRunId !== runId || !Array.isArray(result.shards)) {
    throw new Error('샤드 응답이 현재 실행과 일치하지 않습니다.');
  }
  return result;
}

export function shardRows(observation: ShardObservation): ShardExecutionItem[] {
  return observation.shards.map(member => ({
    shardId: `${observation.planId}:${member.index}`,
    runId: member.runId,
    parentId: observation.parentRunId!,
    nodeId: member.nodeId,
    hostname: member.nodeId,
    executionState: member.state,
    physicallyStopped: member.phase === 'stopped',
    verified: member.phase === 'stopped' && member.state === 'succeeded' && member.evidenceId !== null,
    evidenceId: member.evidenceId ?? undefined,
    // Per-member attempt and resource release are not supplied by this view.
  }));
}

export function shardRefreshNotice(observation: ShardObservation): string {
  return observation.allPhysicallyStopped
    ? '샤드 상태를 새로고침했습니다. 모든 샤드의 물리 정지가 확인되었습니다. 자원 반환 상태는 Run에서 확인하세요.'
    : '샤드 상태를 새로고침했습니다. 아직 모든 샤드의 물리 정지가 확인되지 않았습니다.';
}
