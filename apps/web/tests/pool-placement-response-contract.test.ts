import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  addPoolMember,
  createPoolPlan,
  getPoolCapacity,
  getPoolPlacementPreview,
  removePoolMember,
} from '../src/features/desktop/fabricControlApi';
import { apiClient } from '../src/shared/api/client';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
const schemaUrl = new URL('../../../contracts/', import.meta.url);
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const contracts = [
  'pool-capacity-response',
  'placement-preview-response',
  'pool-created-response',
  'pool-member-response',
  'pool-member-removal-response',
  'distributed-plan-response',
  'distributed-plan-request',
];
const validators = new Map(contracts.map((name) => {
  const schema = JSON.parse(readFileSync(new URL(`${name}.schema.json`, schemaUrl), 'utf8'));
  return [name, ajv.compile(schema)];
}));
const fixture = (name: string) => JSON.parse(readFileSync(new URL(`../../../contracts/fixtures/${name}`, import.meta.url), 'utf8'));

describe('pool and placement shared response contracts', () => {
  beforeEach(() => api.mockReset());

  it.each([
    ['pool-capacity-response', 'pool-capacity-response.json'],
    ['placement-preview-response', 'placement-preview-response.json'],
    ['pool-created-response', 'pool-created-response.json'],
    ['pool-member-response', 'pool-member-response.json'],
    ['pool-member-removal-response', 'pool-member-removal-response.json'],
    ['distributed-plan-response', 'distributed-plan-response.json'],
  ])('validates shared fixture %s against the backend schema', (name, filename) => {
    const validate = validators.get(name)!;
    const payload = fixture(filename);
    expect(validate(payload), JSON.stringify(validate.errors)).toBe(true);
    const changed = structuredClone(payload);
    delete changed[Object.keys(changed)[0]];
    expect(validate(changed)).toBe(false);
  });

  it('maps placement wire spare capacity to the screen view from the shared fixture', async () => {
    const wire = fixture('placement-preview-response.json');
    api.mockResolvedValue(wire);
    const result = await getPoolPlacementPreview(wire.poolId, {
      cpuMillicores: 1200,
      ramBytes: 1024,
      gpuDevices: 1,
    });
    expect(result).toEqual({
      poolId: wire.poolId,
      candidateCount: wire.candidateCount,
      candidates: [{
        nodeId: wire.candidates[0].nodeId,
        hostname: wire.candidates[0].hostname,
        availableCpuMillicores: wire.candidates[0].spare.cpuMillicores,
        availableRamBytes: wire.candidates[0].spare.ramBytes,
        availableGpuDevices: wire.candidates[0].spare.gpuDevices,
        eligible: true,
      }],
    });
    expect(api).toHaveBeenCalledWith(
      `/v1/pools/${wire.poolId}/placement-preview?cpuMillicores=1200&ramBytes=1024&gpuDevices=1`,
    );
  });

  it('uses generated capacity, plan and membership response types at adapter boundaries', async () => {
    const capacity = fixture('pool-capacity-response.json');
    api.mockResolvedValueOnce(capacity);
    expect(await getPoolCapacity(capacity.poolId)).toEqual(capacity);
    expect(api).toHaveBeenLastCalledWith(`/v1/pools/${capacity.poolId}/capacity`);

    const plan = fixture('distributed-plan-response.json');
    api.mockResolvedValueOnce(plan);
    expect(await createPoolPlan('pool_contract_training', {
      runId: plan.runId,
      strategy: plan.strategy,
      shardCount: plan.shardCount,
      shardCpuMillicores: 2000,
      shardRamBytes: 4294967296,
      shardGpuDevices: 1,
      splittableDeclared: true,
    })).toEqual(plan);
    expect(api).toHaveBeenLastCalledWith('/v1/pools/pool_contract_training/plans', expect.objectContaining({ method: 'POST' }));

    const member = fixture('pool-member-response.json');
    api.mockResolvedValueOnce(member);
    expect(await addPoolMember(member.poolId, member.nodeId)).toEqual(member);
    const removal = fixture('pool-member-removal-response.json');
    api.mockResolvedValueOnce(removal);
    expect(await removePoolMember(removal.poolId, removal.nodeId)).toEqual(removal);
  });
});
