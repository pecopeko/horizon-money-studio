"""Unit tests for Wave 9 Track 1 Actors #21-#22, Track 7 deliverable #7, and 10-gate Track 5 CLI."""

from __future__ import annotations

from pathlib import Path

from tracks.track1_apify.jp_jis_wcag_a11y_actor.main import (
    audit_jis_a11y_batch,
    audit_jis_a11y_item,
    calculate_contrast_ratio,
)
from tracks.track1_apify.terraform_iac_security_actor.main import (
    audit_terraform_hcl_batch,
    audit_terraform_hcl_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.html_folder_jis8341_auditor import (
    audit_html_folder_jis8341,
)


def test_actor21_jis8341_a11y_and_contrast_math() -> None:
    bw = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert bw["ratio"] == 21.0
    assert bw["passes_aa"] is True

    bad = """
    <html>
      <head><meta name="viewport" content="width=device-width, user-scalable=no"></head>
      <body>
        <h1>Top</h1><h3>Skip</h3>
        <img src="hero.png">
        <input type="text">
        <button></button>
        <a href="/next">こちら</a>
      </body>
    </html>
    """
    bad_res = audit_jis_a11y_item(bad, foreground_hex="#999999", background_hex="#FFFFFF")
    for expected in (
        "JIS-3.1.1-HTML-LANG",
        "JIS-2.4.2-PAGE-TITLE",
        "JIS-1.4.4-VIEWPORT-ZOOM",
        "JIS-1.1.1-IMG-ALT",
        "JIS-4.1.2-EMPTY-BUTTON-LINK",
        "JIS-2.4.4-AMBIGUOUS-LINK",
        "JIS-1.3.1-UNLABELED-INPUT",
        "JIS-1.3.1-HEADING-SKIP",
        "JIS-1.4.3-CONTRAST-AA",
    ):
        assert expected in bad_res["rule_ids"]
    assert bad_res["status"] == "high_risk"

    good = """<!DOCTYPE html>
    <html lang="ja">
      <head><title>品川パブリックデザイン</title></head>
      <body>
        <h1>案内</h1><h2>詳細</h2>
        <img src="/logo.png" alt="会社ロゴ">
        <label for="u">氏名</label><input id="u" type="text">
        <button type="submit">送信する</button>
      </body>
    </html>
    """
    batch = audit_jis_a11y_batch([{"name": "ok.html", "html_source": good, "foreground_hex": "#171717", "background_hex": "#FFFFFF"}])
    assert batch[0]["score"] == 100
    assert batch[0]["status"] == "pass"


def test_actor22_terraform_hcl_security_and_finops_auditor() -> None:
    vuln_tf = """
resource "aws_s3_bucket_acl" "b" {
  acl = "public-read"
}
resource "aws_security_group" "ssh" {
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_db_instance" "db" {
  storage_encrypted = false
  password          = "SuperSecretProd123!"
}
data "aws_iam_policy_document" "admin" {
  statement {
    effect    = "Allow"
    actions   = ["*"]
    resources = ["*"]
  }
}
"""
    vuln_res = audit_terraform_hcl_item(vuln_tf, "main.tf")
    for expected in (
        "TF-PUBLIC-STORAGE",
        "TF-OPEN-INGRESS-0000",
        "TF-UNENCRYPTED-DATA",
        "TF-HARDCODED-SECRET",
        "TF-WILDCARD-IAM",
        "TF-MISSING-FINOPS-TAGS",
    ):
        assert expected in vuln_res["rule_ids"]
    assert vuln_res["risk_level"] == "high"

    safe_tf = """
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = "t3.micro"
  tags = {
    Env = "prod"
  }
}
"""
    batch = audit_terraform_hcl_batch([{"name": "safe.tf", "hcl_text": safe_tf}])
    assert batch[0]["security_score"] == 100
    assert batch[0]["risk_level"] == "low"
    assert batch[0]["findings"] == []


def test_track7_html_folder_jis8341_auditor(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body><img src='a.png'></body></html>", encoding="utf-8")
    (tmp_path / "about.html").write_text(
        "<html lang='ja'><head><title>会社概要</title></head><body><h1>概要</h1></body></html>",
        encoding="utf-8",
    )
    res = audit_html_folder_jis8341(tmp_path, organization_name="株式会社品川パブリックデザイン")
    assert res["network_calls"] == 0
    assert res["total_files"] == 2
    assert res["flagged_pages"] == 1
    assert Path(res["output_csv"]).read_bytes().startswith(b"\xef\xbb\xbf")
    md_text = Path(res["output_policy_md"]).read_text(encoding="utf-8")
    assert "JIS X 8341-3:2016" in md_text
    assert "株式会社品川パブリックデザイン" in md_text


def test_track5_ten_gate_compliance_suite_audits_html_snippet() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "株式会社東京テスト 担当: 山田太郎",
                "invoice_id": "T7000012050002",
                "payee_name": "シナガワ パブリック",
                "html_snippet": "<html><body><img src='banner.png'><button></button></body></html>",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["jis_a11y_flagged_rows"] == 1
    assert "jis_a11y_audit" in report["rows"][0]
    assert "JIS-1.1.1-IMG-ALT" in report["rows"][0]["jis_a11y_audit"]["rule_ids"]
