# Security Policy

B.S. Portal is currently alpha software.

## Alpha restrictions

- Use synthetic/disposable data only.
- Do not expose Django with `DEBUG=True` to the public internet.
- Keep staging behind an outer web-server authentication barrier where available.
- Never commit `.env`, passwords, API keys, database credentials, or Django secret keys.
- Do not treat application-level authorization as sufficient until RBAC tests and database permissions are reviewed.

## Security-sensitive design principle

Security mechanisms should remain understandable and reviewable. Prefer mature framework primitives over custom authentication, session, password, or cryptographic implementations.

## Planned hardening

- MFA/passkeys
- rate limiting
- DB role separation
- append-only audit enforcement
- security headers review
- dependency/static analysis
- backup/restore drills
- threat model
- authorization matrix tests
