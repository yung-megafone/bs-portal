# Authorization Direction

Alpha uses Django's standard authentication and admin authorization primitives.

Production RBAC will model permissions by subject, action, resource, and scope. Examples:

```text
bam.asset.view
bam.asset.create
bam.asset.modify
shit.ticket.assign
nsec.assessment.perform
psop.document.sync
```

Department-scoped role assignments are expected to build on `DepartmentMembership` rather than being hard-coded into views.
