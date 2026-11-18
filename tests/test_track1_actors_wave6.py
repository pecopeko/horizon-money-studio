"""Unit tests for Wave 6 Track 1 Actors #15-#16, Track 7 deliverable #4, and 7-gate Track 5 CLI."""

from __future__ import annotations

from pathlib import Path

from tracks.track1_apify.jp_appi_gaibusoshin_actor.main import (
    audit_appi_policy_batch,
    audit_appi_policy_item,
)
from tracks.track1_apify.openapi_mcp_readiness_actor.main import (
    audit_openapi_mcp_batch,
    audit_openapi_mcp_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.dencho_folder_renamer_indexer import (
    normalize_and_index_invoice_folder,
)


def test_actor15_appi_and_gaibusoshin_flags_and_passes() -> None:
    weak = audit_appi_policy_item(
        "当社は情報を適切に管理します。",
        script_tags_text='<script src="https://www.googletagmanager.com/gtag/js?id=G-1"></script><script src="https://js.stripe.com/v3/"></script>',
    )
    assert weak["status"] == "high_risk"
    assert "APPI-CROSSBORDER-28" in weak["rule_ids"]
    assert "TBA-GAIBUSOSHIN-27-12" in weak["rule_ids"]
    assert len(weak["unmentioned_vendors"]) == 2

    compliant_policy = """
    個人情報取扱事業者：株式会社鶴見クラウド
    所在地：東京都港区芝浦3-1-1 / 代表者：代表取締役 佐藤 誠一
    利用目的：本サービスの提供、本人確認および決済処理のために利用します。
    安全管理措置：TLS暗号化通信とアクセス制限および委託先の監督を実施しています。
    第三者提供：法令に基づく場合を除き同意なく第三者提供を行いません。
    外国にある第三者への提供（第28条）：米国所在のGoogle Analytics 4およびStripeを利用します。
    外部送信規律（第27条の12）：Google Analytics 4とStripeへCookie識別子とIPアドレスを送信します。オプトアウトで拒否できます。
    開示・訂正・利用停止窓口：privacy@tsurumi-cloud.jp
    """
    batch_res = audit_appi_policy_batch(
        [
            {
                "policy_text": compliant_policy,
                "script_tags_text": '<script src="https://www.googletagmanager.com/gtag/js?id=G-1"></script><script src="https://js.stripe.com/v3/"></script>',
            }
        ]
    )
    assert len(batch_res) == 1
    assert batch_res[0]["compliance_score"] == 100
    assert batch_res[0]["status"] == "pass"


def test_actor16_openapi_and_mcp_readiness_auditor() -> None:
    good_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Ledger API", "description": "Read and validate corporate ledgers."},
        "servers": [{"url": "https://api.ledger-ops.jp"}],
        "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}},
        "paths": {
            "/v1/ledgers": {
                "post": {
                    "operationId": "createLedgerEntry",
                    "summary": "Create a verified double-entry ledger record",
                    "parameters": [
                        {
                            "name": "tenant_id",
                            "in": "header",
                            "description": "Target corporate tenant identifier",
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"amount": {"type": "integer"}},
                                }
                            }
                        }
                    },
                }
            }
        },
    }
    ok_res = audit_openapi_mcp_item(good_openapi)
    assert ok_res["readiness_status"] == "agent_ready"
    assert ok_res["readiness_score"] == 100

    bad_mcp = {
        "tools": [
            {
                "name": "do_thing",
                "description": "short",
                "inputSchema": {
                    "type": "object",
                    "properties": {f"p{i}": {"type": "array"} for i in range(16)},
                },
            }
        ]
    }
    bad_batch = audit_openapi_mcp_batch(
        [
            {"spec": bad_mcp},
            {"spec": "{bad json"},
        ]
    )
    assert "TOOL-WEAK-DESCRIPTION" in bad_batch[0]["rule_ids"]
    assert "TOOL-PARAM-BLOAT" in bad_batch[0]["rule_ids"]
    assert "TOOL-UNBOUNDED-ARRAY" in bad_batch[0]["rule_ids"]
    assert bad_batch[1]["rule_ids"] == ["SPEC-INVALID-JSON"]


def test_track7_dencho_folder_renamer_dry_run_and_apply(tmp_path: Path) -> None:
    f1 = tmp_path / "令和8年11月19日 株式会社サンプル商事 請求書 110,000円 T7000012050002.pdf"
    f2 = tmp_path / "メモ_名称日付不明.png"
    f1.write_bytes(b"%PDF-1.4 sample")
    f2.write_bytes(b"PNGDATA")

    dry = normalize_and_index_invoice_folder(tmp_path, dry_run=True)
    assert dry["network_calls"] == 0
    assert dry["total_files"] == 2
    assert dry["compliant_count"] == 1
    assert dry["renamed_count"] == 0
    assert f1.exists()
    assert Path(dry["index_csv"]).is_file()

    applied = normalize_and_index_invoice_folder(tmp_path, dry_run=False)
    assert applied["renamed_count"] >= 1
    assert not f1.exists()
    renamed_targets = {r["standardized_filename"] for r in applied["records"]}
    assert any(name.startswith("20261119_") and name.endswith(".pdf") for name in renamed_targets)


def test_track5_seven_gate_compliance_suite_audits_privacy_gate() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "株式会社東京テスト 担当: 山田太郎 03-1234-5678",
                "invoice_id": "T7000012050002",
                "payee_name": "カ）トウキョウテスト",
                "privacy_text": "当社は個人情報を管理します。",
                "script_tags_text": '<script src="https://connect.facebook.net/en_US/fbevents.js"></script>',
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["appi_flagged_rows"] == 1
    assert "appi_audit" in report["rows"][0]
    assert report["rows"][0]["appi_audit"]["unmentioned_vendors"]
