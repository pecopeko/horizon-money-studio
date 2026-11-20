# Verified Live Diagnostic Outreach — smarthr.jp

- **Measured Score**: 69/100 (Grade C)
- **Scan Timestamp (UTC)**: 2026-11-20T02:55:53Z
- **Interactive Scorecard**: `teardown_smarthr_jp.html`

## 1. Cold Email (Under 140 Words, Zero Fluff)

**Subject**: 5 verified AI-search & trust gaps found on smarthr.jp (69/100)

Hi [Name],

I ran a quick, read-only 12-point technical diagnostic on **smarthr.jp** today (2026-11-20T02:55:53Z) and put the measured findings + copy-paste fixes into a private scorecard (`teardown_smarthr_jp.html`).

Specifically, our automated check measured **69/100** with 5 concrete gap(s):
- **JSON-LD Schema.org Structured Data** (0/10 pts): Zero valid application/ld+json Schema.org blocks on homepage (raw_blocks=0, parse_errors=0).
- **llms.txt AI Discovery Manifest** (0/9 pts): Missing machine-readable /llms.txt (returned HTTP 404 (195641 bytes)).
- **HTTP Security Headers Posture** (2/8 pts): 1/4 security headers active; missing: Content-Security-Policy, X-Content-Type-Options (nosniff), Referrer-Policy.
- **robots.txt AI Crawler Directives** (5/8 pts): /robots.txt present (64 B) but leaves 4/4 AI crawlers unspecified (no explicit policy for GPTBot/ClaudeBot/PerplexityBot/OAI-SearchBot).

I already generated the drop-in `llms.txt`, Schema.org JSON-LD, and DNS/header config tailored to **smarthr.jp** inside the scorecard — yours to hand straight to engineering at zero cost.

If you'd like us to deploy these fixes and wire up an automated n8n monitoring pipeline (so regressions, competitor pricing shifts, or DNS drift alert Slack instantly), happy to share a fixed-scope 48-hour setup option.

Best,
[Your Name]

## 2. LinkedIn / X DM Version

Hey [Name] — ran a quick non-intrusive diagnostic on smarthr.jp and spotted 5 measurable gap(s) (scored 69/100), including: Zero valid application/ld+json Schema.org blocks on homepage (raw_blocks=0, parse_errors=0).. Built an interactive scorecard with copy-paste fixes specifically for smarthr.jp. Want me to send the link over?
