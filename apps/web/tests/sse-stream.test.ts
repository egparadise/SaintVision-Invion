import { describe, it, expect, vi } from 'vitest';
import { RingBuffer, SseStreamManager } from '../src/shared/realtime/sse-client';

describe('S01-FE: SSE Real-Time Stream Manager & Deduplication', () => {
  describe('RingBuffer Data Structure', () => {
    it('maintains insertion order and bounds capacity to maxSize', () => {
      const buffer = new RingBuffer<string>(3);

      buffer.add('evt_01');
      buffer.add('evt_02');
      buffer.add('evt_03');

      expect(buffer.has('evt_01')).toBe(true);
      expect(buffer.has('evt_02')).toBe(true);
      expect(buffer.has('evt_03')).toBe(true);

      // Adding 4th item should evict oldest (evt_01)
      buffer.add('evt_04');
      expect(buffer.has('evt_01')).toBe(false);
      expect(buffer.has('evt_02')).toBe(true);
      expect(buffer.has('evt_03')).toBe(true);
      expect(buffer.has('evt_04')).toBe(true);
    });

    it('does not duplicate existing items in buffer', () => {
      const buffer = new RingBuffer<string>(5);
      buffer.add('evt_dup');
      buffer.add('evt_dup');

      expect(buffer.has('evt_dup')).toBe(true);
    });

    it('clears all items cleanly', () => {
      const buffer = new RingBuffer<string>(5);
      buffer.add('evt_01');
      buffer.clear();

      expect(buffer.has('evt_01')).toBe(false);
    });
  });

  describe('SseStreamManager Event Parsing & Deduplication', () => {
    it('subscribes, parses SSE block, and invokes registered handler', () => {
      const manager = new SseStreamManager('/v1/projects/prj_01JABCDE/runs/run_01JSHARD_01/events');
      const handler = vi.fn();

      const unsubscribe = manager.on('heartbeat', handler);

      // Test parsing standard SSE block
      const block = 'id: evt_101\nevent: heartbeat\ndata: {"activeNodes": 5}\n';
      (manager as any).parseBlock(block);

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith({
        id: 'evt_101',
        event: 'heartbeat',
        data: { activeNodes: 5 },
      });

      // Unsubscribe
      unsubscribe();

      const nextBlock = 'id: evt_102\nevent: heartbeat\ndata: {"activeNodes": 5}\n';
      (manager as any).parseBlock(nextBlock);

      // Handler should not be called again after unsubscribe
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('drops duplicate event IDs using the ring buffer', () => {
      const manager = new SseStreamManager('/v1/projects/prj_01JABCDE/runs/run_01JSHARD_01/events');
      const handler = vi.fn();

      manager.on('status_update', handler);

      const block1 = 'id: evt_unique_1\nevent: status_update\ndata: {"status": "running"}\n';
      (manager as any).parseBlock(block1);
      expect(handler).toHaveBeenCalledTimes(1);

      // Duplicate delivery with same event ID
      (manager as any).parseBlock(block1);
      // Should still be called only once
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('cleans up resources upon stop', () => {
      const manager = new SseStreamManager('/v1/projects/prj_01JABCDE/runs/run_01JSHARD_01/events');
      manager.stop();
      expect((manager as any).isClosed).toBe(true);
    });
  });
});
