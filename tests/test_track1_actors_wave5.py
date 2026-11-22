"""Comprehensive offline unit tests for Wave 5 Actors (#13-#14) and upgraded Pro CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from tracks.track1_apify.jp_denchoho_ledger_actor.main import (
    parse_japanese_or_iso_date,
    validate_denchoho_batch,
)
from tracks.track1_apify.oss_sbom_license_actor.main import audit_manifest_batch
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import audit_csv_file


def test_jp_denchoho_ledger_actor_normalizes_wareki_tnumber_and_zero_yen() -> None:
    assert parse_japanese_or_iso_date("令和8年11月19日")[0] == "20261119"
    assert parse_japanese_or_iso_date("令和元年5月1日")[0] == "20190501"
    assert parse_japanese_or_iso_date("R6.4.5")[0] == "20240405"
    assert parse_japanese_or_iso_date("２０２６／１１／１９")[0] == "20261119"

    res = validate_denchoho_batch(
        [
            {"raw_text": "令和8年11月19日 株式会社サンプル:商事 請求書 110,000円 T7000012050002.pdf"},
            {"raw_text": "2026-10-31 さくらITサービス ０円"},
            {"raw_text": "領収書_田中商店_8800円.pdf"},
        ]
    )
    assert res[0]["compliant"] is True
    assert res[0]["date"] == "20261119"
    assert res[0]["amount_yen"] == 110000
    assert res[0]["invoice_id"] == "T7000012050002"
    assert res[0]["invoice_id_valid"] is True
    assert res[0]["standardized_filename"] == "20261119_株式会社サンプル商事_110000円.pdf"

    assert res[1]["compliant"] is True
    assert res[1]["amount_yen"] == 0

    assert res[2]["compliant"] is False
    assert res[2]["missing_keys"] == ["date"]


def test_oss_sbom_license_actor_flags_copyleft_and_unpinned_dependencies() -> None:
    res = audit_manifest_batch(
        [
            {
                "repo_name": "acme/risky-saas",
                "package_json": {
                    "dependencies": {
                        "express": "^4.19.2",
                        "git-dep": "git+https://github.com/org/repo.git",
                        "wild-pkg": "*",
                    }
                },
                "packages": [
                    {"name": "express", "license": "MIT"},
                    {"name": "redis-module", "license": "AGPL-3.0-only"},
                    {"name": "opaque-pkg", "license": ""},
                ],
            },
            {
                "repo_name": "acme/clean-lib",
                "requirements_txt": "httpx==0.27.2\npydantic==2.9.2\n",
                "packages": [
                    {"name": "httpx", "license": "BSD-3-Clause"},
                    {"name": "pydantic", "license": "MIT"},
                ],
            },
        ]
    )
    assert res[0]["procurement_status"] == "blocked_copyleft_or_high_risk"
    assert "redis-module" in res[0]["strong_copyleft_packages"]
    assert "opaque-pkg" in res[0]["unknown_license_packages"]
    assert "SUPPLY-UNPINNED-SPEC" in res[0]["rule_ids"]
    assert "LICENSE-STRONG-COPYLEFT" in res[0]["rule_ids"]

    assert res[1]["procurement_status"] == "procurement_ready"
    assert res[1]["compliance_score"] == 100
    assert res[1]["findings_count"] == 0


def test_upgraded_booth_cli_supports_contract_tokusho_and_dencho_columns(tmp_path: Path) -> None:
    in_csv = tmp_path / "pro_suite.csv"
    with in_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "text",
                "invoice_id",
                "payee_name",
                "contract_text",
                "tokusho_text",
                "checkout_text",
                "dencho_record",
            ]
        )
        w.writerow(
            [
                "通常文書",
                "T7000012050002",
                "株式会社ホライゾン",
                "支払期日は納品後90日とする。乙は甲に対し損害賠償の全責任を負う。",
                "販売業者：A商店 返金：いかなる理由であっても一切返金いたしません。",
                "初回500円でお試し！",
                "領収書_田中商店_8800円.pdf",
            ]
        )

    rep = audit_csv_file(in_csv, tmp_path / "pro.json", tmp_path / "pro.md")
    assert rep["keiyaku_flagged_rows"] == 1
    assert rep["tokusho_flagged_rows"] == 1
    assert rep["dencho_noncompliant_rows"] == 1
    assert "keiyaku_audit" in rep["rows"][0]
    assert "tokusho_audit" in rep["rows"][0]
    assert "dencho_check" in rep["rows"][0]
