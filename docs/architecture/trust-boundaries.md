# Trust Boundaries

## Local
Developer machine is trusted only for synthetic development data.

## Staging
`dev.bssply.co` is internet-exposed and therefore treated as hostile even though its data is disposable.

Recommended perimeter:

```text
Internet
  → web-server authentication
  → Django session authentication
  → application authorization
  → MySQL/InnoDB
```

## Production
Production will be a separate deployment and database, not a renamed staging instance.

## Non-boundaries
A subdomain is a routing boundary, not necessarily an operating-system security boundary. Applications under the same cPanel account may share the same Unix account and must not be assumed mutually isolated.
