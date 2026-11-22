"""Unit tests for Wave 17 Actors #37-#38, Track 7 Toriteki CLI #15, and Track 5 18-gate CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track1_apify.jp_toriteki_shitauke_2026_actor.main import (
    audit_toriteki_contract_batch,
    evaluate_toriteki_thresholds,
)
from tracks.track1_apify.k8s_rbac_networkpolicy_pss_actor.main import (
    audit_k8s_cluster_policy_batch,
    audit_k8s_cluster_policy_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.toriteki_shitauke_2026_auditor import (
    audit_toriteki_csv,
)


def test_actor37_toriteki_2026_subcontract_act_auditor() -> None:
    emp_only = evaluate_toriteki_thresholds(
        transaction_category="manufacturing_or_logistics",
        buyer_capital_jpy=10_000_000,
        supplier_capital_jpy=10_000_000,
        buyer_employees=420,
        supplier_employees=85,
        payment_cycle_days=90,
        payment_method="promissory_note",
        has_unilateral_price_freeze=True,
        unpaid_mold_storage_months=12,
    )
    assert emp_only["capital_covered"] is False
    assert emp_only["employee_rule_covered"] is True
    assert emp_only["toriteki_applicable"] is True
    assert emp_only["payment_cycle_over_60d"] is True
    assert emp_only["prohibited_bill_or_fee_deduction"] is True
    assert emp_only["price_freeze_violation"] is True
    assert emp_only["unpaid_mold_storage_violation"] is True

    svc_emp = evaluate_toriteki_thresholds(
        transaction_category="service_or_content",
        buyer_capital_jpy=10_000_000,
        supplier_capital_jpy=10_000_000,
        buyer_employees=150,
        supplier_employees=30,
    )
    assert svc_emp["employee_threshold"] == 100
    assert svc_emp["capital_covered"] is False
    assert svc_emp["employee_rule_covered"] is True
    assert svc_emp["toriteki_applicable"] is True

    compliant_text = "\n".join(
        [
            "直ちに4条書面（電磁的記録・委託内容明記・支払期日明記）を交付する。",
            "物品受領日から60日以内に全額現金振込（銀行振込）で支払う。",
            "約束手形廃止（手形不使用）とし振込手数料委託者負担にて割引料転嫁なしとする。",
            "労務費・原材料費高騰に伴う価格転嫁協議の申出に誠実に応じる。",
            "従業員数基準（300人/100人）で取適法対象取引を確認し特定運送委託も管理する。",
            "量産終了後の金型は保管料有償または型返却とし、5条書類を2年保存する。",
        ]
    )

    batch = audit_toriteki_contract_batch(
        [
            {
                "org_name": "Risky Buyer",
                "transaction_category": "manufacturing_or_logistics",
                "buyer_capital_jpy": 10_000_000,
                "supplier_capital_jpy": 10_000_000,
                "buyer_employees": 420,
                "supplier_employees": 85,
                "payment_cycle_days": 90,
                "payment_method": "promissory_note",
                "has_unilateral_price_freeze": True,
                "unpaid_mold_storage_months": 12,
                "contract_text": "資本金1000万以下対象外として口頭発注し、約束手形払い・価格据置・金型無償保管とする。",
            },
            {
                "org_name": "Compliant Buyer",
                "transaction_category": "manufacturing_or_logistics",
                "buyer_capital_jpy": 10_000_000,
                "supplier_capital_jpy": 10_000_000,
                "buyer_employees": 420,
                "supplier_employees": 85,
                "payment_cycle_days": 45,
                "payment_method": "bank_transfer",
                "has_unilateral_price_freeze": False,
                "unpaid_mold_storage_months": 0,
                "contract_text": compliant_text,
            },
        ]
    )
    assert batch[0]["status"] == "fail"
    bad_rules = {f["rule_id"] for f in batch[0]["findings"]}
    assert {
        "TORITEKI-CYCLE-OVER-60D",
        "TORITEKI-PROHIBITED-BILL",
        "TORITEKI-PRICE-FREEZE",
        "TORITEKI-UNPAID-MOLD-CUSTODY",
    }.issubset(bad_rules)

    assert batch[1]["score"] == 100
    assert batch[1]["status"] == "pass"


def test_actor38_k8s_rbac_networkpolicy_pss_auditor() -> None:
    unsafe_manifest = """
    roleRef:
      kind: ClusterRole
      name: cluster-admin
    rules:
      - verbs: ["*"]
        resources: ["*"]
    automountServiceAccountToken: true
    ingress:
      - from:
          - ipBlock:
              cidr: 0.0.0.0/0
    pod-security.kubernetes.io/enforce: privileged
    failurePolicy: Ignore
    limits: null
    """
    bad = audit_k8s_cluster_policy_item(unsafe_manifest, cluster_name="unsafe-prod")
    assert bad["status"] == "high_risk"
    assert set(bad["rule_ids"]) == {
        "K8S-RBAC-01",
        "K8S-SA-02",
        "K8S-NETPOL-03",
        "K8S-PSS-04",
        "K8S-WEBHOOK-05",
        "K8S-QUOTA-06",
    }

    safe_manifest = """
    roleRef:
      kind: Role
      name: app-reader
    rules:
      - verbs: ["get", "list"]
        resources: ["configmaps"]
    automountServiceAccountToken: false
    spec:
      podSelector: {}
      policyTypes: ["Ingress", "Egress"]
      ingress: []
      egress: []
    pod-security.kubernetes.io/enforce: restricted
    seccompProfile:
      type: RuntimeDefault
    failurePolicy: Fail
    resources:
      limits:
        cpu: "500m"
        memory: "256Mi"
    """
    good = audit_k8s_cluster_policy_batch(
        [{"cluster_name": "safe-prod", "manifest_text": safe_manifest}]
    )
    assert good[0]["status"] == "pass"
    assert good[0]["score"] == 100
    assert good[0]["findings_count"] == 0


def test_track7_toriteki_shitauke_2026_auditor(tmp_path: Path) -> None:
    in_csv = tmp_path / "vendors.csv"
    out_csv = tmp_path / "audited.csv"
    out_json = tmp_path / "audited.json"

    compliant_text = (
        "4条書面 電磁的記録 支払期日明記 60日以内 現金振込 約束手形廃止 振込手数料委託者負担 "
        "価格転嫁協議 従業員数基準 300人 特定運送委託 金型 保管料有償 5条書類 2年保存"
    )

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "org_name",
                "transaction_category",
                "buyer_capital_jpy",
                "supplier_capital_jpy",
                "buyer_employees",
                "supplier_employees",
                "payment_cycle_days",
                "payment_method",
                "has_unilateral_price_freeze",
                "unpaid_mold_storage_months",
                "toriteki_contract_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "org_name": "Clean Vendor A",
                "transaction_category": "manufacturing_or_logistics",
                "buyer_capital_jpy": "10000000",
                "supplier_capital_jpy": "10000000",
                "buyer_employees": "420",
                "supplier_employees": "85",
                "payment_cycle_days": "45",
                "payment_method": "bank_transfer",
                "has_unilateral_price_freeze": "false",
                "unpaid_mold_storage_months": "0",
                "toriteki_contract_text": compliant_text,
            }
        )
        writer.writerow(
            {
                "org_name": "Tegata Risk Vendor B",
                "transaction_category": "manufacturing_or_logistics",
                "buyer_capital_jpy": "10000000",
                "supplier_capital_jpy": "10000000",
                "buyer_employees": "420",
                "supplier_employees": "85",
                "payment_cycle_days": "90",
                "payment_method": "promissory_note",
                "has_unilateral_price_freeze": "true",
                "unpaid_mold_storage_months": "12",
                "toriteki_contract_text": "口頭発注。約束手形払い。価格据置。金型無償保管。",
            }
        )

    res = audit_toriteki_csv(in_csv, out_csv, out_json)
    assert res["network_calls"] == 0
    assert res["total_transactions"] == 2
    assert res["applicable_transactions"] == 2
    assert res["employee_only_covered_transactions"] == 2
    assert res["over_60d_transactions"] == 1
    assert res["prohibited_bill_transactions"] == 1
    assert res["price_freeze_transactions"] == 1
    assert res["mold_custody_violations"] == 1
    assert res["rows"][0]["audit_status"] == "pass"
    assert res["rows"][1]["audit_status"] == "fail"
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_eighteen_gate_cli_audits_toriteki_contract() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "新規委託基本契約条項点検",
                "invoice_id": "T7000012050002",
                "payee_name": "オオミヤカナガタカコウ",
                "transaction_category": "manufacturing_or_logistics",
                "buyer_capital_jpy": "10000000",
                "supplier_capital_jpy": "10000000",
                "buyer_employees": "420",
                "supplier_employees": "85",
                "payment_cycle_days": "90",
                "payment_method": "promissory_note",
                "has_unilateral_price_freeze": "true",
                "unpaid_mold_storage_months": "12",
                "toriteki_contract_text": "口頭発注、約束手形払い、価格据置。",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["toriteki_flagged_rows"] == 1
    assert report["rows"][0]["toriteki_audit"]["status"] == "fail"
    assert report["rows"][0]["toriteki_audit"]["thresholds"]["employee_rule_covered"] is True
    assert report["rows"][0]["toriteki_audit"]["thresholds"]["prohibited_bill_or_fee_deduction"] is True


def test_all_38_apify_actor_input_schemas_have_required_descriptions() -> None:
    schema_paths = sorted(Path("tracks/track1_apify").glob("*/.actor/input_schema.json"))
    assert len(schema_paths) >= 38
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
