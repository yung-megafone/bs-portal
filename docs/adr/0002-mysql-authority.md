# ADR 0002 — MySQL/InnoDB as Operational Authority

Status: Accepted

## Context

B.S. Portal is intended to run on the existing GoDaddy cPanel environment for the foreseeable future. That environment provides MySQL but does not expose PostgreSQL. Maintaining a second database engine solely for local development would increase testing and migration complexity without solving a current business requirement.

## Decision

MySQL using the InnoDB storage engine is the authoritative operational database for B.S. Portal.

Development, testing, staging, and production should use MySQL/InnoDB so database behavior remains representative across environments.

Important invariants should be enforced in both application validation and database constraints where supported. Critical workflow rules that cannot be expressed portably or reliably as database constraints belong in explicit transactional service functions and must be covered by tests.

The application should prefer Django ORM features supported by the deployed MySQL version and avoid unnecessary database-specific raw SQL.

## Consequences

- No PostgreSQL compatibility layer is maintained during the current architecture generation.
- The project gains deployment simplicity and environment parity with the infrastructure already available to B.S. Supply Co.
- Some advanced PostgreSQL-only constraints, data types, and indexing capabilities are intentionally unavailable.
- A future migration to another database engine is treated as a deliberate infrastructure project, not a current requirement.
