# ICT Help Desk (blueprint)

Complaints and ticketing with live Socket.IO notifications, for the Public Benefit
Organizations Regulatory Authority ICT department.

**This is not a separate service.** It is a Flask blueprint mounted on the maintenance
report app at `/helpdesk`, sharing its host, port, database, and migration chain. Run Flask
once from the project root and the **Report a Problem** button works — there is no second
server to start and no port to keep in sync.

| URL (relative to whatever port the app runs on) | Who |
| --- | --- |
| `/helpdesk/` | Anyone — submit a complaint |
| `/helpdesk/track` | Reporter — find a ticket by reference + tracking code |
| `/helpdesk/ticket/<reference>?token=…` | Reporter (token) or signed-in staff |
| `/helpdesk/complaints` | Any signed-in account — tracker of every complaint |
| `/helpdesk/staff` | Live dashboard (help desk roles only) |
| `/helpdesk/staff/export.csv` | CSV export |

## Layout

| File | Purpose |
| --- | --- |
| `__init__.py` | `register_helpdesk(app)` — mounts the blueprint and the Socket.IO handlers |
| `blueprint.py` | The `helpdesk` blueprint, with its own template and static folders |
| `routes.py` | Reporter and staff views |
| `events.py` | Socket.IO handlers (`join_dashboard`, `join_ticket`) |
| `access.py` | Token authorisation for reporters; help desk capability for signed-in users |
| `models.py` | `Ticket`, `TicketEvent` — part of the root migration chain; accounts live in the shared `users` table |
| `services.py` | Ticket operations; the single place that writes state and broadcasts |
| `catalog.py` | 22 common PC/laptop problems, priorities, and self-help steps |
| `seed_data.py` | Help desk accounts and sample tickets |
| `templates/helpdesk/` | Namespaced so it cannot collide with the maintenance templates |
| `static/js/helpdesk.js` | Served at `/helpdesk/static/js/helpdesk.js` |

## What a User Does

1. Opens `/helpdesk/`, picks their problem from a dropdown of common office PC and laptop faults.
2. Sees self-help steps for that problem before submitting — many issues never need a ticket.
3. Submits and gets a reference (`HD-2026-0001`) plus a private tracking link. **No account needed.**
4. Follows progress live, replies to the help desk, and can say "my problem is resolved"
   or reopen the ticket if it comes back.

## What the Help Desk Does

Sign in at `/login`, then work the queue at `/helpdesk/staff`:

- Live tiles for open / in-progress / overdue / unassigned counts.
- Active queue sorted most urgent first, then oldest first.
- **Pick, Return and Transfer** on every row — see below.
- Views for *My tasks*, *Unassigned*, and each status.
- Toast notifications for new complaints and for resolutions, over a real WebSocket.
- Re-prioritise, reply, and mark resolved with required resolution notes.
- Export everything to CSV.

## Picking Up Work

ICT officers, interns and managers all work the same queue. Each row carries the actions
that apply to it:

| Ticket is… | Actions on the row |
| --- | --- |
| unassigned | **Pick** · **Transfer to…** |
| yours | **Yours** badge · **Return** · **Transfer to…** |
| someone else's | nothing, unless you are the ICT manager |

- **Pick** takes the task and moves it to *In Progress*.
- **Return** hands it back to the unassigned pool and moves it to *Open*, so somebody else
  can take it. It does not vanish into limbo.
- **Transfer to…** hands it to another account — officer, intern, manager or administrator.

A task already held by a colleague cannot be taken or returned by anyone except that
colleague or the ICT manager, who can always take over. Every pick, return and transfer is
written to the ticket's audit trail with the actor and their role, so a task's handover
history is visible on the ticket.

## Email

Every new complaint is emailed to `NOTIFY_EMAILS` (`jonyango@pbora.go.ke` and
`ictsupport@pbora.go.ke`) plus every platform account holding an email address, with the
reporter as `Reply-To` and `PBORA` as the sender name. Delivery is best-effort on a
background thread: a mail failure is logged and never loses the ticket. See the root
README for the Gmail settings.

## Who Can Close a Ticket

Deliberately restricted: **the reporter or the ICT manager.** A help desk officer can resolve
a ticket but cannot declare it finished — that stops tickets being closed before the person
with the problem agrees it is fixed.

| Action | Reporter | Intern | Officer | ICT Manager |
| --- | :-: | :-: | :-: | :-: |
| Raise a ticket | ✓ | | | |
| Comment | ✓ | ✓ | ✓ | ✓ |
| Pick / return / transfer own task | | ✓ | ✓ | ✓ |
| Take over someone else's task | | ✗ | ✗ | ✓ |
| Re-prioritise | | ✓ | ✓ | ✓ |
| Mark resolved | ✓ | ✓ | ✓ | ✓ |
| **Close** | ✓ | ✗ | ✗ | ✓ |
| Reopen | ✓ | | | ✓ |

## Problem Categories

22 common office PC and laptop problems (`catalog.py`), each carrying a default priority and
self-help steps: won't power on, slow or freezing, blue screen, no internet, printer or
scanner, email, password or lockout, software install, application error, keyboard/mouse/
monitor, battery or adapter, sound/microphone/camera, disk full, lost files, virus or malware,
suspected phishing, VPN, shared drive, overheating, screen, backup failure, and an open-ended
**Other**, whose *Describe the problem type* box is a free-text area the reporter fills
in themselves. Tables and email subjects show a shortened one-line form of it; the full
text appears on the ticket and in the notification email.

Priority is derived from the category, so a reporter is never asked to judge urgency — data
loss, malware, phishing, and a dead machine come in as Urgent automatically. The help desk can
override it, which recalculates the SLA target.

## Socket.IO

Rooms are authorised server-side, not by trusting the client:

- `helpdesk` — joined only by a signed-in staff session (`join_dashboard`).
- `ticket:<reference>` — joined by staff, or by a reporter presenting the correct token
  (`join_ticket`).

Server events: `ticket:created`, `ticket:updated`, `ticket:comment`, `ticket:resolved`, `stats`.

`ticket:resolved` is the explicit "a problem has been resolved" alert, and carries
`self_resolved` so the dashboard can distinguish "the user fixed it themselves" from
"an officer fixed it".

## Accounts

There is no separate help desk login. Sign-in is the app-wide `/login`, backed by the one
`users` table, and help desk access is the `helpdesk_role` column on that account
(`officer` or `manager`). An administrator counts as a manager. ICT staff therefore hold a
single credential for the maintenance admin area and the help desk.

**Every seeded password is `field.123`.**

| Username | Help desk role | Can close tickets |
| --- | --- | :-: |
| `jonyango` | manager (also administrator) | ✓ |
| `ictmanager` | manager | ✓ |
| `icthelpdesk` | officer | |

Help desk roles are `intern`, `officer` and `manager`. Interns and officers have the same
queue powers; the role is what appears against their actions in the audit trail. Create
interns at `/admin` by choosing **ICT intern** under *Help desk access*.

The administrator grants help desk access when creating a user at `/admin`. Only accounts
carrying a help desk role (or the administrator) can be assigned a ticket.
