"""Unit tests for Wave 13 Actors #29-#30, Track 7 FEFTA/EAR screener #11, and Track 5 14-gate CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track1_apify.jp_fefta_export_control_actor.main import (
    audit_fefta_export_batch,
    evaluate_ear_de_minimis,
)
from tracks.track1_apify.oauth_jwt_oidc_hardening_actor.main import (
    audit_oauth_jwt_batch,
    audit_oauth_jwt_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.export_control_gaihi_screener import (
    audit_export_control_csv,
)


def test_actor29_fefta_export_control_and_ear_de_minimis() -> None:
    general_over = evaluate_ear_de_minimis(
        us_origin_value_jpy=350000,
        total_product_value_jpy=1000000,
        destination_group="general",
    )
    assert general_over["us_ratio_pct"] == 35.0
    assert general_over["subject_to_ear"] is True
    assert general_over["basis"] == "ear_over_25_pct"

    tsu_exempt = evaluate_ear_de_minimis(
        us_origin_value_jpy=800000,
        total_product_value_jpy=1000000,
        destination_group="embargo_e1_d5",
        is_public_oss_encryption=True,
    )
    assert tsu_exempt["subject_to_ear"] is False
    assert tsu_exempt["basis"] == "tsu_742_15b_exempt"

    compliant_text = "\n".join(
        [
            "輸出令別表第1の1〜15項パラメータシートでリスト規制該非判定を実施する。",
            "16項キャッチオール規制（WMD・通常兵器用途・インフォーム要件）を確認する。",
            "経済産業省外国ユーザーリスト・OFAC SDNリスト照合を行う。",
            "外為法第25条みなし輸出特定類型①②③の該当性確認と誓約書取得を行う。",
            "米国EAR ECCN・De Minimis 25%/0%・FDPR再輸出規制を確認する。",
            "9項市販暗号特例及びECCN 5D002 TSU公開暗号要件を確認する。",
            "安全保障貿易管理規程（CP）に基づき輸出管理統括責任者が最終審査・出荷差止権限を持つ。",
            "該非判定書と特定類型誓約書・関連帳簿を7年間保存する。",
        ]
    )
    batch = audit_fefta_export_batch(
        [
            {
                "org_name": "Risky Exporter",
                "us_origin_value_jpy": 420000,
                "total_product_value_jpy": 1200000,
                "policy_text": "該非判定不要、自己承認のみで出荷。特定類型確認不要、判定記録保存なし。",
            },
            {
                "org_name": "Compliant Exporter",
                "us_origin_value_jpy": 100000,
                "total_product_value_jpy": 1000000,
                "policy_text": compliant_text,
            },
        ]
    )
    assert batch[0]["status"] == "fail"
    assert any(f["rule_id"] == "FEFTA-EAR-LICENSE-MISSING" for f in batch[0]["findings"])
    assert batch[1]["score"] == 100
    assert batch[1]["status"] == "pass"


def test_actor30_oauth_jwt_oidc_security_hardening_auditor() -> None:
    weak_config = """
    alg: "none"
    verify_aud: false
    ignoreExpiration: true
    jwt_secret: "local-dev-pass-123"
    response_type: "token"
    pkce: false
    redirect_uri: "https://*.example.com/oauth/callback"
    localStorage.setItem("access_token", tok)
    expiresIn: "24h"
    """
    bad = audit_oauth_jwt_item(weak_config, service_name="bad-sso")
    assert bad["status"] == "high_risk"
    assert set(bad["rule_ids"]) == {
        "OAUTH-JWT-01",
        "OAUTH-JWT-02",
        "OAUTH-JWT-03",
        "OAUTH-OIDC-04",
        "OAUTH-OIDC-05",
        "OAUTH-TOKEN-06",
    }

    hardened_config = """
    jwt.verify(token, jwksPublicKey, {
      algorithms: ["RS256"],
      audience: "api.example.com",
      issuer: "https://auth.example.com/",
    })
    verify_signature: true
    verify_exp: true
    verify_aud: true
    verify_iss: true
    client_secret: "${OIDC_CLIENT_SECRET}"
    response_type: "code"
    code_challenge_method: "S256"
    redirect_uri: "https://app.example.com/oauth/callback"
    accessTokenLifetime: 900
    """
    good = audit_oauth_jwt_batch(
        [{"service_name": "hardened-sso", "config_text": hardened_config}]
    )
    assert good[0]["status"] == "pass"
    assert good[0]["score"] == 100
    assert good[0]["findings_count"] == 0


def test_track7_export_control_gaihi_screener(tmp_path: Path) -> None:
    in_csv = tmp_path / "exports.csv"
    out_csv = tmp_path / "screened.csv"
    out_json = tmp_path / "screened.json"

    compliant_text = (
        "輸出令別表第1 1〜15項パラメータシート 16項キャッチオール WMD確認 "
        "外国ユーザーリスト照合 外為法第25条みなし輸出特定類型①②③誓約書 "
        "米国EAR De Minimis確認 9項市販暗号特例 5D002 TSU "
        "安全保障貿易管理規程 CP 輸出管理統括責任者 出荷差止 帳簿7年間保存"
    )

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "item_name",
                "us_origin_value_jpy",
                "total_product_value_jpy",
                "destination_group",
                "is_public_oss_encryption",
                "has_ear_license_or_exception",
                "foreign_user_list_hit",
                "deemed_export_cat_flagged",
                "retention_years",
                "export_control_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "item_name": "Standard Sensor",
                "us_origin_value_jpy": "100000",
                "total_product_value_jpy": "1000000",
                "destination_group": "general",
                "is_public_oss_encryption": "false",
                "has_ear_license_or_exception": "false",
                "foreign_user_list_hit": "false",
                "deemed_export_cat_flagged": "false",
                "retention_years": "7",
                "export_control_text": compliant_text,
            }
        )
        writer.writerow(
            {
                "item_name": "Blocked Cryo Module",
                "us_origin_value_jpy": "50000",
                "total_product_value_jpy": "1000000",
                "destination_group": "embargo_e1_d5",
                "is_public_oss_encryption": "false",
                "has_ear_license_or_exception": "false",
                "foreign_user_list_hit": "true",
                "deemed_export_cat_flagged": "true",
                "retention_years": "3",
                "export_control_text": "該非判定不要 判定記録保存なし",
            }
        )

    res = audit_export_control_csv(in_csv, out_csv, out_json)
    assert res["network_calls"] == 0
    assert res["total_items"] == 2
    assert res["blocked_items"] == 1
    assert res["ear_subject_items"] == 1
    assert res["rows"][0]["screening_status"] == "approved_non_listed"
    assert res["rows"][1]["screening_status"] == "blocked_prohibited"
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_fourteen_gate_cli_audits_fefta_export_control() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "新規輸出案件確認",
                "invoice_id": "T7000012050002",
                "payee_name": "トウキョウボウエキ",
                "us_origin_value_jpy": "400000",
                "total_product_value_jpy": "1000000",
                "destination_group": "general",
                "export_control_text": "該非判定不要。特定類型確認不要。",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["fefta_export_flagged_rows"] == 1
    assert report["rows"][0]["fefta_export_audit"]["status"] == "fail"
    assert report["rows"][0]["fefta_export_audit"]["ear_result"]["subject_to_ear"] is True


def test_all_30_apify_actor_input_schemas_have_required_descriptions() -> None:
    schema_paths = sorted(Path("tracks/track1_apify").glob("*/.actor/input_schema.json"))
    assert len(schema_paths) >= 30
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

