"""Unit tests for Wave 20 Actors #43-#44, Track 7 Anpo CLI #18, and Track 5 21-gate CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track1_apify.cloud_iam_oidc_least_privilege_actor.main import (
    audit_iam_policy_batch,
    audit_iam_policy_item,
)
from tracks.track1_apify.jp_keizaianpo_clearance_supplychain_actor.main import (
    audit_keizaianpo_batch,
    evaluate_keizaianpo_obligations,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.keizaianpo_clearance_auditor import (
    audit_keizaianpo_csv,
)


def test_actor43_keizaianpo_clearance_auditor() -> None:
    bad_metrics = evaluate_keizaianpo_obligations(
        sector="telecom",
        is_specified_infrastructure_operator=True,
        introduces_critical_equipment=True,
        outsources_critical_maintenance=True,
        prior_notification_filed=False,
        handles_classified_econ_info=True,
        all_handlers_cleared=False,
        is_critical_commodity=True,
        single_country_dependency_pct=85.0,
    )
    assert bad_metrics["requires_prior_notification"] is True
    assert bad_metrics["missing_prior_notification_violation"] is True
    assert bad_metrics["uncleared_access_violation"] is True
    assert bad_metrics["single_source_concentration_risk"] is True

    compliant_text = "\n".join(
        [
            "特定社会基盤役務の特定重要設備は導入前に主務大臣へ事前届出を完了する。",
            "維持管理等委託および再委託先は外国人支配・実質的支配者を確認し事前承認する。",
            "重要経済安保情報は本人同意を得て適性評価完了者のみ扱い不利益取扱い禁止を順守する。",
            "適合事業者として施設保全・電磁的遮断と秘密保持誓約・刑事罰周知を行う。",
            "特定重要物資の供給途絶対策として複数購買・代替調達および備蓄計画を実施する。",
            "安全保障技術審査による一次審査を行い保全指定対象特許の特許出願非公開・外国出願禁止を守る。",
            "重要プログラムのSBOM管理と外国政府アクセス遮断・データ国内保管を実装する。",
            "インシデント即報・主務大臣報告およびアクセスログ保存・監査証跡5年保全を徹底する。",
        ]
    )

    batch = audit_keizaianpo_batch(
        [
            {
                "vendor_name": "Risky Core Vendor",
                "sector": "telecom",
                "is_specified_infrastructure_operator": True,
                "introduces_critical_equipment": True,
                "outsources_critical_maintenance": True,
                "prior_notification_filed": False,
                "handles_classified_econ_info": True,
                "all_handlers_cleared": False,
                "is_critical_commodity": True,
                "single_country_dependency_pct": 85.0,
                "policy_text": "事前届出せず導入し適性評価未了へ共有、無届で海外委託する。",
            },
            {
                "vendor_name": "Cleared Domestic Telecom Partner",
                "sector": "telecom",
                "is_specified_infrastructure_operator": True,
                "introduces_critical_equipment": True,
                "outsources_critical_maintenance": True,
                "prior_notification_filed": True,
                "handles_classified_econ_info": True,
                "all_handlers_cleared": True,
                "is_critical_commodity": True,
                "single_country_dependency_pct": 25.0,
                "policy_text": compliant_text,
            },
        ]
    )
    assert len(batch) == 2
    assert batch[0]["status"] == "fail"
    assert batch[0]["score"] < 40
    rule_ids = {f["rule_id"] for f in batch[0]["findings"]}
    assert "ANPO-MISSING-PRIOR-NOTIFICATION" in rule_ids
    assert "ANPO-UNCLEARED-PERSONNEL-ACCESS" in rule_ids
    assert batch[1]["status"] == "pass"
    assert batch[1]["score"] == 100
    assert batch[1]["findings_count"] == 0


def test_actor44_cloud_iam_oidc_least_privilege_auditor() -> None:
    bad_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": "*",
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Principal": {"Federated": "token.actions.githubusercontent.com"},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringLike": {
                            "token.actions.githubusercontent.com:sub": "repo:acme/*"
                        }
                    },
                },
                {
                    "Effect": "Allow",
                    "Action": ["iam:PassRole", "iam:AttachRolePolicy"],
                    "Resource": "*",
                },
            ],
        }
    )
    res_bad = audit_iam_policy_item(bad_policy, target_name="overprivileged-ci.json")
    assert res_bad["network_calls"] == 0
    assert res_bad["status"] == "fail"
    bad_rules = {f["rule_id"] for f in res_bad["findings"]}
    assert {"IAM-WILD-01", "IAM-OIDC-02", "IAM-PRIVESC-03", "IAM-TRUST-04"} <= bad_rules

    good_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                            "token.actions.githubusercontent.com:sub": "repo:pecopeko/horizon-money-studio:ref:refs/heads/main",
                        }
                    },
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": "arn:aws:s3:::acme-release-artifacts/*",
                },
            ],
        }
    )
    batch = audit_iam_policy_batch([{"target_name": "least-priv.json", "policy_text": good_policy}])
    assert batch[0]["status"] == "pass"
    assert batch[0]["score"] == 100
    assert batch[0]["findings_count"] == 0


def test_track7_deliverable18_keizaianpo_csv_auditor(tmp_path: Path) -> None:
    in_csv = tmp_path / "anpo_in.csv"
    out_csv = tmp_path / "anpo_out.csv"
    out_json = tmp_path / "anpo_report.json"

    compliant_text = "\n".join(
        [
            "特定社会基盤役務の特定重要設備事前届出を実施する。",
            "維持管理等委託の再委託承認および実質的支配者審査を行う。",
            "重要経済安保情報の適性評価・本人同意・不利益取扱い禁止を守る。",
            "適合事業者施設保全・電磁的遮断と刑事罰周知を徹底する。",
            "特定重要物資の複数購買・備蓄計画を運用する。",
            "特許出願非公開・安全保障技術審査を行う。",
            "重要プログラムSBOMおよび外国政府アクセス遮断を実施する。",
            "インシデント即報・主務大臣報告およびアクセスログ保存を行う。",
        ]
    )

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "vendor_name",
                "sector",
                "is_specified_infrastructure_operator",
                "introduces_critical_equipment",
                "outsources_critical_maintenance",
                "prior_notification_filed",
                "handles_classified_econ_info",
                "all_handlers_cleared",
                "is_critical_commodity",
                "single_country_dependency_pct",
                "keizaianpo_policy_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "vendor_name": "Compliant Telecom A",
                "sector": "telecom",
                "is_specified_infrastructure_operator": "true",
                "introduces_critical_equipment": "true",
                "outsources_critical_maintenance": "true",
                "prior_notification_filed": "true",
                "handles_classified_econ_info": "true",
                "all_handlers_cleared": "true",
                "is_critical_commodity": "true",
                "single_country_dependency_pct": "20",
                "keizaianpo_policy_text": compliant_text,
            }
        )
        writer.writerow(
            {
                "vendor_name": "Risky Vendor B",
                "sector": "banking",
                "is_specified_infrastructure_operator": "true",
                "introduces_critical_equipment": "true",
                "outsources_critical_maintenance": "false",
                "prior_notification_filed": "false",
                "handles_classified_econ_info": "true",
                "all_handlers_cleared": "false",
                "is_critical_commodity": "true",
                "single_country_dependency_pct": "90",
                "keizaianpo_policy_text": "事前届出せず導入し適性評価未了者へ共有。",
            }
        )

    res = audit_keizaianpo_csv(in_csv, out_csv, out_json)
    assert res["network_calls"] == 0
    assert res["total_records"] == 2
    assert res["missing_prior_notification_count"] == 1
    assert res["uncleared_access_count"] == 1
    assert res["concentration_risk_count"] == 1
    assert res["rows"][0]["audit_status"] == "pass"
    assert res["rows"][1]["audit_status"] == "fail"
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_twenty_one_gate_cli_audits_keizaianpo() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "基幹インフラ委託監査案件",
                "invoice_id": "T7000012050002",
                "payee_name": "カントウツウシン",
                "sector": "telecom",
                "is_specified_infrastructure_operator": "true",
                "introduces_critical_equipment": "true",
                "prior_notification_filed": "false",
                "handles_classified_econ_info": "true",
                "all_handlers_cleared": "false",
                "keizaianpo_policy_text": "事前届出せず導入し適性評価未了者へ共有。",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["keizaianpo_flagged_rows"] == 1
    assert report["rows"][0]["keizaianpo_audit"]["status"] == "fail"
    assert report["rows"][0]["keizaianpo_audit"]["metrics"]["missing_prior_notification_violation"] is True
    assert report["rows"][0]["keizaianpo_audit"]["metrics"]["uncleared_access_violation"] is True


def test_all_44_apify_actor_input_schemas_have_required_descriptions() -> None:
    schema_paths = sorted(Path("tracks/track1_apify").glob("*/.actor/input_schema.json"))
    assert len(schema_paths) == 44
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
