/**
 * identityRegistry.js
 *
 * Loads and validates the per-person identity map for Story 8.3: slug ->
 * { clientId, clientSecret, webId, label }. Source is a gitignored
 * identities.json (see identities.example.json for the shape) sitting next
 * to package.json — never a committed file.
 *
 * Story 7.9 extends the entry with non-secret bookkeeping (grantId,
 * grantUri, credentialRef, containers, createdAt, expiresAt, lastUsedAt,
 * revoked) plus reserved-nullable poc:ConsentGrant fields (purpose, scope,
 * excluded, consequenceOfRefusal) and adds a validated atomic write path
 * (writeIdentity/updateIdentity) so the backoffice mint/revoke endpoint can
 * safely author this file. Every new field is optional on read — a
 * pre-7.9 entry with only the original 4 fields must still load clean
 * (AC5). Revoked entries are excluded from duplicate-webId/clientId checks
 * and from the returned identities Map (AC7) so a revoked row can never
 * brick bootIdentities()'s fail-fast exit.
 *
 * Slugs are secrets: they gate access the same way the AGENT token does
 * (brief §5 T3's honest trade-off). Validation here exists to catch a weak
 * or malformed slug before boot, not to be a general-purpose schema
 * validator.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DEFAULT_PATH = path.join(__dirname, "..", "identities.json");
const DEFAULT_ENV_PATH = path.join(__dirname, "..", ".env");

// Story 8.5 Task 6.2: a secrets file readable/writable by group or other is
// refused outright rather than left to README advice ("chmod 600"). Mask
// against group+other read/write/execute bits (0o077, i.e. anything beyond
// owner permissions). Windows has no equivalent POSIX mode bits, so the
// check is a no-op there.
const OVER_PERMISSIVE_MASK = 0o077;

// AC6's floor: slugs are secrets, so they must carry >=22 chars of URL-safe
// entropy. This matches exactly what "npm run slug" (gen-slug.js) emits —
// validation and generation agree, so a hand-entered slug can never be
// weaker than a generated one.
const MIN_SLUG_LENGTH = 22;
const SLUG_SAFE_RE = /^[A-Za-z0-9_-]+$/;
const REQUIRED_FIELDS = ["clientId", "clientSecret", "webId", "label"];

// Story 7.9 AC4: reserved-nullable fields, written explicitly as null (never
// omitted) so a later reader can distinguish "nothing recorded" from
// "predates the field" — the same convention receipt.js uses for
// underGrant. Names mirror poc:ConsentGrant (Story 5.5) exactly so porting
// the vocabulary later is a rename of nothing.
const RESERVED_NULLABLE_FIELDS = ["grantUri", "purpose", "scope", "excluded", "consequenceOfRefusal"];

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
 * Refuse to load a secrets file that is readable/writable by group or
 * other. Story 8.5 Task 6.2: this used to be README advice only
 * ("chmod 600 identities.json") — a world-readable secrets file loaded
 * silently. Enforced now, for both identities.json and (best-effort) .env.
 *
 * @param {string} filePath
 * @param {string} humanName - what to call the file in the error message.
 */
function _refuseIfOverPermissive(filePath, humanName) {
  if (process.platform === "win32") return; // no POSIX mode bits to check
  let mode;
  try {
    mode = fs.statSync(filePath).mode & 0o777;
  } catch {
    return; // can't stat it — a separate existence/read error will surface elsewhere
  }
  if (mode & OVER_PERMISSIVE_MASK) {
    throw new Error(
      `${humanName} at ${filePath} is readable/writable by group or other ` +
        `(mode ${mode.toString(8).padStart(3, "0")}). Refusing to load a secrets file with ` +
        `permissive permissions — run: chmod 600 "${filePath}"`
    );
  }
}

/**
 * Validate an already-parsed identities object plus its raw source text.
 * Shared by loadIdentities (boot) and writeIdentity/updateIdentity (Task
 * 1.6's write path validates the MERGED prospective file with these exact
 * rules — AC6). Throws with a message naming the offending slug's *label*
 * (never the slug itself — AC2/Task 1.2).
 *
 * @param {object} parsed - JSON.parse'd identities object
 * @param {string} rawText - the raw JSON text parsed was produced from (for dupe-key detection)
 * @param {string} [humanFileName] - name to use in messages
 * @returns {Map<string, object>} active (non-revoked) identities, extended shape
 */
function validateIdentities(parsed, rawText, humanFileName = "identities.json") {
  const dupeKeys = findDuplicateTopLevelKeys(rawText);
  if (dupeKeys.length > 0) {
    throw new Error(
      `${humanFileName} has duplicate slug key(s) in the file text: ` +
        `${dupeKeys.length} duplicate(s) found. Fix the file — duplicate ` +
        `JSON keys silently drop one identity.`
    );
  }

  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(
      `${humanFileName} must be a JSON object mapping slug -> identity entry ` +
        `(see identities.example.json), not ${Array.isArray(parsed) ? "an array" : typeof parsed}.`
    );
  }

  const identities = new Map();
  // Story 8.5 Task 6.1 / 7.9 AC7: two slugs pointing at the same underlying
  // webId or clientId silently defeats per-person isolation. Revoked rows
  // are excluded from these maps (AC7/Task 1.3) so that revoking then
  // re-minting for the same person is not permanently refused.
  const webIdToLabel = new Map();
  const clientIdToLabel = new Map();

  for (const [slug, entry] of Object.entries(parsed)) {
    // The .example template carries a "_comment" key. Skipping it silently
    // would reintroduce exactly the silent-identity-drop that
    // findDuplicateTopLevelKeys exists to prevent, so say so out loud.
    if (slug === "_comment") {
      // eslint-disable-next-line no-console
      console.warn(
        `[solid-pod-agent] ignoring "_comment" key in ${humanFileName} ` +
          `(template placeholder). If that was meant to be a real identity, give it a generated slug.`
      );
      continue;
    }

    const label = entry && typeof entry.label === "string" ? entry.label : "(unlabeled)";
    const revoked = !!(entry && entry.revoked);

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

    // AC7/Task 1.3: revoked entries never enter the duplicate-webId/clientId
    // checks — a revocation must not permanently block re-minting for the
    // same person.
    if (!revoked) {
      if (webIdToLabel.has(entry.webId)) {
        throw new Error(
          `Identity "${label}" has the same webId as identity "${webIdToLabel.get(entry.webId)}". ` +
            `Two slugs must not point at the same underlying identity — it silently ` +
            `defeats per-person isolation. Give each person their own webId, or remove the duplicate slug.`
        );
      }
      webIdToLabel.set(entry.webId, label);

      if (clientIdToLabel.has(entry.clientId)) {
        throw new Error(
          `Identity "${label}" has the same clientId as identity "${clientIdToLabel.get(entry.clientId)}". ` +
            `Two slugs must not share a client credential — it silently defeats per-person isolation. ` +
            `Generate a separate client-credentials token per person.`
        );
      }
      clientIdToLabel.set(entry.clientId, label);
    }

    // Story 7.9 AC4/AC5: extended fields are optional on read, defaulted in
    // memory. A pre-7.9 entry carrying only the original 4 fields loads
    // clean with every new field null/[]/false — this IS the migration-free
    // guarantee AC5 exists to prove.
    const extended = {
      clientId: entry.clientId,
      clientSecret: entry.clientSecret,
      webId: entry.webId,
      label: entry.label,
      grantId: typeof entry.grantId === "string" ? entry.grantId : null,
      credentialRef: typeof entry.credentialRef === "string" ? entry.credentialRef : null,
      containers: Array.isArray(entry.containers) ? entry.containers : [],
      createdAt: typeof entry.createdAt === "string" ? entry.createdAt : null,
      expiresAt: typeof entry.expiresAt === "string" ? entry.expiresAt : null,
      lastUsedAt: typeof entry.lastUsedAt === "string" ? entry.lastUsedAt : null,
      revoked,
    };
    for (const field of RESERVED_NULLABLE_FIELDS) {
      extended[field] = entry[field] === undefined ? null : entry[field];
    }

    identities.set(slug, extended);
  }

  if (identities.size === 0) {
    throw new Error(
      `${humanFileName} contains no identities. Add at least one slug entry ` +
        `(see identities.example.json).`
    );
  }

  return identities;
}

/**
 * Load and validate identities.json.
 *
 * @param {string} [filePath] defaults to identities.json next to package.json
 * @returns {Map<string, object>} ACTIVE identities only — revoked rows are excluded
 *   so bootIdentities() never attempts to log one in (AC7/Task 1.4).
 */
function loadIdentities(filePath = DEFAULT_PATH) {
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `No identities file at ${filePath}. Copy identities.example.json to ` +
        `identities.json, fill in real values, and chmod 600 it.`
    );
  }

  _refuseIfOverPermissive(filePath, "identities.json");
  // Best-effort: .env carries the AGENT/OWNER client credentials (auth.js)
  // and lives right next to identities.json. It's optional here (auth.js
  // loads it independently) — only check it if it actually exists, so a
  // deployment that supplies these via real environment variables instead
  // of a file isn't penalized for a file that was never created.
  if (fs.existsSync(DEFAULT_ENV_PATH)) {
    _refuseIfOverPermissive(DEFAULT_ENV_PATH, ".env");
  }

  const raw = fs.readFileSync(filePath, "utf-8");

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`identities.json is not valid JSON: ${err.message}`);
  }

  const all = validateIdentities(parsed, raw, path.basename(filePath));

  // AC7: revoked entries are excluded from the map loadIdentities returns —
  // their CSS credential is gone, so bootIdentities() must never try to log
  // them in (a login failure there is process.exit(1)).
  const active = new Map();
  for (const [slug, entry] of all) {
    if (!entry.revoked) active.set(slug, entry);
  }

  // NO throw when active.size === 0. This guard existed here briefly during
  // Story 7.9 development and caused a live outage on 2026-08-12: revoking
  // the last remaining identity made the connector refuse to boot, and
  // because /onboard/mint is served BY THIS SAME PROCESS, there was then no
  // way to mint a replacement — a deadlock with no in-product recovery path.
  // Un-revoking by hand doesn't help either: a revoked identity's CSS
  // credential is already deleted, so its login fails and bootIdentities()
  // exits fail-fast anyway.
  //
  // An all-revoked file is a LEGITIMATE state now that revocation is a
  // product feature (it was not, pre-7.9, when this file was hand-edited
  // only). The failure modes this guard was originally meant to catch — a
  // missing file, unreadable file, or malformed JSON — are each caught by
  // their own explicit throw above and are unaffected.
  return active;
}

// Story 7.9 AC9: serialize concurrent writes in-process (single-process
// service — no cross-process lock, and none is added). Each write re-reads
// the file *inside* this chain, not before it, so two concurrent mints both
// land rather than racing on a stale in-memory copy.
let writeChain = Promise.resolve();

/**
 * Read+parse the current file (or {} if it doesn't exist yet), synchronously,
 * for use inside the serialized write critical section.
 */
function _readRawObject(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const raw = fs.readFileSync(filePath, "utf-8");
  if (raw.trim().length === 0) return {};
  const dupeKeys = findDuplicateTopLevelKeys(raw);
  if (dupeKeys.length > 0) {
    throw new Error(`identities.json has duplicate slug key(s); refusing to write on top of a corrupt file.`);
  }
  return JSON.parse(raw);
}

/**
 * Atomically write `obj` to filePath: temp file in the same directory (so
 * rename is same-filesystem-atomic), mode 600 set BEFORE the rename (a
 * rename does not fix a bad mode), then fs.renameSync into place. Mode and
 * ownership are re-verified after the write (AC8/Task 1.6).
 *
 * PRODUCTION TRAP, confirmed live 2026-08-12 (Story 7.9 Task 7): identities.json
 * is a single-FILE bind mount in docker-compose.yml (made read-write by this
 * story), not a directory mount. That makes filePath itself a mount point —
 * `rename(2)` cannot atomically replace an active mount point and fails
 * with **EBUSY** ("resource busy or locked"), confirmed live against the
 * real VPS container. A cross-device EXDEV is also possible depending on
 * mount topology, so both are treated as the same case. Falls back to
 * copy+truncate-write on EBUSY/EXDEV specifically (never any other error) —
 * loses the crash-atomicity guarantee for that one write (a copy is not
 * atomic the way rename is), but is still far safer than a blind in-place
 * overwrite because the content was already validated before this function
 * was called.
 */
function _atomicWrite(filePath, obj) {
  const dir = path.dirname(filePath);
  const tmpPath = path.join(dir, `.${path.basename(filePath)}.tmp-${process.pid}-${Date.now()}`);
  const text = JSON.stringify(obj, null, 2) + "\n";
  fs.writeFileSync(tmpPath, text, { mode: 0o600 });
  fs.chmodSync(tmpPath, 0o600);
  try {
    fs.renameSync(tmpPath, filePath);
  } catch (err) {
    if (err.code !== "EXDEV" && err.code !== "EBUSY") throw err;
    // eslint-disable-next-line no-console
    console.warn(
      `[identityRegistry] atomic rename failed with ${err.code} (single-file bind mount is itself a mount ` +
        `point — rename cannot replace it); falling back to copy+write for this write. Crash-atomicity is ` +
        `reduced for this one write.`
    );
    fs.copyFileSync(tmpPath, filePath);
    fs.chmodSync(filePath, 0o600);
    fs.unlinkSync(tmpPath);
  }

  const stat = fs.statSync(filePath);
  const mode = stat.mode & 0o777;
  if (process.platform !== "win32" && mode & OVER_PERMISSIVE_MASK) {
    throw new Error(
      `identities.json ended up with permissive mode ${mode.toString(8).padStart(3, "0")} after write — refusing silently.`
    );
  }
}

/**
 * Write a brand-new identity entry (Story 7.9 mint path). Validates the
 * MERGED prospective file with the exact same rules loadIdentities uses
 * (AC6) before persisting — a bad entry must never reach disk, because
 * bootIdentities() is fail-fast and would take the whole connector down at
 * the next restart.
 *
 * @param {string} slug
 * @param {object} entry - full extended entry shape (see AC4)
 * @param {string} [filePath]
 * @returns {Promise<void>}
 */
function writeIdentity(slug, entry, filePath = DEFAULT_PATH) {
  // A rejected write must not permanently break the chain: `.then()` on a
  // rejected promise with no onRejected handler just re-throws, so every
  // later write would silently never run its body and replay this same
  // error forever. Keep `writeChain` itself always-resolving (catch swallowed
  // there) while still returning the real per-call outcome to the caller.
  const result = writeChain.then(() => {
    const current = _readRawObject(filePath);
    if (Object.prototype.hasOwnProperty.call(current, slug)) {
      throw new Error(`Cannot mint: slug already exists in ${path.basename(filePath)}.`);
    }
    const merged = { ...current, [slug]: entry };
    // AC6: validate the MERGED file — duplicate webId/clientId across the
    // whole file, not just the new entry in isolation.
    validateIdentities(merged, JSON.stringify(merged), path.basename(filePath));
    _atomicWrite(filePath, merged);
  });
  writeChain = result.catch(() => {});
  return result;
}

/**
 * Patch an existing identity entry in place (revoke, lastUsedAt, expiresAt,
 * etc.). Re-validates the merged file the same way writeIdentity does.
 *
 * @param {string} slug
 * @param {object} patch - fields to shallow-merge onto the existing entry
 * @param {string} [filePath]
 * @returns {Promise<void>}
 */
function updateIdentity(slug, patch, filePath = DEFAULT_PATH) {
  const result = writeChain.then(() => {
    const current = _readRawObject(filePath);
    if (!Object.prototype.hasOwnProperty.call(current, slug)) {
      throw new Error(`Cannot update: slug not found in ${path.basename(filePath)}.`);
    }
    const merged = { ...current, [slug]: { ...current[slug], ...patch } };
    validateIdentities(merged, JSON.stringify(merged), path.basename(filePath));
    _atomicWrite(filePath, merged);
  });
  writeChain = result.catch(() => {});
  return result;
}

/**
 * Non-secret random identifier, distinct from the slug and safe to write
 * into another person's pod (Story 7.9 AC13 — receipts carry grantId, never
 * the slug, because the slug is a bearer credential and receipts land in
 * the data subject's own pod where a third party could read it).
 */
function generateGrantId() {
  return crypto.randomBytes(12).toString("base64url");
}

module.exports = {
  loadIdentities,
  validateIdentities,
  writeIdentity,
  updateIdentity,
  generateGrantId,
  MIN_SLUG_LENGTH,
  SLUG_SAFE_RE,
  DEFAULT_PATH,
};
