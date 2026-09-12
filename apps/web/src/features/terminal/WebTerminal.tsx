import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/shared/ui/Button';
import { WsTerminalClient } from '@/shared/realtime/ws-terminal';
import { apiClient, isRouteNotFoundError } from '@/shared/api/client';

export interface WebTerminalProps {
  workspaceId: string;
  sessionId: string;
  onClose?: () => void;
}

export const WebTerminal: React.FC<WebTerminalProps> = ({
  workspaceId,
  sessionId,
  onClose,
}) => {
  const [terminalOutput, setTerminalOutput] = useState<string[]>([
    'SaintVision Web Terminal PTY (Session: ' + sessionId + ')',
    'Connected via secure WebSocket with 30s one-time ticket.',
    'Type commands below or use the accessibility text log view.',
    '------------------------------------------------------------',
    'saintvision@wsp-saint-pilot:~$ ',
  ]);
  const [currentInput, setCurrentInput] = useState('');
  const [isAccessibleView, setIsAccessibleView] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const bottomRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<WsTerminalClient | null>(null);

  useEffect(() => {
    let active = true;
    const wsProtocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = typeof window !== 'undefined' && window.location.port === '3000' ? '127.0.0.1:8080' : (typeof window !== 'undefined' ? window.location.host : '127.0.0.1:8080');
    const wsUrl = `${wsProtocol}//${wsHost}/v1/terminal/ws`;

    const initTerminal = async () => {
      try {
        setConnectionStatus('connecting');
        setTerminalOutput((prev) => [
          ...prev,
          `[인계] 제어 평면(/v1/workspaces/${workspaceId}/terminal-tickets)에서 30초 일회용 PTY 티켓 발급 요청 중...`,
        ]);
        let ticketData: { ticketId: string; ptyWsUrl?: string };
        try {
          ticketData = await apiClient<{ ticketId: string; ptyWsUrl?: string }>(
            `/v1/workspaces/${workspaceId}/terminal-tickets`,
            {
              method: 'POST',
              body: JSON.stringify({ workspaceId, sessionId }),
            }
          );
        } catch (err: any) {
          if (isRouteNotFoundError(err)) {
            ticketData = await apiClient<{ ticketId: string; ptyWsUrl?: string }>(
              '/v1/terminal/tickets',
              {
                method: 'POST',
                body: JSON.stringify({ workspaceId, sessionId }),
              }
            );
          } else {
            throw err;
          }
        }
        const ticket = ticketData.ticketId;
        if (!active) return;

        setTerminalOutput((prev) => [
          ...prev,
          `[확인] 일회용 티켓(${ticket.slice(0, 12)}...) 획득 성공 (유효기간: 30초). PTY 세션 연결 중...`,
        ]);

        const client = new WsTerminalClient(
          wsUrl,
          (data) => {
            const lines = data.split(/\r?\n/).filter((l) => l.length > 0);
            if (lines.length > 0) {
              setTerminalOutput((prev) => [...prev, ...lines]);
            }
          },
          (status) => {
            if (active) setConnectionStatus(status);
          }
        );

        clientRef.current = client;
        client.connect(ticket);
      } catch (err: any) {
        if (!active) return;
        setConnectionStatus('error');
        setTerminalOutput((prev) => [
          ...prev,
          `❌ [티켓 발급 실패]: ${err.message || err}. 재접속 버튼으로 다시 시도하십시오.`,
        ]);
      }
    };

    initTerminal();

    return () => {
      active = false;
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
  }, [sessionId, workspaceId]);

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
    const wsUrl = `${wsProtocol}//${wsHost}/v1/terminal/ws`;

    try {
      setConnectionStatus('connecting');
      setTerminalOutput((prev) => [
        ...prev,
        `[안내] 신규 30초 일회용 티켓으로 PTY WebSocket 재접속을 요청합니다...`,
      ]);
      let ticketData: { ticketId: string; ptyWsUrl?: string };
      try {
        ticketData = await apiClient<{ ticketId: string; ptyWsUrl?: string }>(
          `/v1/workspaces/${workspaceId}/terminal-tickets`,
          {
            method: 'POST',
            body: JSON.stringify({ workspaceId, sessionId }),
          }
        );
      } catch (err: any) {
        if (isRouteNotFoundError(err)) {
          ticketData = await apiClient<{ ticketId: string; ptyWsUrl?: string }>(
            '/v1/terminal/tickets',
            {
              method: 'POST',
              body: JSON.stringify({ workspaceId, sessionId }),
            }
          );
        } else {
          throw err;
        }
      }
      const ticket = ticketData.ticketId;

      setTerminalOutput((prev) => [
        ...prev,
        `[확인] 신규 일회용 티켓(${ticket.slice(0, 12)}...) 획득 완료. 재연결 진행.`,
      ]);

      const client = new WsTerminalClient(
        wsUrl,
        (data) => {
          const lines = data.split(/\r?\n/).filter((l) => l.length > 0);
          if (lines.length > 0) {
            setTerminalOutput((prev) => [...prev, ...lines]);
          }
        },
        (status) => {
          setConnectionStatus(status);
        }
      );

      clientRef.current = client;
      client.connect(ticket);
    } catch (err: any) {
      setConnectionStatus('error');
      setTerminalOutput((prev) => [
        ...prev,
        `❌ [재접속 실패]: ${err.message || err}`,
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
    } else {
      // Truthful error notice if disconnected (Zero-Mock: never fabricate fake exit codes)
      setTerminalOutput((prev) => [
        ...prev,
        `saintvision@wsp-saint-pilot:~$ ${cmd}`,
        `🛑 [전송 불가]: PTY 터미널 세션이 오프라인 상태(${connectionStatus})입니다. [재접속] 버튼을 눌러 새 티켓으로 접속하세요.`,
        'saintvision@wsp-saint-pilot:~$ ',
      ]);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '520px',
        backgroundColor: '#0d1117',
        color: '#c9d1d9',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid #30363d',
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
          backgroundColor: '#161b22',
          borderBottom: '1px solid #30363d',
          fontSize: '0.8125rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor:
                connectionStatus === 'connected'
                  ? '#238636'
                  : connectionStatus === 'connecting'
                  ? '#d29922'
                  : '#8b949e',
            }}
          />
          <span>
            PTY Web Terminal: <code>{workspaceId}</code>{' '}
            <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>({connectionStatus})</span>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Button
            variant="secondary"
            size="sm"
            style={{ fontSize: '0.75rem', padding: '2px 8px' }}
            onClick={handleReconnect}
          >
            🔄 재접속 (새 티켓)
          </Button>
          <Button
            variant="ghost"
            size="sm"
            style={{ color: '#c9d1d9', fontSize: '0.75rem', padding: '2px 8px' }}
            onClick={() => setIsAccessibleView((prev) => !prev)}
          >
            {isAccessibleView ? '💻 xterm 터미널 보기' : '♿ 스크린리더 텍스트 뷰'}
          </Button>
          {onClose && (
            <Button
              variant="ghost"
              size="sm"
              style={{ color: '#f85149', fontSize: '0.75rem', padding: '2px 8px' }}
              onClick={onClose}
            >
              닫기
            </Button>
          )}
        </div>
      </div>

      {/* Terminal Content Area */}
      {isAccessibleView ? (
        <div
          role="region"
          aria-label="텍스트 로그 대체 뷰"
          tabIndex={0}
          style={{
            flex: 1,
            padding: '16px',
            overflowY: 'auto',
            backgroundColor: '#090d16',
            color: '#f0f6fc',
            fontFamily: 'sans-serif',
            fontSize: '0.875rem',
            lineHeight: 1.6,
          }}
        >
          <h4 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>
            접근성 텍스트 로그 대체 뷰 (WCAG AA 대응)
          </h4>
          <p style={{ color: '#8b949e', marginBottom: '16px' }}>
            스크린리더 및 텍스트 브라우저를 위한 순수 텍스트 로그 출력 모드입니다.
          </p>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.8125rem' }}>
            {terminalOutput.join('\n')}
          </pre>
        </div>
      ) : (
        <div
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
          <form onSubmit={handleCommandSubmit} style={{ display: 'flex', marginTop: '4px' }}>
            <span style={{ color: '#58a6ff' }}>saintvision@wsp-saint-pilot:~$ &nbsp;</span>
            <input
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              autoFocus
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                border: 'none',
                color: '#f0f6fc',
                outline: 'none',
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
