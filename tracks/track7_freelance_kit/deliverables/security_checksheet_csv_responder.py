"""Freelance Deliverable #8 (Track 7): Vendor Security Checksheet CSV Auto-Responder & METI ★3/★4 Auditor."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_meti_security_checksheet_actor.main import audit_meti_security_item

_QUESTION_PILLAR_MAP: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "mfa_privileged",
        re.compile(r"(?:MFA|多要素|二要素|認証|特権|アカウント|FIDO|パスワード)", re.I),
        "全従業員および管理者・VPN・クラウドコンソールへFIDO2/TOTPによる多要素認証（MFA）を必須適用し、最小権限で四半期ごとに棚卸しを実施しています。",
    ),
    (
        "edr_vuln_patch",
        re.compile(r"(?:EDR|マルウェア|ウイルス|脆弱性|CVE|パッチ|SBOM|WAF)", re.I),
        "全業務端末へEDR/EPPを導入し、公開システムおよびOSSの重要脆弱性（CVE）はCSIRT管理下で原則7〜14日以内にパッチ適用しています。",
    ),
    (
        "backup_321_drill",
        re.compile(r"(?:バックアップ|ランサム|復旧|BCP|リストア|世代管理|イミュータブル)", re.I),
        "イミュータブル/オフライン分離媒体を1面以上含む3-2-1暗号化バックアップを日次取得し、年1回以上の定期復旧訓練を実施しています。",
    ),
    (
        "incident_ppc_sla",
        re.compile(r"(?:インシデント|漏えい|PPC|個人情報保護委員会|速報|確報|緊急連絡|報告)", re.I),
        "漏えい・侵害発生時はCSIRT一次窓口より取引先へ24〜72時間以内に初報し、個人情報保護委員会（PPC）へ概ね3〜5日以内速報・30日（不正目的60日）以内確報を行う手順を整備しています。",
    ),
    (
        "trade_secret_3req",
        re.compile(r"(?:営業秘密|秘密保持|NDA|機密|USB|持ち出し|生成AI|不正競争)", re.I),
        "不正競争防止法の営業秘密3要件に基づき、機密区分表示・アクセス権分離・外部記録媒体利用制限・未契約外部AIへの機密入力禁止を規程化しています。",
    ),
    (
        "subprocessor_control",
        re.compile(r"(?:再委託|委託先|サプライヤー|外部委託|承諾|点検)", re.I),
        "業務を再委託する際は事前書面承諾を得るとともに、同等水準のセキュリティ契約締結および年次の安全管理状況点検を実施しています。",
    ),
    (
        "log_encryption",
        re.compile(r"(?:暗号化|TLS|AES|ログ|証跡|監査|保管期間)", re.I),
        "通信経路はTLS 1.2/1.3、保存データはAES-256で暗号化し、認証・特権操作の監査ログを改ざん防止措置のうえ1年以上保管しています。",
    ),
    (
        "email_auth_dmarc",
        re.compile(r"(?:SPF|DMARC|DKIM|なりすまし|メール認証|BEC)", re.I),
        "SPF（ハードフェイル -all / 10ルックアップ以下）およびDMARC（v=DMARC1; p=reject / rua集計監視）を設定し、なりすましメールを遮断しています。",
    ),
)


def classify_security_question(question_text: str) -> tuple[str, str]:
    """Map a Japanese or English vendor security question to a METI control domain and model answer."""
    q = str(question_text or "").strip()
    for pillar_id, pat, default_answer in _QUESTION_PILLAR_MAP:
        if pat.search(q):
            return pillar_id, default_answer
    return (
        "general",
        "情報セキュリティ基本方針および関連規程に基づき、アクセス制御・暗号化・教育・定期見直しを社内で継続運用しています。",
    )


def audit_security_questionnaire_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
    *,
    company_profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Audit a vendor security checksheet CSV offline, draft answers, and emit CSV + SHA-256 JSON."""
    profile = company_profile or {}
    profile_policy = str(profile.get("policy_summary") or "").strip()
    profile_spf = str(profile.get("spf_record") or "").strip()
    profile_dmarc = str(profile.get("dmarc_record") or "").strip()
    org_name = str(profile.get("org_name") or "organization").strip() or "organization"

    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    combined_corpus_parts: list[str] = [profile_policy] if profile_policy else []
    compliant_rows = 0
    needs_remediation_rows = 0
    last_spf = profile_spf
    last_dmarc = profile_dmarc

    for idx, row in enumerate(raw_rows, 1):
        qid = str(row.get("question_id") or row.get("id") or f"Q{idx}").strip()
        q_text = str(row.get("question") or row.get("check_item") or "").strip()
        cur_ctrl = str(row.get("current_control") or row.get("answer") or "").strip()
        row_spf = str(row.get("spf_record") or profile_spf).strip()
        row_dmarc = str(row.get("dmarc_record") or profile_dmarc).strip()
        if row_spf:
            last_spf = row_spf
        if row_dmarc:
            last_dmarc = row_dmarc

        pillar_id, recommended_answer = classify_security_question(q_text)
        eval_text = "\n".join(part for part in (profile_policy, cur_ctrl) if part)
        if eval_text:
            combined_corpus_parts.append(cur_ctrl)

        audit = audit_meti_security_item(
            eval_text,
            spf_record=row_spf,
            dmarc_record=row_dmarc,
            org_name=org_name,
        )
        is_ok = (
            True
            if pillar_id == "general" and bool(cur_ctrl)
            else pillar_id in audit["passed_pillars"]
        )
        row_status = "compliant" if is_ok else "needs_remediation"
        if is_ok:
            compliant_rows += 1
        else:
            needs_remediation_rows += 1

        drafted_answer = cur_ctrl if (is_ok and cur_ctrl) else f"【回答案】{recommended_answer}"
        remediation_note = (
            "追加是正不要（回答根拠確認済み）"
            if is_ok
            else f"統制領域 `{pillar_id}` の証跡不足・未整備（{recommended_answer}）"
        )
        out_rows.append(
            {
                "question_id": qid,
                "pillar": pillar_id,
                "question": q_text,
                "status": row_status,
                "drafted_answer": drafted_answer,
                "remediation_note": remediation_note,
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["question_id", "pillar", "question", "status", "drafted_answer", "remediation_note"]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    overall_audit = audit_meti_security_item(
        "\n".join(p for p in combined_corpus_parts if p),
        spf_record=last_spf,
        dmarc_record=last_dmarc,
        org_name=org_name,
    )

    summary: dict[str, Any] = {
        "network_calls": 0,
        "org_name": org_name,
        "total_rows": len(out_rows),
        "compliant_rows": compliant_rows,
        "needs_remediation_rows": needs_remediation_rows,
        "overall_audit": overall_audit,
        "output_csv": str(out_csv_path),
        "rows": out_rows,
    }
    digest = hashlib.sha256(
        json.dumps(summary, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    summary["sha256_integrity_digest"] = digest

    out_json_path = Path(output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline Japanese Vendor Security Checksheet CSV Auto-Responder"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--org-name", default="organization")
    parser.add_argument("--spf", default="")
    parser.add_argument("--dmarc", default="")
    args = parser.parse_args()
    res = audit_security_questionnaire_csv(
        args.input_csv,
        args.output_csv,
        args.output_json,
        company_profile={
            "org_name": args.org_name,
            "spf_record": args.spf,
            "dmarc_record": args.dmarc,
        },
    )
    print(
        f"Processed {res['total_rows']} security checksheet rows offline. "
        f"Rating={res['overall_audit']['star_rating']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
