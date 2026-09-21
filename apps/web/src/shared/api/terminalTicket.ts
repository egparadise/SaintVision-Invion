import type {
  TerminalTicketAuthFrame as CanonicalTerminalTicketAuthFrame,
  TerminalTicketInput as CanonicalTerminalTicketInput,
  TerminalTicketResult as CanonicalTerminalTicketResult,
} from '../../../../../packages/contracts-ts/src';
import { apiClient } from './client';

export type TerminalTicketInput = CanonicalTerminalTicketInput;
export type TerminalTicketResult = CanonicalTerminalTicketResult;
export type TerminalTicketAuthFrame = CanonicalTerminalTicketAuthFrame;

const TICKET_PATTERN = /^[0-9a-f]{64}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Runtime-check the canonical single-use PTY ticket response before consumers
 * pass it to the WebSocket transport. Values are deliberately omitted from
 * errors because `ticket` is a bearer credential.
 */
export function parseTerminalTicketResult(
  value: unknown,
  workspaceId: string,
): TerminalTicketResult {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('TerminalTicketResult response must be an object');
  }

  const body = value as Record<string, unknown>;
  const expectedKeys = ['expiresAt', 'sessionId', 'ticket', 'websocketPath'];
  if (
    Object.keys(body).sort().join(',') !== expectedKeys.join(',') ||
    typeof body.ticket !== 'string' || !TICKET_PATTERN.test(body.ticket) ||
    typeof body.expiresAt !== 'string' || !Number.isFinite(Date.parse(body.expiresAt)) ||
    typeof body.sessionId !== 'string' || !UUID_PATTERN.test(body.sessionId) ||
    typeof body.websocketPath !== 'string' || body.websocketPath.length > 500
  ) {
    throw new Error('TerminalTicketResult response violates the canonical wire contract');
  }

  const expectedPath = `/v1/workspaces/${encodeURIComponent(workspaceId)}/terminals/${body.sessionId}`;
  if (body.websocketPath !== expectedPath) {
    throw new Error('TerminalTicketResult websocketPath does not match its workspace and session');
  }

  return body as unknown as TerminalTicketResult;
}

/**
 * Build the server-defined handshake without putting the one-time ticket in a
 * URL, where browser history, proxies, or access logs could retain it.
 */
export function terminalTicketHandshake(ticket: TerminalTicketResult) {
  const authFrame: TerminalTicketAuthFrame = { ticket: ticket.ticket };
  return {
    websocketPath: ticket.websocketPath,
    subprotocol: 'inv-terminal-v1' as const,
    authFrame,
    firstFrame: JSON.stringify(authFrame),
  };
}

export async function issueTerminalTicket(
  workspaceId: string,
  input: TerminalTicketInput,
): Promise<TerminalTicketResult> {
  if (!workspaceId) throw new Error('TerminalTicket workspaceId is required');
  const response = await apiClient<unknown>(
    `/v1/workspaces/${encodeURIComponent(workspaceId)}/terminal-tickets`,
    { method: 'POST', body: JSON.stringify(input) },
  );
  return parseTerminalTicketResult(response, workspaceId);
}
