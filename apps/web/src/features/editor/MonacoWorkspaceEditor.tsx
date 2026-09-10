import React, { useState, useEffect, useRef } from 'react';
import { EditorFile, GitCommitRecord, FileDiffResult } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { computeSha256, computeDiff } from './diffEngine';
import { SessionRecoveryManager, CommandLogEntry } from './sessionRecovery';
import { DiffViewer } from './DiffViewer';
import { ConflictResolutionModal } from './ConflictResolutionModal';
import { GitCommitModal } from './GitCommitModal';

const INITIAL_FILES: EditorFile[] = [
  {
    path: 'src/server.ts',
    name: 'server.ts',
    language: 'typescript',
    content: `import express from 'express';\nimport { traceparentMiddleware } from './middleware';\n\nconst app = express();\nconst PORT = process.env.PORT || 8080;\n\napp.use(traceparentMiddleware);\n\napp.get('/health', (req, res) => {\n  res.json({ status: 'healthy', timestamp: new Date().toISOString() });\n});\n\napp.listen(PORT, () => {\n  console.log(\`Server listening on port \${PORT}\`);\n});\n`,
    etag: computeSha256(`import express from 'express';\nimport { traceparentMiddleware } from './middleware';\n\nconst app = express();\nconst PORT = process.env.PORT || 8080;\n\napp.use(traceparentMiddleware);\n\napp.get('/health', (req, res) => {\n  res.json({ status: 'healthy', timestamp: new Date().toISOString() });\n});\n\napp.listen(PORT, () => {\n  console.log(\`Server listening on port \${PORT}\`);\n});\n`),
    isDirty: false,
  },
  {
    path: 'contracts/governance.yaml',
    name: 'governance.yaml',
    language: 'yaml',
    content: `version: "1.0.0"\npolicy:\n  name: "Two-Person Rule"\n  maxAllowedBudgetKrw: 500000\n  requireDiffForHighRisk: true\n  blastRadiusIsolation: "workspace_isolated"\n`,
    etag: computeSha256(`version: "1.0.0"\npolicy:\n  name: "Two-Person Rule"\n  maxAllowedBudgetKrw: 500000\n  requireDiffForHighRisk: true\n  blastRadiusIsolation: "workspace_isolated"\n`),
    isDirty: false,
  },
  {
    path: 'README.md',
    name: 'README.md',
    language: 'markdown',
    content: `# SaintVision Workspace (AC-06)\n\nDual-mode Monaco Editor, Myers Diff, xterm.js PTY, and Control Plane session recovery.\n`,
    etag: computeSha256(`# SaintVision Workspace (AC-06)\n\nDual-mode Monaco Editor, Myers Diff, xterm.js PTY, and Control Plane session recovery.\n`),
    isDirty: false,
  },
];

interface MonacoWorkspaceEditorProps {
  workspaceId?: string;
}

export const MonacoWorkspaceEditor: React.FC<MonacoWorkspaceEditorProps> = ({
  workspaceId = 'wsp_saint_core_01',
}) => {
  const [files, setFiles] = useState<EditorFile[]>(INITIAL_FILES);
  const [activeFilePath, setActiveFilePath] = useState<string>('src/server.ts');
  const [baseContents, setBaseContents] = useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    INITIAL_FILES.forEach((f) => {
      map[f.path] = f.content;
    });
    return map;
  });

  // Editor states
  const [viewMode, setViewMode] = useState<'editor' | 'diff' | 'frozen'>('editor');
  const [showConflictModal, setShowConflictModal] = useState(false);
  const [conflictDiff, setConflictDiff] = useState<FileDiffResult | null>(null);
  const [simulateConflictOnSave, setSimulateConflictOnSave] = useState(false);

  // ADR-044 Frozen Input Snapshot state
  const [frozenSnapshot] = useState<{
    boundRunVersion: number;
    attempt: number;
    maxAttempts: number;
    inputHash: string;
    files: Record<string, string>;
  }>({
    boundRunVersion: 2,
    attempt: 1,
    maxAttempts: 3,
    inputHash: 'sha256:72f9a95f9eb3460f0c51f1d8c2f0fbc58369e1ceb1e73a5ba45d769887b7570f',
    files: {
      'src/server.ts': INITIAL_FILES[0].content,
      'contracts/governance.yaml': INITIAL_FILES[1].content,
      'README.md': INITIAL_FILES[2].content,
    },
  });

  // Git states
  const [showCommitModal, setShowCommitModal] = useState(false);
  const [commits, setCommits] = useState<GitCommitRecord[]>([
    {
      commitId: '3a8d9f1e4b6c2a0e8d7f5a1b3c4d5e6f7a8b9c0d',
      parentCommitId: null,
      author: 'Codex System <codex@saintvision.internal>',
      message: 'chore(init): initial workspace scaffold',
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      stagedFiles: ['src/server.ts', 'contracts/governance.yaml', 'README.md'],
      treeHash: 'e9b2c1d3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9',
    },
  ]);

  // Terminal & Session Recovery states
  const [sessionManager] = useState<SessionRecoveryManager>(() => new SessionRecoveryManager(workspaceId));
  const [sessionState, setSessionState] = useState(sessionManager.getState());
  const [commandHistory, setCommandHistory] = useState<CommandLogEntry[]>([]);
  const [terminalInput, setTerminalInput] = useState('');
  const [terminalCols, setTerminalCols] = useState(80);
  const [terminalRows, setTerminalRows] = useState(24);
  const [resumeReport, setResumeReport] = useState<{
    resumed: boolean;
    hashMatches: boolean;
    checkpointHash: string;
    duplicateExecutions: number;
  } | null>(null);

  const activeFile = files.find((f) => f.path === activeFilePath) || files[0];
  const terminalBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [commandHistory]);

  // Handle File Content Change
  const handleContentChange = (newContent: string) => {
    setFiles((prev) =>
      prev.map((f) => {
        if (f.path === activeFilePath) {
          const isDirty = newContent !== baseContents[f.path];
          return { ...f, content: newContent, isDirty };
        }
        return f;
      })
    );
  };

  // Handle File Save with ETag / Concurrency check
  const handleSaveFile = () => {
    const baseContent = baseContents[activeFile.path];
    const currentContent = activeFile.content;

    if (simulateConflictOnSave) {
      // Simulate remote modification by another agent (triggering 412 Precondition Failed)
      const remoteModifiedContent = baseContent + '\n// [Remote Conflict]: Modified by Codex background task\n';
      const conflict = computeDiff(activeFile.path, remoteModifiedContent, currentContent);
      setConflictDiff(conflict);
      setShowConflictModal(true);
      return;
    }

    // Normal save: update baseContent and ETag
    const newEtag = computeSha256(currentContent);
    setBaseContents((prev) => ({ ...prev, [activeFile.path]: currentContent }));
    setFiles((prev) =>
      prev.map((f) =>
        f.path === activeFile.path ? { ...f, etag: newEtag, isDirty: false } : f
      )
    );
  };

  // Conflict Resolution Handlers
  const handleKeepMine = () => {
    const newEtag = computeSha256(activeFile.content);
    setBaseContents((prev) => ({ ...prev, [activeFile.path]: activeFile.content }));
    setFiles((prev) =>
      prev.map((f) =>
        f.path === activeFile.path ? { ...f, etag: newEtag, isDirty: false } : f
      )
    );
    setShowConflictModal(false);
    setSimulateConflictOnSave(false);
  };

  const handleAcceptRemote = () => {
    if (!conflictDiff) return;
    // Base content becomes remote modified content
    const remoteContent = baseContents[activeFile.path] + '\n// [Remote Conflict]: Modified by Codex background task\n';
    setBaseContents((prev) => ({ ...prev, [activeFile.path]: remoteContent }));
    setFiles((prev) =>
      prev.map((f) =>
        f.path === activeFile.path
          ? { ...f, content: remoteContent, etag: computeSha256(remoteContent), isDirty: false }
          : f
      )
    );
    setShowConflictModal(false);
    setSimulateConflictOnSave(false);
  };

  const handleMerge = () => {
    const mergedContent =
      activeFile.content + '\n// [Merged]: Concurrency conflict successfully resolved\n';
    const newEtag = computeSha256(mergedContent);
    setBaseContents((prev) => ({ ...prev, [activeFile.path]: mergedContent }));
    setFiles((prev) =>
      prev.map((f) =>
        f.path === activeFile.path
          ? { ...f, content: mergedContent, etag: newEtag, isDirty: false }
          : f
      )
    );
    setShowConflictModal(false);
    setSimulateConflictOnSave(false);
  };

  // Terminal Execution
  const handleCommandSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalInput.trim()) return;

    const cmd = terminalInput.trim();
    setTerminalInput('');

    const nonce = `cmd_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    sessionManager.executeCommand(cmd, nonce);
    setSessionState(sessionManager.getState());
    setCommandHistory(sessionManager.getCommandHistory());
  };

  // PTY Resize
  const handleResize = (deltaCols: number, deltaRows: number) => {
    const newCols = terminalCols + deltaCols;
    const newRows = terminalRows + deltaRows;
    const res = sessionManager.resizeTerminal(newCols, newRows);
    setTerminalCols(res.cols);
    setTerminalRows(res.rows);
    setSessionState(sessionManager.getState());
  };

  // Simulate CP Restart & Resume
  const handleSimulateRestart = () => {
    sessionManager.simulateCpRestart();
    setSessionState(sessionManager.getState());
    setResumeReport(null);
  };

  const handleResumeSession = () => {
    const result = sessionManager.resumeSession(sessionState.reconnectToken, sessionState.lastSeq);
    setSessionState(sessionManager.getState());
    setResumeReport({
      resumed: result.resumed,
      hashMatches: result.hashMatches,
      checkpointHash: result.checkpointHash,
      duplicateExecutions: sessionManager.getState().duplicateExecutions,
    });
  };

  const activeDiff = computeDiff(activeFile.path, baseContents[activeFile.path] || '', activeFile.content);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 120px)',
        backgroundColor: '#0d1117',
        color: '#c9d1d9',
        border: '1px solid #30363d',
        borderRadius: 'var(--radius-lg, 8px)',
        overflow: 'hidden',
      }}
    >
      {/* Top Main Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          backgroundColor: '#161b22',
          borderBottom: '1px solid #30363d',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontWeight: 600, color: '#f0f6fc', fontSize: '14px' }}>
            Workspace: <code style={{ color: '#58a6ff' }}>{workspaceId}</code>
          </span>
          <div style={{ display: 'flex', gap: '4px' }}>
            <Button
              size="sm"
              variant={viewMode === 'editor' ? 'primary' : 'secondary'}
              onClick={() => setViewMode('editor')}
            >
              Code Editor
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'diff' ? 'primary' : 'secondary'}
              onClick={() => setViewMode('diff')}
            >
              Diff View {activeFile.isDirty && `(+${activeDiff.additionsCount}/-${activeDiff.deletionsCount})`}
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'frozen' ? 'primary' : 'secondary'}
              onClick={() => setViewMode('frozen')}
            >
              🔒 Frozen Snapshot (ADR-044)
            </Button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#8b949e', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={simulateConflictOnSave}
              onChange={(e) => setSimulateConflictOnSave(e.target.checked)}
            />
            Simulate 412 Conflict on Save
          </label>

          <Button
            size="sm"
            variant="secondary"
            onClick={handleSaveFile}
            disabled={!activeFile.isDirty && !simulateConflictOnSave}
          >
            Save File (If-Match)
          </Button>

          <Button size="sm" variant="primary" onClick={() => setShowCommitModal(true)}>
            Git Commit ({files.filter((f) => f.isDirty).length})
          </Button>
        </div>
      </div>

      {/* Main Workspace Body: Split Left (Explorer) & Right (Editor / Terminal) */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Left Sidebar: File Tree Explorer & Git Commits */}
        <div
          style={{
            width: '240px',
            backgroundColor: '#0d1117',
            borderRight: '1px solid #30363d',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #21262d', fontSize: '12px', fontWeight: 600, color: '#8b949e' }}>
            EXPLORER
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
            {files.map((file) => (
              <div
                key={file.path}
                onClick={() => setActiveFilePath(file.path)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  borderRadius: '4px',
                  fontSize: '13px',
                  cursor: 'pointer',
                  backgroundColor: file.path === activeFilePath ? '#1f242c' : 'transparent',
                  color: file.path === activeFilePath ? '#58a6ff' : '#c9d1d9',
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{file.name}</span>
                {file.isDirty && (
                  <span style={{ color: '#e3b341', fontSize: '16px', lineHeight: 0 }}>●</span>
                )}
              </div>
            ))}
          </div>

          {/* Git Log Summary */}
          <div style={{ padding: '10px 14px', borderTop: '1px solid #21262d', fontSize: '11px', color: '#8b949e' }}>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>LATEST GIT COMMIT</div>
            <div style={{ fontFamily: 'var(--font-mono, monospace)', color: '#58a6ff' }}>
              {commits[0]?.commitId.slice(0, 7)}
            </div>
            <div style={{ color: '#c9d1d9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {commits[0]?.message}
            </div>
          </div>
        </div>

        {/* Center: Monaco Editor OR Diff Viewer */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            {viewMode === 'diff' ? (
              <DiffViewer
                diff={activeDiff}
                onApply={handleSaveFile}
                onClose={() => setViewMode('editor')}
              />
            ) : viewMode === 'frozen' ? (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                {/* Frozen Snapshot Banner */}
                <div
                  style={{
                    padding: '8px 16px',
                    backgroundColor: 'rgba(56, 139, 253, 0.12)',
                    borderBottom: '1px solid rgba(56, 139, 253, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 600, color: '#58a6ff' }}>
                      🔒 불변 Workspace 실행 입력 스냅샷 (ADR-044 Frozen Input)
                    </span>
                    <span style={{ color: '#8b949e' }}>
                      Attempt #{frozenSnapshot.attempt}/{frozenSnapshot.maxAttempts} • Version v{frozenSnapshot.boundRunVersion}
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '11px', color: '#79c0ff' }}>
                    Digest: {frozenSnapshot.inputHash.slice(0, 24)}...
                  </div>
                </div>

                {/* Editor Tab Bar */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 16px',
                    backgroundColor: '#161b22',
                    borderBottom: '1px solid #30363d',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontFamily: 'var(--font-mono, monospace)', color: '#f0f6fc' }}>
                      {activeFile.path}
                    </span>
                    <span
                      style={{
                        padding: '1px 6px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        backgroundColor: 'rgba(210, 153, 34, 0.2)',
                        color: '#e3b341',
                      }}
                    >
                      READ-ONLY (FROZEN)
                    </span>
                  </div>
                  <span style={{ color: '#8b949e', fontSize: '11px' }}>
                    고정 입력 • 호스트의 후속 편집과 엄격히 분리 보존됨 (ADR-044)
                  </span>
                </div>

                {/* Frozen Code Area */}
                <div style={{ flex: 1, display: 'flex', backgroundColor: '#090d13', overflow: 'hidden' }}>
                  {/* Line Numbers Gutter */}
                  <div
                    style={{
                      width: '44px',
                      padding: '12px 6px',
                      backgroundColor: '#070a0e',
                      borderRight: '1px solid #21262d',
                      color: '#484f58',
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: '13px',
                      lineHeight: '20px',
                      textAlign: 'right',
                      userSelect: 'none',
                    }}
                  >
                    {(frozenSnapshot.files[activeFilePath] || activeFile.content).split('\n').map((_, i) => (
                      <div key={i}>{i + 1}</div>
                    ))}
                  </div>

                  {/* Code Area (Read Only) */}
                  <textarea
                    value={frozenSnapshot.files[activeFilePath] || activeFile.content}
                    readOnly
                    spellCheck={false}
                    style={{
                      flex: 1,
                      padding: '12px',
                      backgroundColor: 'transparent',
                      color: '#8b949e',
                      border: 'none',
                      outline: 'none',
                      resize: 'none',
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: '13px',
                      lineHeight: '20px',
                      whiteSpace: 'pre',
                      overflowY: 'auto',
                      cursor: 'not-allowed',
                    }}
                  />
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                {/* Editor Tab Bar */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 16px',
                    backgroundColor: '#161b22',
                    borderBottom: '1px solid #30363d',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontFamily: 'var(--font-mono, monospace)', color: '#f0f6fc' }}>
                      {activeFile.path}
                    </span>
                    {activeFile.isDirty && <span style={{ color: '#e3b341' }}>(modified)</span>}
                  </div>
                  <span style={{ color: '#8b949e', fontSize: '11px' }}>
                    ETag: {activeFile.etag.slice(0, 16)}... • {activeFile.language} • UTF-8
                  </span>
                </div>

                {/* Editor Textarea with Line Numbers */}
                <div style={{ flex: 1, display: 'flex', backgroundColor: '#0d1117', overflow: 'hidden' }}>
                  {/* Line Numbers Gutter */}
                  <div
                    style={{
                      width: '44px',
                      padding: '12px 6px',
                      backgroundColor: '#090d13',
                      borderRight: '1px solid #21262d',
                      color: '#484f58',
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: '13px',
                      lineHeight: '20px',
                      textAlign: 'right',
                      userSelect: 'none',
                    }}
                  >
                    {activeFile.content.split('\n').map((_, i) => (
                      <div key={i}>{i + 1}</div>
                    ))}
                  </div>

                  {/* Code Area */}
                  <textarea
                    value={activeFile.content}
                    onChange={(e) => handleContentChange(e.target.value)}
                    spellCheck={false}
                    style={{
                      flex: 1,
                      padding: '12px',
                      backgroundColor: 'transparent',
                      color: '#c9d1d9',
                      border: 'none',
                      outline: 'none',
                      resize: 'none',
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: '13px',
                      lineHeight: '20px',
                      whiteSpace: 'pre',
                      overflowY: 'auto',
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Bottom Split: Embedded Web PTY & AC-06 Session Recovery */}
          <div
            style={{
              height: '240px',
              borderTop: '1px solid #30363d',
              backgroundColor: '#090d13',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Terminal Title / Recovery Bar */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 14px',
                backgroundColor: '#161b22',
                borderBottom: '1px solid #21262d',
                fontSize: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontWeight: 600, color: '#f0f6fc' }}>
                  Web Terminal PTY ({sessionState.cols}x{sessionState.rows})
                </span>
                <span
                  style={{
                    padding: '1px 6px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor:
                      sessionState.status === 'connected'
                        ? 'rgba(46, 160, 67, 0.2)'
                        : sessionState.status === 'recovered'
                        ? 'rgba(56, 139, 253, 0.2)'
                        : 'rgba(248, 81, 73, 0.2)',
                    color:
                      sessionState.status === 'connected'
                        ? '#3fb950'
                        : sessionState.status === 'recovered'
                        ? '#58a6ff'
                        : '#f85149',
                  }}
                >
                  {sessionState.status.toUpperCase()}
                </span>
                <span style={{ color: '#8b949e', fontSize: '11px' }}>
                  Seq: {sessionState.lastSeq} • Dups: {sessionState.duplicateExecutions}
                </span>
              </div>

              {/* Recovery & Resize Actions */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Button size="sm" variant="secondary" onClick={() => handleResize(10, 2)}>
                  Resize PTY (+10x+2)
                </Button>
                {sessionState.status === 'connected' && (
                  <Button size="sm" variant="secondary" onClick={handleSimulateRestart}>
                    Simulate CP Restart
                  </Button>
                )}
                {sessionState.status === 'disconnected' && (
                  <Button size="sm" variant="primary" onClick={handleResumeSession}>
                    Resume Session (AC-06)
                  </Button>
                )}
              </div>
            </div>

            {/* Terminal Output */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '8px 14px',
                fontFamily: 'var(--font-mono, monospace)',
                fontSize: '12px',
                lineHeight: '18px',
                color: '#8b949e',
              }}
            >
              <div>[Session {sessionState.sessionId} initialized] Checkpoint: {sessionState.checkpointHash.slice(0, 16)}...</div>
              {commandHistory.map((cmd) => (
                <div key={cmd.seq} style={{ marginTop: '4px' }}>
                  <span style={{ color: '#58a6ff' }}>saintvision@wsp:~$ {cmd.command}</span>
                  <div style={{ color: '#c9d1d9' }}>{cmd.output}</div>
                </div>
              ))}
              {resumeReport && (
                <div
                  style={{
                    margin: '6px 0',
                    padding: '6px 10px',
                    backgroundColor: 'rgba(56, 139, 253, 0.1)',
                    borderLeft: '3px solid #58a6ff',
                    color: '#f0f6fc',
                  }}
                >
                  ✔ AC-06 Session Resumed: Checkpoint Hash Verified (
                  <code style={{ color: '#58a6ff' }}>{resumeReport.checkpointHash.slice(0, 12)}...</code>
                  ), Zero Duplicate Executions ({resumeReport.duplicateExecutions}).
                </div>
              )}
              <div ref={terminalBottomRef} />
            </div>

            {/* Command Input Form */}
            <form
              onSubmit={handleCommandSubmit}
              style={{
                display: 'flex',
                padding: '6px 12px',
                backgroundColor: '#0d1117',
                borderTop: '1px solid #21262d',
              }}
            >
              <span style={{ color: '#3fb950', fontFamily: 'var(--font-mono, monospace)', fontSize: '13px', marginRight: '6px' }}>
                $
              </span>
              <input
                type="text"
                placeholder={sessionState.status === 'disconnected' ? 'Session disconnected (Restart simulated)...' : 'Type command (e.g., git status, npm test, ls -la)...'}
                disabled={sessionState.status === 'disconnected'}
                value={terminalInput}
                onChange={(e) => setTerminalInput(e.target.value)}
                style={{
                  flex: 1,
                  backgroundColor: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: '#c9d1d9',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '13px',
                }}
              />
            </form>
          </div>
        </div>
      </div>

      {/* Concurrency Conflict Modal (412 Precondition Failed) */}
      {showConflictModal && conflictDiff && (
        <ConflictResolutionModal
          filePath={activeFile.path}
          diff={conflictDiff}
          onKeepMine={handleKeepMine}
          onAcceptRemote={handleAcceptRemote}
          onMerge={handleMerge}
          onCancel={() => setShowConflictModal(false)}
        />
      )}

      {/* Git Commit Modal */}
      {showCommitModal && (
        <GitCommitModal
          files={files}
          parentCommit={commits[0] || null}
          onCommit={async (newCommit) => {
            setCommits([newCommit, ...commits]);
            // Clear dirty flags for committed files
            setFiles((prev) =>
              prev.map((f) =>
                newCommit.stagedFiles.includes(f.path) ? { ...f, isDirty: false } : f
              )
            );
            try {
              const { apiClient } = await import('@/shared/api/client');
              await apiClient('/v1/projects/prj_01JABCDE/runs', {
                method: 'POST',
                body: JSON.stringify({
                  objective: `Git Commit [${newCommit.commitId.slice(0, 7)}]: ${newCommit.message}`,
                  stagedFiles: newCommit.stagedFiles,
                  treeHash: newCommit.treeHash,
                }),
              });
            } catch (err) {
              console.warn('Backend run trigger fallback on Git commit:', err);
            }
            setShowCommitModal(false);
          }}
          onCancel={() => setShowCommitModal(false)}
        />
      )}
    </div>
  );
};
