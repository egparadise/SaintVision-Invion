import { describe, it, expect } from 'vitest';
import { redactSensitiveText } from '../src/shared/utils/redact';

describe('Client-side Secret Redaction Utility', () => {
  it('should return empty/null text as is', () => {
    expect(redactSensitiveText('')).toBe('');
  });

  it('should redact Bearer authorization header tokens', () => {
    const raw = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz.secret';
    const redacted = redactSensitiveText(raw);
    expect(redacted).toContain('Bearer ***REDACTED***');
    expect(redacted).not.toContain('secret');
  });

  it('should redact raw JWT tokens', () => {
    const raw = 'Access token is eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHpunv_cYXvdB_k_zkwI_example';
    const redacted = redactSensitiveText(raw);
    expect(redacted).toContain('***REDACTED***');
    expect(redacted).not.toContain('dozjgNryP4J3jVmNHpunv_cYXvdB_k_zkwI_example');
  });

  it('should redact password and secret keys in configurations or logs', () => {
    const log = 'Connecting with secret="super_secret_password_123" and api_key=xyz987654321';
    const redacted = redactSensitiveText(log);
    expect(redacted).toContain('***REDACTED***');
    expect(redacted).not.toContain('super_secret_password_123');
    expect(redacted).not.toContain('xyz987654321');
  });

  it('should redact AWS presigned URL signatures', () => {
    const s3Url = 'https://minio.local/bucket/artifact?X-Amz-Signature=abcd1234ef567890&X-Amz-Expires=3600';
    const redacted = redactSensitiveText(s3Url);
    expect(redacted).toContain('***REDACTED***');
    expect(redacted).not.toContain('abcd1234ef567890');
  });

  it('should leave non-sensitive text untouched', () => {
    const safe = 'Cluster status is online with 5 active nodes and 12 CPU cores.';
    expect(redactSensitiveText(safe)).toBe(safe);
  });
});
