# ADR 0004 — Binary Evidence Outside MySQL/InnoDB

Status: Accepted

Binary attachments and evidence will live in file/object storage. MySQL/InnoDB will retain metadata and integrity hashes rather than storing large binary payloads directly in operational tables.
