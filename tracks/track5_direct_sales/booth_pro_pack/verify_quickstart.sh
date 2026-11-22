#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_DIR="${ROOT_DIR}/_quickstart_out"
mkdir -p "${OUT_DIR}"

echo "[1/3] Zengin 120-byte Shift-JIS (CP932) conversion test..."
PYTHONPATH="${ROOT_DIR}/src:${ROOT_DIR}" python3 \
  "${ROOT_DIR}/tracks/track7_freelance_kit/deliverables/dirty_csv_to_zengin120.py" \
  --bank-preset mufg \
  --transfer-type 21 \
  "${ROOT_DIR}/tracks/track5_direct_sales/booth_pro_pack/samples/sample_zengin_dirty.csv" \
  "${OUT_DIR}/zengin_cp932.txt"

echo "[2/3] 2026 Invoice 50% & Shiharai-Chosho aggregation test..."
PYTHONPATH="${ROOT_DIR}/src:${ROOT_DIR}" python3 \
  "${ROOT_DIR}/tracks/track7_freelance_kit/deliverables/shiharai_chosho_csv_aggregator.py" \
  --input "${ROOT_DIR}/tracks/track5_direct_sales/booth_pro_pack/samples/sample_shiharai_2026.csv" \
  --out "${OUT_DIR}/shiharai_summary.csv" \
  --period post_2026_10

echo "[3/3] Offline PII / Invoice batch CLI test..."
PYTHONPATH="${ROOT_DIR}/src:${ROOT_DIR}" python3 \
  "${ROOT_DIR}/tracks/track5_direct_sales/booth_pro_pack/batch_compliance_suite_cli.py" \
  --input "${ROOT_DIR}/tracks/track5_direct_sales/booth_pro_pack/samples/sample_compliance_batch.csv" \
  --json-out "${OUT_DIR}/compliance_report.json" \
  --md-out "${OUT_DIR}/compliance_certificate.md"

echo "OK: All 3 offline workflows succeeded. Outputs saved in ${OUT_DIR}"
