# Wave 2 Defensive AI/ML Proxy & Server Static Security Audit Report (November 2026)

**Audit Date**: 2026-11-20  
**Scanner**: `tracks/track18_litellm_security_wave2/py_ai_security_auditor_v2.py` (Python 3.11 stdlib AST, 8 CWE rules: `AI-DESER-01`..`AI-SQL-08`, default-false `allow_pickle=False` downgrade awareness, test directories excluded)  
**Disclosure Discipline**: Strictly defensive offline static analysis and manual source review against each repository's live `SECURITY.md` and published GitHub Security Advisories. Zero remote servers were probed and zero offensive payloads were created. All unpatched defensive defects and minimal unified patches are quarantined exclusively inside the `.gitignore`d `CONFIDENTIAL_DO_NOT_PUSH/` directory for coordinated private disclosure through each project's official channel.

---

## 1. Authorized Program Scope & Live `SECURITY.md` Verification

| Repository | Stars | Verified Disclosure Channel | Bounty / Credit Policy | Key Out-of-Scope Boundaries |
|---|---:|---|---|---|
| `BerriAI/litellm` | 63,602 | HackerOne-triaged VDP (`https://security.litellm.ai/vdp/`); draft GitHub GHSAs closed as of 2026-11-11 | Cash bounty: Critical P0 supply-chain (`$1,500–$3,000`), High P1 unauthenticated proxy access leaking secrets (`$500–$1,500`); P2/Low non-cash but welcomed | Missing `master_key` misconfigurations; deliberately disabled security flags (e.g. `disable_responses_id_security=true`); social engineering |
| `open-webui/open-webui` | 159,135 | GitHub Private Vulnerability Reporting (`open-webui/open-webui/security/advisories/new`) ONLY (per `docs/SECURITY.md` & `docs.openwebui.com/security/security-policy/`) | Coordinated CVE/GHSA credit (first reporter; no cash bounty; fixes checked against `dev` branch) | Admin-only actions (administrators are trusted); Tools/Functions/Pipelines arbitrary code execution (by design); pre-sign-in login/config endpoints; self-affecting issues |

---

## 2. Aggregate Scan Metrics

| Repository | Audited Scope | Version / Commit SHA | Files Scanned | LOC Scanned | Parse Errors | Raw AST Findings | Post-Triage Unpatched / Hardening Defects (Quarantined) |
|---|---|---|---:|---:|---:|---:|---:|
| `BerriAI/litellm` | `litellm/proxy/` | `1.112.0` (`f9b908a`, 2026-11-20) | 996 | 467,288 | 0 | 85 | 1 (quarantined in `CONFIDENTIAL_DO_NOT_PUSH/`) |
| `BerriAI/litellm` | `litellm/integrations/` | `1.112.0` (`f9b908a`, 2026-11-20) | 261 | 77,588 | 0 | 1 | 0 |
| `BerriAI/litellm` | `litellm/llms/` | `1.112.0` (`f9b908a`, 2026-11-20) | 1,155 | 275,810 | 0 | 0 | 0 |
| `open-webui/open-webui` | `backend/open_webui/` | `0.13.4` (`0666e59`, 2026-11-17) | 327 | 140,824 | 0 | 104 | 2 (quarantined in `CONFIDENTIAL_DO_NOT_PUSH/`) |
| **Total** | **2 Authorized AI Server Repos** | — | **2,739** | **961,510** | **0** | **190** | **3 (all quarantined privately)** |

### Raw AST Findings by Rule

| Rule ID | CWE | Default Severity | `litellm/proxy` | `litellm/integrations` | `litellm/llms` | `open-webui` | Total |
|---|---|---|---:|---:|---:|---:|---:|
| `AI-DESER-01` | CWE-502 | HIGH (`INFO` if opt-in guarded) | 1 | 0 | 0 | 0 | 1 |
| `AI-PATH-02` | CWE-22 | HIGH | 5 | 0 | 0 | 12 | 17 |
| `AI-CMD-03` | CWE-78 | CRITICAL | 0 | 0 | 0 | 0 | 0 |
| `AI-EVAL-04` | CWE-94 | CRITICAL | 2 | 0 | 0 | 2 | 4 |
| `AI-SSRF-05` | CWE-918 | HIGH | 0 | 0 | 0 | 21 | 21 |
| `AI-TEMP-06` | CWE-377 | MEDIUM | 0 | 0 | 0 | 0 | 0 |
| `AI-AUTH-07` | CWE-306 | HIGH | 69 | 0 | 0 | 35 | 104 |
| `AI-SQL-08` | CWE-89 | CRITICAL | 8 | 1 | 0 | 34 | 43 |
| **Total** | — | — | **85** | **1** | **0** | **104** | **190** |

**Signal-to-Noise Observation**: Scanning **961,510 LOC** across **2,739 production Python files** completed with **0 parse errors** and **190 raw alerts** (`0.20` alerts per 1,000 LOC), enabling **100% manual triage (190/190)** against upstream `SECURITY.md` trust boundaries and recent 2026 GHSAs.

---

## 3. Non-Sensitive Triage Summary & Verified Existing Controls

### A. `BerriAI/litellm` (`v1.112.0` — 2,412 Files, 820,686 LOC, 86 Raw Findings)
All 86 raw findings (`85` in `litellm/proxy/`, `1` in `litellm/integrations/`, `0` in `litellm/llms/`) were manually audited against `.github/SECURITY.md` and recent 2026 LiteLLM GHSAs (`GHSA-2rwg-2wh4-7c4f`, `GHSA-w4c7-34wj-hqm8`, `GHSA-7hp6-4w63-5g45`, `GHSA-3cv6-jpf6-8222`, `GHSA-5jmr-gcrj-2c9q`):

- **Verified Existing Hardening Controls**:
  - **Deserialization (`1 × AI-DESER-01`)**: `openapi_to_mcp_generator.py` uses a custom `_OpenAPISafeLoader` subclassing `yaml.SafeLoader` with strict scalar/mapping tag enforcement.
  - **Custom Guardrail Execution (`2 × AI-EVAL-04`)**: Custom code guardrail compilation is restricted to `PROXY_ADMIN` and routed through `compile_sandboxed(...)`, `build_sandbox_globals()`, and bounded off-loop execution timeouts.
  - **Raw Prisma SQL (`9 × AI-SQL-08`)**: All 9 flagged raw SQL invocations bind dynamic values through positional parameters (`$1`, `$2`, ...) and interpolate only static internal allowlists/tuples (`_SECRET_COLUMNS`, `_KEY_OWNED_TABLES`, `FUNNEL_STAGES`, integer `_ENTITY_LIMIT`) or operator-owned environment config.
  - **Route File Access (`5 × AI-PATH-02`)**: Bundled JSON fixtures are loaded relative to `__file__`; logo serving uses `resolve_validated_local_image_path` (magic-byte allowlisting PNG/GIF/JPEG/WEBP/ICO and rejecting SVG/arbitrary paths following `GHSA-w4c7-34wj-hqm8`); logo uploads generate server-owned UUID filenames with strict extension allowlisting.
  - **Route Authentication (`68/69 × AI-AUTH-07` verified safe/intentional)**:
    - Multiple endpoints protect routes through module-level `Depends(...)` constants (e.g., `_user_api_key_auth_dep`, `_AUTH_DEPENDENCIES`, `_AUTHENTICATED`, `Depends(archive_writer)`), in-handler HMAC/ephemeral-token verification (WebRTC realtime calls, Moyai nonce exchange, CLI SSO poll secrets), ASGI-layer authentication (`handle_streamable_http_mcp` stripping forged internal headers), or opt-in environment gates (`_raise_if_sso_debug_disabled()`).
    - Public OAuth2/OIDC/SAML handshake/metadata endpoints, stubbed telemetry endpoints, and explicitly documented public branding/catalog routes are intentional per design.
- **Quarantined Unpatched Defect (`1 × AI-AUTH-07`)**:
  - One proxy settings read endpoint documented and unit-tested as requiring authenticated user access omits the router's standard authentication dependency, exposing deployment policy flags and configuration provenance metadata without credentials (Low/defense-in-depth hardening; does not leak API keys or master keys). Full analysis and minimal unified patch are quarantined strictly in `CONFIDENTIAL_DO_NOT_PUSH/WAVE2_DISCLOSURE_DOSSIER_2026_11.md` for submission via `https://security.litellm.ai/vdp/`.

### B. `open-webui/open-webui` (`v0.13.4` — 327 Files, 140,824 LOC, 104 Raw Findings)
All 104 raw findings were manually audited against `docs.openwebui.com/security/security-policy/` and recent September–October 2026 Open WebUI GHSAs:

- **Verified Existing Hardening Controls**:
  - **Plugin Execution (`2 × AI-EVAL-04`)**: `utils/plugin.py` tool/function module loading executes admin-approved Python code by design, explicitly outside Open WebUI's vulnerability threat model.
  - **Outbound HTTP / SSRF (`21 × AI-SSRF-05`)**: All 21 flagged outbound requests are either restricted to `get_admin_user` (administrators are explicitly trusted under Open WebUI's threat model) or dispatch exclusively to admin-configured provider/OAuth/search base URLs.
  - **File Serving (`12 × AI-PATH-02`)**: File download routes enforce `file.user_id == user.id or user.role == 'admin' or await has_access_to_file(...)`; model background exports validate ownership on creation/update via `_verify_background_image`; audio TTS caches use SHA-256 hex filenames under `CACHE_DIR`; database download requires `get_admin_user` + `ENABLE_ADMIN_EXPORT`.
  - **SQL Queries (`33/34 × AI-SQL-08` verified safe)**: Chat/search SQL builders bind all user values via SQLAlchemy `:param` / `expanding=True` bindparams while interpolating only dialect-selected static fragments; Alembic migrations and SQLite PRAGMAs use operator configuration or schema introspection; sibling vector DB clients (`oracle23ai.py`, `milvus.py`, `milvus_multitenancy.py`) strictly enforce `_SAFE_METADATA_KEY_RE`.
  - **Route Authentication (`34/35 × AI-AUTH-07` verified safe/intentional)**: Pre-login OAuth/LDAP/signin/signup/MFA/session-refresh routes, RFC 7644 SCIM metadata endpoints, token-authenticated webhooks, and first-message JWT-authenticated WebSockets all enforce their intended authentication mechanisms.
- **Quarantined Unpatched Defects (`2` findings, both verified still present on `dev` as of 2026-11-20)**:
  1. **Capability-Scoped Proxy Path Traversal (`CWE-22` / `CWE-285`)**: Surfaced during `AI-AUTH-07` triage — one capability-token-authenticated reverse proxy branch omits path sanitization prior to prefix concatenation (unlike its adjacent sibling branch in the same handler), allowing relative traversal out of the scoped capability prefix.
  2. **Defense-in-Depth SQL Filter Key Validation Parity Gap (`CWE-89`)**: Surfaced by `AI-SQL-08` — one optional vector database client interpolates metadata filter keys directly into a JSON-extract SQL expression without the `_SAFE_METADATA_KEY_RE` allowlist already enforced in sibling vector database clients (currently unreachable from default router callers, which pass static keys, so classified honestly as Low/defense-in-depth hardening).
  - Exact file paths, line ranges, root-cause analyses, and minimal unified patches are quarantined strictly in `CONFIDENTIAL_DO_NOT_PUSH/WAVE2_DISCLOSURE_DOSSIER_2026_11.md` for coordinated private submission via GitHub Private Vulnerability Reporting.

---

## 4. Auditor v2 Lessons Learned for Future Waves

Running `py_ai_security_auditor_v2.py` on nearly 1 million LOC of production FastAPI code validated `AI-AUTH-07` and `AI-SQL-08` as high-signal bug-finding rules (directly surfacing all 3 quarantined findings) and identified two precision improvements for a future v3:
1. **Module-Level `Depends(...)` Alias Resolution (`AI-AUTH-07`)**: Resolving module-level constants such as `_user_api_key_auth_dep = Depends(user_api_key_auth)` or `_AUTHENTICATED = (Depends(user_api_key_auth),)` and recognizing FastAPI `Annotated[UserAPIKeyAuth, Depends(...)]` return-type hints would eliminate ~20% of `AI-AUTH-07` manual review overhead on large FastAPI proxies like LiteLLM.
2. **SQLAlchemy Bound-Parameter Dialect-Switch Recognition (`AI-SQL-08`)**: Recognizing `text(f"... :{param} ...")` where every interpolated expression is a static dialect-constant string or integer loop index would eliminate ~65% of `AI-SQL-08` false positives on multi-dialect SQLite/PostgreSQL ORMs.
