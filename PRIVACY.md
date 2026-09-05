# Privacy Policy

**B.S. Portal (BSP)** is designed as a privacy-first, self-hosted internal operations platform for B.S. Supply Co. The project intentionally favors first-party operational records over advertising, behavioral tracking, or unnecessary device/user telemetry.

This document describes the privacy posture of the B.S. Portal software and the intended B.S. Supply Co. deployment. Because BSP is open-source and may be self-hosted by others, a third-party operator can configure hosting, logging, integrations, retention, and access differently. In that case, that operator is responsible for describing its own privacy practices.

The reference application also exposes a human-readable privacy page at `/privacy/` so the policy can be reviewed without GitHub access or authentication.

> **Alpha notice:** BSP remains alpha software. This policy describes the current design and intended operating posture; it is not a claim that every future privacy or compliance control has already been implemented.

## Privacy principles

BSP is developed around the following principles:

- **Collect what operations require, not what is merely available.**
- **No advertising or ad-tech tracking.**
- **No sale of portal data.**
- **No third-party behavioral analytics by default.**
- **No covert employee/location surveillance features.**
- **Keep operational data first-party and self-hostable.**
- **Prefer explicit records and audit history over invisible profiling.**
- **Preserve security and accountability without collecting unrelated telemetry.**

## Information BSP may process

The exact information present depends on which modules are used and what users enter.

### Identity and access

BSP uses Django's authentication system with a custom UUID-backed user model. Account records may include:

- username;
- display name;
- name and email fields when supplied;
- password hash and authentication state managed by Django;
- staff/superuser flags;
- department memberships and operational roles.

Passwords are not intended to be stored in plaintext.

### BAM — Asset Management

BAM may store operational information such as:

- asset IDs;
- asset type, manufacturer, model, and serial number;
- department ownership;
- current and historical custodians;
- acquisition/retirement information;
- asset notes;
- evidence files and associated metadata;
- custody, lifecycle, and asset event history;
- asset-use requests, including requester identity, requested date windows, purpose/justification, optional related SHIT work, preferred assets, waitlist/reservation state, allocation history, reservation-backed checkout/return records, direct handoffs, and overdue state derived from the approved return window.

Asset records can therefore associate a person with equipment they currently or previously held, as well as equipment they requested, reserved, checked out, returned, or received by direct handoff for operational work. BAM allocation/custody data is used to coordinate internal resources; it is not intended as employee-location or behavioral-surveillance data. An overdue flag means the approved request end date has passed while the checkout remains open; BSP does not infer physical location from that state.

### SHIT — Ticketing

SHIT may store:

- ticket requester;
- assigned user and department;
- title, description, classification, severity, and status;
- requester-visible comments and internal notes;
- attachments and attachment metadata;
- related BAM assets and document references;
- ticket event/history records;
- manual queue position.

Users should avoid placing unrelated personal or sensitive information in tickets merely because the text fields permit it.

### Timeclock

Timeclock records operational work-time information including:

- employee identity;
- clock-in and clock-out timestamps;
- source of the punch;
- administrative corrections;
- correction reasons;
- actor and audit-event information.

The current Timeclock module is intentionally designed **not** to collect GPS/location data, biometric identifiers, device fingerprints, advertising identifiers, or surveillance-derived presence data.

### Session and security data

BSP uses the cookies and request state needed for authenticated Django sessions and CSRF protection. These are functional/security mechanisms, not advertising cookies. BSP may also store non-sensitive interface preferences, such as theme and SHIT List/Board or Dense/Compact choices, in first-party browser storage and functional preference cookies so the interface can reopen in the operator's chosen presentation. These preferences are not used for authorization, advertising, or cross-site tracking.

The application does not currently include a third-party analytics or advertising SDK. However, the web server, reverse proxy, hosting provider, database, operating system, or security tooling used by a particular deployment may produce technical logs such as IP addresses, timestamps, request paths, browser user-agent strings, error information, or authentication events. Those logs are controlled by the deployment operator and hosting configuration rather than by an application-level advertising profile.

## How information is used

BSP processes operational information to:

- authenticate users;
- enforce access to portal functions;
- operate department workflows;
- maintain asset identity, custody, evidence, and lifecycle history;
- create, route, manage, and audit service tickets;
- record and correct work-time punches;
- preserve operational accountability and change history;
- diagnose failures and protect the service;
- back up and recover authorized business records.

BSP is not designed to use operational data for advertising, cross-service profiling, or sale to data brokers.

## Data sharing

The B.S. Portal application does not require selling or sharing operational records with advertisers.

Data may nevertheless be accessible to:

- authorized BSP users according to application permissions;
- administrators responsible for the BSP deployment;
- infrastructure providers that host the application, database, backups, email, or storage if such providers are configured;
- parties required to receive information by applicable law or valid legal process.

If a deployment adds a third-party integration that receives BSP data, that integration should be documented before it is treated as part of the normal privacy posture.

## Storage and data location

The reference BSP architecture uses MySQL/InnoDB and application-controlled media storage. It does not require a cloud analytics platform or external identity broker to function.

A self-hosted operator controls where the database, uploaded files, logs, and backups physically reside. Operators should treat backups as copies of the same sensitive operational data and protect them accordingly.

## Retention and deletion

BSP contains records whose value depends on preserving history. Asset custody, ticket events, timeclock punches, and corrections are intentionally history-oriented, and some records use protective relationships or append-style correction patterns rather than destructive edits.

The alpha software does **not** currently implement a universal automatic retention/deletion schedule. Retention should therefore be defined by the operator according to operational, contractual, legal, and security requirements.

Where correction is more appropriate than deletion, BSP may preserve the original record and append the correction so that the operational history remains understandable. This is especially relevant to timeclock corrections and audit/event history.

## User access and correction

Access to information is governed by the portal's authentication and module-specific authorization rules. Depending on the module and role, a user may be able to view, add, correct, or manage records directly through BSP.

Requests to review, correct, export, or remove information that cannot be handled through the portal should be directed to the operator of the BSP instance. Some removal requests may be limited when preserving a record is necessary for security, operational history, legal obligations, or the integrity of an audit trail.

## Security and privacy

Privacy depends on security. BSP's current security posture, alpha limitations, deployment expectations, and vulnerability-reporting guidance are documented in [`SECURITY.md`](SECURITY.md).

Operators should, at minimum:

- keep secrets out of source control;
- use TLS for non-local deployments;
- restrict administrative access;
- use least-privilege database and host accounts;
- protect uploaded files and backups;
- review authorization before using real operational data;
- keep dependencies and the host environment patched.

## Open-source distribution

Downloading, cloning, building, or running the B.S. Portal source code does not intentionally contact B.S. Supply Co. for telemetry or usage analytics.

The source repository itself is hosted by a third party, so visiting or interacting with the repository is subject to that hosting provider's own privacy practices.

## Children

BSP is an internal operations platform and is not designed as a consumer service directed to children.

## Changes to this policy

Privacy behavior can change as new modules, integrations, storage systems, authentication methods, or deployment environments are introduced. Material privacy-impacting changes should be reflected in this document alongside the corresponding code or deployment change.

## Contact

For a deployed instance, privacy questions should be directed to the organization or administrator operating that instance. For the reference B.S. Supply Co. project, use a private contact method published by the repository owner rather than placing sensitive personal information in a public GitHub issue.

### BAM allocation and release data

The BAM allocation workflow stores requester identity, requested dates, asset preferences, reservation/check-out state, custody history, release condition, and optional release notes because those fields are required to operate and audit the equipment pool. Toast notifications are rendered from first-party Django message state and do not add third-party tracking or analytics.
