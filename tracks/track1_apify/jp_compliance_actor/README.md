# Japan LLM Compliance, Check-Digit PII Redactor & Injection Guard

Reversibly mask check-digit-verified Japanese business & personal identifiers before sending documents to LLMs or external AI agents, normalize noisy Japanese business text, and screen multilingual inputs for prompt injection — with zero external API keys, zero browser overhead, and Pay-Per-Event pricing.

## Why Use This Actor?

Regex-only PII scrubbers trigger costly false positives on random 12- and 13-digit numbers (order IDs, timestamps, SKU numbers). This Actor validates mathematical check digits before redacting so downstream analytics and LLM workflows stay accurate:

- **Qualified Invoice IDs (`T` + 13 digits)** — Validated using Japan's National Tax Agency (NTA) modulo-9 check-digit algorithm, including full-width (`Ｔ７００００１２０５０００２`) and hyphenated variants.
- **Corporate Numbers (`法人番号`, 13 digits)** — Validated using the NTA modulo-9 check-digit algorithm.
- **MyNumber (`個人番号`, 12 digits)** — Validated using Japan's MIC modulo-11 check-digit formula.
- **Payment Cards (14–19 digits)** — Validated with the standard Luhn checksum.
- **Japanese Phone Numbers, Postal Codes (`〒XXX-XXXX`), and Email Addresses**.
- **Reversible Vault Mapping** — Returns deterministic placeholders (`[INVOICE_ID_1]`, `[CORPORATE_ID_1]`, `[MYNUMBER_1]`) plus `vault_map` so you can restore original entities after receiving an LLM response.
- **Japanese & English Prompt-Injection Pre-Filter** — Detects override attempts, system-prompt exfiltration, jailbreak modes, role-delimiter spoofing, suspicious Base64 blobs, and hidden zero-width/bidi Unicode control characters (`injection_risk_score` in `0.0`–`1.0` + `injection_flags`).

## Pricing (Pay-Per-Event)

- **`document_processed`**: `$0.002` per text document scanned, normalized, redacted, and screened.

## Input Schema

| Field | Type | Default | Description |
|---|---|---|---|
| `texts` | `string[]` | Sample Japanese invoice string | List of Japanese or multilingual documents to screen and redact (required). |
| `normalizeText` | `boolean` | `false` | Apply NFKC width normalization while keeping katakana full-width and stripping hidden zero-width/bidi characters before redaction. |
| `includeVaultMap` | `boolean` | `true` | Include `vault_map` mapping placeholders back to original values. |

### Example Input

```json
{
  "texts": [
    "請求書番号 Ｔ７００００１２０５０００２ / 個人番号 1234-5678-9018 / 連絡先: 03-1234-5678 / test@example.co.jp"
  ],
  "normalizeText": true,
  "includeVaultMap": true
}
```

## Example Output

```json
{
  "index": 0,
  "redacted_text": "請求書番号 [INVOICE_ID_1] / 個人番号 [MYNUMBER_1] / 連絡先: [JP_PHONE_1] / [EMAIL_1]",
  "findings": [
    {
      "kind": "INVOICE_ID",
      "placeholder": "[INVOICE_ID_1]",
      "start": 6,
      "end": 20,
      "verified_check_digit": true
    }
  ],
  "injection_risk_score": 0.0,
  "injection_flags": [],
  "vault_map": {
    "[INVOICE_ID_1]": "T7000012050002",
    "[MYNUMBER_1]": "1234-5678-9018",
    "[JP_PHONE_1]": "03-1234-5678",
    "[EMAIL_1]": "test@example.co.jp"
  }
}
```

## Use Cases

- Pre-screening Japanese invoices, contracts, CSV exports, and support tickets before calling OpenAI, Anthropic, or Gemini APIs.
- Building compliant RAG ingestion pipelines for Japanese enterprises (`インボイス制度` / APPI workflows).
- Guarding autonomous AI agents against bilingual Japanese/English prompt-injection payloads.
