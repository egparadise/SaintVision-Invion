import { describe, it, expect, vi } from 'vitest';
import { WsTerminalClient } from '../src/shared/realtime/ws-terminal';
import { apiClient } from '../src/shared/api/client';

describe('S01-FE: WebSocket Terminal PTY Client', () => {
  it('connects with inv-terminal-v1 subprotocol and sends initial ticket frame', () => {
    const onData = vi.fn();
    const onStatus = vi.fn();

    const client = new WsTerminalClient('ws://localhost:8080/v1/terminal/ws', onData, onStatus);

    // Mock WebSocket class
    class MockWebSocket {
      static OPEN = 1;
      url: string;
      protocols?: string | string[];
      readyState = 1; // OPEN
      onopen: (() => void) | null = null;
      onmessage: ((ev: any) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      sentMessages: string[] = [];

      constructor(url: string, protocols?: string | string[]) {
        this.url = url;
        this.protocols = protocols;
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
      expect(wsInstance.url).toBe('ws://localhost:8080/v1/terminal/ws');
      expect(wsInstance.protocols).toEqual(['inv-terminal-v1']);

      // Trigger open sends initial ticket authentication frame
      wsInstance.onopen!();
      expect(onStatus).toHaveBeenCalledWith('connected');
      expect(wsInstance.sentMessages).toHaveLength(1);
      expect(JSON.parse(wsInstance.sentMessages[0])).toEqual({ ticket: 'ticket_xyz_123' });

      // Send input with monotonic sequence
      client.sendInput('ls -la\n');
      expect(wsInstance.sentMessages).toHaveLength(2);
      expect(JSON.parse(wsInstance.sentMessages[1])).toEqual({
        type: 'data',
        payload: 'ls -la\n',
        sequence: 1,
      });
      expect(client.getSequence()).toBe(1);

      // Send second input with incremented sequence
      client.sendInput('pwd\n');
      expect(wsInstance.sentMessages).toHaveLength(3);
      expect(JSON.parse(wsInstance.sentMessages[2])).toEqual({
        type: 'data',
        payload: 'pwd\n',
        sequence: 2,
      });
      expect(client.getSequence()).toBe(2);

      // Send resize
      client.sendResize(120, 40);
      expect(wsInstance.sentMessages).toHaveLength(4);
      expect(JSON.parse(wsInstance.sentMessages[3])).toEqual({
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

  it('requests one-time terminal ticket from canonical workspace endpoint', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: any) => {
      if (String(url).includes('/v1/workspaces/wsp_01/terminal-tickets')) {
        return {
          ok: true,
          status: 201,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ ticketId: 'tkt_canonical_123', ptyWsUrl: 'ws://localhost:8080/v1/workspaces/wsp_01/terminals/sess_01' }),
        } as any;
      }
      return { ok: false, status: 404, statusText: 'Not Found', headers: new Headers(), json: async () => ({ detail: 'Not Found' }) } as any;
    });

    const ticketData = await apiClient<{ ticketId: string }>('/v1/workspaces/wsp_01/terminal-tickets', {
      method: 'POST',
      body: JSON.stringify({ workspaceId: 'wsp_01', sessionId: 'sess_01' }),
    });

    expect(ticketData.ticketId).toBe('tkt_canonical_123');
    expect(fetchSpy).toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
