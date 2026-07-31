#!/usr/bin/env node
/**
 * gen-slug.js
 *
 * Story 8.3 AC6: generate an unguessable per-person MCP URL slug with a
 * CSPRNG, not Math.random(). >=22 chars of URL-safe entropy (16 random
 * bytes base64url-encoded, no padding, is 22 chars).
 *
 * Usage: npm run slug
 */

const crypto = require("crypto");

function generateSlug(bytes = 16) {
  return crypto.randomBytes(bytes).toString("base64url");
}

if (require.main === module) {
  console.log(generateSlug());
}

module.exports = { generateSlug };
