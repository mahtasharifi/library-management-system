# Architecture notes

Library follows a conventional Django structure with a small service and repository layer around the library domain.

## Application boundaries

- `apps/accounts/` contains authentication, profile management and MFA.
- `apps/books/` contains catalog, borrowing, digital requests, imports and staff workflows.
- `apps/books/services/` holds business operations that would otherwise make views too large.
- `apps/books/repositories/` contains reusable read/query logic.
- `common/` contains cross-cutting concerns such as rate limiting, middleware, health checks, metrics and localization.

## Background jobs

Email delivery and spreadsheet imports run through a small database-backed queue. A separate Django management command claims jobs, records worker heartbeats and recovers stale locks. This keeps the deployment simple for the current workload because the application already depends on MySQL/MariaDB.

If background workload grows significantly, the service boundary can be moved to a dedicated queue such as Celery/Redis without moving business logic into the transport layer.

## Digital file storage

Book covers and PDFs can be stored on a managed HTTPS download host and uploaded through FTPS. The application checks authorization before redirecting an approved user to a stored PDF URL.

The final CDN URL is shareable after it has been issued. Deployments that require non-shareable files should use private object storage with short-lived signed URLs or authenticated streaming.

## Content Security Policy

JavaScript is served from local static files and scripts do not use `unsafe-inline` or `unsafe-eval`. A limited `style-src-attr 'unsafe-inline'` allowance is used because parts of the interface set presentation values through DOM style properties.
