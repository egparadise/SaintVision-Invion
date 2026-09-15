import React, { useState } from 'react';
import { WebTerminal } from '@/features/terminal/WebTerminal';
import { MonacoWorkspaceEditor } from '@/features/editor/MonacoWorkspaceEditor';
import { NodeItem } from '@/contracts/types';
import { TerminalShellType } from '@/contracts/virtualFabric';

export interface TerminalSessionViewProps {
  nodes: NodeItem[];
  defaultNodeId?: string;
  defaultWorkspaceId?: string;
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
  nodes,
  defaultNodeId = 'nod_01JABCDEF01',
  defaultWorkspaceId = 'wsp_01JABCDE001',
}) => {
  const [sessions, setSessions] = useState<ActiveSessionTab[]>([
    {
      id: 'sess_win_01',
      title: 'Node-01 (PowerShell)',
      nodeId: defaultNodeId,
      shellType: 'powershell',
      mode: 'terminal',
      workspaceId: defaultWorkspaceId,
    },
    {
      id: 'sess_linux_05',
      title: 'Node-05 (Bash / Linux)',
      nodeId: 'nod_01JABCDEF05',
      shellType: 'bash',
      mode: 'terminal',
      workspaceId: 'wsp_01JABCDE002',
    },
  ]);

  const [activeSessionId, setActiveSessionId] = useState<string>(sessions[0].id);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];
  const activeNode = nodes.find((n) => n.id === activeSession.nodeId) || nodes[0];

  const handleCreateSession = (mode: 'terminal' | 'ide', targetNodeId: string) => {
    const node = nodes.find((n) => n.id === targetNodeId) || nodes[0];
    const isWin = node.os === 'windows';
    const shellType: TerminalShellType = isWin ? 'powershell' : 'bash';
    const newId = `sess_${Date.now().toString(36)}`;
    const newTab: ActiveSessionTab = {
      id: newId,
      title: `${node.hostname} (${mode === 'ide' ? 'IDE' : shellType})`,
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

  return (
    <div
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
            {nodes.map((n) => (
              <option key={`term:${n.id}`} value={`terminal:${n.id}`}>
                ⌨️ 터미널: {n.hostname} ({n.os === 'windows' ? 'PowerShell' : 'Bash'})
              </option>
            ))}
            <option value={`ide:${defaultNodeId}`}>📝 웹 IDE (Monaco Workspace Editor)</option>
          </select>
        </div>
      </div>

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
            대상 노드: <strong style={{ color: 'var(--color-text-primary)' }}>{activeNode.hostname}</strong> ({activeNode.ipAddress || '127.0.0.1'})
          </span>
          <span>
            쉘 유형: <strong style={{ color: '#38bdf8' }}>{activeSession.shellType.toUpperCase()}</strong>
          </span>
          <span>
            인증: <strong>30초 암호학적 1회용 PTY 티켓 (mTLS 격리)</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={() => {
              const newMode = activeSession.mode === 'terminal' ? 'ide' : 'terminal';
              setSessions((prev) =>
                prev.map((s) => (s.id === activeSession.id ? { ...s, mode: newMode } : s))
              );
            }}
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
          <div style={{ flex: 1, padding: '16px', overflow: 'auto' }}>
            <WebTerminal
              workspaceId={activeSession.workspaceId}
              sessionId={activeSession.id}
            />
          </div>
        ) : (
          <MonacoWorkspaceEditor
            workspaceId={activeSession.workspaceId}
            projectId="prj_01JABCDE"
          />
        )}
      </div>
    </div>
  );
};
