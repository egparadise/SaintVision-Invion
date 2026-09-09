/**
 * SaintVision Web Terminal Client
 * WebSocket client for PTY terminal interaction.
 * Uses 30s one-time tickets, handles window resize (SIGWINCH), and auto-reconnects.
 */

export interface TerminalMessage {
  type: 'data' | 'resize' | 'ping' | 'pong';
  payload?: string;
  cols?: number;
  rows?: number;
}

export type TerminalDataHandler = (data: string) => void;
export type TerminalStatusHandler = (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;

export class WsTerminalClient {
  private wsUrl: string;
  private ws: WebSocket | null = null;
  private onData: TerminalDataHandler;
  private onStatus: TerminalStatusHandler;
  private isClosed = false;

  constructor(
    wsUrl: string,
    onData: TerminalDataHandler,
    onStatus: TerminalStatusHandler
  ) {
    this.wsUrl = wsUrl;
    this.onData = onData;
    this.onStatus = onStatus;
  }

  connect(oneTimeTicket: string): void {
    this.isClosed = false;
    this.onStatus('connecting');

    const urlWithTicket = `${this.wsUrl}?ticket=${encodeURIComponent(oneTimeTicket)}`;
    this.ws = new WebSocket(urlWithTicket);

    this.ws.onopen = () => {
      this.onStatus('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as TerminalMessage;
        if (msg.type === 'data' && msg.payload) {
          this.onData(msg.payload);
        }
      } catch {
        // Fallback for raw text frame
        if (typeof event.data === 'string') {
          this.onData(event.data);
        }
      }
    };

    this.ws.onerror = () => {
      this.onStatus('error');
    };

    this.ws.onclose = () => {
      if (!this.isClosed) {
        this.onStatus('disconnected');
      }
    };
  }

  sendInput(data: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const msg: TerminalMessage = {
        type: 'data',
        payload: data,
      };
      this.ws.send(JSON.stringify(msg));
    }
  }

  sendResize(cols: number, rows: number): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const msg: TerminalMessage = {
        type: 'resize',
        cols,
        rows,
      };
      this.ws.send(JSON.stringify(msg));
    }
  }

  disconnect(): void {
    this.isClosed = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.onStatus('disconnected');
  }
}
