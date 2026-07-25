# BAM v0.1 Architecture

BAM is the authoritative B.S. Portal asset-management module. It supersedes the CSV-authoritative behavior of the `BAM.py` desktop prototype while preserving the prototype's useful business rules.

## Authority

- MySQL/InnoDB is authoritative for asset records, identifiers, status, custody, history, and evidence metadata.
- Evidence bytes live outside the relational database. The database stores the managed file path, filename, MIME type, size, SHA-256 digest, uploader, and timestamp.
- Git/Markdown PSOPs remain authoritative for asset-governance documentation.
- CSV/Markdown/YAML may later be exported as reports or continuity artifacts, but are not peer authoritative databases.

## Identifier allocation

`BS-{DEPARTMENT}-{TYPE}-{4HEX}` is retained from the prototype/STD-7100 convention.

BAM does not pre-read the asset table before allocating an identifier. It:

1. generates a cryptographically random 4-hex candidate;
2. attempts the INSERT inside a transaction;
3. relies on MySQL UNIQUE constraints to arbitrate collisions atomically;
4. retries only MySQL duplicate-key error 1062.

This removes the read/check/read/write race window of the CSV prototype.

## Evidence

Default development storage is `data/asset_media/`, configurable with `BAM_MEDIA_ROOT`. Files are not stored as database BLOBs. Production may later replace local filesystem storage with object storage without changing the evidence model's logical purpose.

## Implemented v0.1 capabilities

- asset type/status reference data (CAS foundation)
- collision-safe ID issuance
- asset registration
- search/list/detail views
- core record editing while preserving issued identity
- status history
- custody assignment/history
- evidence attachments with SHA-256
- asset event history
- asset relationships in the data model
- Django Admin support

## Deferred

- fine-grained RBAC
- full company audit subsystem integration
- CSV continuity/import/export workflow
- NSEC assessments
- SHIT ticket relationships
- PSOP relationships
- object-storage backend
- asset deletion/disposal workflow beyond terminal status
