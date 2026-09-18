import React from 'react';
import { RiskLevel } from '@/contracts/types';

export interface RiskBadgeProps {
  level: RiskLevel;
  showDescription?: boolean;
}

const RISK_CONFIG: Record<
  RiskLevel,
  {
    label: string;
    description: string;
    icon: string;
    colorVar: string;
    bgVar: string;
  }
> = {
  L0: {
    label: 'L0',
    description: '읽기 전용 (안전)',
    icon: '🛡️',
    colorVar: 'var(--color-risk-l0)',
    bgVar: 'rgba(16, 185, 129, 0.15)',
  },
  L1: {
    label: 'L1',
    description: '격리 실행 (경미)',
    icon: 'ℹ️',
    colorVar: 'var(--color-risk-l1)',
    bgVar: 'rgba(59, 130, 246, 0.15)',
  },
  L2: {
    label: 'L2',
    description: '2인 승인 필요 (주의)',
    icon: '⚠️',
    colorVar: 'var(--color-risk-l2)',
    bgVar: 'rgba(245, 158, 11, 0.15)',
  },
  L3: {
    label: 'L3',
    description: '기본 차단 (위험)',
    icon: '🛑',
    colorVar: 'var(--color-risk-l3)',
    bgVar: 'rgba(239, 68, 68, 0.15)',
  },
};

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, showDescription = true }) => {
  const config = RISK_CONFIG[level];
  if (!config) return <span role="status">위험도 미관측</span>;

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
