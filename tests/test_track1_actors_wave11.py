"""Unit tests for Wave 11 Actors #25-#26, Track 7 AI risk register #9, and Track 5 12-gate CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from tracks.track1_apify.jp_ai_governance_guideline_actor.main import (
    audit_ai_governance_batch,
    audit_ai_governance_item,
    classify_ai_use_case_risk,
)
from tracks.track1_apify.nextjs_cors_csp_headers_actor.main import (
    audit_web_headers_batch,
    audit_web_headers_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.ai_tool_inventory_risk_register import (
    audit_ai_inventory_csv,
)


def test_actor25_ai_governance_and_copyright304() -> None:
    prohibited = classify_ai_use_case_risk("職場での感情監視ツール", "apache-2.0")
    assert prohibited["risk_tier"] == "prohibited"
    assert prohibited["license_status"] == "commercial_ok"

    high_nc = classify_ai_use_case_risk("採用エントリーシート審査", "cc-by-nc-4.0")
    assert high_nc["risk_tier"] == "high_risk"
    assert high_nc["license_status"] == "restricted_non_commercial"

    batch = audit_ai_governance_batch(
        [
            {
                "org_name": "Risky Corp",
                "use_case": "職場での感情監視",
                "model_license": "research-only",
                "policy_text": "無料個人アカウント許可。学習オプトアウト不要。人間確認不要で自動決定。",
            },
            {
                "org_name": "Compliant AI Inc.",
                "use_case": "社内FAQチャットボット",
                "model_license": "enterprise-api",
                "policy_text": "\n".join(
                    [
                        "シャドーAI禁止・法人Enterprise APIで学習オプトアウト(ZDR)強制。",
                        "著作権法第30条の4に基づき特定作家の作風模倣指示を禁止し類似性確認。",
                        "個人情報(PII)と営業秘密は事前マスキング後に投入。",
                        "対外発信は人間による最終確認（HITL）を必須化。",
                        "プロンプトインジェクション検証とハルシネーション事実確認を実施。",
                        "チャットボット明示のAI生成表示とガイドライン第1.1版リスク評価を実施。",
                        "プロンプト監査ログ保全とCSIRT緊急停止窓口を整備。",
                        "CAIO統括のもと利用申請台帳・リテラシー研修を実施。",
                    ]
                ),
            },
        ]
    )
    assert batch[0]["status"] == "fail"
    assert any(f["rule_id"] == "AIGOV-EU_PROHIBITED_AI" for f in batch[0]["findings"])
    assert any(f["rule_id"] == "AIGOV-MODEL_LICENSE_NC" for f in batch[0]["findings"])

    assert batch[1]["score"] == 100
    assert batch[1]["status"] == "pass"
    assert batch[1]["findings_count"] == 0


def test_actor26_web_cors_csp_cookie_hardening_auditor() -> None:
    weak_headers = "\n".join(
        [
            "Access-Control-Allow-Origin: *",
            "Access-Control-Allow-Credentials: true",
            "Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'",
            "Strict-Transport-Security: max-age=3600",
            "Set-Cookie: session_id=xyz123; Path=/",
            "X-Powered-By: Express",
            "Server: nginx/1.24.0",
        ]
    )
    bad = audit_web_headers_item(weak_headers, target_name="weak.example.jp")
    assert bad["status"] == "high_risk"
    assert {
        "WEB-CORS-01",
        "WEB-CSP-02",
        "WEB-CLICKJACK-03",
        "WEB-HSTS-04",
        "WEB-COOKIE-05",
        "WEB-LEAK-06",
    } <= set(bad["rule_ids"])

    good_headers = "\n".join(
        [
            "Access-Control-Allow-Origin: https://app.example.jp",
            "Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-r4nd0m'; frame-ancestors 'none'",
            "Strict-Transport-Security: max-age=63072000; includeSubDomains; preload",
            "Set-Cookie: __Host-sid=secret; Path=/; HttpOnly; Secure; SameSite=Lax",
        ]
    )
    good = audit_web_headers_batch([{"target_name": "hardened.example.jp", "headers_text": good_headers}])
    assert good[0]["status"] == "pass"
    assert good[0]["score"] == 100
    assert good[0]["findings_count"] == 0


def test_track7_ai_tool_inventory_risk_register(tmp_path: Path) -> None:
    in_csv = tmp_path / "ai_inventory.csv"
    out_csv = tmp_path / "ai_risk_register.csv"
    out_json = tmp_path / "ai_risk_summary.json"

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "tool_name",
                "department",
                "plan_tier",
                "training_opt_out",
                "use_case",
                "data_types",
                "model_license",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "tool_name": "PersonalChatAI",
                "department": "Marketing",
                "plan_tier": "Free",
                "training_opt_out": "false",
                "use_case": "特定作家の作風模倣LPイラスト案",
                "data_types": "顧客個人情報(PII)",
                "model_license": "cc-by-nc",
            }
        )
        writer.writerow(
            {
                "tool_name": "CorpDocsBot",
                "department": "Engineering",
                "plan_tier": "Enterprise",
                "training_opt_out": "true",
                "use_case": "社内FAQ検索チャットボット",
                "data_types": "公開マニュアルのみ",
                "model_license": "enterprise-api",
            }
        )

    res = audit_ai_inventory_csv(in_csv, out_csv, out_json, org_name="Tokyo Mfg K.K.")
    assert res["network_calls"] == 0
    assert res["total_tools"] == 2
    assert res["shadow_ai_count"] == 1
    assert res["copyright_risk_count"] == 1
    assert res["license_risk_count"] == 1
    assert res["high_risk_count"] == 1
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_twelve_gate_cli_audits_ai_governance() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "テスト文面",
                "invoice_id": "T8380001000127",
                "payee_name": "カブシキガイシャテスト",
                "ai_governance_text": "無料個人アカウント許可。学習オプトアウト不要。",
                "ai_use_case": "採用一次スクリーニング",
                "model_license": "cc-by-nc-4.0",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["aigov_flagged_rows"] == 1
    assert report["rows"][0]["aigov_audit"]["status"] == "fail"
