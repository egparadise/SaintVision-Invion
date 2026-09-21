import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { issueTerminalTicket, parseTerminalTicketResult, terminalTicketHandshake } from '@/shared/api/terminalTicket';

const { apiClient } = vi.hoisted(() => ({ apiClient: vi.fn() }));
vi.mock('@/shared/api/client', () => ({ apiClient }));

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const fixtureUrl = new URL('../../../contracts/fixtures/terminal-ticket-result.json', import.meta.url);
const inputFixtureUrl = new URL('../../../contracts/fixtures/terminal-ticket-input.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const fixture = JSON.parse(readFileSync(fixtureUrl, 'utf8'));
const inputFixture = JSON.parse(readFileSync(inputFixtureUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validate = ajv.compile({ $ref: `${schema.$id}#/$defs/TerminalTicketResult` });
const validateInput = ajv.compile({ $ref: `${schema.$id}#/$defs/TerminalTicketInput` });
const validateAuthFrame = ajv.compile({ $ref: `${schema.$id}#/$defs/TerminalTicketAuthFrame` });

describe('PTY terminal ticket shared wire contract', () => {
  beforeEach(() => apiClient.mockReset());

  it('validates the shared fixture against core.schema.json TerminalTicketResult', () => {
    expect(validate(fixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects external WebSocket URLs because the wire path must remain workspace-scoped', () => {
    expect(validate({ ...fixture, websocketPath: 'wss://attacker.invalid/socket' })).toBe(false);
  });

  it('validates the shared request fixture against core.schema.json TerminalTicketInput', () => {
    expect(validateInput(inputFixture), JSON.stringify(validateInput.errors)).toBe(true);
    expect(validateInput({})).toBe(false);
  });

  it('issues a ticket with the canonical commandId input and workspace route', async () => {
    apiClient.mockResolvedValueOnce(fixture);
    const result = await issueTerminalTicket('wsp_0123456789ABCDEFGHJKMNPQRS', inputFixture);

    expect(apiClient).toHaveBeenCalledWith('/v1/workspaces/wsp_0123456789ABCDEFGHJKMNPQRS/terminal-tickets', {
      method: 'POST',
      body: JSON.stringify(inputFixture),
    });
    expect(result).toEqual(fixture);
  });

  it('rejects response aliases used by the pre-contract UI instead of accepting drift', () => {
    const legacyShape = {
      ticketId: fixture.ticket,
      expiresAt: fixture.expiresAt,
      sessionId: fixture.sessionId,
      ptyWsUrl: fixture.websocketPath,
    };
    expect(() => parseTerminalTicketResult(legacyShape, 'wsp_0123456789ABCDEFGHJKMNPQRS')).toThrow(/canonical wire contract/);
  });

  it('rejects a websocket path that does not bind the requested workspace and session', () => {
    expect(() => parseTerminalTicketResult({ ...fixture, websocketPath: '/v1/terminal/ws' }, 'wsp_0123456789ABCDEFGHJKMNPQRS'))
      .toThrow(/does not match its workspace and session/);
  });

  it('keeps the bearer ticket out of the WebSocket URL and places it only in the first auth frame', () => {
    const handshake = terminalTicketHandshake(fixture);
    expect(handshake).toEqual({
      websocketPath: fixture.websocketPath,
      subprotocol: 'inv-terminal-v1',
      authFrame: { ticket: fixture.ticket },
      firstFrame: JSON.stringify({ ticket: fixture.ticket }),
    });
    expect(validateAuthFrame(handshake.authFrame), JSON.stringify(validateAuthFrame.errors)).toBe(true);
    expect(JSON.parse(handshake.firstFrame)).toEqual(handshake.authFrame);
    expect(validateAuthFrame({ ...handshake.authFrame, workspaceId: 'wsp_ignored' })).toBe(false);
    expect(handshake.websocketPath).not.toContain(fixture.ticket);
    expect(handshake.websocketPath).not.toContain('?');
  });

  it('does not reveal a malformed credential in adapter errors', () => {
    const secret = 'a'.repeat(63) + 'z';
    expect(() => parseTerminalTicketResult({ ...fixture, ticket: secret }, 'wsp_0123456789ABCDEFGHJKMNPQRS'))
      .toThrow(/canonical wire contract/);
    try {
      parseTerminalTicketResult({ ...fixture, ticket: secret }, 'wsp_0123456789ABCDEFGHJKMNPQRS');
    } catch (error) {
      expect(String(error)).not.toContain(secret);
    }
  });
});
