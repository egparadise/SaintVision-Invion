import { describe, it, expect } from 'vitest';
import { generateCodeVerifier, generateCodeChallenge, generateState, generateNonce } from '../src/features/auth/pkce';

describe('Auth & Security: RFC 7636 PKCE Cryptographic Protocol', () => {
  it('generates high-entropy code verifier conforming to RFC 7636 bounds', () => {
    const verifier1 = generateCodeVerifier(43);
    const verifier2 = generateCodeVerifier(43);

    expect(verifier1).toBeDefined();
    expect(verifier1.length).toBeGreaterThanOrEqual(43);
    // Verifiers must be distinct
    expect(verifier1).not.toBe(verifier2);
    // Base64url character set: [A-Za-z0-9_-]
    expect(/^[A-Za-z0-9_-]+$/.test(verifier1)).toBe(true);
  });

  it('calculates deterministic S256 code challenge from verifier', async () => {
    const verifier = 'test-verifier-string-with-sufficient-entropy-for-testing';
    const challenge1 = await generateCodeChallenge(verifier);
    const challenge2 = await generateCodeChallenge(verifier);

    expect(challenge1).toBeDefined();
    expect(challenge1).toBe(challenge2);
    // Challenge must be base64url encoded SHA-256
    expect(/^[A-Za-z0-9_-]+$/.test(challenge1)).toBe(true);
    expect(challenge1).not.toBe(verifier);
  });

  it('generates unique CSRF state tokens', () => {
    const state1 = generateState();
    const state2 = generateState();

    expect(state1).toBeDefined();
    expect(state1.length).toBe(32); // 16 bytes hex = 32 chars
    expect(state1).not.toBe(state2);
  });

  it('generates unique replay-protection nonces', () => {
    const nonce1 = generateNonce();
    const nonce2 = generateNonce();

    expect(nonce1).toBeDefined();
    expect(nonce1.length).toBe(32); // 16 bytes hex = 32 chars
    expect(nonce1).not.toBe(nonce2);
  });
});
