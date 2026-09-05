# BAM Guide — Assets, Requests, Allocation, Checkout, and Automation

**BAM (B.S. Asset Management)** is both the authoritative asset register and the resource-allocation subsystem in B.S. Portal `v0.2.0-alpha`.

The most important conceptual rule is:

> **Reference ≠ reservation ≠ checkout ≠ custody.**

A SHIT ticket can reference an asset without reserving it. A BAMR reservation can commit an asset for next week without pretending the requester holds it today. A checkout creates actual custody.

## 1. Asset identity

BAM asset IDs are immutable application identifiers:

```text
BS-{DEPARTMENT}-{TYPE}-{4HEX}
```

Examples:

```text
BS-SR69-R-6969
BS-DEV5-L-21CE
BS-SR69-F-B640
```

The 4-hex suffix is unique inside the organization/department/type namespace. Registration may request a preferred suffix. BAM tries that value first and falls back to a random cryptographically generated suffix if the preferred candidate collides.

### Default asset type seed data

The `seed_bam` management command defines the current standard type codes:

| Code | Type |
| --- | --- |
| R | Radio |
| B | Battery |
| L | Laptop |
| D | Desktop |
| S | Server |
| N | Network Equipment |
| P | Phone |
| T | Tablet |
| M | Monitor |
| C | Camera |
| V | Vehicle Equipment |
| H | Headset |
| K | Keyboard |
| X | Charger / Power Supply |
| F | File / Document |
| O | Other |

### Default lifecycle status seed data

| Code | Name | Terminal? |
| --- | --- | --- |
| ACTIVE | Active | No |
| RESERVED | Reserved | No |
| STORAGE | Storage | No |
| REPAIR | Repair | No |
| LOST | Lost | No |
| RETIRED | Retired | Yes |
| DISPOSED | Disposed | Yes |

`REPAIR`, `LOST`, `RETIRED`, `DISPOSED`, and administrative `RESERVED` are excluded from normal automated allocation matching. Terminal status also records `retired_at`.

## 2. Registering an asset

Use **BAM → Register asset**.

Required/available fields include:

- Department;
- Asset type;
- Status;
- Ownership;
- Manufacturer;
- Model;
- Serial number;
- Custodian (optional);
- Acquired date;
- Notes;
- Preferred suffix (optional);
- Asset photo (optional);
- Serial evidence (optional).

### Ownership vs custody

Ownership values are:

- **Company**;
- **Managed personal**.

Custody is separate. A company-owned asset with no explicit custodian is assigned to BAM's default stock custodian when one exists.

### Vanguard default stock custody

BAM determines the default stock custodian in this order:

1. `BAMAutomationSettings.default_custodian` when configured;
2. otherwise, the first active account whose username matches `vanguard` (case-insensitive).

When BAM discovers the `vanguard` fallback, it persists that account as the configured default custodian and uses it as automation actor too when no actor is configured.

If neither exists, company assets may remain without a default custodian until an administrator configures one.

## 3. Asset detail and maintenance

The asset detail page is the authoritative per-asset workspace.

### Edit details

Editable values include:

- ownership;
- manufacturer/model;
- serial;
- acquisition date;
- notes;
- **Allow automatic allocation**;
- **Allocation hold**;
- allocation hold reason.

The ordinary edit form intentionally does not mutate issued asset ID, department, or asset type.

### Automatic-allocation flag

`Allow automatic allocation` controls whether BAM automation may pick that asset. A department manager can still deliberately allocate an otherwise valid asset manually when automatic allocation is disabled.

### Allocation hold

An allocation hold is stronger. It removes the asset from both automatic and normal availability matching until the hold is cleared. Typical reasons include damaged equipment, missing accessories, or pending inspection.

### Manual custody override

The asset page includes a **Manual Custody Override** for administrative corrections. This is an escape hatch, not the normal reservation-backed checkout workflow.

A manual custody change:

- closes any currently open `AssetCustody` history row;
- optionally creates a new custody row;
- updates `Asset.current_custodian`;
- writes BAM events;
- triggers asset automation reconciliation after the view action so newly eligible stock can be reconsidered.

Use it for corrections, not ordinary checkouts.

### Evidence

Evidence kinds are:

- Asset photo;
- Serial evidence;
- Receipt / proof of purchase;
- Warranty;
- Inspection evidence;
- Other.

BAM stores the file outside MySQL and records filename, MIME type, size, uploader/time, notes, and SHA-256 in MySQL.

## 4. Creating a BAMR

Use **Asset requests → New request** or **Request this asset** from an asset record.

BAM request identifiers use:

```text
BAMR-YY-HHHHHH
```

### Request-level fields

- **Purpose** — project/work the equipment supports.
- **Related SHIT ticket** — optional; only tickets visible to the requester are selectable.
- **Priority** — Normal, Time-sensitive, Critical dependency.
- **Requested start/end** — reservation window.
- **Desired completion date** — optional project target; not the asset return date.
- **Justification** — optional longer context.

BAM priority is descriptive/operational and is intentionally separate from SHIT severity. It does not silently change waitlist order.

### First requirement

A BAMR is created with one resource requirement. More requirements can be added from the request detail page.

Each item records:

- requested department;
- requested asset type/class;
- preference mode;
- optional preferred asset;
- optional requirement note.

### Preference modes

#### Any suitable asset

Use when any eligible unit in the selected department/type is acceptable. BAM does not retain a preferred asset.

#### Prefer this asset; allow equivalent

Use when a specific unit is desirable but substitution is acceptable. Automation tries the preferred unit, then may select another eligible equivalent when the global **allow equivalent substitution** policy is enabled.

#### Require this exact asset

Use when the exact unit matters. If unavailable, the item waits for that asset. BAM will not fulfill it with another unit.

### Current matching limitation

Automatic matching in `v0.2.0-alpha` uses:

- department;
- asset type;
- lifecycle status;
- allocation hold;
- automatic-allocation policy for automated actions;
- stock custody for automated actions;
- reservation/checkout conflicts;
- exact/preferred/any semantics.

It does **not** parse freeform requirement notes into machine-enforced capabilities. A note such as “discrete GPU preferred” is currently human context only. Capability tags/pools are future work.

## 5. Automatic request processing

New BAMR items are submitted with `apply_automation=True` through the normal UI.

If `auto_approve_available_requests` is enabled:

1. BAM checks the preferred/exact asset where applicable;
2. otherwise it searches eligible equivalent assets when allowed;
3. when several equivalents are available, BAM uses a deterministic least-recently-allocated choice rather than random selection;
4. if an eligible asset exists, the item becomes **Reserved** (`ALLOCATED`);
5. if no eligible asset exists, the item becomes **Waitlisted**;
6. if the reservation is active today and `auto_transfer_on_approval` is enabled, BAM immediately issues a checkout and transfers custody to the requester.

If auto-approval is disabled, new items remain pending for manual manager review.

### Automatic eligibility

For an automated allocation, an asset must:

- match department and asset type;
- not be terminal;
- not use a non-allocatable status;
- not be on allocation hold;
- have `automatic_allocation_enabled=True`;
- be in stock custody (no custodian, or the configured stock custodian);
- have no conflicting reservation/active checkout for the requested window.

Manual manager allocation intentionally does **not** require stock custody for a non-overlapping future reservation. This permits approving tomorrow's reservation while today's user still has the asset.

## 6. Waitlists and queue position

A requirement becomes **Waitlisted** when allocation cannot currently succeed.

Queue order is date-aware and deterministic. The UI can display a non-sensitive explanation, for example:

- preferred asset is in non-stock custody;
- preferred asset is on allocation hold;
- preferred asset requires manual allocation;
- conflicting reservation/checkout exists;
- no automatically eligible equivalent is available;
- asset is eligible now and will be retried on the next automation pulse.

Waitlisted work is reconsidered by:

- the startup/launcher BAM automation pulse;
- explicit `process_bam_automation` pulses;
- relevant manual asset status/custody/hold changes;
- normal release/return workflows.

## 7. Manager actions on a BAMR

Department-scoped managers can act on individual requirements for departments they manage.

### Allocate / reserve

A manager may select an explicit matching asset or allow BAM to choose. If no eligible asset exists, the requirement returns to the queue.

### Deny

Only pending/waitlisted requirements can be denied. A reason is required.

### Cancel requirement

The requester or authorized department manager may cancel a requirement when the workflow state permits.

### Release reservation

A manager may release an active reservation that has **not** been checked out. A checked-out item must be returned instead.

Releasing a reservation reevaluates compatible waitlisted work.

### Checkout

Checkout requires an approved/reserved item and creates a dedicated `AssetCheckout`. It transfers asset custody to the BAMR requester and changes the item/request state accordingly.

### Return

Returning closes the checkout and returns custody to the stock custodian. Manager/manual return promotes the queue but, by design, does not silently issue the next physical checkout unless automation is being applied through the self-release flow.

### Direct handoff

A manager can hand an active checkout directly to another already-approved reservation for the same asset when the target reservation is active today or begins the next day and still covers today/next-day handoff semantics.

Direct handoff:

- closes the current checkout;
- creates the target checkout;
- transfers custody directly to the next requester;
- preserves a continuous custody chain with no fake stock gap;
- writes request and asset events to both sides.

## 8. Self-service release

The current custodian of an active reservation-backed checkout may release their own asset.

Condition choices:

| Condition | Result |
| --- | --- |
| Good / ready for next user | eligible for queue promotion/automatic transfer |
| Minor issue | allocation hold |
| Damaged | allocation hold |
| Missing accessory | allocation hold |
| Needs attention | allocation hold |

A problem release records condition/notes, puts the asset on hold, returns custody to stock, and prevents reallocation until an authorized user clears the hold.

A good release may:

1. return custody to stock;
2. promote compatible waitlisted reservations;
3. when `auto_transfer_on_release` is enabled, issue an active promoted/approved reservation automatically;
4. otherwise leave the asset in stock custody.

## 9. Overdue checkout behavior

An active checkout is overdue when today's date is after the BAMR requested end date.

Overdue checkouts:

- remain active physical custody;
- display overdue state/days;
- continue to block future automatic allocation until returned or handed off.

BAM does not infer physical location. Overdue is a workflow/date condition only.

## 10. BAM automation settings

Superusers/staff use Django Admin → **BAM automation settings**.

The singleton policy has:

- **Default custodian** — stock holder, normally Vanguard.
- **Automation actor** — account recorded as actor for automatic event history. If blank, stock custodian/fallback is used.
- **Auto approve available requests**.
- **Allow equivalent substitution**.
- **Auto transfer on approval**.
- **Auto promote waitlist**.
- **Auto transfer on release**.

Turning off an automation feature does not delete existing requests/reservations/checkouts. It changes what BAM is allowed to perform automatically going forward.

## 11. Automation pulse

Source checkout:

```powershell
.\.venv\Scripts\python.exe portal\manage.py process_bam_automation --settings=config.settings.local
```

The Windows source launcher executes one pulse after schema checks. The packaged executable runs one pulse at application startup.

The pulse is designed to be idempotent and processes pending/waitlisted/due work. `v0.2.0-alpha` does not yet install a permanent repeating scheduler; use an external scheduler if continuous time-based processing is required between user actions/startups.

## 12. Permissions and privacy

### Requester

- can create BAMRs;
- can view own BAMRs;
- can add requirements to own non-terminal request;
- can cancel own items/request where permitted;
- can self-release an active checkout they currently hold.

### Department Manager / Department administrator

- can view/manage requirements in departments they manage;
- can allocate, deny, release, checkout, return, and handoff those department items;
- whole-request actions require authority over every department represented by that BAMR.

### Staff / superuser

Global BAM request-management authority.

Asset-detail request/checkouts/backlinks redact request-specific information when the viewer cannot open the underlying BAMR. The portal avoids exposing hidden BAMR IDs through checkout/history prose.

## 13. Event/history records

BAM maintains separate histories for:

- asset events;
- asset custody;
- asset request events;
- checkout history.

Automatic actions write the same domain history paths and add `automated: true` in event metadata rather than occurring invisibly.

These are useful operational histories but are not yet the future hardened company-wide append-only audit ledger.

## 14. Example: radio request

A requester needs any SR69 radio today:

1. Create BAMR.
2. Department: `SR69`.
3. Type: `R — Radio`.
4. Preference: **Any suitable asset**.
5. Start/end: today through required return date.
6. Submit.

If an automatically eligible radio is in Vanguard stock custody and has no conflict, BAM reserves it and can immediately check it out to the requester. If not, the request enters the queue.

When the requester is finished, they release it from My Checkouts. A good-condition release can hand it to the next active eligible BAMR or return it to Vanguard.

## 15. Example: prefer the better laptop

A requester prefers a Pavilion but will accept another DEV5 laptop:

1. Department: DEV5.
2. Type: Laptop.
3. Preference: **Prefer this asset; allow equivalent**.
4. Preferred asset: Pavilion.
5. Requirement note: “Discrete GPU preferred.”

BAM gives the Pavilion first if eligible. If it is busy and equivalent substitution is enabled, another eligible DEV5 laptop may be assigned. The note is visible to humans but does not currently impose a GPU capability filter.

If the Pavilion itself is mandatory, choose **Require this exact asset** instead.
