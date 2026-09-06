# Security

Library includes several application-level security controls:

- TOTP MFA with encrypted secrets and one-time recovery codes
- MFA replay protection and administrative reset/key-rotation commands
- Database-backed rate limiting on sensitive authentication paths
- CSRF protection and server-side authorization checks
- Upload validation and bounded spreadsheet processing
- HTTPS, secure cookies and HSTS in production settings
- Content Security Policy and local JavaScript assets
- Environment-based credentials and ignored runtime `.env` files
- Health/readiness checks and token-protected operational metrics

## Digital downloads

The application checks authorization before redirecting an approved user to a managed PDF URL. After that redirect, the final CDN URL can be shared. A deployment that requires non-shareable files should use private storage with expiring signed URLs or authenticated streaming instead.

## Secrets

Do not commit production `.env` files, database dumps, private keys, API tokens, user data or uploaded private documents. Credentials that have been exposed should be rotated rather than reused.
