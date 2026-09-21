/**
 * WebCrypto-based SHA-256 digest computation utility.
 * Used across the frontend for immutable file integrity and download validation.
 */
export async function calculateSha256(content: string | Uint8Array): Promise<string> {
  const data = typeof content === 'string' ? new TextEncoder().encode(content) : content;
  if (typeof globalThis.crypto?.subtle?.digest === 'function') {
    const hashBuffer = await globalThis.crypto.subtle.digest('SHA-256', data as unknown as BufferSource);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  throw new Error('WebCrypto API가 지원되지 않아 무결성을 검증할 수 없습니다.');
}
