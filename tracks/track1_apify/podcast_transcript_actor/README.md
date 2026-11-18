# Podcast RSS, Show Notes, Chapters & Transcript Extractor

Extract clean episode metadata, HTML-stripped show notes, audio enclosure URLs, Podcasting 2.0 JSON chapters, and normalized timestamped transcripts (`.srt`, `.vtt`, `.json`, `.txt`) from any podcast RSS feed — or discover feeds automatically by Apple Podcasts ID or iTunes Search query.

Built for **zero-CAPTCHA, zero-browser** reliability: runs in pure Python over public iTunes Lookup/Search APIs and direct RSS XML feeds without brittle headless browser scrapers.

## Key Features

- **Flexible Feed Resolution**:
  - **Apple Podcasts IDs or URLs** (`applePodcastIds`): Resolves numeric IDs (e.g., `1584274529`) or full `podcasts.apple.com` URLs via `itunes.apple.com/lookup`.
  - **iTunes Search Queries** (`searchQueries`): Finds matching podcast feeds via `itunes.apple.com/search`.
  - **Direct RSS URLs** (`rssUrls`): Parses any HTTP/HTTPS RSS XML feed directly.
- **Podcasting 2.0 `<podcast:transcript>` Support**:
  - Supports multiple `<podcast:transcript>` formats (`.json`, `.vtt`, `.srt`, `.txt`), prioritizing structured formats first and falling back cleanly if a host fails.
  - Normalizes every format into uniform timestamped segments (`start_sec`, `end_sec`, `speaker`, `text`) plus a clean `full_transcript` string for RAG, summarization, and LLM pipelines.
- **Podcasting 2.0 `<podcast:chapters>` Support**:
  - Fetches and normalizes JSON chapters (`start_sec`, `title`, `url`, `img`).
- **Clean Show Notes & Safe XML Parsing**:
  - Strips HTML tags from `content:encoded` / `description` / `itunes:summary` into readable plain text.
  - Rejects DTD/ENTITY declarations (`<!DOCTYPE`, `<!ENTITY`) to guard against XML billion-laughs attacks.
- **Honest Provenance**:
  - Reports explicit `transcript_status` (`extracted`, `not_provided_in_rss`, `fetch_failed`, or `skipped_by_config`) — never fabricates transcripts when an episode lacks one.

## Pricing (Pay-Per-Event)

- **`episode_extracted`**: `$0.004` per episode record pushed to the dataset.

## Input Schema

| Field | Type | Default | Description |
|---|---|---|---|
| `applePodcastIds` | `string[]` | `["1584274529"]` (prefill) | Apple Podcasts IDs or URLs to resolve via iTunes Lookup. |
| `searchQueries` | `string[]` | `[]` | Search queries resolved to RSS feeds via iTunes Search. |
| `rssUrls` | `string[]` | `[]` | Direct podcast RSS feed URLs. |
| `maxEpisodesPerFeed` | `integer` | `10` | Maximum newest episodes extracted per feed (`1`–`500`). |
| `searchLimitPerQuery` | `integer` | `3` | Maximum podcast feeds resolved per search query (`1`–`25`). |
| `country` | `string` | `"US"` | Two-letter iTunes Store country code (`US`, `JP`, `GB`, etc.). |
| `fetchTranscripts` | `boolean` | `true` | Download and normalize `<podcast:transcript>` files. |
| `fetchChapters` | `boolean` | `true` | Download and normalize `<podcast:chapters>` JSON files. |
| `includeTranscriptSegments` | `boolean` | `true` | Include timestamped `transcript_segments` array in output. |

### Example Input

```json
{
  "applePodcastIds": ["1584274529"],
  "maxEpisodesPerFeed": 2,
  "fetchTranscripts": true,
  "fetchChapters": true,
  "includeTranscriptSegments": true
}
```

## Example Output

```json
{
  "feed_url": "https://feeds.podcastindex.org/pc20.xml",
  "podcast_title": "Podcasting 2.0",
  "episode_title": "Episode 278: \"1 Billion Tokens!\"",
  "pub_date_iso": "2026-11-13T20:38:43+00:00",
  "audio": {
    "url": "https://mp3s.nashownotes.com/PC20-278-2026-11-13-Final.mp3",
    "type": "audio/mpeg",
    "length_bytes": 123456789
  },
  "transcript_status": "extracted",
  "transcript_format": "srt",
  "transcript_url": "https://mp3s.nashownotes.com/PC20-278-Captions.srt",
  "transcript_segment_count": 1420,
  "full_transcript": "Podcasting 2.0 for November 13, 2026, episode 278...",
  "transcript_segments": [
    {
      "start_sec": 0.5,
      "end_sec": 6.349,
      "speaker": null,
      "text": "Podcasting 2.0 for November 13, 2026, episode 278, 1 Billion"
    }
  ],
  "chapters_status": "extracted",
  "chapters": [
    {
      "start_sec": 0.0,
      "title": "1 Billion Tokens! Welcome to the Boardroom",
      "url": null,
      "img": null
    }
  ]
}
```
