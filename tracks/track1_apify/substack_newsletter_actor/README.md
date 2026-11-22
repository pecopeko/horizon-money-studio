# Substack Newsletter Posts & Public Markdown Extractor

Extract structured newsletter posts, engagement counts (`reaction_count`, `comment_count`, `restacks`), podcast audio URLs, authors, and **LLM/RAG-ready Markdown & plain text** from any Substack publication (handles, `*.substack.com` URLs, or custom domains) — at **$1.00 per 1,000 posts** with zero headless browsers.

## Strictly Lawful & Transparent Paywall Handling

This Actor uses **publicly accessible archive JSON (`/api/v1/archive`), public RSS (`/feed`), and public free post endpoints only**:
- **Free public posts (`audience == "everyone"`)**: Enriched with full `body_markdown` and `body_text`, labeled `paywall_status: "free_public"`.
- **Paid / subscriber-only posts**: **Never** bypasses paywalls or logins. Honestly labeled `paywall_status: "paid_preview_only"` with only the public title, metadata, and archive preview text.

## Key Features

- **Handles, Subdomains & Custom Domains**: Pass `"pragmaticengineer"`, `"https://pragmaticengineer.substack.com"`, or `"https://newsletter.pragmaticengineer.com"` interchangeably.
- **Smart Pagination + RSS Merging**: Automatically paginates Substack's cursor-based `/api/v1/archive` endpoint (with legacy offset fallback), merges `/feed` RSS content in a single request to minimize network calls, and gracefully falls back to `/feed` RSS on non-Substack newsletter domains.
- **LLM & RAG Ready Output**: Clean `body_markdown` (preserving headings, links, lists, blockquotes, code blocks) plus plain `body_text`, `word_count`, `authors`, `post_date`, and `podcast_url`.
- **Precision Filtering**: Filter by `onlyFree`, `publishedAfter` (with early pagination cutoff), and `keywordFilter`.
- **Hardened Security & Reliability**: Full SSRF protection (blocks private, loopback, link-local, and cloud metadata IPs on initial URLs and every redirect hop), DTD/ENTITY XML hardening, polite rate limiting with `429`/`503` `Retry-After` backoff, and fault-isolated batch execution.

## Pricing (Pay-Per-Event)

- **`post_extracted`**: **`$0.001`** per extracted post (`$1.00 / 1,000 posts`). Error records are never charged.

## Popular Use Cases

1. **AI Research & RAG Pipelines**: Continuously index public tech, finance, and macro Substacks into clean Markdown chunks (`onlyFree: true`, `publishedAfter: "2026-01-01"`).
2. **Creator & Audience Analytics**: Track posting cadence, `reaction_count`, `comment_count`, `restacks`, and free vs. paid ratio across newsletter cohorts.
3. **Topic & Competitor Intelligence**: Monitor mentions of specific startups, frameworks, or tickers with `keywordFilter`.

## Input Example

```json
{
  "publications": [
    "pragmaticengineer",
    "https://www.astralcodexten.com"
  ],
  "maxPostsPerPublication": 25,
  "includeFullText": true,
  "onlyFree": false,
  "publishedAfter": "2026-01-01",
  "keywordFilter": "",
  "requestDelayMs": 350
}
```

## Output Example

```json
{
  "record_type": "post",
  "status": "ok",
  "publication": "newsletter.pragmaticengineer.com",
  "publication_url": "https://newsletter.pragmaticengineer.com",
  "post_id": 225268679,
  "title": "Software factories and code reviews with Harjot Gill",
  "subtitle": "CodeRabbit CEO Harjot Gill explains how he shipped over 5,000 pull requests in a month.",
  "slug": "software-factories-and-code-reviews",
  "canonical_url": "https://newsletter.pragmaticengineer.com/p/software-factories-and-code-reviews",
  "post_date": "2026-11-18T18:08:52.693Z",
  "audience": "everyone",
  "paywall_status": "free_public",
  "authors": ["Gergely Orosz"],
  "reaction_count": 70,
  "comment_count": 1,
  "restacks": 6,
  "word_count": 2388,
  "podcast_url": "https://api.substack.com/api/v1/audio/upload/example/src",
  "cover_image": "https://substackcdn.com/image/fetch/example.png",
  "body_markdown": "## Key Takeaways\n\nCode review throughput scales with automated static checks...",
  "body_text": "Key Takeaways\n\nCode review throughput scales with automated static checks...",
  "source_api": "substack_archive+rss"
}
```
