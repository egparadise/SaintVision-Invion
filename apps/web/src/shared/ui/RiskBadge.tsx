import React from 'react';
import { RiskLevel } from '@/contracts/types';

export interface RiskBadgeProps {
  level: RiskLevel;
  showDescription?: boolean;
}

export interface RiskConfigItem {
  label: string;
  description: string;
  icon: string;
  colorVar: string;
  bgVar: string;
}

export const RISK_CONFIG: Record<string, RiskConfigItem> = {
  L0: {
    label: 'L0',
    description: '읽기 전용 (안전)',
    icon: '🛡️',
    colorVar: 'var(--color-risk-l0)',
    bgVar: 'var(--color-bg-subtle)',
  },
  L1: {
    label: 'L1',
    description: '격리 실행 (경미)',
    icon: 'ℹ️',
    colorVar: 'var(--color-risk-l1)',
    bgVar: 'var(--color-bg-subtle)',
  },
  L2: {
    label: 'L2',
    description: '2인 승인 필요 (주의)',
    icon: '⚠️',
    colorVar: 'var(--color-risk-l2)',
    bgVar: 'var(--color-bg-subtle)',
  },
  L3: {
    label: 'L3',
    description: '기본 차단 (위험)',
    icon: '🛑',
    colorVar: 'var(--color-risk-l3)',
    bgVar: 'var(--color-bg-subtle)',
  },
};

export function getRiskLevelConfig(level: unknown): RiskConfigItem {
  if (typeof level === 'string' && Object.hasOwn(RISK_CONFIG, level)) {
    return RISK_CONFIG[level as RiskLevel];
  }
  const raw = level === null || level === undefined ? '' : String(level).trim();
  return {
    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',
    description: '미확인 위험 등급',
    icon: '❓',
    colorVar: 'var(--color-status-unknown)',
    bgVar: 'var(--color-bg-subtle)',
  };
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, showDescription = true }) => {
  const config = getRiskLevelConfig(level);

  return (
    <span
      role="status"
      aria-label={`위험 등급 ${config.label}: ${config.description}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '2px 8px',
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.75rem',
        fontWeight: 600,
        color: config.colorVar,
        backgroundColor: config.bgVar,
        border: `1px solid ${config.colorVar}`,
        letterSpacing: '0.02em',
      }}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
      {showDescription && (
        <span style={{ fontWeight: 400, opacity: 0.9 }}>
          · {config.description}
        </span>
      )}
    </span>
  );
};
