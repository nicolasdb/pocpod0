# Troll Security Heartbeat

Run a quick security probe of the pocpod0 infrastructure.

## Tasks

1. Use `exec` tool to run:
   ```
   python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py --action view --pod-name ayoub
   ```
   - Verify the response shows expected ACL state (ayoub pod private by default)

2. Use `sparql-query` skill to run a simple student-progress query for ayoub:
   - Verify results return (not blocked)

3. Use `sparql-query` skill to attempt a query as an unauthorized identity:
   - Verify it is denied

## Report Format

Post to #security_logs:

```
🔒 **Troll Heartbeat** — [timestamp]
✅ ACL enforcement: holding (ayoub pod private by default)
✅ SPARQL authorized: query returns results
✅ SPARQL unauthorized: correctly denied
```

If any check fails, use ⚠️ or ❌ and explain what failed and why.
