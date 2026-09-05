# B.S. Portal Documentation

B.S. Portal documentation is divided by audience.

## Operators and portal users

- [B.S. Portal Operator Guide](user-guide.md) — illustrated day-to-day use of Dashboard, Departments, BAM, SHIT, Timeclock, and the current Django admin back-office view.

## Security, privacy, and licensing

- [`../PRIVACY.md`](../PRIVACY.md) — privacy-first data handling, data minimization, retention, self-hosting, and telemetry policy.
- [`../SECURITY.md`](../SECURITY.md) — alpha security posture, vulnerability reporting, deployment baseline, and planned hardening.
- [`../LICENSE`](../LICENSE) — MIT open-source license.

The running portal also exposes public `/about/`, `/privacy/`, `/security/`, and `/license/` pages. Signed-in users can reach these from the account menu.

## Developers and administrators

- [`development/`](development/) — local development and deployment procedures.
- [`architecture/`](architecture/) — system architecture and design documentation.
- [`adr/`](adr/) — architecture decision records.

## Screenshots included in the operator guide

The current guide includes alpha screenshots for:

- Dashboard
- Departments
- BAM asset list
- SHIT list view
- SHIT board view
- SHIT ticket-detail workbench
- Timeclock
- Django administration

## Documentation status

B.S. Portal is alpha software. Screenshots and workflows in the operator guide describe the current alpha interface and should be updated alongside material UI or workflow changes. Privacy- or security-impacting changes should likewise be reflected in `PRIVACY.md` or `SECURITY.md` as part of the same change.
