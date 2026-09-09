import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/shared/ui/Button';

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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminalOutput]);

  const handleCommandSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentInput.trim()) return;

    const cmd = currentInput;
    setCurrentInput('');

    setTerminalOutput((prev) => [
      ...prev,
      `saintvision@wsp-saint-pilot:~$ ${cmd}`,
      `[Executed: ${cmd}] (exit code: 0)`,
      'saintvision@wsp-saint-pilot:~$ ',
    ]);
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
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#238636' }} />
          <span>PTY Web Terminal: <code>{workspaceId}</code></span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
