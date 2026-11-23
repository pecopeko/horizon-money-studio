# Japan 2026 (Reiwa 8) Year-End Tax Adjustment & Payroll CSV Auditor (`jp-nenmatsu-2026-tax-payroll-auditor`)

Fast, deterministic statutory batch auditor for **Japan Reiwa 8 (2026) Year-End Tax Adjustment (`令和8年分 年末調整`, effective December 1, 2026)** — engineered for Japanese HR, payroll SaaS pipelines, and accounting BPO workflows.

## Statutory Rules Verified (`nta.go.jp`)

- **Employment Income Deduction (`No.1410` / `所得税法別表第五` / `措法29条の4`)**: `740,000 JPY` minimum deduction, exact `2,191,000–2,199,999 JPY` transitional notches (`1,451,000 / 1,453,000 / 1,456,000 JPY`), and `4,000 JPY` bracket steps under `6,600,000 JPY`.
- **Basic Deduction (`No.1199` / `措法41条の16の2`)**: `1,040,000 JPY` up to `4,890,000 JPY` total income, `670,000 JPY` (`4,890,001–6,550,000 JPY`), `620,000 JPY` (`6,550,001–23,500,000 JPY`).
- **Dependent & Spouse Thresholds (`No.1180` / `No.1191` / `No.1195`)**: `620,000 JPY` total income (`1,360,000 JPY` salary) boundary; Special Spouse Deduction up to `1,330,000 JPY` (`2,070,000 JPY` salary).
- **9-Step Special Relative Deduction (`特定親族特別控除`, `No.1177`)**: Exact 9-step deduction schedule (`630k → 610k → 510k → 410k → 310k → 210k → 110k → 60k → 30k JPY`) for ages 19–22 earning `1,360,001–1,970,000 JPY`.

## Pricing (`PAY_PER_EVENT`)

- **`employee_audited` (`$0.002` / employee = `$2.00` per 1,000 employees)**: Charged only for valid audited employee records. Malformed or unparseable rows are never charged.

## Interactive Zero-Network Web App

- https://pecopeko.github.io/nenmatsu-2026-csv-auditor/

Apache-2.0 · Crafted by peco
