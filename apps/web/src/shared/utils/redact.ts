/**
 * Client-side secret redaction utility.
 * Defense-in-depth: masks credentials, tokens, and presigned signatures
 * before rendering in DOM or copying to clipboard.
 */

const SENSITIVE_PATTERNS = [
  /Bearer\s+[A-Za-z0-9\-_.]+/gi,
  /(?:password|secret|token|apiKey|api_key|access_key)[\s:=]+["']?([^\s"']+)["']?/gi,
  /X-Amz-Signature=[0-9a-fA-F]+/gi,
  /ey[A-Za-z0-9-_=]+\.ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+/g, // JWT
];

export function redactSensitiveText(text: string): string {
  if (!text) return text;

  let sanitized = text;
  for (const pattern of SENSITIVE_PATTERNS) {
    sanitized = sanitized.replace(pattern, (match) => {
      if (match.toLowerCase().startsWith('bearer ')) {
        return 'Bearer ***REDACTED***';
      }
      return match.slice(0, Math.min(10, match.length)) + '...***REDACTED***';
    });
  }

  return sanitized;
}
