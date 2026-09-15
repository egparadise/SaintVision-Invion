import React, { useState, useMemo } from 'react';
import { InvNamespace, InvFileItem, InvDriveSummary } from '@/contracts/virtualFabric';

export interface InvFileExplorerProps {
  initialUri?: string;
  onOpenFile?: (file: InvFileItem) => void;
}

const SAMPLE_FILES: InvFileItem[] = [
  {
    uri: 'inv://models/pacs-segmentation-v2/1.0.0/model.safetensors',
    namespace: 'models',
    relativePath: 'pacs-segmentation-v2/1.0.0/model.safetensors',
    name: 'model.safetensors',
    type: 'file',
    sizeBytes: 3840 * 1024 * 1024, // 3.84 GB
    version: '1.0.0',
    contentHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    contentType: 'application/octet-stream',
    replicas: [
      {
        nodeId: 'nod_01JABCDEF01',
        nodeHostname: 'Node-01-WinMain',
        status: 'healthy',
        localPath: 'C:\\SaintStorage\\models\\pacs-v2-shard0.bin',
        updatedAt: '2026-09-14T22:00:00Z',
      },
      {
        nodeId: 'nod_01JABCDEF05',
        nodeHostname: 'Node-05-LinuxTrain',
        status: 'healthy',
        localPath: '/data/models/pacs-v2-shard0.bin',
        updatedAt: '2026-09-14T22:05:00Z',
      },
    ],
    requiredReplicas: 2,
    isPinned: true,
    classification: 'confidential',
    updatedAt: '2026-09-14T22:05:00Z',
  },
  {
    uri: 'inv://models/pacs-segmentation-v2/1.0.0/manifest.json',
    namespace: 'models',
    relativePath: 'pacs-segmentation-v2/1.0.0/manifest.json',
    name: 'manifest.json',
    type: 'file',
    sizeBytes: 4200,
    version: '1.0.0',
    contentHash: 'f4b3c2a1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3',
    contentType: 'application/json',
    replicas: [
      {
        nodeId: 'nod_01JABCDEF01',
        nodeHostname: 'Node-01-WinMain',
        status: 'healthy',
        localPath: 'C:\\SaintStorage\\models\\manifest.json',
        updatedAt: '2026-09-14T22:00:00Z',
      },
      {
        nodeId: 'nod_01JABCDEF05',
        nodeHostname: 'Node-05-LinuxTrain',
        status: 'healthy',
        localPath: '/data/models/manifest.json',
        updatedAt: '2026-09-14T22:00:00Z',
      },
    ],
    requiredReplicas: 2,
    isPinned: true,
    classification: 'internal',
    updatedAt: '2026-09-14T22:00:00Z',
  },
  {
    uri: 'inv://workspaces/wsp_01JABCDE001/src/train.py',
    namespace: 'workspaces',
    relativePath: 'wsp_01JABCDE001/src/train.py',
    name: 'train.py',
    type: 'file',
    sizeBytes: 14200,
    version: 'commit-c5f2154',
    contentHash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0',
    contentType: 'text/x-python',
    replicas: [
      {
        nodeId: 'nod_01JABCDEF01',
        nodeHostname: 'Node-01-WinMain',
        status: 'healthy',
        localPath: 'C:\\Workspaces\\wsp_01JABCDE001\\src\\train.py',
        updatedAt: '2026-09-15T01:10:00Z',
      },
    ],
    requiredReplicas: 1,
    isPinned: false,
    classification: 'internal',
    updatedAt: '2026-09-15T01:10:00Z',
  },
  {
    uri: 'inv://datasets/pacs-dicom-lung-ct-2026/dicom_manifest.tar.gz',
    namespace: 'datasets',
    relativePath: 'pacs-dicom-lung-ct-2026/dicom_manifest.tar.gz',
    name: 'dicom_manifest.tar.gz',
    type: 'file',
    sizeBytes: 1240 * 1024 * 1024, // 1.24 GB
    version: '2026.09-rc1',
    contentHash: '9876543210abcdef0123456789abcdef9876543210abcdef0123456789abcdef',
    contentType: 'application/gzip',
    replicas: [
      {
        nodeId: 'nod_01JABCDEF04',
        nodeHostname: 'Node-04-LinuxBuild',
        status: 'unreachable', // Demonstrating partial failure / degraded replica state
        localPath: '/mnt/nvme/datasets/dicom_manifest.tar.gz',
        updatedAt: '2026-09-13T10:00:00Z',
      },
      {
        nodeId: 'nod_01JABCDEF01',
        nodeHostname: 'Node-01-WinMain',
        status: 'healthy',
        localPath: 'C:\\SaintStorage\\datasets\\dicom_manifest.tar.gz',
        updatedAt: '2026-09-13T10:00:00Z',
      },
    ],
    requiredReplicas: 2,
    isPinned: true,
    classification: 'restricted',
    updatedAt: '2026-09-13T10:00:00Z',
  },
  {
    uri: 'inv://artifacts/run_01JABCDE0001/output_receipt.json',
    namespace: 'artifacts',
    relativePath: 'run_01JABCDE0001/output_receipt.json',
    name: 'output_receipt.json',
    type: 'file',
    sizeBytes: 8420,
    version: '1',
    contentHash: '7766554433221100aabbccddeeff00112233445566778899aabbccddeeff0011',
    contentType: 'application/json',
    replicas: [
      {
        nodeId: 'nod_01JABCDEF01',
        nodeHostname: 'Node-01-WinMain',
        status: 'healthy',
        localPath: 'C:\\SaintStorage\\artifacts\\output_receipt.json',
        updatedAt: '2026-09-15T00:50:00Z',
      },
    ],
    requiredReplicas: 1,
    isPinned: true, // Evidence references are GC-exempt!
    classification: 'internal',
    updatedAt: '2026-09-15T00:50:00Z',
  },
];

const DRIVES: InvDriveSummary[] = [
  {
    namespace: 'workspaces',
    label: 'Workspaces',
    uriPrefix: 'inv://workspaces',
    description: '샌드박스 개발 소스코드 및 환경 파일',
    totalItems: 14,
    totalSizeBytes: 240 * 1024 * 1024,
    icon: '💻',
  },
  {
    namespace: 'models',
    label: 'AI Models',
    uriPrefix: 'inv://models',
    description: 'AI 가중치, Shard Manifest, PyTorch/GGUF',
    totalItems: 8,
    totalSizeBytes: 18 * 1024 * 1024 * 1024,
    icon: '🧠',
  },
  {
    namespace: 'datasets',
    label: 'Datasets',
    uriPrefix: 'inv://datasets',
    description: 'PACS DICOM 영상 및 전처리 데이터셋',
    totalItems: 5,
    totalSizeBytes: 62 * 1024 * 1024 * 1024,
    icon: '📊',
  },
  {
    namespace: 'artifacts',
    label: 'Artifacts & Receipts',
    uriPrefix: 'inv://artifacts',
    description: '불변 실행 증거, 검증 영수증, 모델 체크포인트',
    totalItems: 42,
    totalSizeBytes: 12 * 1024 * 1024 * 1024,
    icon: '📜',
  },
];

export const InvFileExplorer: React.FC<InvFileExplorerProps> = ({
  initialUri = 'inv://models',
  onOpenFile,
}) => {
  const [addressInput, setAddressInput] = useState<string>(initialUri);
  const [files, setFiles] = useState<InvFileItem[]>(SAMPLE_FILES);
  const [selectedFile, setSelectedFile] = useState<InvFileItem | null>(null);
  const [activeNamespace, setActiveNamespace] = useState<InvNamespace | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const filteredFiles = useMemo(() => {
    return files.filter((file) => {
      if (activeNamespace !== 'all' && file.namespace !== activeNamespace) {
        return false;
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          file.name.toLowerCase().includes(q) ||
          file.uri.toLowerCase().includes(q) ||
          file.contentHash.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [files, activeNamespace, searchQuery]);

  const handleNavigate = (uri: string) => {
    setAddressInput(uri);
    if (uri.startsWith('inv://workspaces')) setActiveNamespace('workspaces');
    else if (uri.startsWith('inv://models')) setActiveNamespace('models');
    else if (uri.startsWith('inv://datasets')) setActiveNamespace('datasets');
    else if (uri.startsWith('inv://artifacts')) setActiveNamespace('artifacts');
    else setActiveNamespace('all');
  };

  const handleTogglePin = (uri: string) => {
    setFiles((prev) =>
      prev.map((f) => (f.uri === uri ? { ...f, isPinned: !f.isPinned } : f))
    );
    if (selectedFile && selectedFile.uri === uri) {
      setSelectedFile((prev) => (prev ? { ...prev, isPinned: !prev.isPinned } : null));
    }
  };

  const handleRepairReplica = (file: InvFileItem) => {
    // Simulate re-replicating from healthy replica to another node
    setFiles((prev) =>
      prev.map((f) => {
        if (f.uri === file.uri) {
          return {
            ...f,
            replicas: f.replicas.map((r) =>
              r.status === 'unreachable' ? { ...r, status: 'healthy' } : r
            ),
          };
        }
        return f;
      })
    );
    alert(`[Repair] 파일 ${file.name}의 복제본을 정상 노드에서 동기화 복구 완료했습니다.`);
  };

  return (
    <div
      style={{
        display: 'flex',
        height: '100%',
        backgroundColor: 'var(--color-bg-surface, #0f172a)',
        color: 'var(--color-text-primary, #f8fafc)',
        overflow: 'hidden',
      }}
    >
      {/* 1. Left Sidebar: inv:// Drives & Nodes */}
      <div
        style={{
          width: '240px',
          borderRight: '1px solid var(--color-border-subtle, #334155)',
          backgroundColor: 'var(--color-bg-subtle, #1e293b)',
          display: 'flex',
          flexDirection: 'column',
          padding: '16px 12px',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--color-text-muted, #94a3b8)', textTransform: 'uppercase', marginBottom: '8px', paddingLeft: '8px' }}>
            논리 드라이브 (inv://)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <button
              type="button"
              onClick={() => handleNavigate('inv://')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 10px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeNamespace === 'all' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                color: activeNamespace === 'all' ? '#93c5fd' : 'inherit',
                fontSize: '0.8125rem',
                fontWeight: activeNamespace === 'all' ? 600 : 500,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span>🌐</span>
              <span>전체 네임스페이스</span>
            </button>

            {DRIVES.map((d) => {
              const active = activeNamespace === d.namespace;
              return (
                <button
                  key={d.namespace}
                  type="button"
                  onClick={() => handleNavigate(d.uriPrefix)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: active ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    color: active ? '#93c5fd' : 'inherit',
                    fontSize: '0.8125rem',
                    fontWeight: active ? 600 : 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>{d.icon}</span>
                    <span>{d.label}</span>
                  </div>
                  <span style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>{d.totalItems}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--color-text-muted, #94a3b8)', textTransform: 'uppercase', marginBottom: '8px', paddingLeft: '8px' }}>
            기여 물리 저장소 노드
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.75rem', paddingLeft: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#60a5fa' }}>
              <span>💽</span>
              <span>Node-01 (C:\SaintStorage)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fbbf24' }}>
              <span>💽</span>
              <span>Node-04 (/mnt/nvme-pool)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#34d399' }}>
              <span>💽</span>
              <span>Node-05 (/data/models-fast)</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Main Area: Address Bar, Actions, File List & Drawer */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Address & Search Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 16px',
            borderBottom: '1px solid var(--color-border-subtle, #334155)',
            backgroundColor: 'var(--color-bg-surface, #0f172a)',
          }}
        >
          {/* Navigation Buttons */}
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              type="button"
              title="상위 디렉토리로 이동"
              onClick={() => handleNavigate('inv://')}
              style={{
                padding: '4px 8px',
                borderRadius: '4px',
                border: '1px solid var(--color-border-subtle, #334155)',
                backgroundColor: 'transparent',
                color: 'inherit',
                cursor: 'pointer',
              }}
            >
              ▲
            </button>
          </div>

          {/* inv:// Address Input */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', position: 'relative' }}>
            <input
              type="text"
              value={addressInput}
              onChange={(e) => setAddressInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleNavigate(addressInput);
              }}
              aria-label="inv 네임스페이스 경로 주소창"
              style={{
                width: '100%',
                padding: '6px 12px 6px 32px',
                fontSize: '0.8125rem',
                fontFamily: 'monospace',
                borderRadius: '6px',
                border: '1px solid var(--color-border-strong, #475569)',
                backgroundColor: 'rgba(0,0,0,0.3)',
                color: '#38bdf8',
              }}
            />
            <span style={{ position: 'absolute', left: '10px', fontSize: '0.875rem' }}>🔗</span>
          </div>

          {/* Search Input */}
          <div style={{ width: '200px' }}>
            <input
              type="text"
              placeholder="파일 / 해시 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="파일 및 SHA-256 해시 검색"
              style={{
                width: '100%',
                padding: '6px 10px',
                fontSize: '0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--color-border-subtle, #334155)',
                backgroundColor: 'rgba(0,0,0,0.2)',
                color: 'inherit',
              }}
            />
          </div>
        </div>

        {/* Toolbar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 16px',
            borderBottom: '1px solid var(--color-border-subtle, #334155)',
            backgroundColor: 'rgba(0,0,0,0.1)',
            fontSize: '0.8125rem',
          }}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={() => alert('[Upload] 클라이언트 측 SHA-256 자동 계산 및 청크 분할 업로드 트리거')}
              style={{
                padding: '4px 10px',
                borderRadius: '5px',
                border: '1px solid rgba(59, 130, 246, 0.4)',
                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                color: '#60a5fa',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              ⬆️ 파일 업로드
            </button>
            <button
              type="button"
              onClick={() => alert('[New Folder] inv:// 경로에 논리 디렉토리 생성')}
              style={{
                padding: '4px 10px',
                borderRadius: '5px',
                border: '1px solid var(--color-border-subtle, #334155)',
                backgroundColor: 'transparent',
                color: 'inherit',
                cursor: 'pointer',
              }}
            >
              📁 폴더 생성
            </button>
          </div>

          <div style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>
            {filteredFiles.length}개 항목 표시 중
          </div>
        </div>

        {/* File Table */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid var(--color-border-subtle, #334155)',
                  backgroundColor: 'rgba(0,0,0,0.2)',
                  color: 'var(--color-text-muted, #94a3b8)',
                  textAlign: 'left',
                }}
              >
                <th style={{ padding: '10px 14px' }}>이름</th>
                <th style={{ padding: '10px 14px' }}>크기</th>
                <th style={{ padding: '10px 14px' }}>버전</th>
                <th style={{ padding: '10px 14px' }}>SHA-256 무결성 해시</th>
                <th style={{ padding: '10px 14px' }}>분산 복제본 (Replicas)</th>
                <th style={{ padding: '10px 14px' }}>고정(Pin)</th>
                <th style={{ padding: '10px 14px' }}>보안 분류</th>
              </tr>
            </thead>
            <tbody>
              {filteredFiles.map((file) => {
                const isSelected = selectedFile?.uri === file.uri;
                const hasDegradedReplica = file.replicas.some((r) => r.status !== 'healthy');
                const healthyCount = file.replicas.filter((r) => r.status === 'healthy').length;

                return (
                  <tr
                    key={file.uri}
                    onClick={() => setSelectedFile(file)}
                    onDoubleClick={() => onOpenFile?.(file)}
                    style={{
                      borderBottom: '1px solid var(--color-border-subtle, #334155)',
                      backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    {/* Name & Icon */}
                    <td style={{ padding: '10px 14px', fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>{file.type === 'directory' ? '📁' : file.name.endsWith('.safetensors') ? '🧠' : '📄'}</span>
                        <span>{file.name}</span>
                      </div>
                    </td>

                    {/* Size */}
                    <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>
                      {formatBytes(file.sizeBytes)}
                    </td>

                    {/* Version */}
                    <td style={{ padding: '10px 14px' }}>
                      <code style={{ fontSize: '0.75rem', backgroundColor: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
                        {file.version}
                      </code>
                    </td>

                    {/* SHA-256 Hash */}
                    <td style={{ padding: '10px 14px' }}>
                      <code
                        title={file.contentHash}
                        style={{
                          fontSize: '0.6875rem',
                          color: '#38bdf8',
                        }}
                      >
                        {file.contentHash.substring(0, 16)}...
                      </code>
                    </td>

                    {/* Replicas & Partial Failure */}
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 600,
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor: hasDegradedReplica ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                            color: hasDegradedReplica ? '#fbbf24' : '#34d399',
                          }}
                        >
                          {hasDegradedReplica ? '⚠️ ' : '● '}
                          {healthyCount}/{file.requiredReplicas} 가용
                        </span>
                        <span style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>
                          ({file.replicas.map((r) => r.nodeHostname.replace('-WinMain', '').replace('-LinuxTrain', '').replace('-LinuxBuild', '')).join(', ')})
                        </span>
                      </div>
                    </td>

                    {/* Pin Status */}
                    <td style={{ padding: '10px 14px' }}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleTogglePin(file.uri);
                        }}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          fontSize: '0.875rem',
                          opacity: file.isPinned ? 1 : 0.3,
                        }}
                        title={file.isPinned ? 'GC 제외 고정됨 (Pinned)' : '고정 해제됨 (Unpinned)'}
                      >
                        📌
                      </button>
                    </td>

                    {/* Classification */}
                    <td style={{ padding: '10px 14px' }}>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor:
                            file.classification === 'restricted'
                              ? 'rgba(239, 68, 68, 0.15)'
                              : file.classification === 'confidential'
                              ? 'rgba(168, 85, 247, 0.15)'
                              : 'rgba(148, 163, 184, 0.15)',
                          color:
                            file.classification === 'restricted'
                              ? '#f87171'
                              : file.classification === 'confidential'
                              ? '#c084fc'
                              : '#94a3b8',
                          textTransform: 'uppercase',
                        }}
                      >
                        {file.classification}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* 3. Detail Inspection Drawer (When file is selected) */}
        {selectedFile && (
          <div
            style={{
              padding: '16px 20px',
              borderTop: '1px solid var(--color-border-subtle, #334155)',
              backgroundColor: 'var(--color-bg-subtle, #1e293b)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>{selectedFile.name}</span>
                <code style={{ fontSize: '0.75rem', color: '#38bdf8' }}>{selectedFile.uri}</code>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                크기: {formatBytes(selectedFile.sizeBytes)} · 전체 무결성 SHA-256: <code>{selectedFile.contentHash}</code>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              {selectedFile.replicas.some((r) => r.status !== 'healthy') && (
                <button
                  type="button"
                  onClick={() => handleRepairReplica(selectedFile)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid rgba(245, 158, 11, 0.4)',
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    color: '#fbbf24',
                    fontWeight: 600,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  ⚡ 손실 복제본 복구 (Repair)
                </button>
              )}
              <button
                type="button"
                onClick={() => alert(`[Download] ${selectedFile.uri} 실제 원본 바이트 스트림 다운로드 시작`)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                  backgroundColor: 'rgba(59, 130, 246, 0.2)',
                  color: '#60a5fa',
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                }}
              >
                ⬇️ 원본 바이트 다운로드
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
