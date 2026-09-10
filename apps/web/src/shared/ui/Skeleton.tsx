import React from 'react';

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  style?: React.CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '1rem',
  borderRadius = 'var(--radius-sm)',
  style,
}) => {
  return (
    <div
      aria-hidden="true"
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: 'var(--color-bg-subtle)',
        backgroundImage: 'linear-gradient(90deg, var(--color-bg-subtle) 0px, var(--color-border-subtle) 50%, var(--color-bg-subtle) 100%)',
        backgroundSize: '200px 100%',
        animation: 'skeleton-pulse 1.5s ease-in-out infinite',
        ...style,
      }}
    />
  );
};
