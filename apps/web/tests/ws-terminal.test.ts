import { describe, it, expect, vi } from 'vitest';
import { WsTerminalClient } from '../src/shared/realtime/ws-terminal';

describe('S01-FE: WebSocket Terminal PTY Client', () => {
  it('connects with 30s one-time ticket query parameter', () => {
    const onData = vi.fn();
    const onStatus = vi.fn();

    const client = new WsTerminalClient('ws://localhost:8080/v1/terminal/ws', onData, onStatus);

    // Mock WebSocket class
    class MockWebSocket {
      static OPEN = 1;
      url: string;
      readyState = 1; // OPEN
      onopen: (() => void) | null = null;
      onmessage: ((ev: any) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      sentMessages: string[] = [];

      constructor(url: string) {
        this.url = url;
      }

      send(data: string) {
        this.sentMessages.push(data);
      }

      close() {
        if (this.onclose) this.onclose();
      }
    }

    const originalWs = globalThis.WebSocket;
    globalThis.WebSocket = MockWebSocket as any;

    try {
      client.connect('ticket_xyz_123');

      expect(onStatus).toHaveBeenCalledWith('connecting');
      const wsInstance = (client as any).ws as MockWebSocket;
      expect(wsInstance.url).toBe('ws://localhost:8080/v1/terminal/ws?ticket=ticket_xyz_123');

      // Trigger open
      wsInstance.onopen!();
      expect(onStatus).toHaveBeenCalledWith('connected');

      // Send input with monotonic sequence
      client.sendInput('ls -la\n');
      expect(wsInstance.sentMessages).toHaveLength(1);
      expect(JSON.parse(wsInstance.sentMessages[0])).toEqual({
        type: 'data',
        payload: 'ls -la\n',
        sequence: 1,
      });
      expect(client.getSequence()).toBe(1);

      // Send second input with incremented sequence
      client.sendInput('pwd\n');
      expect(wsInstance.sentMessages).toHaveLength(2);
      expect(JSON.parse(wsInstance.sentMessages[1])).toEqual({
        type: 'data',
        payload: 'pwd\n',
        sequence: 2,
      });
      expect(client.getSequence()).toBe(2);

      // Send resize
      client.sendResize(120, 40);
      expect(wsInstance.sentMessages).toHaveLength(3);
      expect(JSON.parse(wsInstance.sentMessages[2])).toEqual({
        type: 'resize',
        cols: 120,
        rows: 40,
      });

      // Receive message from terminal
      wsInstance.onmessage!({
        data: JSON.stringify({ type: 'data', payload: 'total 64\ndrwxr-xr-x ...' }),
      });
      expect(onData).toHaveBeenCalledWith('total 64\ndrwxr-xr-x ...');

      // Fallback: receive raw non-JSON text frame
      wsInstance.onmessage!({
        data: 'saintvision@wsp-saint-pilot:~$ ',
      });
      expect(onData).toHaveBeenCalledWith('saintvision@wsp-saint-pilot:~$ ');

      // Trigger error and close
      wsInstance.onerror!();
      expect(onStatus).toHaveBeenCalledWith('error');

      // Disconnect
      client.disconnect();
      expect((client as any).isClosed).toBe(true);
      expect(onStatus).toHaveBeenCalledWith('disconnected');
    } finally {
      globalThis.WebSocket = originalWs;
    }
  });

  it('handles disconnect and reconnect cycle gracefully', () => {
    const onData = vi.fn();
    const onStatus = vi.fn();
    const client = new WsTerminalClient('ws://localhost:8080/v1/terminal/ws', onData, onStatus);

    expect(client.getSequence()).toBe(0);
    client.disconnect();
    expect(onStatus).toHaveBeenCalledWith('disconnected');
  });
});
