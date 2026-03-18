# Edge Case Hunter Review Prompt
## Story 1.5: Troll ACL Enforcement Validation

**Instructions:** You are an Edge Case Hunter. Walk every branching path, boundary condition, and error handling scenario. Report ONLY unhandled edge cases — places where code could fail unexpectedly.

**Story Context:**
- Troll agent tests ACL enforcement by making HTTP requests to CSS
- Tests: unauthenticated (401/403), unauthorized (403), authorized (200)
- Must handle errors gracefully (errors = partial results, not failures)
- Results logged as structured JSON, blocking flag on failures
- Must test 6 pods, unauthorized access matrix, positive test cases

**Files in Scope:**
- `agents/troll-adversary/attacks/acl_enforcement.py` (418 lines)
- `agents/troll-adversary/attacks/__init__.py` (9 lines)
- `pipeline/tests/integration/test_troll_acl.py` (337 lines)
- `pipeline/src/pocpod0_pipeline/provision_pods.py` (modified)
- Configuration: `.acl` files, `docker-compose.yml`, `infra/css/config.json`

**Edge Cases to Probe:**
1. **Network Failures:**
   - CSS unreachable (connection refused, timeout)
   - DNS resolution fails
   - SSL/TLS handshake fails
   - Slow network (hanging requests)

2. **HTTP Anomalies:**
   - Unexpected status codes (500, 502, 504, 429, etc.)
   - Malformed responses (missing headers, truncated body)
   - Redirects (3xx responses)
   - No response body when body expected

3. **Authorization & Headers:**
   - Authorization header malformed or missing
   - WebID format incorrect or invalid
   - Header size limits exceeded
   - Special characters in WebID not escaped

4. **Pod & Data Issues:**
   - Pod doesn't exist at CSS
   - Pod exists but ACL file missing/malformed
   - ACL file valid but empty
   - Concurrent ACL modifications during test

5. **Timing & Concurrency:**
   - Test execution order affects results (state leakage)
   - Concurrent tests race on shared state
   - Timeout handling (what's the timeout value?)
   - Retry logic (are retries implemented? What if none?)

6. **Data Model & Logging:**
   - TrollTestResult missing required fields
   - JSON serialization fails (non-serializable objects)
   - Timestamp format invalid
   - Evidence dict contains circular references

7. **Test Suite Control Flow:**
   - What if one test crashes? Do remaining tests run?
   - What if summary generation fails?
   - What if test ordering is non-deterministic?
   - How does blocking flag interact with partial results?

8. **Environment & Configuration:**
   - CSS_BASE_URL not set or invalid
   - CSS config file doesn't mount
   - Pod `.acl` files don't exist or aren't readable
   - provisioner identity not recognized

9. **Boundary Conditions:**
   - Pod names with special characters
   - Very long pod names
   - Empty ACL files
   - WebID with unusual characters/encoding

**Output format:** Markdown list of edge cases with:
- **Title**: edge case or boundary condition
- **Evidence**: code path or condition not handled
- **Impact**: what goes wrong

Please run this review and paste back your findings.
