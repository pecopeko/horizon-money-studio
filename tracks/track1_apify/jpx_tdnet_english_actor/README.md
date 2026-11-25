# Tokyo Stock Exchange (JPX / TDnet) Filings, Quotes & Microstructure English Feed

Built for **overseas quantitative hedge funds, global equity researchers, M&A analysts, and AI financial agents** that need real-time Japanese corporate announcements and Tokyo Stock Exchange (`JPX` / `TSE`) market microstructure rules normalized into **structured English JSON** — with zero Japanese-language parsing headaches and zero external API keys required.

## What You Get in Every Run
1. **Real-Time TDnet Timely Corporate Disclosures -> Structured English Catalysts**:
   - Market-wide across **TSE Prime, Standard, and Growth** (`tickers: []`) or filtered to any portfolio of 4-character Japanese stock codes (`["7203", "9984", "8035", "130A"]`, supporting post-2024 alphanumeric codes).
   - Deterministic institutional classification (`EARNINGS_SUMMARY`, `GUIDANCE_REVISION`, `SHARE_BUYBACK`, `DIVIDEND_REVISION`, `TENDER_OFFER_MA`, `GOVERNANCE_CAPITAL_EFFICIENCY`, `MONTHLY_KPI`, `STOCK_SPLIT_OFFERING`) + direct official `release.tdnet.info` PDF and XBRL links.
2. **Live `.T` JPY Quotes + Exact TSE Arrowhead Microstructure**:
   - Dual tick-size table (`TOPIX100/500` sub-yen `0.1 / 0.5 JPY` vs Standard TSE tick bands).
   - Exact **34-tier Daily Price Limits (`S-taka` Stop-High & `S-yasu` Stop-Low)** tick-aligned to the valid JPX order grid, plus distance-to-limit (`%`) and intraday limit-touch flags.
   - Live `Asia/Tokyo` session phase including the post-Nov-5-2024 **`15:25–15:30` Pre-Closing Preparation** and **`15:30` Closing Itayose Auction**.
3. **Official Japan Exchange Group (`JPX`) & Bank of Japan (`BOJ`) English Macro Announcements**:
   - Direct official English policy, monetary statement, and exchange rule updates in the same structured dataset.

## Transparent Pay-Per-Event Pricing
- **`$0.005` per extracted record** (`$5.00 per 1,000 records`), zero monthly subscription.
