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

## 2. Loop B — 8-Hour Zero-Template Monetization Exploration (`8h_venture`)

> **ZERO ROUTINE / ZERO TEMPLATE RULE (`定型作業・テンプレ量産・固定メニュー完全禁止`)**:
> - Do **NOT** follow any fixed recipe, fixed naming convention (no `〇〇GATE`, no `*-auditor` clones), or fixed category checklist/rotation.
> - Turning this loop into repetitive busywork (e.g., churning out similar static web tools, queuing unread articles, or mechanically cycling through a preset menu) is strictly prohibited.

Every 8 hours, start from a **blank slate**:

1. **Check `data/revenue_ops_memory.json` to Avoid Repeating Patterns**:
   - Look at what was tried in recent runs. Do **not** repeat the same product shape, same channel combo, or same routine task.
2. **Look Outward at the Real World Right Now**:
   - Search live news, social/search trends, marketplaces, communities, and platforms across completely varied domains (consumer/prosumer digital goods, creator/media formats, live marketplaces with built-in traffic, real buyer pain points, arbitrage/information edges, contests, security/bounties, distribution hacks, etc.).
3. **Apply the Ruthless "Will Anyone Actually Pay?" Filter**:
   - Before touching code or text, ask: *Where do the actual human buyers or prize/payout dollars come from at `$0.00` spend? If nobody will ever find this URL, do not build another lonely page — either build where buyers already browse, or build the traffic/distribution bridge itself.*
4. **Autonomous Account Registration Authorized (`$0.00` Free Tiers Only)**:
   - Whenever a new marketplace, contest, affiliate/creator platform, or API requires an account, **do NOT stop and ask the user if you can register it yourself**:
     1. Read the local `0600` operator profile in the conversation scratch directory (`private_operator_profile.json` — **NEVER copy its private fields into any git-tracked file or public profile!**).
     2. Always set **public username / pen name / shop name = `peco` (`pecopeko`)**; only enter private legal/contact details into strictly private account/payout fields when required.
     3. Use the built-in `browser` subagent (`Model="flash"`, opening 1 temporary tab and closing it when done; never touching `browser__*`, `browser__popup-*`, `agent-tab-12`, or `agent-tab-14`) to submit the signup form or `"Continue with GitHub"`, and use the `gmail` CLI (`gmail readonly search` / `gmail readonly read`, never piping to `grep`/`awk`) to retrieve verification links or 6-digit OTP codes automatically.
     4. Record newly created credentials/handles back into `private_operator_profile.json` (`registered_accounts`).
     5. *Only pause for the user* if a site presents a mandatory anti-bot challenge / CAPTCHA, government photo-ID selfie KYC, or paid billing screen (never bypass those).
5. **Execute End-to-End & Log Factually**:
   - Whatever angle you discover, carry it all the way to a live, testable real-world action under `peco` / `pecopeko` (`$0.00` spend, zero personal data exposure, 8 GB Mac RAM safe).
   - Record what you tried and why in `autonomous_revenue_ops.py record-action --loop 8h_venture --category <free_label> --summary "<what & why>" --url "<live_url>"`.
