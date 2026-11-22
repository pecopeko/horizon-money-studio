# AGENTS.md — Horizon-Money Studio Engineering & Safety Rules

## Studio Tracks
- **Track 1 (`tracks/track1_apify/`, `src/makemoney/scouts/apify_scout.py`)**: Apify Store Pay-Per-Event (PPE) & RapidAPI niche actors/APIs.
- **Track 2 (`src/makemoney/compliance_guard/`, `tracks/track2_micro_saas/`, `Dockerfile.cloudrun`)**: Micro-SaaS, browser-local Web/Chrome-extension privacy tools, and zero-cost static/Pages products targeting underserved Japanese business & LLM compliance workflows.
- **Track 3 (`src/makemoney/scouts/bounty_scout.py`, `tracks/track3_bounties/`)**: Live GitHub / Algora / GitHub Sponsors open-source cash bounty discovery, pre-qualification, and PR delivery.
- **Track 4 (`tracks/track4_m2m_colab/`, `colab/track4_m2m_gpu_offload_sweep.ipynb`)**: Non-invasive Google Colab GPU offload & AFML orthogonality/fixed-capital audit kit for `macroTomicro`.

## Mandatory Operational & Engineering Discipline
1. **Strict Boundary on `macroTomicro`**: Never modify any file under `~/Documents/macroTomicro` and never SSH into the Windows production machine (`192.168.1.3`) from this studio. All Track 4 experiments and notebooks live strictly inside `~/Documents/makemoney/tracks/track4_m2m_colab/` and `colab/`.
2. **No Silent Error Swallowing or Fake Metrics**: Never replace missing API responses, rate-limit errors, or failed computations with fabricated values or silent `.fillna(0)` fallbacks. Always surface errors or exact provenance.
3. **Autonomous Free External Publishing & PR Submission Authorized**: You are authorized to autonomously create public GitHub repositories, deploy to free GitHub Pages / GitHub Releases, and submit genuine, fully tested OSS Pull Requests without waiting for human sign-off.
4. **Strict `$0.00` Out-of-Pocket Rule**: Never perform any action that incurs money (`金かかることは勝手にやらない`) — never enable paid cloud billing, attach credit cards, deploy paid GCP Cloud Build / Cloud Run workloads, register paid domains, or incur paid API charges outside already-included free/subscription tiers.
5. **Anti-Honeypot & Anti-Spam PR Discipline**: Blocklist known AI-honeypot or non-cash bait orgs (`SecureBananaLabs`, `UnsafeLabs`, `ClankerNation`, `IES-BoilerRoom`, `zhangjiayang6835-cyber`), verify zero competing open PRs before working an issue, and run the target repository's test suite to 100% pass before opening any PR.
6. **No CAPTCHA / Anti-Bot Bypass**: Never bypass CAPTCHAs, login walls, or anti-bot protections. Rely exclusively on public APIs, official SDKs, and lawful developer workflows.
7. **Local Mac Memory Discipline (8 GB RAM)**: Keep the local `.venv` lightweight; route PyTorch / LLM distillation / large sweeps to the Google Colab A100/L4 notebooks under `colab/`. **NEVER launch local background daemon servers, remote-control servers, or extra headless/headed Chrome instances (`PocketBridge`, Playwright/CDP daemons, etc.) on this Mac — spawning a second browser instance exhausts 8 GB RAM and forces a system reboot.**
8. **Python 3.11 Compatibility**: Avoid Python 3.12+ f-string syntax (no backslashes or nested quotes inside `{...}` in f-strings).
