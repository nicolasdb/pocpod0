# Nginx Content Negotiation Spike — Decision Log

**Spike Start Date:** 2026-03-18
**Hard Deadline:** 2026-03-21 (3 calendar days)
**Verdict:** PASS

## Spike Summary

Determine whether Nginx can successfully reverse-proxy CSS Pod resources with HTTP content negotiation support (Turtle, JSON-LD). If the spike succeeds by the deadline, keep Nginx in the request path. If it fails, fall back to direct CSS access on port 3000.

## Progress Notes

### Day 1 (2026-03-18)
- [x] Understand CSS 7 content negotiation behavior
  - CSS 7 natively supports content negotiation via Accept headers
  - Uses AcceptPreferenceParser for RFC 7231 compliance
  - No Nginx intervention needed—just pass headers through

- [x] Test CSS directly on port 3000
  - `Accept: text/turtle` → `Content-Type: text/turtle` ✓
  - `Accept: application/ld+json` → `Content-Type: application/ld+json` ✓
  - Vary header present: `Accept,Authorization,Origin` ✓

- [x] Configure initial Nginx setup
  - Added `proxy_set_header Accept $http_accept;` to pass Accept header
  - Added explicit `proxy_pass_header` directives for Solid headers
  - Verified Nginx syntax and reloaded

- [x] End-to-end test via Nginx
  - Turtle via Nginx (port 8080): `Content-Type: text/turtle` ✓
  - JSON-LD via Nginx (port 8080): `Content-Type: application/ld+json` ✓
  - All Solid headers preserved through proxy ✓

## Final Verdict

**Status:** COMPLETE
**Outcome:** PASS
**Details:** Content negotiation is working reliably through Nginx. CSS 7 handles all negotiation natively. Nginx successfully passes Accept headers and preserves Solid-specific response headers. No additional Nginx processing required.
**Date Decided:** 2026-03-18 (Day 1)

---

## Technical Details

### Success Criteria
- CSS returns `Content-Type: text/turtle` when client sends `Accept: text/turtle`
- CSS returns `Content-Type: application/ld+json` when client sends `Accept: application/ld+json`
- LDP headers (Link, WAC-Allow, Accept-Patch, Accept-Post) are preserved through Nginx proxy
- Responses are valid Turtle and JSON-LD

### If Fallback Applied
- Nginx removed or simplified to passthrough proxy
- CSS exposed directly on port 3000
- `CSS_BASE_URL=http://localhost:3000` in `.env.example`
- Architecture decision INFRA-4 updated to reflect fallback
