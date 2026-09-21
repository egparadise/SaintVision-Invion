import React, { useMemo, useState } from 'react';
import { WebTerminal } from '@/features/terminal/WebTerminal';
import { MonacoWorkspaceEditor } from '@/features/editor/MonacoWorkspaceEditor';
import { NodeItem } from '@/contracts/types';
import { TerminalShellType } from '@/contracts/virtualFabric';

export interface TerminalSessionViewProps {
  nodes?: NodeItem[];
  defaultNodeId?: string;
  defaultWorkspaceId?: string;
  projectId?: string;
  initialMode?: 'terminal' | 'ide';
  commandId?: string | null;
  onCreateSessionError?: (err: string) => void;
}

interface ActiveSessionTab {
  id: string;
  title: string;
  nodeId: string;
  shellType: TerminalShellType;
  mode: 'terminal' | 'ide';
  workspaceId: string;
}

export const TerminalSessionView: React.FC<TerminalSessionViewProps> = ({
  nodes = [],
  defaultNodeId,
  defaultWorkspaceId = 'wsp_01JABCDE001',
  projectId = 'prj_01JABCDE',
  initialMode = 'terminal',
  commandId,
  onCreateSessionError,
}) => {
  const [activeCommandId, setActiveCommandId] = useState<string>(commandId ?? '');

  React.useEffect(() => {
    if (commandId !== undefined) {
      setActiveCommandId(commandId ?? '');
    }
  }, [commandId]);
  if (!nodes || nodes.length === 0) {
    return (
      <div
        data-testid="terminal-session-view-container"
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          backgroundColor: 'var(--color-bg-surface, #0f172a)',
          color: 'var(--color-text-primary, #f8fafc)',
        }}
      >
        <div
          data-testid="terminal-empty-nodes-notice"
          role="status"
          style={{
            padding: '16px',
            backgroundColor: '#1e293b',
            color: '#94a3b8',
            fontSize: '0.875rem',
            borderBottom: '1px solid #334155',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span data-testid="terminal-no-nodes-notice">
            ℹ️ 등록된 클러스터 노드가 없습니다. PTY 터미널 세션을 생성할 수 없습니다.
          </span>
        </div>
      </div>
    );
  }

  // Filter eligible (schedulable & non-observation) nodes for initial sessions
  const eligibleNodes = nodes.filter((n) => !n.observationOnly && n.schedulable !== false);
  const primaryNode =
    (defaultNodeId ? nodes.find((n) => n.id === defaultNodeId) : null) ||
    eligibleNodes[0] ||
    nodes[0];

  const initialSessions: ActiveSessionTab[] = useMemo(() => {
    const list: ActiveSessionTab[] = [];
    const isWin = primaryNode.os === 'windows';
    const shell: TerminalShellType = isWin ? 'powershell' : 'bash';

    list.push({
      id: 'sess_init_01',
      title: `${primaryNode.hostname} (${initialMode === 'ide' ? 'IDE' : isWin ? 'PowerShell' : 'Bash'})`,
      nodeId: primaryNode.id,
      shellType: shell,
      mode: initialMode,
      workspaceId: defaultWorkspaceId,
    });

    // Add secondary linux session if another eligible node exists
    const secondaryNode = eligibleNodes.find((n) => n.id !== primaryNode.id);
    if (secondaryNode) {
      const secIsWin = secondaryNode.os === 'windows';
      list.push({
        id: 'sess_init_02',
        title: `${secondaryNode.hostname} (${secIsWin ? 'PowerShell' : 'Bash'})`,
        nodeId: secondaryNode.id,
        shellType: secIsWin ? 'powershell' : 'bash',
        mode: 'terminal',
        workspaceId: `${defaultWorkspaceId}_02`,
      });
    }

    return list;
  }, [primaryNode, defaultWorkspaceId, initialMode, eligibleNodes]);

  const [sessions, setSessions] = useState<ActiveSessionTab[]>(initialSessions);
  const [activeSessionId, setActiveSessionId] = useState<string>(
    initialSessions[0]?.id || 'sess_init_01'
  );
  const [sessionError, setSessionError] = useState<string | null>(null);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) || sessions[0] || initialSessions[0];
  const activeNode =
    nodes.find((n) => n.id === activeSession.nodeId) || primaryNode;

  const handleCreateSession = (mode: 'terminal' | 'ide', targetNodeId: string) => {
    const node = nodes.find((n) => n.id === targetNodeId) || nodes[0];

    // Observation-only / unschedulable node guard (ADR-028 & ADR-041)
    if (mode === 'terminal' && (node.observationOnly || node.schedulable === false)) {
      const err = `노드 ${node.hostname}은(는) 관측 전용 노드로 대화형 PTY 세션을 생성할 수 없습니다.`;
      setSessionError(err);
      onCreateSessionError?.(err);
      return;
    }

    setSessionError(null);
    const isWin = node.os === 'windows';
    const shellType: TerminalShellType = isWin ? 'powershell' : 'bash';
    const newId = `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
    const newTab: ActiveSessionTab = {
      id: newId,
      title: `${node.hostname} (${mode === 'ide' ? 'IDE' : isWin ? 'PowerShell' : 'Bash'})`,
      nodeId: node.id,
      shellType,
      mode,
      workspaceId: defaultWorkspaceId,
    };

    setSessions((prev) => [...prev, newTab]);
    setActiveSessionId(newId);
  };

  const handleCloseSession = (id: string) => {
    if (sessions.length <= 1) return;
    const remaining = sessions.filter((s) => s.id !== id);
    setSessions(remaining);
    if (activeSessionId === id) {
      setActiveSessionId(remaining[0].id);
    }
  };

  const handleToggleMode = () => {
    const nextMode = activeSession.mode === 'terminal' ? 'ide' : 'terminal';
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSession.id ? { ...s, mode: nextMode } : s))
    );
  };

  return (
    <div
      data-testid="terminal-session-view-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--color-bg-surface, #0f172a)',
        color: 'var(--color-text-primary, #f8fafc)',
      }}
    >
      {/* Session Top Bar / Tabs */}
      <div
        role="tablist"
        aria-label="PTY 및 IDE 활성 세션 탭"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--color-bg-subtle, #1e293b)',
          borderBottom: '1px solid var(--color-border-subtle, #334155)',
          padding: '0 12px',
          height: '42px',
        }}
      >
        {/* Tabs */}
        <div style={{ display: 'flex', gap: '4px', overflow: 'auto', flex: 1 }}>
          {sessions.map((sess) => {
            const isActive = sess.id === activeSessionId;
            return (
              <div
                key={sess.id}
                role="tab"
                aria-selected={isActive}
                data-testid={`session-tab-${sess.id}`}
                onClick={() => setActiveSessionId(sess.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 12px',
                  backgroundColor: isActive ? 'var(--color-bg-surface, #0f172a)' : 'transparent',
                  borderTop: isActive ? '2px solid var(--color-brand-primary, #3b82f6)' : '2px solid transparent',
                  borderRight: '1px solid var(--color-border-subtle, #334155)',
                  fontSize: '0.8125rem',
                  fontWeight: isActive ? 600 : 500,
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                <span>{sess.mode === 'ide' ? '📝' : sess.shellType === 'powershell' ? '🟦' : '🐧'}</span>
                <span>{sess.title}</span>
                {sessions.length > 1 && (
                  <button
                    type="button"
                    title="세션 종료"
                    data-testid={`close-session-${sess.id}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCloseSession(sess.id);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--color-text-muted, #94a3b8)',
                      cursor: 'pointer',
                      padding: '0 2px',
                      fontSize: '0.75rem',
                    }}
                  >
                    ×
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* New Session Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <select
            data-testid="new-session-select"
            onChange={(e) => {
              if (e.target.value) {
                const [mode, nId] = e.target.value.split(':');
                handleCreateSession(mode as 'terminal' | 'ide', nId);
                e.target.value = '';
              }
            }}
            defaultValue=""
            style={{
              padding: '4px 8px',
              fontSize: '0.75rem',
              borderRadius: '4px',
              backgroundColor: 'var(--color-bg-surface, #0f172a)',
              color: 'inherit',
              border: '1px solid var(--color-border-strong, #475569)',
            }}
          >
            <option value="" disabled>
              ➕ 새 세션 열기...
            </option>
            {nodes.map((n) => {
              const isObs = n.observationOnly || n.schedulable === false;
              return (
                <option
                  key={`term:${n.id}`}
                  value={`terminal:${n.id}`}
                  disabled={isObs}
                  data-testid={`option-node-${n.id}`}
                >
                  ⌨️ 터미널: {n.hostname} ({n.os === 'windows' ? 'PowerShell' : 'Bash'})
                  {isObs ? ' [관측 전용 - PTY 불가]' : ''}
                </option>
              );
            })}
            <option value={`ide:${primaryNode.id}`} data-testid="option-ide-mode">
              📝 웹 IDE (Monaco Workspace Editor)
            </option>
          </select>
        </div>
      </div>



      {/* Observation node error alert */}
      {sessionError && (
        <div
          role="alert"
          data-testid="terminal-session-error-alert"
          style={{
            padding: '8px 16px',
            backgroundColor: '#7f1d1d',
            color: '#fecaca',
            fontSize: '0.8125rem',
            borderBottom: '1px solid #ef4444',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>🚫 {sessionError}</span>
          <button
            type="button"
            onClick={() => setSessionError(null)}
            style={{
              background: 'none',
              border: 'none',
              color: '#fecaca',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Session Header Info */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          backgroundColor: 'rgba(0,0,0,0.2)',
          borderBottom: '1px solid var(--color-border-subtle, #334155)',
          fontSize: '0.75rem',
          color: 'var(--color-text-muted, #94a3b8)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span>
            대상 노드:{' '}
            <strong
              data-testid="active-node-hostname"
              style={{ color: 'var(--color-text-primary, #f8fafc)' }}
            >
              {activeNode.hostname}
            </strong>{' '}
            ({activeNode.ipAddress || '127.0.0.1'})
          </span>
          <span>
            쉘 유형:{' '}
            <strong
              data-testid="active-shell-type"
              style={{ color: activeSession.shellType === 'powershell' ? '#38bdf8' : '#4ade80' }}
            >
              {activeSession.shellType.toUpperCase()}
            </strong>
          </span>
          <span>
            인증:{' '}
            <strong data-testid="pty-ticket-badge" style={{ color: '#fbbf24' }}>
              30초 암호학적 1회용 PTY 티켓 (mTLS 격리)
            </strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '0.6875rem' }}>명령 ID:</span>
            <input
              type="text"
              data-testid="terminal-command-id-input"
              value={activeCommandId}
              onChange={(e) => setActiveCommandId(e.target.value)}
              placeholder="승인 commandId..."
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '4px',
                color: '#f8fafc',
                fontSize: '0.6875rem',
                padding: '2px 6px',
                width: '130px',
              }}
            />
          </div>
          <button
            type="button"
            data-testid="switch-mode-btn"
            onClick={handleToggleMode}
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              color: '#60a5fa',
              fontSize: '0.6875rem',
              cursor: 'pointer',
            }}
          >
            {activeSession.mode === 'terminal' ? '📝 IDE 모드로 전환' : '⌨️ PTY 터미널로 전환'}
          </button>
        </div>
      </div>

      {/* Session Active Body */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {activeSession.mode === 'terminal' ? (
          <div
            data-testid="active-terminal-container"
            style={{ flex: 1, padding: '16px', overflow: 'auto' }}
          >
            <WebTerminal
              workspaceId={activeSession.workspaceId}
              sessionId={activeSession.id}
              commandId={activeCommandId.trim() ? activeCommandId.trim() : undefined}
            />
          </div>
        ) : (
          <div data-testid="active-ide-container" style={{ flex: 1, overflow: 'hidden' }}>
            <MonacoWorkspaceEditor
              workspaceId={activeSession.workspaceId}
              projectId={projectId}
            />
          </div>
        )}
      </div>
    </div>
  );
};

