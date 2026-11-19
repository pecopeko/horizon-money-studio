"""Unit tests for Wave 10 Actors #23-#24, Track 7 responder #8, and Track 5 11-gate CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from tracks.track1_apify.jp_meti_security_checksheet_actor.main import (
    audit_meti_security_batch,
    audit_meti_security_item,
    parse_email_auth_posture,
)
from tracks.track1_apify.sql_migration_zero_downtime_actor.main import (
    audit_sql_migration_batch,
    audit_sql_migration_item,
)
from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import (
    run_offline_compliance_audit,
)
from tracks.track7_freelance_kit.deliverables.security_checksheet_csv_responder import (
    audit_security_questionnaire_csv,
)


def test_actor23_meti_security_and_email_auth_posture() -> None:
    spf_overflow = "v=spf1 " + " ".join(f"include:s{i}.example.jp" for i in range(11)) + " +all"
    weak_auth = parse_email_auth_posture(spf_overflow, "v=DMARC1; p=none;")
    assert weak_auth["spf_qualifier"] == "+all"
    assert weak_auth["spf_lookups"] == 11
    assert weak_auth["dmarc_policy"] == "none"
    assert any("+all" in w for w in weak_auth["warnings"])
    assert any("11" in w for w in weak_auth["warnings"])

    strong_batch = audit_meti_security_batch(
        [
            {
                "org_name": "Weak Corp",
                "checksheet_text": "パスワードのみ（MFA未導入）。バックアップ未実施、報告期限なし。",
                "spf_record": "v=spf1 ~all",
                "dmarc_record": "v=DMARC1; p=none;",
            },
            {
                "org_name": "Strong Mfg K.K.",
                "checksheet_text": "\n".join(
                    [
                        "全社員・特権IDにFIDO2多要素認証(MFA)を必須化。",
                        "全端末にEDR導入、CVE脆弱性は7日以内セキュリティパッチ適用。",
                        "イミュータブル/オフライン3-2-1バックアップと年次復旧訓練を実施。",
                        "個人情報保護委員会(PPC)への速報(3〜5日)と確報(30日)手順あり。",
                        "営業秘密3要件に基づくアクセス制御・USB禁止・NDA厳守。",
                        "再委託時は事前書面承諾と同等水準契約を実施。",
                        "TLS 1.3・AES-256暗号化および監査ログ1年以上保管。",
                    ]
                ),
                "spf_record": "v=spf1 include:_spf.google.com -all",
                "dmarc_record": "v=DMARC1; p=reject; pct=100; rua=mailto:dmarc@strong.jp",
            },
        ]
    )
    assert strong_batch[0]["status"] == "fail"
    assert strong_batch[0]["star_rating"] == "★3未満（要是正）"
    assert strong_batch[1]["score"] == 100
    assert strong_batch[1]["star_rating"] == "★4相当"
    assert strong_batch[1]["status"] == "pass"


def test_actor24_sql_migration_zero_downtime_rules() -> None:
    risky_sql = """
    BEGIN;
    CREATE INDEX CONCURRENTLY idx_orders_user ON orders(user_id);
    COMMIT;
    CREATE INDEX idx_users_email ON users(email);
    ALTER TABLE orders ALTER COLUMN note TYPE varchar(200);
    ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
    DROP TABLE legacy_tmp;
    DELETE FROM audit_logs;
    """
    res = audit_sql_migration_item(risky_sql, dialect="postgres", filename="001_bad.sql")
    rules = set(res["rule_ids"])
    assert {
        "SQL-TXN-02",
        "SQL-LOCK-01",
        "SQL-TYPE-03",
        "SQL-FK-04",
        "SQL-DESTRUCTIVE-05",
        "SQL-UNBOUNDED-DML-06",
        "SQL-TIMEOUT-07",
    } <= rules
    assert res["status"] == "high_risk"

    safe_sql = """
    -- safety-ack: allow-destructive
    SET lock_timeout = '2s';
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_uid ON orders(user_id);
    ALTER TABLE orders ADD CONSTRAINT fk_u FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
    DELETE FROM audit_logs WHERE created_at < '2020-01-01';
    DROP TABLE IF EXISTS old_staging;
    """
    safe_batch = audit_sql_migration_batch(
        [{"filename": "002_safe.sql", "dialect": "postgres", "sql_text": safe_sql}]
    )
    assert safe_batch[0]["status"] == "pass"
    assert safe_batch[0]["score"] == 100
    assert safe_batch[0]["findings_count"] == 0


def test_track7_security_checksheet_csv_responder(tmp_path: Path) -> None:
    in_csv = tmp_path / "vendor_sheet.csv"
    out_csv = tmp_path / "drafted_answers.csv"
    out_json = tmp_path / "summary.json"

    with in_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question_id", "question", "current_control"])
        writer.writeheader()
        writer.writerow(
            {
                "question_id": "Q1",
                "question": "特権IDへの多要素認証（MFA）適用状況",
                "current_control": "全管理者・VPNにFIDO2 MFA強制済み",
            }
        )
        writer.writerow(
            {
                "question_id": "Q2",
                "question": "SPF/DMARCメールなりすまし対策",
                "current_control": "SPFのみ、DMARC未設定",
            }
        )

    res = audit_security_questionnaire_csv(
        in_csv,
        out_csv,
        out_json,
        company_profile={
            "org_name": "Test Mfg K.K.",
            "spf_record": "v=spf1 include:_spf.example.jp -all",
            "dmarc_record": "v=DMARC1; p=none;",
        },
    )
    assert res["network_calls"] == 0
    assert res["total_rows"] == 2
    assert res["compliant_rows"] == 1
    assert res["needs_remediation_rows"] == 1
    assert out_csv.exists()
    assert out_json.exists()


def test_track5_eleven_gate_cli_audits_bouheki_security() -> None:
    report = run_offline_compliance_audit(
        [
            {
                "text": "株式会社テスト (T1234567890123)",
                "invoice_id": "T8380001000127",
                "payee_name": "カブシキガイシャテスト",
                "security_checksheet_text": "パスワードのみ運用（MFA未導入）、バックアップ未実施。",
                "spf_record": "v=spf1 +all",
                "dmarc_record": "v=DMARC1; p=none;",
            }
        ]
    )
    assert report["network_calls"] == 0
    assert report["bouheki_security_flagged_rows"] == 1
    assert report["rows"][0]["bouheki_security_audit"]["star_rating"] == "★3未満（要是正）"
