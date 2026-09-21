// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { TerminalSessionView } from '../src/features/desktop/TerminalSessionView';
import { WebTerminal } from '../src/features/terminal/WebTerminal';
import * as client from '../src/shared/api/client';
import { NodeItem } from '../src/contracts/types';

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  url: string;
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((ev: any) => void) | null = null;
  onerror: ((err: any) => void) | null = null;
  onclose: (() => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    queueMicrotask(() => {
      if (this.onopen) this.onopen();
    });
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose();
  }
}

const mockNodes: NodeItem[] = [
  {
    id: 'nod_01',
    hostname: 'Node-01-WinMain',
    ipAddress: '192.168.45.101',
    os: 'windows',
    role: 'worker',
    status: 'online',
    schedulable: true,
    observationOnly: false,
    cpuCoresTotal: 16,
    memoryTotalBytes: 64 * 1024 * 1024 * 1024,
  },
  {
    id: 'nod_02',
    hostname: 'Node-02-LinuxGPU',
    ipAddress: '192.168.45.102',
    os: 'linux',
    role: 'worker',
    status: 'online',
    schedulable: true,
    observationOnly: false,
    cpuCoresTotal: 12,
    memoryTotalBytes: 32 * 1024 * 1024 * 1024,
  },
  {
    id: 'nod_04',
    hostname: 'Node-04-WinObserve',
    ipAddress: '192.168.45.225',
    os: 'windows',
    role: 'observer',
    status: 'online',
    schedulable: false,
    observationOnly: true,
    cpuCoresTotal: 4,
    memoryTotalBytes: 8 * 1024 * 1024 * 1024,
  },
  {
    id: 'nod_05',
    hostname: 'Node-05-LinuxUbuntu',
    ipAddress: '192.168.45.105',
    os: 'linux',
    role: 'worker',
    status: 'online',
    schedulable: true,
    observationOnly: false,
    cpuCoresTotal: 8,
    memoryTotalBytes: 16 * 1024 * 1024 * 1024,
  },
];

describe('VF-GM-05: Terminal & Virtual IDE Web Session UX DOM Harness', () => {
  let container: HTMLDivElement;
  let root: Root;
  const originalWs = globalThis.WebSocket;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    globalThis.WebSocket = MockWebSocket as any;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.includes('/terminal-tickets')) {
        return { ticketId: 'tkt_30s_test_token_valid', ptyWsUrl: 'ws://localhost:8080/v1/terminal/ws' };
      }
      return {};
    });
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
    globalThis.WebSocket = originalWs;
  });

  // Helper to set input values in React
  const setInputValue = (input: HTMLInputElement, value: string) => {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    descriptor?.set?.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };

  // ---------------------------------------------------------------------------
  // 1. Initial Sessions and OS to Shell Mapping
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-INIT-SESSION] renders initial tabs and accurately maps node OS to shell type (Catches Mutation 4)', async () => {
    await act(async () => {
      root.render(
        <TerminalSessionView
          nodes={mockNodes}
          defaultNodeId="nod_01"
          defaultWorkspaceId="wsp_core_01"
        />
      );
    });

    // Verify container
    expect(container.querySelector('[data-testid="terminal-session-view-container"]')).not.toBeNull();

    // Verify target node hostname
    const activeHostname = container.querySelector('[data-testid="active-node-hostname"]');
    expect(activeHostname?.textContent).toContain('Node-01-WinMain');

    // Windows node MUST map to POWERSHELL
    const shellTypeBadge = container.querySelector('[data-testid="active-shell-type"]');
    expect(shellTypeBadge?.textContent).toBe('POWERSHELL');

    // Ticket security badge
    const ticketBadge = container.querySelector('[data-testid="pty-ticket-badge"]');
    expect(ticketBadge?.textContent).toContain('30초 암호학적 1회용 PTY 티켓');
  });

  // ---------------------------------------------------------------------------
  // 2. Ticket Issuance & WebSocket Connection
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-TICKET-CONNECT] requests 30s one-time PTY ticket and establishes connected WebSocket state', async () => {
    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_core_01"
          sessionId="sess_test_01"
        />
      );
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 60));
    });

    const statusBadge = container.querySelector('[data-testid="terminal-connection-status"]');
    expect(statusBadge?.textContent).toBe('(connected)');

    const dot = container.querySelector('[data-testid="connection-status-dot"]');
    expect(dot).not.toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 3. Ticket Failure & Honest Error Alerting (Catches Mutation 2)
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-TICKET-RETRY] surfaces honest role="alert" when ticket issuance fails and allows retry (Catches Mutation 2)', async () => {
    vi.spyOn(client, 'apiClient').mockRejectedValueOnce(new Error('403 Forbidden: PTY Ticket Expired or Unauthorized'));

    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_core_01"
          sessionId="sess_test_fail"
        />
      );
      await new Promise((r) => setTimeout(r, 50));
    });

    const errorAlert = container.querySelector('[data-testid="terminal-error-alert"]');
    expect(errorAlert).not.toBeNull();
    expect(errorAlert?.getAttribute('role')).toBe('alert');
    expect(errorAlert?.textContent).toContain('403 Forbidden');

    // Retry button MUST be visible
    const retryBtn = container.querySelector<HTMLButtonElement>('[data-testid="terminal-error-retry-btn"]');
    expect(retryBtn).not.toBeNull();

    // Now mock recovery on retry
    vi.spyOn(client, 'apiClient').mockResolvedValueOnce({
      ticketId: 'tkt_fresh_30s',
      ptyWsUrl: 'ws://localhost:8080/v1/terminal/ws',
    });

    await act(async () => {
      retryBtn!.click();
      await new Promise((r) => setTimeout(r, 50));
    });

    // Error alert MUST clear upon successful reconnection
    expect(container.querySelector('[data-testid="terminal-error-alert"]')).toBeNull();
    const statusBadge = container.querySelector('[data-testid="terminal-connection-status"]');
    expect(statusBadge?.textContent).toBe('(connected)');
  });

  // ---------------------------------------------------------------------------
  // 4. Disconnected Command Submission Rejection (Catches Mutation 3)
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-OFFLINE-REJECTION] rejects terminal command with role="alert" when disconnected without fake exit codes (Catches Mutation 3)', async () => {
    // Fail initial connection to leave terminal disconnected/error
    vi.spyOn(client, 'apiClient').mockRejectedValue(new Error('503 Service Unavailable'));

    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_core_01"
          sessionId="sess_offline"
        />
      );
      await new Promise((r) => setTimeout(r, 50));
    });

    const input = container.querySelector<HTMLInputElement>('[data-testid="terminal-command-input"]');
    const form = container.querySelector<HTMLFormElement>('[data-testid="terminal-command-form"]');
    expect(input).not.toBeNull();
    expect(form).not.toBeNull();

    await act(async () => {
      setInputValue(input!, 'cat /etc/shadow');
      form!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });

    // Disconnected command alert MUST appear with role="alert"
    const cmdAlert = container.querySelector('[data-testid="terminal-disconnected-cmd-alert"]');
    expect(cmdAlert).not.toBeNull();
    expect(cmdAlert?.getAttribute('role')).toBe('alert');
    expect(cmdAlert?.textContent).toContain('명령 \'cat /etc/shadow\'을(를) 전송할 수 없습니다');
  });

  // ---------------------------------------------------------------------------
  // 5. Accessible Screen-Reader Text Log View
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-A11Y-VIEW] toggles accessible screen-reader text log view with role="region"', async () => {
    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_core_01"
          sessionId="sess_a11y"
        />
      );
      await new Promise((r) => setTimeout(r, 50));
    });

    const toggleBtn = container.querySelector<HTMLButtonElement>('[data-testid="terminal-toggle-a11y-btn"]');
    expect(toggleBtn).not.toBeNull();
    expect(container.querySelector('[data-testid="terminal-raw-stream"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="terminal-a11y-region"]')).toBeNull();

    // Toggle to accessible view
    await act(async () => {
      toggleBtn!.click();
    });

    const a11yRegion = container.querySelector('[data-testid="terminal-a11y-region"]');
    expect(a11yRegion).not.toBeNull();
    expect(a11yRegion?.getAttribute('role')).toBe('region');
    expect(a11yRegion?.getAttribute('aria-label')).toBe('텍스트 로그 대체 뷰');
    expect(container.querySelector('[data-testid="terminal-a11y-output"]')).not.toBeNull();

    // Toggle back to raw xterm view
    await act(async () => {
      toggleBtn!.click();
    });
    expect(container.querySelector('[data-testid="terminal-a11y-region"]')).toBeNull();
    expect(container.querySelector('[data-testid="terminal-raw-stream"]')).not.toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 6. Observation-Only Node PTY Exclusion Guard (Catches Mutation 1)
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-OBSERVATION-GUARD] disables observation-only Node-04 and rejects PTY session creation (Catches Mutation 1)', async () => {
    const onErrorMock = vi.fn();

    await act(async () => {
      root.render(
        <TerminalSessionView
          nodes={mockNodes}
          defaultNodeId="nod_01"
          onCreateSessionError={onErrorMock}
        />
      );
    });

    // Check dropdown option for Node-04 is disabled
    const node4Option = container.querySelector<HTMLOptionElement>('[data-testid="option-node-nod_04"]');
    expect(node4Option).not.toBeNull();
    expect(node4Option?.disabled).toBe(true);
    expect(node4Option?.textContent).toContain('관측 전용');

    // Simulate attempted invocation to create session on Node-04
    const select = container.querySelector<HTMLSelectElement>('[data-testid="new-session-select"]');
    await act(async () => {
      select!.value = 'terminal:nod_04';
      select!.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // Alert banner MUST appear with role="alert"
    const sessionAlert = container.querySelector('[data-testid="terminal-session-error-alert"]');
    expect(sessionAlert).not.toBeNull();
    expect(sessionAlert?.getAttribute('role')).toBe('alert');
    expect(sessionAlert?.textContent).toContain('관측 전용 노드로 대화형 PTY 세션을 생성할 수 없습니다');
    expect(onErrorMock).toHaveBeenCalledWith(expect.stringContaining('관측 전용'));
  });

  // ---------------------------------------------------------------------------
  // 7. Toggle between PTY Terminal and Monaco IDE Mode
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-SWITCH-IDE] toggles active session between PTY terminal mode and Monaco IDE editor mode', async () => {
    await act(async () => {
      root.render(
        <TerminalSessionView
          nodes={mockNodes}
          defaultNodeId="nod_01"
          projectId="prj_01"
        />
      );
      await new Promise((r) => setTimeout(r, 50));
    });

    // Initially in terminal mode
    expect(container.querySelector('[data-testid="active-terminal-container"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="active-ide-container"]')).toBeNull();

    const switchBtn = container.querySelector<HTMLButtonElement>('[data-testid="switch-mode-btn"]');
    expect(switchBtn).not.toBeNull();
    expect(switchBtn?.textContent).toContain('IDE 모드로 전환');

    // Switch to IDE mode
    await act(async () => {
      switchBtn!.click();
    });

    expect(container.querySelector('[data-testid="active-ide-container"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="active-terminal-container"]')).toBeNull();
    expect(switchBtn?.textContent).toContain('PTY 터미널로 전환');

    // Switch back to Terminal mode
    await act(async () => {
      switchBtn!.click();
    });

    expect(container.querySelector('[data-testid="active-terminal-container"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="active-ide-container"]')).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 8. Session Tab Lifecycle: Creation, Switching, and Closing
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-TAB-LIFECYCLE] creates a new Linux Bash session tab, switches between tabs, and closes tabs', async () => {
    await act(async () => {
      root.render(
        <TerminalSessionView
          nodes={mockNodes}
          defaultNodeId="nod_01"
        />
      );
    });

    // Create a new session on Node-02 (Linux -> Bash)
    const select = container.querySelector<HTMLSelectElement>('[data-testid="new-session-select"]');
    await act(async () => {
      select!.value = 'terminal:nod_02';
      select!.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // Target node should now be Node-02-LinuxGPU
    const activeHostname = container.querySelector('[data-testid="active-node-hostname"]');
    expect(activeHostname?.textContent).toContain('Node-02-LinuxGPU');

    // Shell type MUST be BASH for Linux
    const shellTypeBadge = container.querySelector('[data-testid="active-shell-type"]');
    expect(shellTypeBadge?.textContent).toBe('BASH');

    // Find and close the newly created session
    const closeButtons = container.querySelectorAll<HTMLButtonElement>('[data-testid^="close-session-"]');
    expect(closeButtons.length).toBeGreaterThan(1);

    await act(async () => {
      closeButtons[closeButtons.length - 1].click();
    });

    // Reverted back to remaining session
    expect(container.querySelector('[data-testid="active-node-hostname"]')?.textContent).toContain('Node-01-WinMain');
  });

  // ---------------------------------------------------------------------------
  // 9. Safe Empty State
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-EMPTY-NODES] renders safe empty fallback when cluster nodes array is empty', async () => {
    await act(async () => {
      root.render(<TerminalSessionView nodes={[]} />);
    });

    const emptyNotice = container.querySelector('[data-testid="terminal-empty-nodes-notice"]');
    expect(emptyNotice).not.toBeNull();
    expect(emptyNotice?.textContent).toContain('등록된 클러스터 노드가 없습니다');
  });

  // ---------------------------------------------------------------------------
  // 10. Reconnect with Fresh Ticket
  // ---------------------------------------------------------------------------
  it('[VF-GM-05-RECONNECT-PTY] reconnect button issues fresh 30s ticket and restores connected status', async () => {
    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_core_01"
          sessionId="sess_recon"
        />
      );
      await new Promise((r) => setTimeout(r, 50));
    });

    const reconnectBtn = container.querySelector<HTMLButtonElement>('[data-testid="terminal-reconnect-btn"]');
    expect(reconnectBtn).not.toBeNull();

    const apiClientSpy = vi.spyOn(client, 'apiClient');

    await act(async () => {
      reconnectBtn!.click();
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(apiClientSpy).toHaveBeenCalledWith(
      expect.stringContaining('/v1/workspaces/wsp_core_01/terminal-tickets'),
      expect.objectContaining({ method: 'POST' })
    );

    const statusBadge = container.querySelector('[data-testid="terminal-connection-status"]');
    expect(statusBadge?.textContent).toBe('(connected)');
  });
});
