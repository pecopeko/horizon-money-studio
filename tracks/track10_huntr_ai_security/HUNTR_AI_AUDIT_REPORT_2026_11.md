# Defensive Python AI/ML Open-Source Static Audit Report (November 2026)

**Audit Date**: 2026-11-20  
**Scanner**: `tracks/track10_huntr_ai_security/py_ai_security_auditor.py` (Python 3.11 stdlib AST, 6 CWE rules, test directories excluded)  
**Disclosure Discipline**: Strictly defensive offline static analysis and manual source review. Zero remote servers were probed and zero offensive payloads were created. All unpatched defensive security defects and recommended patches are quarantined exclusively in the `.gitignore`d `CONFIDENTIAL_DO_NOT_PUSH/` directory for coordinated private disclosure via each repository's official `SECURITY.md` channel.

---

## 1. Aggregate Scan Metrics

| Repository | Audited Scope | Version / Commit SHA | Files Scanned | LOC Scanned | Parse Errors | Raw AST Findings | Post-Triage True Hardening / Unpatched Defects |
|---|---|---|---:|---:|---:|---:|---:|
| `huggingface/smolagents` | `src/` | `1.27.0.dev0` (`2689e45`, 2026-11-18) | 18 | 12,895 | 0 | 6 | 1 (quarantined in `CONFIDENTIAL_DO_NOT_PUSH/`) |
| `gradio-app/gradio` | `gradio/` + `client/python/` | `6.32.0` (`c9a6433`, 2026-11-19) | 190 | 65,327 | 0 | 19 | 2 (quarantined in `CONFIDENTIAL_DO_NOT_PUSH/`) |
| `run-llama/llama_index` | Huntr-eligible packages (`llama-index-core`, `llama-index-cli`, `llama-index-llms-openai`, `llama-index-embeddings-openai`) | `0.14.26` (`99d7433`, 2026-11-13) | 484 | 79,584 | 0 | 0 | 0 |
| **Total** | **3 Authorized AI/ML OSS Repos** | — | **692** | **157,806** | **0** | **25** | **3 (all quarantined privately)** |

### Raw AST Findings by Rule

| Rule ID | CWE | Severity | `smolagents` | `gradio` (`pkg` + `client`) | `llama_index` (Huntr scope) | Total |
|---|---|---|---:|---:|---:|---:|
| `AI-DESER-01` | CWE-502 | HIGH | 3 | 0 | 0 | 3 |
| `AI-PATH-02` | CWE-22 | HIGH | 0 | 14 | 0 | 14 |
| `AI-CMD-03` | CWE-78 | CRITICAL | 0 | 1 | 0 | 1 |
| `AI-EVAL-04` | CWE-94 | CRITICAL | 3 | 4 | 0 | 7 |
| `AI-SSRF-05` | CWE-918 | HIGH | 0 | 0 | 0 | 0 |
| `AI-TEMP-06` | CWE-377 | MEDIUM | 0 | 0 | 0 | 0 |
| **Total** | — | — | **6** | **19** | **0** | **25** |

**Signal-to-Noise Observation**: Scanning **157,806 LOC** across 692 non-test production Python files produced only **25 raw alerts** (`0.16` alerts per 1,000 LOC) with **0 syntax/parse errors**, enabling complete manual inspection of **100% of raw alerts (25/25)** against each repository's `SECURITY.md` trust model.

---

## 2. Per-Repository Triage Summary (Non-Sensitive Verified Observations)

### A. `run-llama/llama_index` (Huntr.com Eligible Scope — 484 Files, 79,584 LOC, 0 Findings)
- **Result**: **0 raw AST findings** across all 6 CWE rules; cross-verified via direct pattern inspection of `llama-index-core` and `llama-index-cli`.
- **Verified Defensive Controls Already in Place**:
  - `llama-index-core/llama_index/core/objects/base_node_mapping.py` replaces raw `pickle.load` with a custom allowlisted `_RestrictedUnpickler(pickle.Unpickler)` explicitly annotated for CWE-502 defense.
  - Output parsers (`output_parsers/utils.py`, `output_parsers/selection.py`) consistently use `yaml.safe_load`.
  - Temporary file creation (`core/schema.py`) uses `tempfile.NamedTemporaryFile()`.
- **Takeaway**: The core packages eligible for Huntr.com bounties are clean against baseline static deserialization, archive extraction, shell injection, eval/SSTI, and insecure tempfile sinks.

### B. `huggingface/smolagents` (`src/` — 18 Files, 12,895 LOC, 6 Raw Findings)
All 6 raw findings were manually audited against `smolagents/SECURITY.md`:
- **3 × `AI-DESER-01` — Already Mitigated by Default (`allow_pickle=False`)**:
  - `src/smolagents/remote_executors.py` (`_deserialize_final_answer`) and `src/smolagents/serialization.py` (`SafeSerializer.loads`) contain `pickle.loads` fallback branches, but both default to `allow_pickle: bool = False`, raise `SerializationError` unless a caller explicitly opts in, and emit `FutureWarning`. **Triage**: Mitigated-by-default; not a vulnerability.
- **2 × `AI-EVAL-04` — Out-of-Scope / Static Template**:
  - `Tool.from_code` (`exec`) is gated by `if not trust_remote_code: raise ValueError(...)` in `Tool.from_hub()`, placing remote-code loading explicitly outside `SECURITY.md` scope when opted in.
  - `create_agent_gradio_app_template` (`utils.py`) compiles a static module-level constant string (`AGENT_GRADIO_APP_TEMPLATE`), not attacker-controlled template syntax. **Triage**: False positive / static template constant.
- **1 × `AI-EVAL-04` — Quarantined Defensive Hardening Defect**:
  - One dynamic template-rendering path lacks Jinja2 sandboxing despite adjacent `yaml.safe_load` usage. Full technical review and an `ImmutableSandboxedEnvironment` patch recommendation have been saved strictly to `CONFIDENTIAL_DO_NOT_PUSH/DEFENSIVE_DISCLOSURE_DOSSIER_2026_11.md` for coordinated maintainer review.

### C. `gradio-app/gradio` (`gradio/` + `client/python/` — 190 Files, 65,327 LOC, 19 Raw Findings)
All 19 raw findings (19 in `gradio/`, 0 in `gradio_client`) were manually audited against `gradio/SECURITY.md`:
- **4 × `AI-EVAL-04` — Intentional Developer Runtime / Trusted Internal Metadata**:
  - `events.py` renders internal Python `__doc__` strings of Gradio event listeners; `ipython_ext.py` executes the user's own Jupyter cell magic; `utils.py` (`watchfn`) executes the local developer's watched demo file for hot-reload. **Triage**: Expected runtime behavior / out of scope per `SECURITY.md`.
- **13 × `AI-PATH-02` — Server-Generated, App-Configured, or Opt-In Local File Operations**:
  - `deep_link` writes to a server-computed hash directory (`route_utils.create_url_safe_hash`), not user-controlled path segments.
  - Streaming file responses serve internally synthesized paths (`stream.combined_file`) or `tempfile.NamedTemporaryFile`/`mkstemp` outputs.
  - `pwa_icon` serves `blocks.favicon_path`, which is explicitly trusted app-author configuration under `SECURITY.md`.
  - Local dev-editor handlers reading/writing the configured `GRADIO_WATCH_DEMO_PATH` or `secrets.token_hex(16)` snapshot files are server-owned paths (though see quarantined auth/path findings below).
- **2 Genuine Unpatched Defects Quarantined Privately (`1 × AI-PATH-02 + CWE-306`, `1 × AI-CMD-03`)**:
  - One route-level CWE-22 path containment omission combined with a missing route authentication dependency (`CWE-306`) on an opt-in feature mode, and one defense-in-depth CWE-78 `asyncio.create_subprocess_shell` call that should be converted to `asyncio.create_subprocess_exec` for parity with sibling invocations in the same module.
  - Full details, exact commit/version metadata, and minimal unified diffs are stored strictly in `CONFIDENTIAL_DO_NOT_PUSH/DEFENSIVE_DISCLOSURE_DOSSIER_2026_11.md` for private disclosure via `gradio-app/gradio`'s GitHub Private Vulnerability Reporting channel.

---

## 3. Auditor Precision & Future Hardening Enhancements

Running `py_ai_security_auditor.py` across 157,806 LOC of real-world AI/ML production code validated both its high precision and highlighted two optional future improvements:
1. **Default-False Opt-In Gate Recognition**: Recognizing `if not allow_pickle: raise ...` guards immediately preceding `pickle.loads` would downgrade mitigated-by-default fallbacks from `HIGH` to `INFO` while keeping unprotected `pickle.loads` at `HIGH`.
2. **Route Authentication Consistency Audit**: Comparing per-route `dependencies=[Depends(...)]` across siblings on the same FastAPI `APIRouter` was the decisive signal during manual review — a strong candidate for a future `AI-AUTH-07` rule.
