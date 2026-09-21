import type { NodeItem, NodeStatus } from '@/contracts/types';

const metrics = ['cpuCores', 'cpuUsagePercent', 'memoryTotalBytes', 'memoryUsedBytes',
  'gpuCount', 'storageTotalBytes', 'storageUsedBytes'] as const;

/** Missing values stay unavailable; NaN is internal and never a displayed measurement. */
export function observedNode(value: object): NodeItem {
  // Both untrusted legacy row objects and the strict generated NodeResponse
  // enter this projection. Fields absent from the wire remain unavailable.
  const raw = value as Record<string, unknown>;
  const number = (key: string) => typeof raw[key] === 'number' && Number.isFinite(raw[key]) && raw[key] >= 0 ? raw[key] as number : Number.NaN;
  const heartbeat = raw.lastHeartbeatAt ?? raw.heartbeatAt;
  const os = raw.osType ?? raw.os;
  const knownStatuses = ['online', 'degraded', 'offline', 'draining', 'enrolling', 'retired', 'active'];
  const rawStatus = typeof raw.status === 'string' ? raw.status : '';
  let mappedStatus: NodeStatus;
  if (rawStatus === 'lost') {
    mappedStatus = 'lost';
  } else if (rawStatus === 'active') {
    mappedStatus = 'active';
  } else if (knownStatuses.includes(rawStatus)) {
    mappedStatus = rawStatus as NodeStatus;
  } else {
    // 계약에도 없고 뷰에도 없는 진정한 미확인 상태를 조용히 합류/정상으로 꾸미지 않고 unknown으로 명시
    mappedStatus = 'unknown';
  }
  const valid = metrics.every(key => Number.isFinite(number(key))) &&
    typeof heartbeat === 'string' && Number.isFinite(Date.parse(heartbeat)) &&
    (os === 'windows' || os === 'linux') && (knownStatuses.includes(rawStatus) || rawStatus === 'lost') && !!(raw.nodeId ?? raw.id) &&
    number('cpuUsagePercent') <= 100 && number('memoryUsedBytes') <= number('memoryTotalBytes') &&
    number('storageUsedBytes') <= number('storageTotalBytes') &&
    (number('gpuCount') === 0 || (Number.isFinite(number('gpuVramTotalBytes')) &&
      number('gpuVramUsedBytes') <= number('gpuVramTotalBytes')));
  return {
    id: String(raw.nodeId ?? raw.id ?? ''), hostname: String(raw.hostname ?? raw.nodeId ?? raw.id ?? ''),
    status: mappedStatus,
    os: os === 'linux' ? 'linux' : 'windows', telemetryUnavailable: !valid || mappedStatus === 'lost',
    cpuCores: number('cpuCores'), cpuUsagePercent: number('cpuUsagePercent'),
    memoryTotalBytes: number('memoryTotalBytes'), memoryUsedBytes: number('memoryUsedBytes'),
    storageTotalBytes: number('storageTotalBytes'), storageUsedBytes: number('storageUsedBytes'),
    gpuCount: number('gpuCount'), gpuName: typeof raw.gpuName === 'string' ? raw.gpuName : undefined,
    gpuVramTotalBytes: number('gpuCount') === 0 ? 0 : number('gpuVramTotalBytes'), gpuVramUsedBytes: number('gpuCount') === 0 ? 0 : number('gpuVramUsedBytes'),
    heartbeatAt: typeof heartbeat === 'string' ? heartbeat : '',
    schedulable: valid && raw.status === 'online' && raw.schedulable === true &&
      raw.observationOnly === false && raw.killSwitchEngaged === false && raw.isDraining === false &&
      Number.isFinite(number('allocatableCores')) && Number.isFinite(number('allocatableMemoryBytes')), observationOnly: !valid || raw.observationOnly !== false,
    allocatableCores: Number.isFinite(number('allocatableCores')) ? number('allocatableCores') : undefined,
    allocatableMemoryBytes: Number.isFinite(number('allocatableMemoryBytes')) ? number('allocatableMemoryBytes') : undefined,
    isDraining: raw.isDraining === true, killSwitchEngaged: raw.killSwitchEngaged !== false,
    ipAddress: typeof raw.ipAddress === 'string' ? raw.ipAddress : undefined,
  };
}
