import { describe,it,expect } from 'vitest';
import { parseOverview,freshNodes,total,LiveOverview,LiveNode } from '../src/features/dashboard/liveData';
describe('actual cluster data',() => {
  const now=Date.now();
  const node={nodeId:'actual-node',status:'online',fresh:true,lastSnapshotAt:new Date(now).toISOString(),cpuCores:16,memoryTotalBytes:8000,memoryUsedBytes:0} as LiveNode;
  const data={source:'live-postgresql-mtls',generatedAt:new Date(now).toISOString(),nodes:[node],runs:[],tests:[]} as unknown as LiveOverview;
  it('keeps empty live inventory empty',() => {
    const empty=parseOverview({...data,nodes:[]});
    expect(freshNodes(empty,now)).toEqual([]);
    expect(total(empty.nodes,'cpuCores')).toBeNull();
  });
  it('does not count old online rows as connected capacity',() => {
    expect(freshNodes(data,now)).toEqual([node]);
    expect(freshNodes(data,now+21000)).toEqual([]);
  });
  it('preserves zero and excludes unknown capacity',() => {
    expect(total([node],'memoryUsedBytes')).toBe(0);
    expect(total([{...node,cpuCores:null}],'cpuCores')).toBeNull();
  });
  it('rejects demo or malformed responses instead of supplying example nodes',() => {
    expect(() => parseOverview({items:[]})).toThrow();
    expect(() => parseOverview({...data,source:'mock'})).toThrow();
  });
});
