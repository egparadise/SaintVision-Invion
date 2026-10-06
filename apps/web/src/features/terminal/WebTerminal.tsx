import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/shared/ui/Button';
import { WsTerminalClient } from '@/shared/realtime/ws-terminal';
import { issueTerminalTicket, terminalTicketHandshake } from '@/shared/api/terminalTicket';

export const PLACEHOLDER_COMMAND_ID = '11111111-1111-4111-8111-111111111111';

export function isAuthorizedCommandId(id?: string | null): id is string {
  if (!id || typeof id !== 'string') return false;
  const trimmed = id.trim();
  if (!trimmed || trimmed === PLACEHOLDER_COMMAND_ID) return false;
  return true;
}

export interface WebTerminalProps {
  workspaceId: string;
  sessionId?: string | null;
  commandId?: string | null;
  onClose?: () => void;
  initialConnectionStatus?: WebTerminalConnectionStatus;
  disableAutoConnect?: boolean;
}


export type WebTerminalConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebTerminalConnectionStatusConfigItem {
  label: string;
  dotColor: string;
  colorVar: string;
  textColor: string;
  promptColor: string;
  borderVar: string;
  bgVar: string;
}

export const WEB_TERMINAL_CONNECTION_STATUS_CONFIG = {
  connected: {
    label: 'connected',
    dotColor: 'var(--color-status-online)',
    colorVar: 'var(--color-status-online)',
    textColor: 'var(--color-status-online)',
    promptColor: 'var(--color-brand-primary)',
    borderVar: 'var(--color-status-online)',
    bgVar: 'var(--color-diff-added-bg)',
  },
  connecting: {
    label: 'connecting',
    dotColor: 'var(--color-status-degraded)',
    colorVar: 'var(--color-status-degraded)',
    textColor: 'var(--color-status-degraded)',
    promptColor: 'var(--color-status-degraded)',
    borderVar: 'var(--color-status-degraded)',
    bgVar: 'var(--color-bg-subtle)',
  },
  disconnected: {
    label: 'disconnected',
    dotColor: 'var(--color-text-muted)',
    colorVar: 'var(--color-text-muted)',
    textColor: 'var(--color-text-muted)',
    promptColor: 'var(--color-text-muted)',
    borderVar: 'var(--color-border-subtle)',
    bgVar: 'var(--color-bg-subtle)',
  },
  error: {
    label: 'error',
    dotColor: 'var(--color-status-offline)',
    colorVar: 'var(--color-status-offline)',
    textColor: 'var(--color-status-offline)',
    promptColor: 'var(--color-status-offline)',
    borderVar: 'var(--color-status-offline)',
    bgVar: 'var(--color-risk-l3-bg)',
  },
} as const satisfies Record<WebTerminalConnectionStatus, WebTerminalConnectionStatusConfigItem>;

export const WEB_TERMINAL_CONNECTION_STATUS_FALLBACK: WebTerminalConnectionStatusConfigItem = {
  label: 'UNKNOWN',
  dotColor: 'var(--color-status-unknown)',
  colorVar: 'var(--color-status-unknown)',
  textColor: 'var(--color-status-unknown)',
  promptColor: 'var(--color-status-unknown)',
  borderVar: 'var(--color-status-unknown)',
  bgVar: 'var(--color-bg-subtle)',
};

export function getWebTerminalConnectionStatusConfig(
  status?: string | null
): WebTerminalConnectionStatusConfigItem {
  if (
    typeof status === 'string' &&
    Object.hasOwn(WEB_TERMINAL_CONNECTION_STATUS_CONFIG, status)
  ) {
    return WEB_TERMINAL_CONNECTION_STATUS_CONFIG[status as WebTerminalConnectionStatus];
  }
  const raw = status !== undefined && status !== null ? String(status).trim() : '';
  return {
    ...WEB_TERMINAL_CONNECTION_STATUS_FALLBACK,
    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',
  };
}

export const WebTerminal: React.FC<WebTerminalProps> = ({
  workspaceId,
  sessionId,
  commandId,
  onClose,
  initialConnectionStatus,
  disableAutoConnect,
}) => {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(sessionId || null);
  const [terminalOutput, setTerminalOutput] = useState<string[]>([
    `SaintVision Web Terminal PTY (Workspace: ${workspaceId || '미지정'})`,
    '대기 중: 승인된 실행 명령(commandId) 및 30초 일회용 티켓 검증 대기...',
    '------------------------------------------------------------',
  ]);
  const [currentInput, setCurrentInput] = useState('');
  const [isAccessibleView, setIsAccessibleView] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<WebTerminalConnectionStatus>(initialConnectionStatus || 'disconnected');

  useEffect(() => {
    if (initialConnectionStatus !== undefined) {
      setConnectionStatus(initialConnectionStatus);
    }
  }, [initialConnectionStatus]);
  const [lastError, setLastError] = useState<string | null>(null);
  const [disconnectedCmdAlert, setDisconnectedCmdAlert] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<WsTerminalClient | null>(null);

  useEffect(() => {
    if (disableAutoConnect) return;
    let active = true;
    const wsProtocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = typeof window !== 'undefined' && window.location.port === '3000' ? '127.0.0.1:8080' : (typeof window !== 'undefined' ? window.location.host : '127.0.0.1:8080');

    const initTerminal = async () => {
      // Security Invariant: PTY ticket is an authorized execution credential.
      // If there is no real authorized commandId, do NOT request a ticket at all (zero network calls).
      if (!isAuthorizedCommandId(commandId)) {
        setConnectionStatus('disconnected');
        setLastError(null);
        setTerminalOutput((prev) => [
          ...prev,
          '⚠️ [승인 실행 필요]: 유효한 승인 명령 신원(commandId)이 지정되지 않았습니다.',
          '보안 정책: 백엔드 티켓 발급 요청(POST /terminal-tickets) 및 WebSocket 연결을 수행하지 않고 중단했습니다.',
          '상위 파이프라인에서 승인된 실행(Approved Execution)을 선택하십시오. (위조 식별자 합성 방지)',
        ]);
        return;
      }

      try {
        setConnectionStatus('connecting');
        setLastError(null);
        setTerminalOutput((prev) => [
          ...prev,
          `[인계] 제어 평면(/v1/workspaces/${workspaceId}/terminal-tickets)에서 30초 일회용 PTY 티켓 발급 요청 중...`,
        ]);
        // Canonical TerminalTicketInput: strictly requires authorized commandId
        const ticketData = await issueTerminalTicket(workspaceId, { commandId });
        if (!active) return;
        setActiveSessionId(ticketData.sessionId);

        const handshake = terminalTicketHandshake(ticketData);
        const finalWsUrl = `${wsProtocol}//${wsHost}${handshake.websocketPath}`;

        // SECURITY INVARIANT: NEVER log ticketData.ticket or its slice/prefix!
        setTerminalOutput((prev) => [
          ...prev,
          '[확인] 30초 일회용 티켓 발급 완료 (유효기간: 30초). PTY WebSocket 연결 시도 중...',
        ]);

        const client = new WsTerminalClient(
          finalWsUrl,
          (data) => {
            const lines = data.split(/\r?\n/).filter((l) => l.length > 0);
            if (lines.length > 0) {
              setTerminalOutput((prev) => [...prev, ...lines]);
            }
          },
          (status) => {
            if (active) {
              setConnectionStatus(status);
              if (status === 'connected') {
                setLastError(null);
                setDisconnectedCmdAlert(null);
                // ONLY append Connected message and shell prompt after connection is actually established!
                setTerminalOutput((prev) => [
                  ...prev,
                  'Connected via secure WebSocket with 30s one-time ticket.',
                  `saintvision@${workspaceId}:~$ `,
                ]);
              }
            }
          }
        );

        clientRef.current = client;
        client.connect(handshake.authFrame.ticket);
      } catch (err: any) {
        if (!active) return;
        const msg = err?.message || String(err);
        setConnectionStatus('error');
        setLastError(msg);
        setTerminalOutput((prev) => [
          ...prev,
          `❌ [티켓 발급 실패]: ${msg}`,
          '보안 거부: 승인되지 않은 명령이거나 실행 권한이 만료되었습니다. (가상 터미널 표출 차단)',
        ]);
      }
    };

    initTerminal();

    return () => {
      active = false;
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
  }, [sessionId, workspaceId, commandId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminalOutput]);

  const handleReconnect = async () => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    const wsProtocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = typeof window !== 'undefined' && window.location.port === '3000' ? '127.0.0.1:8080' : (typeof window !== 'undefined' ? window.location.host : '127.0.0.1:8080');

    if (!isAuthorizedCommandId(commandId)) {
      setConnectionStatus('disconnected');
      setDisconnectedCmdAlert('승인된 실행(commandId)이 선택되지 않아 새 PTY 티켓을 발급받을 수 없습니다. 상단에서 실행을 선택하십시오.');
      return;
    }

    try {
      setConnectionStatus('connecting');
      setLastError(null);
      setDisconnectedCmdAlert(null);
      setTerminalOutput((prev) => [
        ...prev,
        `[안내] 신규 30초 일회용 티켓으로 PTY WebSocket 재접속을 요청합니다...`,
      ]);
      const ticketData = await issueTerminalTicket(workspaceId, { commandId });
      setActiveSessionId(ticketData.sessionId);
      const handshake = terminalTicketHandshake(ticketData);
      const finalWsUrl = `${wsProtocol}//${wsHost}${handshake.websocketPath}`;

      // SECURITY INVARIANT: NEVER log ticketData.ticket or its slice/prefix!
      setTerminalOutput((prev) => [
        ...prev,
        '[확인] 신규 30초 일회용 티켓 발급 완료. 재연결 진행 중...',
      ]);

      const client = new WsTerminalClient(
        finalWsUrl,
        (data) => {
          const lines = data.split(/\r?\n/).filter((l) => l.length > 0);
          if (lines.length > 0) {
            setTerminalOutput((prev) => [...prev, ...lines]);
          }
        },
        (status) => {
          setConnectionStatus(status);
          if (status === 'connected') {
            setLastError(null);
            setDisconnectedCmdAlert(null);
            setTerminalOutput((prev) => [
              ...prev,
              'Connected via secure WebSocket with 30s one-time ticket.',
              `saintvision@${workspaceId}:~$ `,
            ]);
          }
        }
      );

      clientRef.current = client;
      client.connect(handshake.authFrame.ticket);
    } catch (err: any) {
      const msg = err?.message || String(err);
      setConnectionStatus('error');
      setLastError(msg);
      setTerminalOutput((prev) => [
        ...prev,
        `❌ [재접속 실패]: ${msg}`,
      ]);
    }
  };

  const handleCommandSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentInput.trim()) return;

    const cmd = currentInput;
    setCurrentInput('');

    // Send command to live WebSocket
    if (clientRef.current && connectionStatus === 'connected') {
      clientRef.current.sendInput(cmd + '\r');
      setDisconnectedCmdAlert(null);
    } else {
      // Truthful error notice if disconnected (Zero-Mock: never fabricate fake exit codes)
      const alertMsg = `PTY 터미널 세션이 오프라인 상태(${connectionStatus})입니다. 명령 '${cmd}'을(를) 전송할 수 없습니다. [재접속] 버튼으로 새 티켓을 발급받으세요.`;
      setDisconnectedCmdAlert(alertMsg);
      setTerminalOutput((prev) => [
        ...prev,
        `saintvision@${workspaceId}:~$ ${cmd}`,
        `🛑 [전송 불가]: ${alertMsg}`,
        `saintvision@${workspaceId}:~$ `,
      ]);
    }
  };

  return (
    <div
      data-testid="web-terminal-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '520px',
        backgroundColor: 'var(--color-bg-canvas)',
        color: 'var(--color-text-primary)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border-subtle)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-lg)',
      }}
    >
      {/* Terminal Title Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 16px',
          backgroundColor: 'var(--color-bg-surface)',
          borderBottom: '1px solid var(--color-border-subtle)',
          fontSize: '0.8125rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {(() => {
            const statusConfig = getWebTerminalConnectionStatusConfig(connectionStatus);
            return (
              <>
                <span
                  data-testid="connection-status-dot"
                  aria-hidden="true"
                  style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: statusConfig.dotColor,
                  }}
                />
                <span>
                  PTY Web Terminal: <code>{workspaceId}</code>{' '}
                  <span
                    data-testid="terminal-session-id"
                    style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}
                  >
                    (세션: {activeSessionId || '미발급'})
                  </span>{' '}
                  <span
                    data-testid="terminal-connection-status"
                    role="status"
                    aria-live="polite"
                    style={{
                      fontSize: '0.75rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      backgroundColor: statusConfig.bgVar,
                      color: statusConfig.colorVar,
                      border: `1px solid ${statusConfig.borderVar}`,
                    }}
                  >
                    ({statusConfig.label})
                  </span>
                </span>
              </>
            );
          })()}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Button
            data-testid="terminal-reconnect-btn"
            variant="secondary"
            size="sm"
            aria-disabled={!isAuthorizedCommandId(commandId)}
            aria-describedby={!isAuthorizedCommandId(commandId) ? 'terminal-command-required-notice' : undefined}
            title={!isAuthorizedCommandId(commandId) ? '승인된 실행(commandId)이 필요합니다 (사용자 조치 필요).' : '재접속 (새 티켓)'}
            style={{ fontSize: '0.75rem', padding: '2px 8px' }}
            onClick={handleReconnect}
          >
            🔄 재접속 (새 티켓)
          </Button>
          <Button
            data-testid="terminal-toggle-a11y-btn"
            variant="ghost"
            size="sm"
            style={{ color: 'var(--color-text-primary)', fontSize: '0.75rem', padding: '2px 8px' }}
            onClick={() => setIsAccessibleView((prev) => !prev)}
          >
            {isAccessibleView ? '💻 xterm 터미널 보기' : '♿ 스크린리더 텍스트 뷰'}
          </Button>
          {onClose && (
            <Button
              data-testid="terminal-close-btn"
              variant="ghost"
              size="sm"
              style={{ color: 'var(--color-status-offline)', fontSize: '0.75rem', padding: '2px 8px' }}
              onClick={onClose}
            >
              닫기
            </Button>
          )}
        </div>
      </div>

      {/* Missing Authorized Command Notice Banner */}
      {!isAuthorizedCommandId(commandId) && (
        <div
          id="terminal-command-required-notice"
          role="alert"
          data-testid="terminal-command-required-notice"
          style={{
            padding: '8px 16px',
            backgroundColor: 'var(--color-bg-subtle)',
            color: 'var(--color-status-degraded)',
            fontSize: '0.8125rem',
            borderBottom: '1px solid var(--color-status-degraded)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
          }}
        >
          <span>
            ⚠️ <strong>[승인 명령 부재]</strong> 유효한 승인 명령 신원(commandId)이 없어 30초 일회용 PTY 티켓을 발급하지 않았습니다. (위조 식별자 합성 방지)
            <br />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
              👉 <strong>[사용자 조치 필요]</strong>: 상단 '승인 실행(Run)' 드롭다운에서 실행을 선택하거나 '승인 명령 ID' 입력창에 유효한 commandId(예: cmd_...)를 입력하십시오.
            </span>
          </span>
        </div>
      )}

      {/* Ticket / Connection Error Alert Banner */}
      {connectionStatus === 'error' && (
        <div
          role="alert"
          data-testid="terminal-error-alert"
          style={{
            padding: '8px 16px',
            backgroundColor: 'var(--color-risk-l3-bg)',
            color: 'var(--color-status-offline)',
            fontSize: '0.8125rem',
            borderBottom: '1px solid var(--color-risk-l3-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>
            ❌ {lastError?.includes('AUTH-0070')
              ? '[AUTH-0070 권한 없음 / 실행 만료]: 유효한 승인 실행이 아니거나 세션이 만료되었습니다. (티켓 발급 거부) 🛠️ [운영자 조치 필요]: 관리자/운영자에게 해당 실행(Run) 승인 또는 리스 연장을 요청하십시오.'
              : lastError?.includes('VAL-0002')
              ? '[VAL-0002 계약 검증 실패]: 요청 계약 형식이 유효하지 않습니다.'
              : (lastError || '30초 일회용 PTY 티켓 발급 또는 연결 실패')}
          </span>
          <button
            type="button"
            data-testid="terminal-error-retry-btn"
            onClick={handleReconnect}
            disabled={!isAuthorizedCommandId(commandId)}
            aria-disabled={!isAuthorizedCommandId(commandId)}
            aria-describedby={!isAuthorizedCommandId(commandId) ? 'terminal-command-required-notice' : undefined}
            title={!isAuthorizedCommandId(commandId) ? '승인된 실행(commandId)을 선택해야 재시도할 수 있습니다 (사용자 조치 필요).' : '새 티켓으로 재시도'}
            style={{
              padding: '2px 8px',
              backgroundColor: isAuthorizedCommandId(commandId) ? 'var(--color-status-offline-bg)' : 'var(--color-bg-subtle)',
              color: isAuthorizedCommandId(commandId) ? 'var(--color-brand-primary-fg)' : 'var(--color-text-muted)',
              border: 'none',
              borderRadius: '4px',
              cursor: isAuthorizedCommandId(commandId) ? 'pointer' : 'not-allowed',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            {isAuthorizedCommandId(commandId) ? '새 티켓으로 재시도' : '실행 선택 후 재시도'}
          </button>
        </div>
      )}

      {/* Disconnected Command Rejection Alert Banner */}
      {disconnectedCmdAlert && (
        <div
          role="alert"
          data-testid="terminal-disconnected-cmd-alert"
          style={{
            padding: '6px 16px',
            backgroundColor: 'var(--color-bg-subtle)',
            color: 'var(--color-status-degraded)',
            fontSize: '0.75rem',
            borderBottom: '1px solid var(--color-status-degraded)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>⚠️ {disconnectedCmdAlert}</span>
          <button
            type="button"
            onClick={() => setDisconnectedCmdAlert(null)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-status-degraded)',
              cursor: 'pointer',
              fontSize: '0.75rem',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Terminal Content Area */}
      {isAccessibleView ? (
        <div
          role="region"
          data-testid="terminal-a11y-region"
          aria-label="텍스트 로그 대체 뷰"
          tabIndex={0}
          style={{
            flex: 1,
            padding: '16px',
            overflowY: 'auto',
            backgroundColor: 'var(--color-bg-canvas)',
            color: 'var(--color-text-primary)',
            fontFamily: 'sans-serif',
            fontSize: '0.875rem',
            lineHeight: 1.6,
          }}
        >
          <h4 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>
            접근성 텍스트 로그 대체 뷰 (WCAG AA 대응)
          </h4>
          <p style={{ color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            스크린리더 및 텍스트 브라우저를 위한 순수 텍스트 로그 출력 모드입니다.
          </p>
          <pre
            data-testid="terminal-a11y-output"
            style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.8125rem' }}
          >
            {terminalOutput.join('\n')}
          </pre>
        </div>
      ) : (
        <div
          data-testid="terminal-raw-stream"
          style={{
            flex: 1,
            padding: '16px',
            overflowY: 'auto',
            fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',
            fontSize: '0.8125rem',
            lineHeight: 1.5,
          }}
        >
          {terminalOutput.map((line, idx) => (
            <div key={idx}>{line}</div>
          ))}
          <form
            data-testid="terminal-command-form"
            onSubmit={handleCommandSubmit}
            style={{ display: 'flex', marginTop: '4px' }}
          >
            <span style={{ color: getWebTerminalConnectionStatusConfig(connectionStatus).promptColor }}>
              {connectionStatus === 'connected'
                ? `saintvision@${workspaceId || 'terminal'}:~$ `
                : `[${connectionStatus}] $ `}
              &nbsp;
            </span>
            <input
              data-testid="terminal-command-input"
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              autoFocus
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                border: 'none',
                color: 'var(--color-text-primary)',
                fontFamily: 'inherit',
                fontSize: 'inherit',
              }}
            />
          </form>
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
};
