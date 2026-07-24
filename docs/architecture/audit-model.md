# Audit Model Direction

Audit logging is planned as a platform capability, not an ad-hoc feature implemented separately by each domain.

Target event shape:

```text
AuditEvent
- id UUID
- timestamp
- actor
- action
- object_type
- object_id
- request_id
- before JSONB
- after JSONB
- metadata JSONB
```

Long-term goal: the ordinary application database role may insert/select audit events but not update/delete historical audit rows.
