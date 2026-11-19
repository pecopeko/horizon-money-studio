"""Unit tests for Wave 19 Actors #41-#42, Track 7 Lease CLI #17, and Track 5 20-gate CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track1_apify.iac_github_env_secret_entropy_actor.main import (
    audit_env_secret_config_batch,
    audit_env_secret_config_item,
)
from tracks.track1_apify.jp_new_lease_accounting_asbj34_actor.main import (
    audit_asbj34_lease_batch,
    evaluate_asbj34_lease_pv,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.asbj34_new_lease_auditor import (
    audit_asbj34_lease_csv,
)


def test_actor41_asbj34_new_lease_accounting_auditor() -> None:
    on_bal = evaluate_asbj34_lease_pv(
        monthly_lease_jpy=1_200_000,
        lease_term_months=36,
        annual_discount_rate_pct=1.8,
        underlying_new_value_jpy=180_000_000,
        has_purchase_option=False,
        controls_identified_asset=True,
        already_on_balance_sheet=False,
    )
    assert on_bal["is_short_term_exempt"] is False
    assert on_bal["is_low_value_exempt"] is False
    assert on_bal["on_balance_required"] is True
    assert on_bal["off_balance_omission_risk"] is True
    assert on_bal["total_undiscounted_jpy"] == 43_200_000.0
    assert 41_900_000.0 < on_bal["lease_liability_pv_jpy"] < 42_200_000.0
    assert 13_900_000.0 < on_bal["year1_depreciation_jpy"] < 14_100_000.0

    short_term = evaluate_asbj34_lease_pv(
        monthly_lease_jpy=500_000,
        lease_term_months=12,
        underlying_new_value_jpy=20_000_000,
        has_purchase_option=False,
    )
    assert short_term["is_short_term_exempt"] is True
    assert short_term["on_balance_required"] is False

    low_val = evaluate_asbj34_lease_pv(
        monthly_lease_jpy=45_000,
        lease_term_months=36,
        underlying_new_value_jpy=2_500_000,
    )
    assert low_val["is_low_value_exempt"] is True
    assert low_val["on_balance_required"] is False

    compliant_text = "\n".join(
        [
            "特定資産の識別判定により使用権資産を計上する。",
            "解約不能期間と延長オプションを確認してリース期間を決定し追加借入利子率(IBR)で現在価値を算定する。",
            "短期リース（12か月以内・購入オプションなし）および少額リース（300万円以下）を契約単位判定する。",
            "倉庫専用の組込リース識別を実施し、保守料区分など非リース構成部分を独立価格配分する。",
            "企業会計基準第34号に基づき減価償却・加重平均割引率・満期分析を注記開示し計算根拠保存を徹底する。",
        ]
    )

    batch = audit_asbj34_lease_batch(
        [
            {
                "contract_name": "Unrecognized HQ Floor",
                "monthly_lease_jpy": 1_200_000,
                "lease_term_months": 36,
                "annual_discount_rate_pct": 1.8,
                "underlying_new_value_jpy": 180_000_000,
                "already_on_balance_sheet": False,
                "contract_text": "使用権資産計上せず全額オフバランス賃貸費用処理し注記省略とする。",
            },
            {
                "contract_name": "Recognized HQ Floor",
                "monthly_lease_jpy": 1_200_000,
                "lease_term_months": 36,
                "annual_discount_rate_pct": 1.8,
                "underlying_new_value_jpy": 180_000_000,
                "already_on_balance_sheet": True,
                "contract_text": compliant_text,
            },
        ]
    )
    assert batch[0]["status"] == "fail"
    assert "ASBJ34-OFF-BALANCE-OMISSION" in {f["rule_id"] for f in batch[0]["findings"]}
    assert batch[1]["score"] == 100
    assert batch[1]["status"] == "pass"


def test_actor42_env_secret_key_leak_entropy_auditor() -> None:
    aws_key = "AKIA" + "0000000000000000"
    vcs_tok = "ghp_" + "9" * 24
    pay_tok = "sk_live_" + "8" * 20
    unsafe_env = "\n".join(
        [
            f"AWS_ACCESS_KEY_ID={aws_key}",
            f"GITHUB_TOKEN={vcs_tok}",
            f"STRIPE_KEY={pay_tok}",
            "DATABASE_URL=postgres://admin:demoPass@db.internal:5432/prod",
            "JWT_SECRET=changeme",
            "NODE_TLS_REJECT_UNAUTHORIZED=0",
        ]
    )
    bad = audit_env_secret_config_item(unsafe_env, target_name=".env.prod")
    assert bad["status"] == "high_risk"
    assert set(bad["rule_ids"]) == {
        "SEC-CLOUD-01",
        "SEC-VCS-02",
        "SEC-PAY-03",
        "SEC-DB-04",
        "SEC-JWT-05",
        "SEC-ENV-06",
    }

    safe_env = "\n".join(
        [
            "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}",
            "GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}",
            "DATABASE_HOST=db.internal",
            "JWT_SECRET=${KMS_JWT_SIGNING_KEY}",
            "DEBUG=false",
            "CORS_ORIGIN=https://app.example.com",
        ]
    )
    good = audit_env_secret_config_batch(
        [{"target_name": ".env.template", "config_text": safe_env}]
    )
    assert good[0]["status"] == "pass"
    assert good[0]["score"] == 100
    assert good[0]["findings_count"] == 0


def test_track7_asbj34_new_lease_auditor(tmp_path: Path) -> None:
    in_csv = tmp_path / "leases.csv"
    out_csv = tmp_path / "audited.csv"
    out_json = tmp_path / "audited.json"

    compliant_text = (
        "特定資産 識別判定 使用権資産 リース期間 解約不能期間 延長オプション 追加借入利子率 現在価値 "
        "短期リース 購入オプションなし 少額リース 300万円以下 組込リース 倉庫専用 保守料区分 企業会計基準第34号 注記開示 計算根拠保存"
    )

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contract_name",
                "monthly_lease_jpy",
                "lease_term_months",
                "annual_discount_rate_pct",
                "underlying_new_value_jpy",
                "has_purchase_option",
                "controls_identified_asset",
                "already_on_balance_sheet",
                "lease_contract_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "contract_name": "Clean Office A",
                "monthly_lease_jpy": "1200000",
                "lease_term_months": "36",
                "annual_discount_rate_pct": "1.8",
                "underlying_new_value_jpy": "180000000",
                "has_purchase_option": "false",
                "controls_identified_asset": "true",
                "already_on_balance_sheet": "true",
                "lease_contract_text": compliant_text,
            }
        )
        writer.writerow(
            {
                "contract_name": "OffBal Logistics B",
                "monthly_lease_jpy": "800000",
                "lease_term_months": "48",
                "annual_discount_rate_pct": "2.0",
                "underlying_new_value_jpy": "90000000",
                "has_purchase_option": "false",
                "controls_identified_asset": "true",
                "already_on_balance_sheet": "false",
                "lease_contract_text": "使用権資産計上せずオフバランス賃貸費用処理し注記省略とする。",
            }
        )

    res = audit_asbj34_lease_csv(in_csv, out_csv, out_json)
    assert res["network_calls"] == 0
    assert res["total_contracts"] == 2
    assert res["on_balance_required_contracts"] == 2
    assert res["off_balance_omission_contracts"] == 1
    assert res["total_on_balance_pv_jpy"] > 78_000_000.0
    assert res["rows"][0]["audit_status"] == "pass"
    assert res["rows"][1]["audit_status"] == "fail"
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_twenty_gate_cli_audits_asbj34_lease() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "新規拠点オフィス定期賃貸借監査",
                "invoice_id": "T7000012050002",
                "payee_name": "マルノウチショウジ",
                "monthly_lease_jpy": "1200000",
                "lease_term_months": "36",
                "annual_discount_rate_pct": "1.8",
                "underlying_new_value_jpy": "180000000",
                "already_on_balance_sheet": "false",
                "lease_contract_text": "使用権資産計上せず全額オフバランス賃貸費用処理。",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["lease_flagged_rows"] == 1
    assert report["rows"][0]["lease_audit"]["status"] == "fail"
    assert report["rows"][0]["lease_audit"]["metrics"]["off_balance_omission_risk"] is True
    assert report["rows"][0]["lease_audit"]["metrics"]["lease_liability_pv_jpy"] > 41_900_000.0


def test_all_42_apify_actor_input_schemas_have_required_descriptions() -> None:
    schema_paths = sorted(Path("tracks/track1_apify").glob("*/.actor/input_schema.json"))
    assert len(schema_paths) >= 42
    for schema_path in schema_paths:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert str(data.get("title") or "").strip(), schema_path
        assert data.get("type") == "object", schema_path
        assert data.get("schemaVersion") == 1, schema_path
        props = data.get("properties")
        assert isinstance(props, dict) and props, schema_path
        for key, prop in props.items():
            assert isinstance(prop, dict), f"{schema_path}:{key}"
            assert str(prop.get("title") or "").strip(), f"{schema_path}:{key} missing title"
            assert str(prop.get("type") or "").strip(), f"{schema_path}:{key} missing type"
            assert str(prop.get("description") or "").strip(), f"{schema_path}:{key} missing description"
            if prop.get("type") in {"array", "object"}:
                assert str(prop.get("editor") or "").strip(), f"{schema_path}:{key} missing editor"
