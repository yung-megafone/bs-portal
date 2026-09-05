# SHIT Guide — Ticketing, Board, Assets, Comments, and Queues

**SHIT (Software Helpdesk and Internet Technology)** is the operational work-management module in B.S. Portal `v0.2.0-alpha`.

Use SHIT for work that needs to be tracked as an incident/request/change/problem/etc. Use **BAMR** for the resource waitlist/reservation itself. A SHIT ticket may depend on assets and reference the BAMR that supports the work without turning routine equipment allocation into another helpdesk ticket.

## 1. Ticket identifiers

Tickets receive an immutable identifier:

```text
SHIT-YY-HHHHHH
```

The six-character suffix is uppercase hexadecimal and protected by a database unique constraint.

## 2. Ticket types

- Incident
- Service request
- Access request
- Change request
- Problem
- PSOP / documentation
- Feedback / note
- Other

## 3. Severity

- `NONE`
- `SEV-5`
- `SEV-4`
- `SEV-3`
- `SEV-2`
- `SEV-1`

Severity and Board queue position are independent. Reordering a card never changes severity.

## 4. Ticket statuses

The Board and normal management form use the same nine status values:

1. New
2. Acknowledged
3. Assigned
4. In progress
5. Waiting on requester
6. Waiting on vendor
7. Resolved
8. Closed
9. Cancelled

Status transitions go through the SHIT service layer. Resolved/closed timestamps and history are therefore preserved whether the change came from drag/drop or the normal management form.

## 5. Creating a ticket

Use **SHIT → Submit ticket**.

Fields:

- Title;
- Description;
- Ticket type;
- Severity;
- optional route-to department;
- optional selection of multiple existing BAM assets;
- one initial relationship type applied to all selected assets;
- optional related document/PSOP ID;
- optional attachment.

New tickets start in `New`. The requester is the signed-in user.

## 6. Scopes

SHIT list/board supports:

### My tickets

Tickets where you are requester or assigned user.

### Department queue

Tickets assigned to one of your active departments.

### All tickets

Staff/superusers only. A non-staff user requesting All is forced back to My tickets.

The currently selected scope is not persisted as a browser preference in v0.2.0-alpha.

## 7. Board and List

### Board

Board is the default for a browser with no saved SHIT view preference. Every actual ticket status is a column.

Horizontal card movement changes status. Vertical movement controls queue order inside the target status.

Drag/drop sends the server the target status and an optional visible queue neighbor. The server revalidates authorization and the neighbor's current status before writing anything.

The service normalizes stored queue positions instead of trusting arbitrary client coordinates.

### Accessible queue controls

The Board also supports non-drag movement:

- Up;
- Down;
- Top;
- Bottom;
- status selection.

A status change without a drag position appends the ticket to the target status queue.

### List

List presents the same Ticket records in a conventional table. Search works in either presentation.

### Saved presentation preference

Selecting List/Board persists the preference. Board is the fallback default. Dense/Compact detail layout is stored similarly.

## 8. Search

Ticket search matches:

- ticket number;
- title;
- description;
- related document ID;
- linked BAM asset ID;
- linked asset manufacturer;
- linked asset model.

## 9. Ticket detail

The detail page combines:

- dense ticket identity/status header;
- description/work context;
- linked BAM assets;
- permission-filtered supporting BAM requests;
- requester-visible comments/internal notes according to role;
- attachments;
- event/history records for managers;
- management controls for authorized agents.

Dense and Compact are presentations of the same underlying record, not different ticket models.

## 10. Multiple BAM assets per ticket

SHIT uses `TicketAssetLink` so one ticket can relate to multiple BAM records.

Relationship types:

| Relationship | Intended meaning |
| --- | --- |
| Related | general connection |
| Affected asset | asset directly affected by the issue/work |
| Required for work | resource the ticket depends on |
| Test equipment | asset being used as instrumentation/test equipment |
| Replacement / alternate | fallback/replacement resource |
| Supporting resource | supporting data/file/equipment |

Each relationship can have a ticket-specific note.

The legacy single `related_asset` field remains temporarily for migration compatibility; new workflows use `TicketAssetLink`.

### Important: relationship does not allocate

Linking a radio as **Required for work** does not reserve the radio. Create a BAMR when the ticket needs an actual resource window.

The BAMR can cite the SHIT ticket, and the SHIT ticket detail will show supporting BAM requests that the current viewer is authorized to see.

## 11. Adding/editing/removing asset links

Ticket managers can:

- add another BAM asset;
- change relationship type/note;
- remove a relationship.

Each operation writes a SHIT event:

- Asset linked;
- Asset unlinked;
- Asset relationship changed.

Changing a ticket's ordinary status/severity/assignee does not modify these relationships.

## 12. Comments

Comment visibility:

- **Requester visible**;
- **Internal note**.

Any ticket viewer can add requester-visible comments. Only users who can manage the ticket may add Internal notes. Non-managers do not receive internal comments in their detail queryset.

### Current limitation

Typed strings such as `BS-SR69-R-6969` or `SHIT-26-ABC123` inside freeform comment prose are plain text in v0.2.0-alpha. Automatic comment reference parsing/autocomplete/backlinks are planned but not implemented.

## 13. Attachments

Ticket viewers can add an attachment. SHIT records:

- original filename;
- MIME type;
- size;
- SHA-256;
- uploader;
- created time.

Attachment bytes live under BSP media storage, not inside MySQL. Include media when making portable backups if attachments need to move with the database.

## 14. Ticket management

Authorized managers can change:

- status;
- severity;
- assigned department;
- assigned user;
- related document.

If both department and assignee are selected, a non-staff assignee must be an active member of the assigned department.

Ticket event history records changes to status, severity, department, assignee, and related document.

## 15. Visibility and management rules

### Staff / superuser

Can see/manage all SHIT tickets.

### Non-staff visibility

Can view a ticket when any of the following is true:

- requester is the current user;
- assigned user is the current user;
- current user is an active member of the assigned department.

### Non-staff management

Can manage a ticket when:

- assigned user is the current user; or
- current user is an active member of the assigned department.

Being the requester alone does not grant management authority.

## 16. Board limits

List/Board views cap the rendered result set at 500 tickets in the current alpha implementation. Managers should use scope/search to narrow very large datasets.

## 17. Ticket event/history types

Current event types include:

- Created;
- Commented;
- Internal note;
- Attachment added;
- Status changed;
- Severity changed;
- Department changed;
- Assignee changed;
- Asset linked/unlinked/relationship changed;
- Document linked;
- Queue reordered.

This module history is operationally useful but is not yet the future centralized tamper-resistant audit ledger.

## 18. Example: RF capture project

A SHIT ticket might represent:

> Establish TYT MD-UV390 Plus Signaling Capture Corpus

Linked assets could be:

- DEV5 laptop — **Required for work**;
- RTL-SDR — **Test equipment**;
- MD-UV390 — **Test equipment**;
- canonical `data.zip` corpus — **Supporting resource**.

The ticket records the work. A BAMR records the requested checkout windows for the physical equipment. The file asset can remain a supporting reference without being physically checked out.

## 19. Planned but not present

- ticket-to-ticket Blocks/Blocked-by/Duplicate/Parent-child relationships;
- comment autocomplete for assets/tickets/users;
- automatic autolinking of identifiers typed in comments;
- saved named filters/views;
- global Ctrl+K command palette.
