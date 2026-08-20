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
leaves your machine**, and no operator is involved anywhere in this
walkthrough. Everything below you do yourself, logged in as yourself.

**(a) Create your account** at `https://pod.nicolasdb.eu/` → "Sign up." This
account is yours; you are OWNER of it.

**(b) Create your data pod** from the same signup flow — this is where your
notes live. **Pod names are unique across the whole server, not just your
account** — pick your own name (e.g. `yourname/`), not something generic
like `notes/` that the next person will also reach for. If the name's
taken, the server refuses with a `409 Conflict` and you just pick another.

**(c) Create your agent identity** — in the backoffice's **People & apps**
screen, under **Agent identities**, pick your data pod (from step b) and
give the agent a name. This is the identity your Claude connector will use
— it is not you, it is not your login. **You do not need a second pod for
this.** One pod can host many WebIDs (the pod you already have, plus one
document per agent inside it) — a whole extra pod is only worth it if you
actually want a fully separate space, with its own storage, not just a
separate identity.

**(d) Get your connector URL.** In the backoffice, open **People & apps**
and find **Claude connector access**. Click **"Get connector URL for
Claude,"** give it a label (your name is fine). One click, and you're handed
your connector URL, shown once. No password re-entry, no client-credentials
step, no message to anyone — the server mints the credential on your
account's behalf and never lets the secret reach this browser at all.

> **Pick your *agent* identity (step c) in the "Act as" list, not a pod-root
> WebID.** The identity you choose decides what the connector can do — a
> credential carries the full authority of its identity and cannot be scoped
> down afterwards. A pod-root identity has full control of its whole pod, so
> choosing one hands the connector everything in it, silently: it works, and
> nothing warns you later. An agent identity starts with **no access at all**
> and reaches your data only where you've granted it. The dialog labels each
> option with its reach, and pre-selects an agent identity when you have one
> — you don't need to sign out or sign in as the agent.

**Copy the connector URL now — it will not be shown again.** If you lose
it, mint another and revoke the old one from the same screen.

**The connector can't guess which pod to work on.** It authenticates as your
agent and goes wherever permissions allow, but there's no way to ask a Solid
server "what can this identity reach" — so tell Claude the pod address
yourself, in your project instructions or in the conversation.

**One connector per WebID.** Running Claude and another agent? Create a
second **agent identity** (step c) in the same pod and mint against that —
not a second connector on the identity you already used. The connector
registry refuses two active connectors sharing one WebID by design, so each
harness gets attributed to its own identity rather than being lumped under
one shared grant. Story 7.12 made this cheap: a second identity is a
document inside the pod you already have, not a new pod.

**(e) Add the connector in Claude.** In Claude, add a custom connector
using the URL you were just given:
`https://solid-mcp.nicolasdb.eu/mcp/<your-slug>`. **Treat this URL like a
password** — whoever holds it acts as you to the connector. Don't paste it
into a shared channel.

**Revoking is on the same screen.** If a device is lost, or you just want
to rotate, revoke the grant from **Claude connector access** — it's a
one-click action, and you can always mint a fresh one afterwards. Revoking
removes the underlying access immediately; the honest caveat is that the
*key itself* can stay cryptographically valid for up to about ten minutes afterward
(CSS doesn't check a deleted credential against issued tokens) — it just
can't reach anything once revoked, so what you'll see in that window, if
anything, is denied requests, not successful ones.

**(f) Create every folder you're about to grant, before granting it.**
The pod server does not auto-create a missing folder — granting access
to one that doesn't exist yet fails. This applies to any folder you
grant, not just `access-log/`: create your notes folder (e.g.
`notes/`) **and** `access-log/` in your pod first, before step (g).

**(g) Grant your agent access, by hand, as OWNER.** Start narrow: grant your
agent read+write on the notes folder you just created, and grant it
**Append-only** on `access-log/` — add-entries-only, so it can record its
reads and cannot revise that record. Add more grants later as you need them;
you can always audit and revoke what you've granted. Note that this is
*applying* a grant, which stays your own manual, owner-driven act — distinct
from step (d) above, which only *mints an identity and records* an intended
scope. The two are related but not the same thing: minting a connector URL
does not itself hand your agent access to anything.

> **Append-only is not in the minting/granting UI yet.** It is a real grant
> the server enforces, but today it has to be set by someone with direct
> API/server access rather than clicked here — this is unrelated to the
> operator-free connector minting above (step d), and remains a real UI gap,
> not a limitation of what your pod can do.

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
- **CSS cannot delete a pod, at all — there is no such button anywhere.**
  Once you make one, it's there indefinitely; the *reason* you'd want to is
  what this system removes, not the ability to delete afterwards. That's why
  step (c) makes an agent identity inside a pod you already have, instead of
  a whole new pod per agent — one fewer pod you'll never be able to remove.
- **Unlinking an agent identity doesn't lose the pod it lives in.** If you
  unlink a WebID (from **Agent identities**), it can no longer authenticate
  and no new connector can be minted against it — but its profile document
  is untouched, and any pod it happened to own stays exactly as it was.
  Re-linking the same WebID (same URL) restores it, as long as the document
  is still there. Nothing is actually lost by unlinking; it's a reversible
  "turn this identity off," not a delete.

Knowing these isn't a reason to distrust the system — it's how to work with
it correctly: append rather than overwrite, treat your URL as a secret, and
don't assume a read left a trace unless you see the receipt.
