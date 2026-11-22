# Website Tech Stack, Recursive Sitemap & SEO Intelligence Extractor

Fast, zero-browser website intelligence profiler that detects **75+ web technologies** across 7 commercial categories, recursively traverses **`robots.txt` + XML/gzip (`.xml.gz`) sitemap indexes**, and extracts **SEO metadata, Schema.org JSON-LD types, and public contact/social links** — at **$2.00 per 1,000 sites**.

## Why Browserless Tech Stack + Sitemap Profiling?

Browser-heavy tech stack detectors fail on timeouts, burn high proxy/compute budgets, and still miss HTTP header signals (`CF-Ray`, `X-Vercel-Id`, `X-Shopify-Stage`, `Set-Cookie`, `X-Amz-Cf-Id`). This Actor inspects raw HTTP headers, HTML markup, `robots.txt`, and `.xml`/`.xml.gz` sitemaps directly with sub-second latency and zero headless browsers.

## Key Capabilities

### 1. 75+ Technology Signatures Across 7 Categories
- **`framework`**: Next.js, Nuxt, Astro, Remix, Gatsby, React, Vue, Svelte, Angular, SolidJS, Qwik, Tailwind CSS, Bootstrap, jQuery
- **`cms_ecommerce`**: Shopify, WordPress, WooCommerce, Webflow, Wix, Squarespace, Ghost, Contentful, Sanity, Framer, BigCommerce, Magento
- **`analytics`**: Google Analytics 4, Google Tag Manager, Meta Pixel, Segment, PostHog, Mixpanel, Amplitude, Sentry, Datadog, Hotjar, Microsoft Clarity, Plausible, Fathom Analytics, FullStory
- **`payments`**: Stripe, PayPal, Paddle, Adyen, Klarna, Shop Pay, Chargebee, Lemon Squeezy
- **`cdn_hosting`**: Cloudflare, Vercel, Netlify, AWS CloudFront, Fastly, Akamai, Render, Fly.io, GitHub Pages, Google Cloud CDN, Nginx, Apache
- **`support_crm`**: Intercom, Zendesk, HubSpot, Crisp, Drift, Freshworks, Help Scout, Marketo, Klaviyo
- **`auth_infra`**: reCAPTCHA, hCaptcha, Cloudflare Turnstile, Clerk, Auth0, Supabase, Firebase, Algolia, LaunchDarkly, OneTrust

### 2. Recursive `robots.txt` + XML / `.xml.gz` Sitemap Extractor
- Parses all `Sitemap:` directives from `/robots.txt` (gracefully falling back to `/sitemap.xml` and `/sitemap_index.xml`).
- Transparently decompresses `.xml.gz` sitemaps with a 15 MB gzip-bomb safety cap and XML DTD/ENTITY injection guard.
- Recursively follows `<sitemapindex>` child sitemaps (up to 5 child sitemaps when `followSitemapIndexes: true`) and reports `sitemap_count`, `discovered_url_count`, `latest_lastmod`, and `sample_urls`.

### 3. SEO, JSON-LD & Public Contacts
- Extracts `title`, `meta_description`, `canonical_url`, `og_title`, `jsonld_types`, `language`, public `mailto:` links (`public_emails`), and official `social_links` (`github`, `x_twitter`, `linkedin`, `youtube`) from HTML and JSON-LD `sameAs`.

### 4. Security & Batch Fault Isolation
- Strict SSRF IP/hostname validation blocking localhost, private, loopback, link-local, and cloud metadata IPs — re-validated on **every redirect hop (up to 3 hops)** and every discovered sitemap URL.
- Automatic `429`/`503` `Retry-After` exponential backoff and per-site fault isolation (failed sites emit structured error rows and are never charged).

## Pricing (Pay-Per-Event)

- **`site_profiled`**: **`$0.002`** per profiled website (`$2.00 / 1,000 sites`). Failed site error records are never charged.

## Input Example

```json
{
  "urls": [
    "https://stripe.com",
    "vercel.com"
  ],
  "maxSitemapUrls": 200,
  "followSitemapIndexes": true,
  "extractPublicContacts": true,
  "requestDelayMs": 250
}
```

## Output Example

```json
{
  "record_type": "site_profile",
  "status": "ok",
  "input_url": "vercel.com",
  "final_url": "https://vercel.com",
  "domain": "vercel.com",
  "http_status": 200,
  "technologies": ["Next.js", "React", "Vercel"],
  "tech_count": 3,
  "tech_by_category": {
    "framework": ["Next.js", "React"],
    "cms_ecommerce": [],
    "analytics": [],
    "payments": [],
    "cdn_hosting": ["Vercel"],
    "support_crm": [],
    "auth_infra": []
  },
  "robots_txt_found": true,
  "sitemap_count": 1,
  "discovered_url_count": 420,
  "latest_lastmod": "2026-11-18T00:00:00Z",
  "sample_urls": ["https://vercel.com/", "https://vercel.com/pricing"],
  "title": "Vercel: Build and deploy the best web experiences",
  "meta_description": "Vercel gives developers the frameworks, workflows, and infrastructure...",
  "canonical_url": "https://vercel.com/",
  "og_title": "Vercel: Build and deploy the best web experiences",
  "jsonld_types": ["Organization", "WebSite"],
  "language": "en",
  "public_emails": [],
  "social_links": {
    "github": ["https://github.com/vercel"],
    "x_twitter": ["https://x.com/vercel"],
    "linkedin": ["https://linkedin.com/company/vercel"],
    "youtube": ["https://youtube.com/@VercelHQ"]
  }
}
```
