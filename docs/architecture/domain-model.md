# Domain Model — Alpha Baseline

```text
User
 └── DepartmentMembership
       └── Department
```

Future direction:

```text
User
 ├── DepartmentMembership → Department
 ├── creates / owns → Ticket
 ├── custodian → Asset
 ├── performs → ComplianceAssessment
 └── actor → AuditEvent

Department
 ├── Asset
 ├── Ticket
 └── DepartmentMembership

Asset
 ├── AssetType
 ├── AssetStatus
 ├── AssetCustody
 ├── AssetRelationship
 ├── AssetEvent
 ├── ComplianceAssessment
 ├── Ticket
 └── Attachment

AssetIntake
 ├── Attachment
 ├── ComplianceAssessment
 └── creates → Asset

PSOPDocument
 └── references authoritative Git repository object
```
