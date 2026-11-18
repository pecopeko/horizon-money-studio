# Japan Electronic Books Preservation Act (Dencho-ho) Filename & Ledger Validator

Apify Pay-Per-Event (`record_validated` @ ``$0.001``) Actor that normalizes messy Japanese invoice/receipt strings (with Gregorian, Wareki `令和`/`平成`/`R`/`H`, and full-width numerals) into Art.7 search-compliant `YYYYMMDD_Partner_Amount.pdf` filenames and validates NTA Modulo-9 Qualified Invoice `T+13` IDs.
