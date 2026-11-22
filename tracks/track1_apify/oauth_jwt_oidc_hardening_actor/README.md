# OAuth2 / OIDC & JWT Security Hardening Auditor (`oauth2-oidc-jwt-security-hardening-auditor`)

Deterministic Pay-Per-Event (`auth_config_audited` @ `$0.003`) auditor checking 6 authentication hardening rules:
1. `OAUTH-JWT-01` (`critical`): `alg: "none"` or symmetric/asymmetric algorithm confusion (`HS256` with public key/JWKS or missing `algorithms` allowlist)
2. `OAUTH-JWT-02` (`high`): Disabled claim/signature verification (`verify_aud: False`, `verify_iss: False`, `ignoreExpiration: true`, `verify_exp: False`, `verify_signature: False`)
3. `OAUTH-JWT-03` (`critical`): Exposed signing secrets, weak hardcoded HMAC secrets, private JWK (`"d":`), or PEM private key blocks
4. `OAUTH-OIDC-04` (`high`): Legacy implicit `response_type=token`, disabled PKCE (`pkce: false`), or downgrade `code_challenge_method: plain`
5. `OAUTH-OIDC-05` (`high`): Wildcard `*` or non-localhost plain `http://` `redirect_uri`
6. `OAUTH-TOKEN-06` (`medium`): Browser `localStorage`/`sessionStorage` token storage or excess access-token TTL `> 3600s` without refresh rotation
