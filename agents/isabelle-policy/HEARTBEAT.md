# Isabelle Policy Heartbeat

Check the aggregate consent state for the regional program.

## Tasks

1. Use `sparql-query` skill to run the aggregate-anonymized template for the STEM/robotics program
2. Note the total consented student count

## Report Format

Post to #general:

```
📊 **Policy Check** — [timestamp]
Consented students in STEM aggregate: [count]
Program status: nominal
```

If the count changed since last check, note: "⬆️/⬇️ Count changed from X to Y"
