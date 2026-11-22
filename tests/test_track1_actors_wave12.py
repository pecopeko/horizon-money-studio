"""Unit tests for Wave 12 Actors #27-#28, Track 7 KYC UBO screener #10, and Track 5 13-gate CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track1_apify.graphql_api_security_hardening_actor.main import (
    audit_graphql_security_batch,
    audit_graphql_security_item,
)
from tracks.track1_apify.jp_hansha_kyc_whistleblower_actor.main import (
    audit_hansha_kyc_batch,
    compute_ubo_beneficial_owners,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.vendor_kyc_ubo_hansha_screener import (
    audit_vendor_kyc_csv,
)


def test_actor27_hansha_ubo_chain_and_whistleblower_audit() -> None:
    chain_res = compute_ubo_beneficial_owners(
        holders=[
            {"name": "山田 太郎", "type": "individual", "directPct": 15},
            {
                "name": "山田HD",
                "type": "corporate",
                "directPct": 22,
                "controllerName": "山田 太郎",
                "controllerPct": 60,
            },
            {"name": "佐藤 花子", "type": "individual", "directPct": 25},
        ],
        representative_name="鈴木 一郎",
    )
    assert chain_res["fallback_representative_used"] is False
    assert len(chain_res["ubos"]) == 1
    assert chain_res["ubos"][0]["name"] == "山田 太郎"
    assert chain_res["ubos"][0]["effective_pct"] == 37.0
    assert chain_res["ubos"][0]["basis"] == "ubo_over_25"

    dispersed = compute_ubo_beneficial_owners(
        holders=[{"name": "A", "type": "individual", "directPct": 20}],
        representative_name="鈴木 一郎",
    )
    assert dispersed["fallback_representative_used"] is True
    assert dispersed["ubos"][0]["name"] == "鈴木 一郎"
    assert dispersed["ubos"][0]["basis"] == "deemed_representative"

    batch = audit_hansha_kyc_batch(
        [
            {
                "org_name": "Risky Corp",
                "clause_text": "催告の上解除する。損害賠償を負担する。確認記録保存なし。正社員のみ受付。",
                "representative_name": "鈴木 一郎",
            },
            {
                "org_name": "Clean Corp",
                "holders": [{"name": "大株主 次郎", "type": "individual", "directPct": 55}],
                "representative_name": "Clean CEO",
                "clause_text": "\n".join(
                    [
                        "現在・過去5年間および将来にわたって反社会的勢力に該当しない。",
                        "共生者（資金提供・密接交際）と不当要求を排除する。",
                        "違反時は催告を要せず無催告解除する。",
                        "相手方に損害が生じても一切賠償請求しない（損害賠償免責）。",
                        "犯収法に基づき実質的支配者(25%超UBO)および外国PEPsを確認し確認記録を7年保存する。",
                        "公益通報対応業務従事者を書面指定し刑事罰対象守秘義務を運用する。",
                        "退職後1年以内およびフリーランス（業務委託）も通報受付対象とする。",
                        "通報者の特定・探索を禁止し不利益取扱いを禁止する。",
                    ]
                ),
            },
        ]
    )
    assert batch[0]["status"] == "fail"
    assert batch[1]["score"] == 100
    assert batch[1]["status"] == "pass"
    assert batch[1]["ubo_result"]["ubos"][0]["basis"] == "dominant_ubo_over_50"


def test_actor28_graphql_dos_introspection_and_sensitive_field_auditor() -> None:
    vulnerable_gql = """
    introspection: true
    allowBatchedHttpRequests: true
    csrfPrevention: false
    type User {
      id: ID!
      passwordHash: String!
      posts: [Post!]!
    }
    type Post {
      id: ID!
      author: User!
    }
    type Query {
      users: [User!]!
    }
    """
    bad = audit_graphql_security_item(vulnerable_gql, target_name="bad.graphql")
    assert bad["status"] == "high_risk"
    assert {
        "GQL-INTROSPECTION-01",
        "GQL-DEPTH-02",
        "GQL-BATCH-03",
        "GQL-SENSITIVE-04",
        "GQL-UNBOUNDED-LIST-05",
        "GQL-CSRF-06",
    } <= set(bad["rule_ids"])

    hardened_gql = """
    introspection: false
    csrfPrevention: true
    validationRules: [depthLimit(6), costLimit(500), maxAliases(10)]
    allowBatchedHttpRequests: true
    type User {
      id: ID!
      email: String!
      passwordHash: String! @redact
      posts: [Post!]!
    }
    type Post {
      id: ID!
      author: User!
    }
    type Query {
      users(first: Int = 20): [User!]!
    }
    """
    good = audit_graphql_security_batch(
        [{"target_name": "good.graphql", "sdl_text": hardened_gql}]
    )
    assert good[0]["status"] == "pass"
    assert good[0]["score"] == 100
    assert good[0]["findings_count"] == 0


def test_track7_vendor_kyc_ubo_hansha_screener(tmp_path: Path) -> None:
    in_csv = tmp_path / "vendors.csv"
    out_csv = tmp_path / "screened.csv"
    out_json = tmp_path / "screened.json"

    holders_json = json.dumps(
        [
            {"name": "高橋 三郎", "type": "individual", "directPct": 10},
            {
                "name": "高橋管財合同会社",
                "type": "corporate",
                "directPct": 20,
                "controllerName": "高橋 三郎",
                "controllerPct": 100,
            },
        ]
    )
    compliant_clause = (
        "現在および過去5年間・将来にわたり反社会的勢力・共生者に該当せず、"
        "違反時は無催告解除・一切損害賠償請求しない。犯収法UBO確認・確認記録7年保存。"
        "公益通報従事者指定・フリーランス・退職後1年保護・探索禁止。"
    )

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "vendor_name",
                "invoice_id",
                "representative_name",
                "shareholders_json",
                "peps_flag",
                "hansha_clause_text",
                "retention_years",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "vendor_name": "Tokyo Tech Inc.",
                "invoice_id": "T1234567890123",
                "representative_name": "高橋 三郎",
                "shareholders_json": holders_json,
                "peps_flag": "true",
                "hansha_clause_text": compliant_clause,
                "retention_years": "5",
            }
        )

    res = audit_vendor_kyc_csv(in_csv, out_csv, out_json)
    assert res["network_calls"] == 0
    assert res["total_vendors"] == 1
    assert res["invalid_invoice_ids"] == 1
    assert res["peps_hits"] == 1
    assert res["rows"][0]["lead_ubo_name"] == "高橋 三郎"
    assert res["rows"][0]["lead_ubo_pct"] == "30.0"
    assert res["rows"][0]["screening_status"] == "blocked_remediate"
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_thirteen_gate_cli_audits_hansha_kyc() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "テスト商事契約確認",
                "invoice_id": "T1234567890123",
                "payee_name": "カブシキガイシャテスト",
                "hansha_clause_text": "催告の上解除する。確認記録保存なし。",
                "representative_name": "代表 太郎",
                "ubo_holders_json": '[{"name":"高橋","type":"individual","directPct":30}]',
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["hansha_kyc_flagged_rows"] == 1
    assert report["rows"][0]["hansha_kyc_audit"]["status"] == "fail"
    assert report["rows"][0]["hansha_kyc_audit"]["ubo_result"]["ubos"][0]["name"] == "高橋"
