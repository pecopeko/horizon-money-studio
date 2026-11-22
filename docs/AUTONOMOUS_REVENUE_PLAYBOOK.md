# Autonomous Revenue Operations Playbook (`peco` / `pecopeko`)

This playbook governs the two autonomous background cron loops operating inside `/Users/wakabayashishuntaira/Documents/makemoney`:

1. **Loop A — Every 24 Hours (`24h_optimize`)**: Live portfolio telemetry audit, rate-limit queue flush, maintainer review response, and conversion/SEO optimization of shipped products.
2. **Loop B — Every 8 Hours (`8h_venture`)**: Live news, AI/LLM/MCP trend & cash-bounty discovery, followed by **end-to-end engineering, automated testing (`100% pass`), and live `$0.00` deployment/submission** of a concrete new monetization shot.

---

## 0. Non-Negotiable Safety & Privacy Rules (Read First Every Run)

1. **Strict Public Anonymity (`peco` ONLY)**:
   - Public display names, git commits (`peco <pecopeko@users.noreply.github.com>`), READMEs, PRs, articles, and store listings MUST NEVER contain the user's real name, address, phone number, or personal Gmail.
2. **Strict `$0.00` Out-of-Pocket Rule (`金かかることは勝手にやらない`)**:
   - Never attach credit cards, enable paid cloud billing, buy domains, or exceed free-tier compute allowances.
3. **Strict 8 GB Mac RAM Discipline**:
   - **NEVER** spawn local background daemon servers, remote-control bridges, or extra headless/headed Chrome processes.
   - If built-in browser interaction is needed (`invoke_subagent(TypeName="browser", Model="flash", ...)`), NEVER touch `[user tab] browser__*`, `browser__popup-*`, `agent-tab-12`, or `agent-tab-14`, and **always close any temporary `agent-tab-*` you opened** before finishing.
4. **Strict `macroTomicro` Firewall**:
   - Never read or modify `~/Documents/macroTomicro` and never SSH to `192.168.1.3`.
5. **No Silent Error Swallowing & Anti-Small-Sample Overfitting**:
   - Never invent fake metrics. Record exact factual counts via `scripts/autonomous_revenue_ops.py audit`.
   - Do not scrap or pivot a newly published asset based on 1–2 days of zero sales; give SEO/Store indexing time while fixing concrete funnel gaps (missing links, schemas, examples, rate-limited items).
6. **Anti-Honeypot & 100%-Tested PR Discipline**:
   - Always filter bounty candidates through `src/makemoney/scouts/bounty_scout.py` (`is_honeypot_or_bait`, `is_non_cash_org`, `has_competing_open_pr`), verify **zero competing open PRs** right before coding AND right before opening a PR, and run the target repository's test suite to **100% pass**.

---

## 1. Loop A — 24-Hour Portfolio Analysis & Improvement (`24h_optimize`)

Execute these steps in order on every 24-hour trigger:

1. **Collect Live Metrics & Check Gmail**:
   - Run `.venv/bin/python /Users/wakabayashishuntaira/Documents/makemoney/scripts/autonomous_revenue_ops.py audit`.
   - Check Gmail (`gmail readonly search "newer_than:2d" --max 15`, never piping to `grep`/`awk`) for any sale notifications (BOOTH / Zenn / Sponsors / Apify), GHSA security maintainer replies, PR review comments, or Metaculus tournament updates.
2. **Respond Immediately to Active Money-in-Flight Signals**:
   - If any external PR (`cognizant-ai-labs/agentic-web#71` or OSS bounty PR) or GHSA (`GHSA-xj7c-g4mm-6q8v`, `GHSA-mh2m-r84q-fj89`) has new maintainer comments or failing CI, address them with a clean, tested update first.
   - Check `pecopeko/metaculus-futureeval-quant-bot` recent workflow runs; if any scheduled run failed, diagnose and fix immediately so zero 3-hour FutureEval/MiniBench windows are missed.
3. **Flush Rate-Limited Publishing Queues**:
   - **Apify Store (`5/24h` limit)**: If `website-tech-stack-sitemap-extractor` (`5JvTo62JolQgtk3EM`) is still `"is_public": false`, open `https://console.apify.com/actors/5JvTo62JolQgtk3EM/publication` via the built-in `browser` subagent (`Model="flash"`), click `Publish on Store`, and close the temporary tab! Furthermore, up to Apify's `5/day` limit, upgrade top remaining Actors in `pecopeko/apify-ppe-actors` with `output_schema.json` + `dataset_schema.json` + PPE pricing and publish them on Apify Store.
   - **Zenn Content (`pecopeko/zenn-content`)**: Publish 1–2 queued `published: false` high-intent B2B compliance articles per day (ensuring every published article includes natural footer links to `https://zenn.dev/pecopeko/books/afml-quant-and-local-ai-guard` and `https://pecopeko1011.booth.pm/items/9179705`) and trigger `手動デプロイ` on `https://zenn.dev/dashboard/deploys` if GitHub webhook hit a rate limit.
4. **Ship 1 Concrete Funnel / Conversion Improvement**:
   - Examples: add saved Task Examples / richer README input-output tables on Apify Actors with runs > 0 to boost Apify Store Quality Score; add internal cross-links or fresh 2026 pricing data to `pecopeko/ai-tax-cost-atlas` (152-page pSEO); improve `pecopeko/predmarket-arb-radar` signal clarity.
5. **Log Action**:
   - Run `.venv/bin/python /Users/wakabayashishuntaira/Documents/makemoney/scripts/autonomous_revenue_ops.py record-action --loop 24h_optimize --category <cat> --summary "<exact change>" --url "<live_url>"`.

---

## 2. Loop B — 8-Hour News / AI Trend Discovery & New `$0.00` Venture Execution (`8h_venture`)

Execute these steps in order on every 8-hour trigger:

1. **Read Recent Ventures Memory First (Deduplication)**:
   - Read `/Users/wakabayashishuntaira/Documents/makemoney/data/revenue_ops_memory.json` (`ventures_shipped` and `actions_log`) so you never duplicate a tool, bounty issue, article, or niche already shipped.
2. **Scan Live AI Trends, Breaking Tech News & Fresh Cash Opportunities**:
   - Use `search_web` and lightweight APIs (`Hacker News` top/show stories, GitHub Trending, newly announced AI/LLM/MCP/Agent protocols, regulatory changes, new developer benchmarks/hackathons/contests, and `makemoney.scouts.bounty_scout.scan_bounty_issues()`).
   - Evaluate candidates strictly on **Expected Value (`EV`) at `$0.00` cost with zero human labor required from the user**:
     1. **Tier 1 (Fastest Cash)**: Newly opened, genuine, funded GitHub / Algora cash bounty (`$50–$1,000+`, zero competing PRs, non-honeypot, reproducible test suite) OR high-impact verifiable security vulnerability in a major OSS AI/ML repo with active GitHub Private Vulnerability Reporting / Huntr bounty program.
     2. **Tier 2 (High-Demand Developer / AI Agent Distribution)**: A brand-new Apify Pay-Per-Event (`PPE`) Actor, MCP server, CLI/Action, or zero-backend interactive web calculator/tool riding a **breaking 2026 AI/tech/regulatory trend** discovered in today's news — coupled with live deployment (GitHub Pages / Releases / Apify / Zenn article) and cross-links into existing paid products (`Zenn ¥1,200 Book`, `BOOTH ¥1,980 Kit`, `GitHub Sponsors`, `Apify PPE`).
     3. **Tier 3 (Live Cash Tournaments / Hackathons)**: Newly announced remote AI/quant/agent cash competitions accepting automated GitHub PR or API submissions at `$0.00`.
3. **Actually Build, Test (`100% Pass`) & Ship Live**:
   - Do **not** stop at research notes! Write production-grade code + unit tests, verify `pytest` / `node --test` passes `100%`, push/deploy/submit publicly under `peco` (`pecopeko <pecopeko@users.noreply.github.com>`), and verify `HTTP 200` or live PR URL.
4. **Log Shipped Venture**:
   - Run `.venv/bin/python /Users/wakabayashishuntaira/Documents/makemoney/scripts/autonomous_revenue_ops.py record-action --loop 8h_venture --category <bounty_pr|security_ghsa|apify_ppe|trend_tool|contest> --summary "<what trend was spotted & what was shipped>" --url "<live_url>"`.
