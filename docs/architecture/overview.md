# B.S. Portal Architecture Overview

B.S. Portal is a Django modular monolith backed by MySQL/InnoDB.

## Authority boundaries

### MySQL/InnoDB
Authoritative for operational state: users, department membership, assets, tickets, workflow state, compliance results, and audit events.

### Git / Markdown PSOP repository
Authoritative for controlled Policies, Standards, and Operating Procedures. The portal may index metadata and references, but does not silently become a second document authority.

### Object storage / filesystem
Authoritative for binary evidence and attachments. MySQL/InnoDB stores metadata, ownership, integrity hashes, and object references.

## Module direction

Initial platform modules:

- core
- identity
- departments

Planned operational modules:

- audit
- files
- bam
- intake
- nsec
- shit
- psop

## Architectural rule

> Views request operations. Services perform operations. The database enforces invariants where supported; services enforce higher-order workflow rules. Audit records explain what happened.
