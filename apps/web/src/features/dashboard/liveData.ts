export interface LiveNode {
  nodeId: string; address: string | null; status: string; fresh: boolean;
  lastHeartbeatAt: string | null; lastSnapshotAt: string | null;
  observationAgeSeconds: number | null; osType: string | null;
  profileVersion: string | null; agentVersion: string | null;
  cpuCores: number | null; cpuUsagePercent: number | null;
  memoryTotalBytes: number | null; memoryUsedBytes: number | null;
  gpuCount: number | null; storageTotalBytes: number | null;
}
export interface LiveTest {
  test: string; passed: boolean; completedAt: string; commandId?: string;
  exitCode?: number; stopped?: boolean; processStarted?: boolean; reason?: string;
  outputSha256?: string; stdout: string; stderr: string; duplicate?: boolean; sameReceipt?: boolean;
}
export interface LiveOverview {
  source: 'live-postgresql-mtls'; generatedAt: string; serverAddress: string;
  nodes: LiveNode[]; runs: {runId: string; state: string; version: number}[];
  offered: Record<string,number>; killSwitch: boolean;
  userWorkloadSubmission: boolean; webAuthenticationConfigured: boolean; tests: LiveTest[];
}
export function parseOverview(value: unknown): LiveOverview {
  const data = value as LiveOverview;
  if (!data || data.source !== 'live-postgresql-mtls' || !Array.isArray(data.nodes)
    || !Array.isArray(data.runs) || !Array.isArray(data.tests) || !Number.isFinite(Date.parse(data.generatedAt))) {
    throw new Error('실제 관측 데이터의 형식이 올바르지 않습니다.');
  }
  return data;
}
export function freshNodes(data: LiveOverview, now = Date.now()): LiveNode[] {
  return data.nodes.filter(n => n.status === 'online' && n.fresh && n.lastSnapshotAt
    && now - Date.parse(n.lastSnapshotAt) >= -5000 && now - Date.parse(n.lastSnapshotAt) <= 20000);
}
export function total(nodes: LiveNode[], field: 'cpuCores'|'memoryTotalBytes'|'memoryUsedBytes'): number | null {
  if (!nodes.length || nodes.some(n => n[field] === null || !Number.isFinite(n[field]))) return null;
  return nodes.reduce((sum, n) => sum + n[field]!, 0);
}
