# ADR 0001 — Modular Monolith

Status: Accepted

B.S. Portal will begin as a Django modular monolith. Domain boundaries are expressed as Django apps and service layers. Microservices are deferred until an actual independent scaling, deployment, security, or ownership requirement exists.
