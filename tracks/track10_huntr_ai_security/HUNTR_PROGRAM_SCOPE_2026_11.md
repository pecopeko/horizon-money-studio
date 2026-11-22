# Authorized Python AI/ML Open-Source Security Programs & Huntr Scope Survey (November 2026)

**Audit Date**: 2026-11-20  
**Methodology**: Live read-only inspection of upstream `SECURITY.md` files, GitHub repository metadata, public GitHub Security Advisories (GHSAs), and Huntr.com (Protect AI / Palo Alto Networks Prisma AIRS) program disclosures.  
**Operational Rule**: Strictly defensive static analysis and responsible coordinated disclosure only. Never test against third-party hosted infrastructure or publish unpatched vulnerability details publicly.

---

## Executive Summary: November 2026 Disclosure Landscape Shift

Live inspection of upstream `SECURITY.md` policies on 2026-11-20 reveals a critical operational shift across Python AI/ML open-source projects:

1. **Huntr.com (Protect AI / Palo Alto Networks)** remains the flagship AI/ML OSS vulnerability platform and CVE Numbering Authority (CNA), with projects such as **`run-llama/llama_index`** explicitly pointing researchers to `https://huntr.com/repos/run-llama/llama_index` for bounties on core packages.
2. **Direct VDP / Cash Bounty Programs**: High-velocity AI gateways such as **`BerriAI/litellm`** run dedicated cash bug bounty programs (`$500–$3,000` via HackerOne VDP) and **`langchain-ai/langchain`** routes disclosures through Intigriti VDP.
3. **Anti-AI-Spam Opt-Outs**: Several projects that were historically top Huntr targets (notably **`mlflow/mlflow`** and **`bentoml/BentoML`**) now explicitly state in their 2026 `SECURITY.md` that they **do not accept Huntr.com submissions** due to automated/LLM-generated report spam, requiring direct **GitHub Private Vulnerability Reporting (PVR)** or dedicated security email with a minimal reproducible PoC that crosses a documented trust boundary.
4. **Strict Trust-Boundary Filtering**: Almost every major AI/ML repository now explicitly rejects theoretical scanner output, `torch.load` / `pickle` on artifacts the user intentionally chose to load, `trust_remote_code=True`, prompt injection, and non-sandboxed local code executors. Real, accepted 2026 CVEs overwhelmingly fall into **concrete boundary violations**:
   - **CWE-22 / CWE-59**: Path traversal / symlink escapes (`ComfyUI`, `gradio`, `vLLM`, `LangChain`, `BentoML`).
   - **CWE-918**: SSRF & redirect/DNS-rebinding filter bypasses (`MLflow`, `Gradio`, `LiteLLM`, `LangChain`).
   - **CWE-78 / CWE-94 / CWE-1336**: Shell command injection & unsandboxed Jinja2 SSTI (`BentoML`, `MLflow`, `Ray`).
   - **CWE-502**: Deserialization in unintended/default code paths (`Ray` `CVE-2026-57516`, `LangChain` `CVE-2026-44843`, `MLflow` `CVE-2026-116692`).
   - **CWE-377**: Predictable `/tmp` temporary files explicitly listed as in-scope by `run-llama/llama_index`.

---

## Top 10 Actively Maintained Python AI/ML Programs (Verified 2026-11-20)

| # | Repository | Stars | Last Push | Primary Disclosure Channel | Monetary Bounty / Huntr Status | Recent 2026 Advisory Signal |
|---|---|---:|---|---|---|---|
| 1 | `run-llama/llama_index` | 52,965 | 2026-11-20 | **Huntr.com** (`huntr.com/repos/run-llama/llama_index`) + GitHub PVR | **Active Huntr Bounty** (first-degree `llama-index` deps only) | Explicit `SECURITY.md` Huntr scope + `/tmp` & TLS examples |
| 2 | `BerriAI/litellm` | 63,566 | 2026-11-20 | **LiteLLM VDP** (`security.litellm.ai/vdp/`, HackerOne) | **Cash Bounty** (`$1,500–$3,000` Critical P0; `$500–$1,500` High P1) | 5+ 2026 GHSAs (SSRF, file read, privilege escalation; GHSA drafts closed as of 2026-11-11) |
| 3 | `gradio-app/gradio` | 44,093 | 2026-11-20 | GitHub PVR / `security@huggingface.co` | CVE/GHSA credit (no direct HF cash bounty; historically indexed on Huntr) | `CVE-2026-28414` (CWE-36), `CVE-2026-28416` (CWE-918 SSRF), `CVE-2026-28415` |
| 4 | `huggingface/smolagents` | 30,448 | 2026-11-18 | GitHub PVR / `security@huggingface.co` | CVE/GHSA credit (no direct HF cash bounty) | Strict boundary between local executor (OOS) vs sandboxed backends (in-scope) |
| 5 | `huggingface/transformers` | 169,292 | 2026-11-20 | GitHub PVR / `security@huggingface.co` | CVE/GHSA credit (no direct HF cash bounty) | `apply_chat_template` Jinja sandbox escape & `safetensors` bypass in-scope |
| 6 | `mlflow/mlflow` | 28,902 | 2026-11-20 | GitHub PVR (`mlflow/mlflow/security/advisories/new`) | **Explicitly Opted OUT of Huntr** (auto-closed without review) | `CVE-2026-116692` (Critical RCE), `CVE-2026-64849` (High SSRF), `CVE-2026-115886` |
| 7 | `vllm-project/vllm` | 97,235 | 2026-11-20 | GitHub PVR (`vllm-project/vllm/security/advisories/new`) | CVE credit (first reporter only; private fork for High/Critical) | `GHSA-xgh8-qwjh-q853` (Nov 18, 2026), `GHSA-qrj2-j723-m6w8` (CWE-22), `CVE-2026-115915` |
| 8 | `langchain-ai/langchain` | 149,932 | 2026-11-20 | **Intigriti VDP** (`langchain-open-source-vdp`) | Coordinated VDP (historically heavy Huntr OSS target) | `CVE-2026-55443` (CWE-22), `CVE-2026-44843` (`load()` deser), `CVE-2026-41488` (SSRF) |
| 9 | `comfyanonymous/ComfyUI` | 147,688 | 2026-11-20 | GitHub PVR (`comfyanonymous/ComfyUI/security/advisories/new`) | CVE/GHSA credit (local `127.0.0.1` threat model) | `CVE-2026-56670..56673` (Jul 2026 High CWE-22 path traversal & SVG XSS) |
| 10 | `bentoml/BentoML` | 8,942 | 2026-11-17 | `security@bentoml.com` / GitHub PVR | **Explicitly Non-Huntr** (no bounty budget) | `CVE-2026-35044` (Jinja2 SSTI), `CVE-2026-35043`/`44345`/`44346` (CWE-78), `CVE-2026-40610` |

*Notable adjacent Python AI/ML target verified during survey*: **`ray-project/ray`** (44,344 stars, `security@anyscale.com`) published **`CVE-2026-57516`** (2026-07-01, High, CWE-94/CWE-502) specifically for `pickle.loads(value)` and `torch.load(weights_only=False)` in `ray.data.read_webdataset` — directly validating the `AI-DESER-01` detector.

---

## Per-Program Scope Boundaries & In-Scope vs Out-of-Scope Matrix

### 1. `run-llama/llama_index` (Apache/MIT — Active Huntr Bounty)
- **Source**: `https://raw.githubusercontent.com/run-llama/llama_index/main/SECURITY.md`
- **Channel**: Huntr.com (`https://huntr.com/repos/run-llama/llama_index`) for eligible packages; GitHub PVR for other repo integrations.
- **In-Scope Packages (Huntr-eligible)**: `llama-index` umbrella + first-degree repo packages ONLY: `llama-index-core`, `llama-index-embeddings-openai`, `llama-index-llms-openai`, `llama-index-cli`.
- **Explicitly In-Scope Defect Classes**:
  - Race conditions / predictable filenames in `/tmp` (`open(..., 'w')` without `O_EXCL` — matches `AI-TEMP-06`).
  - Sensitive data / API key exposure in default debug logs.
  - Disabled TLS verification (`verify=False`) in outbound library helpers.
  - Self-contained library vulnerabilities reproducible with a minimal Python script (no external web wrapper needed).
- **Explicitly Out-of-Scope**:
  - Any third-party/community integration package not listed above.
  - Caller-supplied SSRF (`resolve_image`, `download_loader`, readers), caller-supplied path traversal/deserialization, OWASP Top-10 flaws introduced by a user's own FastAPI/Flask wrapper, prompt injection, and DoS via arbitrarily large web payloads.

### 2. `BerriAI/litellm` (Active Cash Bounty via HackerOne VDP)
- **Source**: `https://raw.githubusercontent.com/BerriAI/litellm/main/.github/SECURITY.md`
- **Channel**: `https://security.litellm.ai/vdp/` (HackerOne-triaged; **do NOT file draft GitHub GHSAs**, closed automatically since 2026-11-11).
- **Bounty Tiers**:
  - **P0 Critical (`$1,500–$3,000`)**: CI/CD supply-chain compromise affecting PyPI or Docker images.
  - **P1 High (`$500–$1,500`)**: Unauthenticated LiteLLM proxy access leaking protected data (e.g., master key, provider API keys, unauthorized file read/SSRF).
  - **P2 Medium (non-bounty, encouraged)**: Authenticated privilege escalation or cross-tenant data access.
- **Explicitly Out-of-Scope**:
  - Misconfigurations (e.g., running proxy without `master_key`).
  - Deliberately weakened flags (e.g., setting `disable_responses_id_security=True`).
  - Social engineering.

### 3. `gradio-app/gradio` (Hugging Face Ecosystem — GitHub PVR)
- **Source**: `https://raw.githubusercontent.com/gradio-app/gradio/main/SECURITY.md`
- **Channel**: GitHub PVR (preferred) or `security@huggingface.co` (cc `gradio-team@huggingface.co`). Latest release only; no backports.
- **Explicitly In-Scope**:
  - RCE, path traversal, unauthorized file access outside `allowed_paths` or bypassing `blocked_paths`, and SSRF reachable through standard Gradio routes/components.
  - XSS / session boundary violations in standard components; auth/session isolation bypasses.
  - Client-side RCE, directory escape, or local data disclosure in `gradio_client` / `gr.load()` triggered by a malicious remote Gradio app.
- **Explicitly Out-of-Scope**:
  - Unsafe Python callbacks, custom HTML/JS/CSS, or intentionally shared `allowed_paths` configured by the app author.
  - Local DoS without multi-tenant/remote impact; scanner/LLM reports without a minimal self-contained PoC.

### 4. `huggingface/smolagents` (Hugging Face Ecosystem — GitHub PVR)
- **Source**: `https://raw.githubusercontent.com/huggingface/smolagents/main/SECURITY.md`
- **Channel**: GitHub PVR (preferred) or `security@huggingface.co`.
- **Explicitly In-Scope**:
  - RCE, memory corruption, or unauthorized file access in published package code (`src/smolagents/`) via normal API calls on non-artifact inputs.
  - **Real escapes from documented sandboxed execution backends** (E2B, Docker, Modal, Pyodide/WASM).
  - Bypass of advertised protections (`safetensors`-only loading, pinned revisions) or token/credential mishandling.
- **Explicitly Out-of-Scope**:
  - **Local Python executor (`LocalPythonExecutor`) escapes**: explicitly documented as *not* a security boundary.
  - Loading untrusted pickle/model artifacts opted into by the user; prompt injection / model jailbreaks; findings in `examples/`, docs, or tests.

### 5. `huggingface/transformers` (Hugging Face Ecosystem — GitHub PVR)
- **Source**: `https://raw.githubusercontent.com/huggingface/transformers/main/SECURITY.md`
- **Channel**: GitHub PVR (preferred) or `security@huggingface.co`.
- **Explicitly In-Scope**:
  - **Jinja2 sandbox escapes in `apply_chat_template`** (running arbitrary code, reading files, or accessing Python objects outside template inputs).
  - Code execution despite `use_safetensors=True` / `safetensors`-only loading, or pinned Hub revision bypasses.
  - Credential/token leaks and normal API RCE/file access on non-untrusted-model inputs.
- **Explicitly Out-of-Scope**:
  - Anything requiring `trust_remote_code=True` or intentional pickle checkpoint loading.
  - Operator/developer scripts under top-level `examples/`, `scripts/`, and `utils/`.
  - Local DoS, prompt injection, and unverified scanner reports.

### 6. `mlflow/mlflow` (GitHub PVR Only — Opted Out of Huntr)
- **Source**: `https://raw.githubusercontent.com/mlflow/mlflow/master/SECURITY.md`
- **Channel**: GitHub PVR (`https://github.com/mlflow/mlflow/security/advisories/new`) ONLY.
- **Explicit Huntr Exclusion**: *"we no longer accept vulnerability reports through bounty platforms such as Huntr. All reports submitted through such platforms will be automatically closed without review."*
- **In-Scope (evidenced by 2026 GHSAs)**:
  - Unauthenticated/authenticated server-side SSRF and redirect/DNS-rebinding bypasses (`CVE-2026-64849`, `CVE-2026-115886`).
  - Deserialization / dynamic module import RCE on MLflow tracking/GenAI servers (`CVE-2026-116692`).
  - Missing authorization in workspace/gateway endpoints (`GHSA-4449-4cjp-ffp5`) and secret leakage in autologging traces (`CVE-2026-116691`).
- **Out-of-Scope**: Public GitHub issues for security bugs; unverified scanner/LLM spam.

### 7. `vllm-project/vllm` (GitHub PVR)
- **Source**: `https://raw.githubusercontent.com/vllm-project/vllm/main/SECURITY.md`
- **Channel**: GitHub PVR (`https://github.com/vllm-project/vllm/security/advisories/new`). First reporter only credited.
- **In-Scope**:
  - Critical/High RCE via network endpoints, unsafe deserialization chains, multimodal parser RCE (e.g., `CVE-2026-115915` Ghostscript/EPS), path traversal (`GHSA-qrj2-j723-m6w8`), and security gate bypasses (`GHSA-xgh8-qwjh-q853` bypassing `--trust-request-chat-template`).
  - Moderate remotely triggerable engine OOM/DoS (`CVE-2026-115913`).
- **Out-of-Scope**: Duplicate/AI-generated submissions; PyTorch upstream untrusted-model risks documented in PyTorch's `SECURITY.md`.

### 8. `langchain-ai/langchain` (Intigriti VDP)
- **Source**: `https://raw.githubusercontent.com/langchain-ai/.github/main/SECURITY.md`
- **Channel**: Intigriti VDP (`https://app.intigriti.com/researcher/programs/langchain/langchain-open-source-vdp`).
- **In-Scope (evidenced by 2026 GHSAs)**:
  - Unsafe deserialization / overly broad `load()` allowlists (`CVE-2026-44843`).
  - Path traversal & symlink escapes in loaders/middleware (`CVE-2026-55443`, `CVE-2026-34070`).
  - SSRF filter bypasses including DNS rebinding (`CVE-2026-41488`) and prompt template validation escapes (`CVE-2026-40087`).
- **Out-of-Scope**: Non-sandboxed REPL tools explicitly opted into by developers; prompt injection without code/trust-boundary escape.

### 9. `comfyanonymous/ComfyUI` (GitHub PVR — Local Threat Model)
- **Source**: `https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/SECURITY.md`
- **Channel**: GitHub PVR (`https://github.com/comfyanonymous/ComfyUI/security/advisories/new`).
- **Explicitly In-Scope**:
  - Workflow files using **built-in nodes only** that cause untrusted code execution, arbitrary file read/write outside expected directories, or credential/data exfiltration on a standard local installation (see July 2026 `CVE-2026-56670`..`56673`).
- **Explicitly Out-of-Scope**:
  - Anything requiring `--listen` or non-localhost network exposure.
  - Third-party custom nodes.
  - `torch.load` / deserialization issues dependent on outdated PyTorch (`<= 2.6`) not shipped/recommended by ComfyUI.
  - Workflow crashes, hangs, or OOM DoS.

### 10. `bentoml/BentoML` (Email / GitHub PVR — Non-Huntr)
- **Source**: `https://raw.githubusercontent.com/bentoml/BentoML/main/SECURITY.md`
- **Channel**: `security@bentoml.com` or GitHub PVR. Explicitly does not participate in Huntr.com.
- **In-Scope (evidenced by 2026 GHSAs)**:
  - Command injection in build/cloud deployment pipelines (`CVE-2026-35043`, `CVE-2026-44345`, `CVE-2026-44346`).
  - Unsandboxed Jinja2 SSTI during Dockerfile generation from bento archives (`CVE-2026-35044`).
  - Symlink traversal in `bentoml build` (`CVE-2026-40610`).
- **Explicitly Out-of-Scope**:
  - Pickle deserialization reports targeting the internal runner service or dependency service.

---

## Mapping Auditor Rules (`py_ai_security_auditor.py`) to Valid Program Defect Classes

| Auditor Rule | CWE | High-Signal In-Scope Targets | Common False-Positive Traps to Filter Manually |
|---|---|---|---|
| `AI-DESER-01` | CWE-502 | Default data-loader/server deserialization paths (e.g., Ray `read_webdataset`, MLflow scorer loader, LiteLLM server handlers) | Explicit user-opted checkpoint loading (`transformers` without `use_safetensors`, BentoML internal runner, ComfyUI on PyTorch >=2.6) |
| `AI-PATH-02` | CWE-22 | Web endpoints (`FileResponse`/`send_file`/`open`) bypassing `allowed_paths`/`blocked_paths`; archive extraction (`tarfile`/`zipfile`) of remote artifacts | CLI/dev helper scripts; intentionally exposed author paths; internal trusted cache dirs |
| `AI-CMD-03` | CWE-78 | Container/Docker/cloud build commands, multimodal CLI wrappers (`ffmpeg`/Ghostscript), agent sandbox orchestrators | Static literal commands or local developer/release scripts |
| `AI-EVAL-04` | CWE-94 | Unsandboxed `jinja2.Template` / `Environment` on prompt/Dockerfile/chat templates; `eval`/`exec` in API config parsers | Documented local code executors (`smolagents` `LocalPythonExecutor` is explicitly OOS) |
| `AI-SSRF-05` | CWE-918 | FastAPI/Starlette/Flask proxy endpoints, webhooks, `gr.load()` remote fetchers, OAuth/URL helpers lacking private-IP + redirect checks | Fixed-origin SDK calls (`https://api.openai.com/...`); library helpers explicitly excluded by `llama_index` threat model |
| `AI-TEMP-06` | CWE-377 | Predictable `/tmp/` paths or `tempfile.mktemp` in shared libraries (`llama_index` explicitly lists this as Huntr-eligible!) and multi-user web routes | Test fixtures and read-only default fallbacks |
