# Greenhouse, Lever & Ashby ATS Jobs Board Extractor

Fast, zero-browser extraction of structured, enriched job postings directly from the official public **Greenhouse**, **Lever**, and **Ashby** ATS JSON APIs — with automatic remote/hybrid classification, seniority tagging, compensation range parsing, and **45+ tech stack tags** at **$1.00 per 1,000 jobs**.

## Why Official Public ATS JSON APIs?

Instead of brittle headless-browser scrapers that break on DOM changes or trigger anti-bot walls, this Actor queries each ATS platform's documented public job-board JSON endpoints directly:

- **Greenhouse**: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` (plus EU `boards-api.eu.greenhouse.io`)
- **Lever**: `https://api.lever.co/v0/postings/{slug}?mode=json` (plus EU `api.eu.lever.co`)
- **Ashby**: `https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`

## Key Features

- **Unified Multi-ATS Input**: Mix structured objects (`{"provider": "greenhouse", "slug": "stripe"}`), full career board URLs (`https://boards.greenhouse.io/stripe`, `https://jobs.lever.co/spotify`, `https://jobs.ashbyhq.com/linear`), or shorthands (`ashby:linear`) in one batch run.
- **Rich Structured Normalization**: Every job across all 3 ATS providers is mapped to one consistent schema with `workplace_type` (`remote` / `hybrid` / `onsite` / `unspecified`), `seniority` (`intern` / `junior` / `mid` / `senior` / `staff_principal` / `manager_exec`), `salary_min` / `salary_max` / `salary_currency` / `salary_interval`, `tech_tags` (45+ skills including Python, TypeScript, Go, Rust, React, Kubernetes, AWS, PyTorch, SQL, Solidity, Terraform, LLM/GenAI, etc.), `published_at`, `apply_url`, and clean stripped `description_text`.
- **Precision Filtering**: Filter server-side by `remoteOnly`, `keywordFilter`, `departmentFilter`, and `maxJobsPerBoard`.
- **Production Security & Fault Isolation**: Strict SSRF host/IP allowlisting, redirect re-validation, polite `429`/`503` `Retry-After` exponential backoff, and per-board error isolation so one invalid slug never fails the rest of your batch.

## Pricing (Pay-Per-Event)

- **`job_extracted`**: **`$0.001`** per extracted job (`$1.00 / 1,000 jobs`). Failed board error records are never charged.

## Popular Use Cases

1. **Recruiting & Job Aggregators**: Keep niche remote engineering, AI, or fintech job boards continuously synced without browser compute costs.
2. **B2B Sales & Hiring Intent Signals**: Track which target accounts are hiring for `Kubernetes`, `Snowflake`, `PyTorch`, `Solidity`, or `Security` roles.
3. **Compensation & Talent Market Benchmarks**: Aggregate `salary_min`, `salary_max`, `seniority`, and `workplace_type` trends across venture-backed startups and public tech companies.

## Input Example

```json
{
  "boards": [
    { "provider": "greenhouse", "slug": "stripe" },
    { "provider": "lever", "slug": "spotify" },
    "https://jobs.ashbyhq.com/linear"
  ],
  "remoteOnly": false,
  "keywordFilter": "",
  "departmentFilter": "",
  "maxJobsPerBoard": 100,
  "requestDelayMs": 250
}
```

## Output Example

```json
{
  "record_type": "job",
  "status": "ok",
  "provider": "ashby",
  "company_slug": "linear",
  "company_name": "linear",
  "job_id": "d3bc1ced-3ce4-4086-a050-555055dbb1ff",
  "title": "Senior / Staff Fullstack Engineer",
  "department": "Product",
  "team": "Engineering",
  "location": "Europe",
  "workplace_type": "remote",
  "seniority": "staff_principal",
  "salary_min": 200000,
  "salary_max": 260000,
  "salary_currency": "USD",
  "salary_interval": "yearly",
  "tech_tags": ["PostgreSQL", "React", "TypeScript"],
  "published_at": "2026-04-27T20:13:45.158+00:00",
  "apply_url": "https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff/application",
  "description_text": "At Linear, we are building the product development system for teams and agents...",
  "source_api": "ashby_job_board_api"
}
```
