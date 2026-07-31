/**
 * identityRegistry.js
 *
 * Loads and validates the per-person identity map for Story 8.3: slug ->
 * { clientId, clientSecret, webId, label }. Source is a gitignored
 * identities.json (see identities.example.json for the shape) sitting next
 * to package.json — never a committed file.
 *
 * Slugs are secrets: they gate access the same way the AGENT token does
 * (brief §5 T3's honest trade-off). Validation here exists to catch a weak
 * or malformed slug before boot, not to be a general-purpose schema
 * validator.
 */

const fs = require("fs");
const path = require("path");

const DEFAULT_PATH = path.join(__dirname, "..", "identities.json");

// AC6's floor: slugs are secrets, so they must carry >=22 chars of URL-safe
// entropy. This matches exactly what "npm run slug" (gen-slug.js) emits —
// validation and generation agree, so a hand-entered slug can never be
// weaker than a generated one.
const MIN_SLUG_LENGTH = 22;
const SLUG_SAFE_RE = /^[A-Za-z0-9_-]+$/;
const REQUIRED_FIELDS = ["clientId", "clientSecret", "webId", "label"];

/**
 * Detect duplicate JSON object keys at the text level. JSON.parse silently
 * keeps only the last occurrence of a duplicate key, so by the time we have
 * a parsed object the duplication is invisible — this has to run on the raw
 * source text.
 */
function findDuplicateTopLevelKeys(raw) {
  const seen = new Map();
  const dupes = new Set();
  let depth = 0;
  let inString = false;
  let escaped = false;
  let stringStart = -1;

  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];

    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (ch === "\\") {
        escaped = true;
      } else if (ch === '"') {
        inString = false;
        if (depth === 1) {
          const key = JSON.parse(raw.slice(stringStart, i + 1));
          // Only count it as a key if followed (after whitespace) by ':'.
          let j = i + 1;
          while (j < raw.length && /\s/.test(raw[j])) j++;
          if (raw[j] === ":") {
            seen.set(key, (seen.get(key) || 0) + 1);
            if (seen.get(key) > 1) dupes.add(key);
          }
        }
      }
      continue;
    }

    if (ch === '"') {
      inString = true;
      stringStart = i;
    } else if (ch === "{") {
      depth++;
    } else if (ch === "}") {
      depth--;
    }
  }

  return [...dupes];
}

/**
 * Load and validate identities.json. Throws with a message naming the
 * offending slug's *label* (never the slug itself — AC2/Task 1.2).
 *
 * @param {string} [filePath] defaults to identities.json next to package.json
 * @returns {Map<string, {clientId:string, clientSecret:string, webId:string, label:string}>}
 */
function loadIdentities(filePath = DEFAULT_PATH) {
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `No identities file at ${filePath}. Copy identities.example.json to ` +
        `identities.json, fill in real values, and chmod 600 it.`
    );
  }

  const raw = fs.readFileSync(filePath, "utf-8");

  const dupeKeys = findDuplicateTopLevelKeys(raw);
  if (dupeKeys.length > 0) {
    throw new Error(
      `identities.json has duplicate slug key(s) in the file text: ` +
        `${dupeKeys.length} duplicate(s) found. Fix the file — duplicate ` +
        `JSON keys silently drop one identity.`
    );
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`identities.json is not valid JSON: ${err.message}`);
  }

  // The documented shape is a plain object mapping slug -> entry. Anything
  // else (array, string, null) would also defeat findDuplicateTopLevelKeys'
  // brace-depth tracking, so reject it here rather than half-validating it.
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(
      `identities.json must be a JSON object mapping slug -> identity entry ` +
        `(see identities.example.json), not ${Array.isArray(parsed) ? "an array" : typeof parsed}.`
    );
  }

  const identities = new Map();

  for (const [slug, entry] of Object.entries(parsed)) {
    // The .example template carries a "_comment" key. Skipping it silently
    // would reintroduce exactly the silent-identity-drop that
    // findDuplicateTopLevelKeys exists to prevent, so say so out loud.
    if (slug === "_comment") {
      // eslint-disable-next-line no-console
      console.warn(
        `[solid-pod-agent] ignoring "_comment" key in ${path.basename(filePath)} ` +
          `(template placeholder). If that was meant to be a real identity, give it a generated slug.`
      );
      continue;
    }

    const label = entry && typeof entry.label === "string" ? entry.label : "(unlabeled)";

    if (!SLUG_SAFE_RE.test(slug)) {
      throw new Error(
        `Identity "${label}" has a slug that isn't URL-safe. Slugs must ` +
          `match ${SLUG_SAFE_RE}. Use "npm run slug" to generate a valid one.`
      );
    }

    if (slug.length < MIN_SLUG_LENGTH) {
      throw new Error(
        `Identity "${label}" has a slug shorter than ${MIN_SLUG_LENGTH} ` +
          `characters — too guessable. Use "npm run slug" to generate one.`
      );
    }

    for (const field of REQUIRED_FIELDS) {
      if (!entry || typeof entry[field] !== "string" || entry[field].length === 0) {
        throw new Error(`Identity "${label}" is missing required field "${field}".`);
      }
    }

    identities.set(slug, {
      clientId: entry.clientId,
      clientSecret: entry.clientSecret,
      webId: entry.webId,
      label: entry.label,
    });
  }

  if (identities.size === 0) {
    throw new Error(
      `identities.json contains no identities. Add at least one slug entry ` +
        `(see identities.example.json).`
    );
  }

  return identities;
}

module.exports = { loadIdentities, MIN_SLUG_LENGTH, SLUG_SAFE_RE };
