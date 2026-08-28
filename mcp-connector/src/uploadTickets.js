/**
 * uploadTickets.js
 *
 * Story 8.10: in-memory ticket store backing the out-of-band upload path
 * (solid_prepare_upload issues a ticket, POST /upload/:token redeems it).
 * Plain Map, no persistence — a restart drops every in-flight ticket, which
 * is acceptable at a 5-minute TTL: nothing durable is ever built on top of
 * an unredeemed ticket, and the agent just calls solid_prepare_upload again.
 *
 * Never expose a ticket's token in a log line — same discipline journal.js
 * already applies to the /mcp/:slug secret.
 */

const crypto = require("crypto");

const TTL_MS = 5 * 60 * 1000; // 300s, AC2

// token -> { targetUrl, identity, contentType, bytes, expiresAt }
// `identity` is the same object buildMcpServer/safeHandler close over
// elsewhere in this codebase (mutated in place on reauth), stored by
// reference rather than re-resolved from a label, so a ticket always
// redeems against the exact session that was live when it was issued.
const tickets = new Map();

/**
 * Same generator class as scripts/gen-slug.js (Task 1.2: do not invent a
 * second scheme) — CSPRNG bytes, base64url, no padding. 16 bytes -> 22 chars.
 */
function generateToken() {
  return crypto.randomBytes(16).toString("base64url");
}

/** Drop expired entries. Called on every access so the Map stays bounded
 * without a dedicated interval (Task 1.3). */
function sweep() {
  const now = Date.now();
  for (const [token, ticket] of tickets) {
    if (ticket.expiresAt <= now) tickets.delete(token);
  }
}

/**
 * @param {{targetUrl: string, identity: object, contentType: string, bytes: number}} params
 * @returns {{token: string, expiresAt: number, expiresIn: number}}
 */
function createTicket({ targetUrl, identity, contentType, bytes }) {
  sweep();
  const token = generateToken();
  const expiresAt = Date.now() + TTL_MS;
  tickets.set(token, { targetUrl, identity, contentType, bytes, issuedAt: Date.now(), expiresAt });
  return { token, expiresAt, expiresIn: Math.floor(TTL_MS / 1000) };
}

/**
 * Redeem a ticket: single-use by construction (delete happens before the
 * expiry check, so a concurrent second call — Node is single-threaded, this
 * runs to completion before any other JS executes — always sees it gone;
 * Task 1.4).
 *
 * @param {string} token
 * @returns {{targetUrl: string, identity: object, contentType: string, bytes: number}|null}
 *   null for unknown, already-redeemed, or expired — callers must treat all
 *   three identically (no oracle on which case it was, AC10).
 */
function redeemTicket(token) {
  sweep();
  const ticket = tickets.get(token);
  if (!ticket) return null;
  tickets.delete(token);
  if (ticket.expiresAt <= Date.now()) return null;
  return ticket;
}

module.exports = { createTicket, redeemTicket, TTL_MS };
