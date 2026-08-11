# Your Pod, Your Agent, Your Grants

You've been told "put your notes in a pod." This page explains what that
actually means, walks you from zero to a working connector in Claude, and
tells you honestly what the system does and does not guarantee.

## The model (read this first)

You are creating an account at `pod.nicolasdb.eu`. That makes you **OWNER**
of that account — the strongest role Solid has, and nobody else holds it for
you.

**Nobody overwrites your pod but your own AGENT.** Your agent is a *separate
identity* — its own WebID, its own credential — that Claude uses on your
behalf. You are not "logging Claude in as you." You create the agent, and
you **grant** it access to specific folders in your pod. Everything
outside those grants stays closed to it by default.

Everything else you'll hear about — someone else's agent reading your
`access-log/`, a collective service reading your school's aggregate — is the
same idea: a grant *you* hold on *someone else's* pod, or someone else holds
on yours. You can see every grant and revoke it. The one exception is an
**append-only mailbox**: some folders (like `access-log/`) only accept new
entries — a grant there lets someone add an entry, never read, edit, or
delete what's already in it. That's what makes an access log trustworthy:
the agent writing entries about its own reads cannot go back and remove one.
This is live as of 2026-08-11, verified against the real server. It has one
honest edge, spelled out in the limits section: it constrains the *reader*,
not you — the log lives in your pod and you hold full control over it.

**Why isn't there just one shared agent login for the team?** Because a
shared secret is a skeleton key: whoever holds it can act as *everyone* it
was granted for, there's no way to tell which human triggered which write,
and one person leaving means rotating a secret every other person also
depends on. What scales instead is **grants, not credentials** — one agent
identity per person, each individually granted into only what it needs.

## The three identities you'll hear about

- **Personal agent** — one human, one agent, capture into your own pod. **This
  walkthrough covers this case.**
- **Collective service agent** — nobody personally holds it; it runs
  unattended (e.g. a scheduled job) and only ever touches a collective's own
  pods, never a person's.
- **Role-assigned control** — a role like "class rep" or "team lead" holds
  Control over a shared pod. Roles are named bundles of grants, not
  identities — when someone new takes the role, grants move, no credential
  changes hands. There's no UI for this yet; today it's done by hand.

## Walkthrough: from zero to capturing

Your OWNER credential (the email + password you register with) **never
leaves your machine** and the person running the connector never asks for
it. Everything below except step (e) you do yourself, logged in as
yourself.

**(a) Create your account** at `https://pod.nicolasdb.eu/` → "Sign up." This
account is yours; you are OWNER of it.

**(b) Create your data pod** from the same signup flow — this is where your
notes live. **Pod names are unique across the whole server, not just your
account** — pick your own name (e.g. `yourname/`), not something generic
like `notes/` that the next person will also reach for. If the name's
taken, the server refuses with a `409 Conflict` and you just pick another.

**(c) Create your agent pod**: a second pod on the *same account*, with its
own WebID. This is the identity your Claude connector will use — it is not
you, it is not your login. Same uniqueness rule applies: name it something
like `yourname-agent/`, not a generic `agent/` — that name is only free for
the first person who claims it.

**(d) Mint AGENT client-credentials.** Still at `https://pod.nicolasdb.eu/`,
sign in, open **Apps & credentials**, and mint a client-credentials pair for
your *agent's* WebID (not your own). Copy the `clientId` and `clientSecret`
now — the one-time reveal won't show the secret again.

**(e) Hand the operator four things**: your agent's `clientId`,
`clientSecret`, `webId`, and a short `label` (your name is fine). They add
one entry to the connector's identity map and run its slug generator for
you. This takes effect on your very next request — no restart, nothing else
to wait for. (A later story will turn this into a button; today it's a
short message to the operator.)

**(f) Add the connector in Claude.** The operator gives you your URL:
`https://solid-mcp.nicolasdb.eu/mcp/<your-slug>`. In Claude, add it as a
custom connector using that exact URL. **Treat this URL like a password** —
whoever holds it acts as you to the connector. Don't paste it into a shared
channel.

**(g) Create every folder you're about to grant, before granting it.**
The pod server does not auto-create a missing folder — granting access
to one that doesn't exist yet fails. This applies to any folder you
grant, not just `access-log/`: create your notes folder (e.g.
`notes/`) **and** `access-log/` in your pod first, before step (h).

**(h) Grant your agent access, by hand, as OWNER.** Start narrow: grant your
agent read+write on the notes folder you just created, and grant it
**Append-only** on `access-log/` — add-entries-only, so it can record its
reads and cannot revise that record. Add more grants later as you need them;
you can always audit and revoke what you've granted.

> **Append-only is not in the minting UI yet.** It is a real grant the server
> enforces, but today it has to be set for you rather than clicked — ask the
> operator. Everything else on this page is self-service; this one step is
> not, and that is a UI gap, not a limitation of what your pod can do.

**State your pod's own root URL to Claude on first use** — something like
`https://pod.nicolasdb.eu/<your-account-name>/`. Claude cannot guess it and
will otherwise ask you cold before any tool call works, so give it up
front.

## Day to day

Capture a note, ask Claude to read it back in a *later* conversation, extend
it. That read-back round trip — not a download-and-reimport — is the whole
point: your notes live in your pod, not in the chat. See the capture skill
for the actual commands.

## Honest limits — read these, don't skip them

- **Destructive-action confirmations are hints, not guarantees.** Claude.ai
  is observed pausing twice (its own text confirmation, then a native
  approval dialog) before a destructive call — but that's *this client's*
  current behaviour, not a protocol promise. The guarantee only holds as
  long as the client honours the hint.
- **Read receipts are a voluntary convention, not enforcement.** The pod
  server keeps no per-resource read log of its own. If a reader chooses not
  to write a receipt, there's no trace that a read happened.
- **There is no pod versioning.** Appending is safe; overwriting can lose
  data permanently. When in doubt, append.
- **Your connector URL *is* a credential.** Anyone holding it is you, as far
  as the connector is concerned.
- **Append-only constrains the reader, not you.** Your agent — and anyone
  else's agent writing receipts into your `access-log/` — can add entries and
  cannot read, edit, or delete them. You can: it is your pod and you hold
  full control over every folder in it. So the log is evidence against *them*,
  not against you. That follows from where the log lives, and the log has to
  live in your pod — a receipt held by the party being audited could be
  quietly deleted by them.
- **A receipt records a read; it doesn't record what was done next.** Once a
  reader has your file, the receipt says they took it. It cannot say what
  they did with it afterwards.

Knowing these isn't a reason to distrust the system — it's how to work with
it correctly: append rather than overwrite, treat your URL as a secret, and
don't assume a read left a trace unless you see the receipt.
