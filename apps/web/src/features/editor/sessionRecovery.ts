import { TerminalSessionState } from '@/contracts/types';
import { computeSha256 } from './diffEngine';

export interface CommandLogEntry {
  seq: number;
  command: string;
  output: string;
  exitCode: number;
  timestamp: string;
  nonce: string;
}

export class SessionRecoveryManager {
  private state: TerminalSessionState;
  private commandHistory: CommandLogEntry[] = [];
  private executedNonces = new Set<string>();

  constructor(workspaceId: string, initialSessionId?: string) {
    const sessionId = initialSessionId || `sess_${Math.random().toString(36).substring(2, 10)}`;
    this.state = {
      sessionId,
      workspaceId,
      cols: 100,
      rows: 30,
      lastSeq: 0,
      checkpointHash: computeSha256(`init:${sessionId}`),
      reconnectToken: `tok_${sessionId}_${Date.now()}`,
      status: 'connected',
      duplicateExecutions: 0,
    };
  }

  getState(): TerminalSessionState {
    return { ...this.state };
  }

  getCommandHistory(): CommandLogEntry[] {
    return [...this.commandHistory];
  }

  /**
   * Execute command ensuring exactly-once semantic with nonce (AC-06: zero duplicate executions)
   */
  executeCommand(command: string, nonce: string): { success: boolean; entry: CommandLogEntry; isDuplicate: boolean } {
    if (this.executedNonces.has(nonce)) {
      this.state.duplicateExecutions++;
      const existing = this.commandHistory.find((c) => c.nonce === nonce)!;
      return { success: true, entry: existing, isDuplicate: true };
    }

    this.executedNonces.add(nonce);
    const nextSeq = this.state.lastSeq + 1;
    const timestamp = new Date().toISOString();
    
    // Simulate output
    const output = `[Executed in session ${this.state.sessionId}]: ${command}`;
    const entry: CommandLogEntry = {
      seq: nextSeq,
      command,
      output,
      exitCode: 0,
      timestamp,
      nonce,
    };

    this.commandHistory.push(entry);
    this.state.lastSeq = nextSeq;
    this.state.checkpointHash = this.computeCheckpointHash();
    this.state.reconnectToken = `tok_${this.state.sessionId}_${nextSeq}_${Date.now()}`;

    return { success: true, entry, isDuplicate: false };
  }

  /**
   * Resize PTY terminal (SIGWINCH)
   */
  resizeTerminal(cols: number, rows: number): { cols: number; rows: number; event: string } {
    this.state.cols = Math.max(20, Math.min(240, cols));
    this.state.rows = Math.max(10, Math.min(100, rows));
    return {
      cols: this.state.cols,
      rows: this.state.rows,
      event: 'SIGWINCH',
    };
  }

  /**
   * Compute deterministic cumulative checkpoint hash
   */
  computeCheckpointHash(): string {
    const raw = this.commandHistory
      .map((c) => `${c.seq}:${c.nonce}:${c.command}:${c.exitCode}`)
      .join('|');
    return computeSha256(`ckpt:${this.state.sessionId}:${raw}`);
  }

  /**
   * Simulate Control Plane Restart (AC-06 crash scenario)
   * The CP restarts, connection drops, but durable checkpoint state is preserved.
   */
  simulateCpRestart(): void {
    this.state.status = 'disconnected';
  }

  /**
   * Resume session after restart with token and last acknowledged sequence number
   */
  resumeSession(token: string, clientLastSeq: number): {
    resumed: boolean;
    missedCommands: CommandLogEntry[];
    hashMatches: boolean;
    checkpointHash: string;
  } {
    if (!token.startsWith(`tok_${this.state.sessionId}`)) {
      return { resumed: false, missedCommands: [], hashMatches: false, checkpointHash: '' };
    }

    this.state.status = 'reconnecting';

    // Commands client missed during downtime
    const missedCommands = this.commandHistory.filter((c) => c.seq > clientLastSeq);

    // Verify hash
    const currentHash = this.computeCheckpointHash();
    const hashMatches = currentHash === this.state.checkpointHash;

    this.state.status = 'recovered';

    return {
      resumed: true,
      missedCommands,
      hashMatches,
      checkpointHash: currentHash,
    };
  }
}
