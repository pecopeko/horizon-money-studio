# Japan METI Supply Chain Security & SPF/DMARC Auditor (`jp-meti-supplychain-security-auditor`)

Deterministic Pay-Per-Event (`checksheet_audited` @ `$0.004`) auditor scoring Japanese vendor security checksheets against:
- **METI 2026 Supply Chain Security Evaluation System (`★3` / `★4`)**
- **PPC Personal Information Breach Reporting SLA** (initial notice `3–5` days, final report `30/60` days)
- **Unfair Competition Prevention Act Trade Secret 3 Requirements**
- **SPF (`-all` vs `+all`, RFC 7208 `<= 10` DNS lookup cap) & DMARC (`p=reject`/`quarantine`/`none`, `rua=`)**
