# Web CSP, CORS, HSTS & Cookie Hardening Auditor (`web-csp-cors-cookie-hardening-auditor`)

Deterministic Pay-Per-Event (`config_audited` @ `$0.003`) auditor verifying HTTP response headers & framework security configs:
- `WEB-CORS-01` (`critical`): `Access-Control-Allow-Origin: *` / reflected wildcard with `Allow-Credentials: true`
- `WEB-CSP-02` (`high`): Missing CSP or `script-src` allowing `'unsafe-inline'`, `'unsafe-eval'`, or `*`
- `WEB-CLICKJACK-03` (`medium`): Missing both `frame-ancestors` and `X-Frame-Options`
- `WEB-HSTS-04` (`medium`): Missing HSTS or `max-age < 31536000`
- `WEB-COOKIE-05` (`high`): `Set-Cookie` missing `HttpOnly`, `Secure`, or `SameSite`
- `WEB-LEAK-06` (`low`): Exposed `X-Powered-By` or versioned `Server:` banner
