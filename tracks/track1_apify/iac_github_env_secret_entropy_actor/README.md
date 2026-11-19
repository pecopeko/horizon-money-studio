# CI/CD .env, Cloud Credential & TLS-Bypass Config Auditor

Pay-Per-Event (`secret_scan_audited` @ `$0.003`) Apify Actor screening `.env`, CI logs, and config manifests:
- `SEC-CLOUD-01`: Cloud IAM key / private key material exposure
- `SEC-VCS-02`: VCS personal access token / CI token assignment
- `SEC-PAY-03`: Payment / webhook / workspace API key prefix exposure
- `SEC-DB-04`: Cleartext database / broker DSN password URI (`postgres://user:pass@...`)
- `SEC-JWT-05`: Weak/hardcoded `JWT_SECRET` or `SESSION_SECRET` value
- `SEC-ENV-06`: Insecure runtime overrides (`NODE_TLS_REJECT_UNAUTHORIZED=0`, `SSL_VERIFY=false`, `CORS_ORIGIN=*`)
