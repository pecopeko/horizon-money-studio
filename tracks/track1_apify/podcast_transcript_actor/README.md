# Podcast RSS, Host Contacts, Apple Reviews & Transcript Extractor

Extract **podcast host/owner contact emails** (`<itunes:owner>`), show categories, Podcasting 2.0 `<podcast:person>` & `<podcast:funding>` tags, **Apple Podcasts customer reviews**, clean HTML-stripped show notes, chapters, and normalized **Podcasting 2.0 transcripts (`.vtt`, `.srt`, `.json`, `.txt`)** directly from RSS XML and official iTunes APIs.

Built for **zero-CAPTCHA, zero-browser** reliability with strict SSRF IP validation on every RSS, transcript, chapter, and redirect URL.

## Key Features

- **Host Contact & Lead-Gen Show Metadata**:
  - Automatically parses `<itunes:owner>` into `owner_name` and `owner_email` (with `<managingEditor>` email fallback), `<itunes:category>` (including nested subcategories), `<itunes:author>`, `language`, `<podcast:person>` hosts/guests, and `<podcast:funding>` support URLs.
- **Podcasting 2.0 VTT / SRT / JSON / TXT Transcripts**:
  - Prioritizes structured formats (`.json` → `.vtt` → `.srt` → `.txt`), preserves VTT speaker labels (`<v Speaker>`), and outputs uniform timestamped segments (`start_sec`, `end_sec`, `speaker`, `text`) plus a clean `full_transcript` string ready for RAG and LLM summarization.
- **Optional Apple Podcasts Customer Reviews (`includeAppleReviews`)**:
  - Fetches official public Apple Podcasts reviews JSON (`itunes.apple.com/{country}/rss/customerreviews/...`) once per show when an iTunes ID is available, outputting `apple_reviews`, `apple_review_count`, and `apple_average_rating`.
- **Precision Filtering**:
  - `onlyWithTranscripts`: Return only episodes with extracted transcripts.
  - `publishedAfter`: ISO date filter (e.g. `"2026-01-01"`).
  - `keywordFilter`: Case-insensitive filter across episode title, show notes, and transcript text.
- **Hardened XML & SSRF Safety**:
  - Blocks DTD/ENTITY declarations (`<!DOCTYPE`, `<!ENTITY`) against XML billion-laughs attacks.
  - Validates every RSS, transcript, chapter, and redirect hop against loopback, private, link-local, and cloud metadata IPs.

## Fair Split Pricing (Pay-Per-Event)

Pay only for what you actually get:

- **`episode_extracted` (Primary)**: **`$0.002`** per episode record extracted (metadata, host email, show notes, chapters, Apple reviews).
- **`transcript_extracted` (Conditional)**: **`$0.002`** charged **ONLY** when Podcasting 2.0 transcript segments are actually extracted for an episode. Episodes without transcripts are never charged the transcript fee.

## Popular Use Cases

1. **Podcast Guest Booking & Sponsorship Outreach**: Search iTunes niches via `searchQueries` and export `owner_name`, `owner_email`, `categories`, `funding_urls`, and `apple_average_rating`.
2. **AI / RAG Audio Knowledge Bases**: Pull timestamped transcripts (`onlyWithTranscripts: true`) + chapters for podcast search engines and briefing agents.
3. **Brand & Topic Monitoring**: Track mentions via `keywordFilter` + `publishedAfter` across hundreds of RSS feeds without paying for Whisper transcription.

## Input Example

```json
{
  "applePodcastIds": ["1584274529"],
  "rssUrls": ["https://podnews.net/rss"],
  "maxEpisodesPerFeed": 5,
  "country": "US",
  "fetchTranscripts": true,
  "fetchChapters": true,
  "includeTranscriptSegments": true,
  "includeAppleReviews": true,
  "onlyWithTranscripts": false,
  "publishedAfter": "2026-01-01",
  "keywordFilter": ""
}
```

## Output Example

```json
{
  "feed_url": "https://podnews.net/rss",
  "podcast_title": "Podnews Daily",
  "podcast_author": "Podnews",
  "language": "en",
  "owner_name": "James Cridland",
  "owner_email": "editor@podnews.net",
  "categories": ["News", "Tech News", "Technology"],
  "people": [
    {
      "name": "James Cridland",
      "role": "host",
      "group": "cast",
      "href": "https://james.cridland.net/",
      "img": null
    }
  ],
  "funding_urls": ["https://podnews.net/article/support-podnews"],
  "episode_title": "Daily Podcast Industry Briefing",
  "pub_date_iso": "2026-11-19T08:00:00+00:00",
  "transcript_status": "extracted",
  "transcript_format": "vtt",
  "transcript_segment_count": 42,
  "full_transcript": "Welcome to Podnews Daily...",
  "chapters_status": "extracted",
  "chapters": [
    {
      "start_sec": 0.0,
      "title": "Headlines",
      "url": null,
      "img": null
    }
  ],
  "apple_reviews_status": "extracted",
  "apple_review_count": 10,
  "apple_average_rating": 4.9,
  "apple_reviews": [
    {
      "review_id": "1092837465",
      "author": "PodcastListener",
      "rating": 5,
      "title": "Essential daily briefing",
      "content": "Concise, accurate, and always includes full transcripts.",
      "updated_at": "2026-11-12T10:15:00-07:00"
    }
  ]
}
```
