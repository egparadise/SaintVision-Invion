import { describe, it, expect } from 'vitest';
import { RingBuffer } from '../src/shared/realtime/sse-client';
import { generateTraceId, generateSpanId } from '../src/shared/api/client';

describe('Realtime SSE RingBuffer Deduplication', () => {
  it('should store items and detect duplicates', () => {
    const ring = new RingBuffer<string>(3);
    ring.add('evt_01');
    ring.add('evt_02');

    expect(ring.has('evt_01')).toBe(true);
    expect(ring.has('evt_02')).toBe(true);
    expect(ring.has('evt_03')).toBe(false);
  });

  it('should evict oldest items when exceeding maxSize', () => {
    const ring = new RingBuffer<string>(3);
    ring.add('evt_01');
    ring.add('evt_02');
    ring.add('evt_03');
    ring.add('evt_04'); // Should evict evt_01

    expect(ring.has('evt_01')).toBe(false);
    expect(ring.has('evt_02')).toBe(true);
    expect(ring.has('evt_03')).toBe(true);
    expect(ring.has('evt_04')).toBe(true);
  });
});

describe('W3C Trace Context Generator', () => {
  it('should generate valid 32-character lowercase hex traceId', () => {
    const traceId = generateTraceId();
    expect(traceId).toHaveLength(32);
    expect(/^[0-9a-f]{32}$/.test(traceId)).toBe(true);
  });

  it('should generate valid 16-character lowercase hex spanId', () => {
    const spanId = generateSpanId();
    expect(spanId).toHaveLength(16);
    expect(/^[0-9a-f]{16}$/.test(spanId)).toBe(true);
  });
});
