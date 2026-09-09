/**
 * SaintVision SSE Client
 * Implements:
 * - 1,000-entry eventId ring buffer deduplication (at-least-once bus)
 * - Exponential backoff with jitter (1s -> 2s -> 4s ... up to 30s)
 * - Last-Event-ID resume cursor
 * - Client latency measurement (run_event_delivery_lag_ms)
 */

export interface SseEvent<T = unknown> {
  id: string;
  event: string;
  data: T;
  occurredAt?: string;
}

export type SseEventHandler<T = unknown> = (event: SseEvent<T>) => void;

export class RingBuffer<T> {
  private buffer: T[] = [];
  private set = new Set<T>();
  private maxSize: number;

  constructor(maxSize: number = 1000) {
    this.maxSize = maxSize;
  }

  has(item: T): boolean {
    return this.set.has(item);
  }

  add(item: T): void {
    if (this.set.has(item)) return;

    if (this.buffer.length >= this.maxSize) {
      const removed = this.buffer.shift();
      if (removed !== undefined) {
        this.set.delete(removed);
      }
    }

    this.buffer.push(item);
    this.set.add(item);
  }

  clear(): void {
    this.buffer = [];
    this.set.clear();
  }
}

export class SseStreamManager {
  private url: string;
  private lastEventId: string | null = null;
  private ringBuffer = new RingBuffer<string>(1000);
  private handlers = new Map<string, Set<SseEventHandler>>();
  private abortController: AbortController | null = null;
  private retryAttempt = 0;
  private isClosed = false;

  constructor(url: string) {
    this.url = url;
  }

  on<T>(eventType: string, handler: SseEventHandler<T>): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    const set = this.handlers.get(eventType)!;
    set.add(handler as SseEventHandler);

    return () => {
      set.delete(handler as SseEventHandler);
      if (set.size === 0) {
        this.handlers.delete(eventType);
      }
    };
  }

  start(): void {
    this.isClosed = false;
    this.connect();
  }

  stop(): void {
    this.isClosed = true;
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  private async connect(): Promise<void> {
    if (this.isClosed) return;

    this.abortController = new AbortController();

    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
    };
    if (this.lastEventId) {
      headers['Last-Event-ID'] = this.lastEventId;
    }

    try {
      const response = await fetch(this.url, {
        headers,
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`SSE HTTP ${response.status}: ${response.statusText}`);
      }

      // Successful connection: reset backoff
      this.retryAttempt = 0;

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body has no readable stream.');

      const decoder = new TextDecoder();
      let buffer = '';

      while (!this.isClosed) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const block of lines) {
          this.parseBlock(block);
        }
      }
    } catch (err: unknown) {
      if (this.isClosed) return;
      this.scheduleReconnect();
    }
  }

  private parseBlock(block: string): void {
    let id = '';
    let event = 'message';
    let dataStr = '';

    for (const line of block.split('\n')) {
      if (line.startsWith('id:')) {
        id = line.slice(3).trim();
      } else if (line.startsWith('event:')) {
        event = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataStr += line.slice(5).trim();
      }
    }

    if (!dataStr) return;

    // Deduplication via 1,000-entry ring buffer
    if (id) {
      if (this.ringBuffer.has(id)) {
        return; // drop duplicate
      }
      this.ringBuffer.add(id);
      this.lastEventId = id;
    }

    try {
      const parsedData = JSON.parse(dataStr);

      // Latency Measurement (SLO P95 <= 5s)
      if (parsedData?.occurredAt) {
        const sentTime = new Date(parsedData.occurredAt).getTime();
        const now = Date.now();
        const lagMs = Math.max(0, now - sentTime);
        // Telemetry hook
        if (typeof window !== 'undefined' && (window as unknown as { __saintvision_sse_lag_ms?: number }).__saintvision_sse_lag_ms !== undefined) {
          (window as unknown as { __saintvision_sse_lag_ms: number }).__saintvision_sse_lag_ms = lagMs;
        }
      }

      const sseEvent: SseEvent = {
        id,
        event,
        data: parsedData,
        occurredAt: parsedData?.occurredAt,
      };

      const listeners = this.handlers.get(event);
      if (listeners) {
        listeners.forEach((handler) => handler(sseEvent));
      }

      // Also notify wildcards if any
      const wildcards = this.handlers.get('*');
      if (wildcards) {
        wildcards.forEach((handler) => handler(sseEvent));
      }
    } catch {
      // Ignored malformed event data
    }
  }

  private scheduleReconnect(): void {
    this.retryAttempt++;
    // Exponential backoff with jitter: min(1000 * 2^(attempt-1), 30000) + random(0, 1000)
    const baseDelay = Math.min(1000 * Math.pow(2, this.retryAttempt - 1), 30000);
    const jitter = Math.random() * 1000;
    const delay = baseDelay + jitter;

    setTimeout(() => {
      if (!this.isClosed) {
        this.connect();
      }
    }, delay);
  }
}
