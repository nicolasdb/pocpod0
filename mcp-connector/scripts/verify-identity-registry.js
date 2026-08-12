#!/usr/bin/env node
/**
 * verify-identity-registry.js
 *
 * Story 7.9 Task 1.9. Offline, no network, no live pod — exercises
 * identityRegistry.js's extended shape and atomic write path against
 * temp files. Run: node scripts/verify-identity-registry.js
 */

const fs = require("fs");
const os = require("os");
const path = require("path");
const assert = require("assert");

const {
  loadIdentities,
  writeIdentity,
  updateIdentity,
  generateGrantId,
} = require("../src/identityRegistry.js");

function tmpFile() {
  return path.join(fs.mkdtempSync(path.join(os.tmpdir(), "id-reg-")), "identities.json");
}

function baseEntry(overrides = {}) {
  return {
    label: "Test Person",
    webId: "https://pod.example.org/test-person/profile/card#me",
    clientId: "test-client-id",
    clientSecret: "test-client-secret",
    ...overrides,
  };
}

async function main() {
  let passed = 0;

  // AC5: pre-7.9-shaped file (only 4 original fields) loads clean.
  {
    const f = tmpFile();
    fs.writeFileSync(f, JSON.stringify({ ["a".repeat(22)]: baseEntry() }), { mode: 0o600 });
    const identities = loadIdentities(f);
    const entry = identities.get("a".repeat(22));
    assert.strictEqual(entry.grantId, null);
    assert.strictEqual(entry.grantUri, null);
    assert.strictEqual(entry.purpose, null);
    assert.deepStrictEqual(entry.containers, []);
    assert.strictEqual(entry.revoked, false);
    console.log("PASS AC5: pre-7.9-shaped file loads clean, new fields default null/[]/false");
    passed++;
  }

  // AC4: reserved fields present and explicitly null on a freshly minted grant.
  {
    const f = tmpFile();
    fs.writeFileSync(f, JSON.stringify({}), { mode: 0o600 });
    const slug = "b".repeat(22);
    await writeIdentity(
      slug,
      {
        ...baseEntry(),
        grantId: generateGrantId(),
        credentialRef: "https://pod.example.org/.account/x",
        containers: [],
        createdAt: new Date().toISOString(),
        expiresAt: null,
        lastUsedAt: null,
        revoked: false,
        grantUri: null,
        purpose: null,
        scope: null,
        excluded: null,
        consequenceOfRefusal: null,
      },
      f
    );
    const identities = loadIdentities(f);
    const entry = identities.get(slug);
    for (const field of ["grantUri", "purpose", "scope", "excluded", "consequenceOfRefusal"]) {
      assert.strictEqual(entry[field], null, `${field} should be explicit null`);
    }
    console.log("PASS AC4: reserved fields present and null on a freshly minted grant");
    passed++;
  }

  // AC6: duplicate webId refused, file untouched.
  {
    const f = tmpFile();
    const slug1 = "c".repeat(22);
    fs.writeFileSync(f, JSON.stringify({ [slug1]: baseEntry() }), { mode: 0o600 });
    const before = fs.readFileSync(f, "utf-8");
    const slug2 = "d".repeat(22);
    await assert.rejects(() => writeIdentity(slug2, baseEntry({ clientId: "different" }), f));
    const after = fs.readFileSync(f, "utf-8");
    assert.strictEqual(before, after, "file must be byte-identical after a refused write");
    console.log("PASS AC6: duplicate webId mint refused, file untouched");
    passed++;
  }

  // Regression guard for the 2026-08-12 live outage: an ALL-REVOKED file must
  // load cleanly and return an empty map, NOT throw. Throwing here deadlocked
  // production — the connector refused to boot, and /onboard/mint (the only
  // way to create a replacement identity) is served by that same process.
  {
    const f = tmpFile();
    const slug = "y".repeat(22);
    await writeIdentity(slug, baseEntry(), f);
    await updateIdentity(slug, { revoked: true }, f);
    const identities = loadIdentities(f); // must NOT throw
    assert.strictEqual(identities.size, 0, "all-revoked file must yield an empty active map");
    console.log("PASS all-revoked file loads clean and empty (no boot deadlock)");
    passed++;
  }

  // AC7: mint -> revoke -> boot (clean) -> re-mint same webId (accepted).
  {
    const f = tmpFile();
    const stableSlug = "z".repeat(22);
    await writeIdentity(stableSlug, baseEntry({ webId: "https://pod.example.org/stable/profile/card#me", clientId: "stable-client" }), f);
    const slug1 = "e".repeat(22);
    await writeIdentity(slug1, baseEntry(), f);
    let identities = loadIdentities(f);
    assert.ok(identities.has(slug1));

    await updateIdentity(slug1, { revoked: true }, f);
    identities = loadIdentities(f); // "boot" — must not throw, and must exclude the revoked row
    assert.ok(!identities.has(slug1), "revoked entry must be excluded from active map");

    const slug2 = "f".repeat(22);
    await writeIdentity(slug2, baseEntry(), f); // same webId as slug1, now revoked
    identities = loadIdentities(f);
    assert.ok(identities.has(slug2));
    console.log("PASS AC7: mint -> revoke -> boot clean -> re-mint same webId accepted");
    passed++;
  }

  // AC9: concurrent writes both land.
  {
    const f = tmpFile();
    fs.writeFileSync(f, JSON.stringify({}), { mode: 0o600 });
    const slugA = "g".repeat(22);
    const slugB = "h".repeat(22);
    await Promise.all([
      writeIdentity(slugA, baseEntry({ webId: "https://pod.example.org/a/profile/card#me" }), f),
      writeIdentity(slugB, baseEntry({ webId: "https://pod.example.org/b/profile/card#me", clientId: "client-b" }), f),
    ]);
    const identities = loadIdentities(f);
    assert.ok(identities.has(slugA) && identities.has(slugB), "both concurrent mints must land");
    console.log("PASS AC9: concurrent mints both land");
    passed++;
  }

  // AC8: mode 600 enforced after write.
  {
    const f = tmpFile();
    await writeIdentity("i".repeat(22), baseEntry(), f);
    const mode = fs.statSync(f).mode & 0o777;
    assert.strictEqual(mode, 0o600);
    console.log("PASS AC8: mode 600 after atomic write");
    passed++;
  }

  console.log(`\n${passed} checks passed.`);
}

main().catch((err) => {
  console.error("FAIL:", err);
  process.exit(1);
});
