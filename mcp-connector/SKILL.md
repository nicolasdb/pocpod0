---
name: solid-pod-capture
description: Use when the person in a Claude conversation wants to save, capture, externalize, or "put this in my pod" — turning insight from the chat into a durable note in their own Solid Pod, and later finding, reading, and building on what's already there. Covers when to offer capture, where it goes, what shape it takes, and how to read it back. For the underlying toolkit (auth, podClient, wacManager, mcp-server) see references/developer-toolkit.md.
---

# Capturing into a Solid Pod

Your pod connection is a **capture path**, not a document dump: externalize
something worth keeping from this conversation into the person's own pod —
and, unlike an artifact you download and re-import, **read it back later and
build on it**. Ten tools are available: `solid_read_resource`,
`solid_list_container`, `solid_get_permissions` (all safe, no ceremony),
`solid_append_resource` (the default write path), `solid_write_resource`,
`solid_delete_resource`, the three permission tools (`solid_grant_access`,
`solid_revoke_access`, `solid_set_public_access`), and `solid_prepare_upload`
(for a file that already exists on disk — see "Uploading an existing file"
below; **shell-capable clients only**, not claude.ai).

## When to offer capture

Offer it when the person says something that reads as "keep this" —
decisions, running notes, a synthesis worth finding again — not for every
reply. If they say "save this to my pod" or similar, act; don't ask them to
repeat themselves.

## Before the first capture: know the pod root

You cannot guess a pod's root URL. If you don't already know it for this
person, ask once, up front, rather than failing a tool call first and asking
after. A typical layout looks like `https://pod.example.org/<name>/`, with
capture notes living under a `shared/` (or similar, person-specific)
container inside it.

## Append vs. new resource — append is the default

**`solid_append_resource` is the default.** It reads what's there, adds your
content after it, and creates the resource if it's absent — it can never
silently replace existing content. Reach for `solid_write_resource` only when
you genuinely mean "replace this entire resource," and expect it to report
what it's about to overwrite (existing size + first line) so the human is
confirming against reality, not a URL. Creating a brand-new resource with
`solid_write_resource` is fine and unceremonious; overwriting an existing one
is not.

Why append-first: pods have no versioning yet. Until they do, append **is**
the safety mechanism — an overwrite you didn't mean is unrecoverable.

Concurrency note: neither tool does optimistic locking (no ETag/If-Match).
Two near-simultaneous appends to the same resource are a last-writer-wins
race. Fine for one person capturing from one conversation at a time; say so
if it matters for the case at hand.

## Naming and shape of a captured note

- One resource per topic/thread, not one giant running file — makes read-back
  targeted instead of "read everything and hope."
- A short, stable, human-guessable name (e.g. `meeting-notes-2026-08-02.md`,
  not a UUID) — the person should be able to find it themselves later too.
- Lead each append with a dated header line (`## 2026-08-02 — <topic>`) so a
  resource that accumulates multiple sessions stays scannable on read-back.
- Plain text/Markdown (`text/markdown` or `text/plain`) is the default
  content type for capture notes — use `text/turtle` only for actual RDF.

## Reading back and extending

Before writing, check whether a note on this topic already exists:
`solid_list_container` the target container, and if a matching name turns
up, `solid_read_resource` it first. If it does exist, append to it rather
than creating a sibling with a slightly different name — that fragmentation
defeats the whole point of read-back. This round trip — capture now, find
and extend later, possibly in an entirely different conversation — is the
thing artifact-download-and-reimport can't do, and is the reason this
connector exists.

## Destructive actions need a human, explicitly

`solid_write_resource` (when overwriting) and `solid_delete_resource` both
carry `destructiveHint: true`. Treat that as a signal to pause and confirm
with the person before calling them — describe concretely what will be lost,
not just the URL. Note the honest limit: MCP annotations are *hints*: some
clients gate on them with a visible approval prompt, some don't. Don't assume
the client's UI is your only safety net — confirm in the conversation too.

`solid_delete_resource` on a container only works if it's empty; deleting a
container recursively is out of scope for this connector entirely (a
separate, owner-driven flow exists elsewhere). A delete that reports success
is verified gone, not assumed.

## Read receipts (when reading something you don't own)

Reading a resource whose pod root differs from your own identity's pod root
posts a receipt (timestamp, your label, the resource, the outcome) as its own
new resource in *that resource's owner's* `access-log/` container — not your
own. One resource per receipt, because that is the write an **append-only**
grant permits: you can add entries there and cannot read, overwrite, or
delete the ones already written, including your own. So a person asking "can
your agent quietly edit the log of what it read?" gets a straight no — the
server refuses it (verified live 2026-08-11).

Two things that no is *not*:

- It is **not enforcement of logging.** The pod server keeps no read log of
  its own. This works only because the connector chooses to write receipts. A
  reader that declines to write one leaves no trace by this mechanism. If a
  person asks whether their pod logs who reads it: it doesn't, on its own.
- It is **not protection from the pod owner.** They hold control over their
  own `access-log/` and can edit it. The receipt is evidence against the
  reader, which is the direction that matters — evidence held by the party
  being audited could be quietly deleted by them.

If you don't have the append-only grant, the receipt attempt fails quietly in
the background and the read still succeeds.

Reading someone else's resource is a little slower than reading your own,
because of this receipt attempt (and a possible one-time reauth retry) — it
never fails or blocks the read, but don't be surprised if a foreign read
takes noticeably longer than one from your own pod.

## Uploading an existing file

If a file **already exists on disk** — a screen capture, an audio message, a
session transcript a script just wrote — do not read it into context and
re-emit it as `content:` on `solid_write_resource`/`solid_append_resource`.
For anything past a few KB that is slow, truncation-prone, and hits a hard
100kb ceiling on the JSON-RPC path.

Use `solid_prepare_upload(targetUrl, contentType, bytes)` instead. It returns
a ready-to-run command:

```
curl --data-binary @<path-to-file> <uploadUrl>
```

Run that command yourself, from your own shell, with the real local path
substituted in. The bytes go straight from disk to the pod; they never pass
through this tool call as an argument. The URL is a one-time credential —
expires in 5 minutes, works once, bound to the target URL and this identity —
so don't paste it anywhere else, and don't wait to run the command.

Writing to a resource that already exists needs `overwrite: true`, same
ceremony as `solid_write_resource` — you'll be told what's there first if you
omit it.

**This tool needs a shell. claude.ai does not have one and cannot run the
returned command** — asking it to "upload a file" will get you a ticket
claude.ai then has no way to redeem. For claude.ai, the answer stays:
download the file, then upload it from the backoffice
(https://backoffice.nicolasdb.eu). Shell-capable clients (Claude Code, a
local script) are the only intended users of this tool.

Chunked/multi-call append of a large file through tool arguments is
explicitly not supported — don't slice a big file into pieces to route
around the size limit; use this tool instead.

## What this skill does not cover

Recursive container deletion, pod versioning/undo, granting or revoking WAC
permissions on someone else's behalf without their say-so, and anything
about setting up a new person's identity or credentials — those are separate,
larger, human-mediated flows. For the toolkit internals (auth, podClient,
wacManager, running the MCP server yourself), see
`references/developer-toolkit.md`.
