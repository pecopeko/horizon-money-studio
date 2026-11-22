"""Freelance Deliverable #9 (Track 7): Corporate Shadow AI Inventory & Copyright Art. 30-4 Risk Register."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_ai_governance_guideline_actor.main import (
    classify_ai_use_case_risk,
)

_FREE_OR_PERSONAL_RE = re.compile(r"(?:free|personal|trial|無料|個人|unlicensed)", re.I)
_SENSITIVE_DATA_RE = re.compile(
    r"(?:pii|個人情報|customer|顧客|secret|営業秘密|機密|confidential|マイナンバー|source|財務)",
    re.I,
)
_COPYRIGHT_30_4_RISK_RE = re.compile(
    r"(?:作風|特定作家|mimic|style\s*transfer|既存キャラ|キャラ模倣|enjoyment|享受目的)",
    re.I,
)
_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|済|有効|zdr|opt[-_ ]?out)$", re.I)


def audit_ai_inventory_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
    *,
    org_name: str = "organization",
) -> dict[str, Any]:
    """Audit corporate AI tool inventory CSV offline and emit UTF-8-SIG risk register + SHA-256 JSON."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    shadow_ai_count = 0
    copyright_risk_count = 0
    license_risk_count = 0
    high_risk_count = 0

    for row in raw_rows:
        tool_name = str(row.get("tool_name") or "unknown_tool").strip()
        department = str(row.get("department") or "").strip()
        plan_tier = str(row.get("plan_tier") or "").strip()
        raw_opt_out = str(row.get("training_opt_out") or "").strip()
        use_case = str(row.get("use_case") or "").strip()
        data_types = str(row.get("data_types") or "").strip()
        model_license = str(row.get("model_license") or "").strip()

        opt_out_enabled = bool(_TRUTHY_RE.match(raw_opt_out))
        is_free_tier = bool(_FREE_OR_PERSONAL_RE.search(plan_tier))
        has_sensitive = bool(_SENSITIVE_DATA_RE.search(data_types))
        shadow_flag = is_free_tier or (not opt_out_enabled and has_sensitive)
        if shadow_flag:
            shadow_ai_count += 1

        cls = classify_ai_use_case_risk(use_case, model_license)
        art30_4_flag = bool(_COPYRIGHT_30_4_RISK_RE.search(use_case))
        if art30_4_flag:
            copyright_risk_count += 1
        if cls["license_status"] == "restricted_non_commercial":
            license_risk_count += 1

        flags: list[str] = []
        actions: list[str] = []
        if shadow_flag:
            flags.append("SHADOW_AI_OR_NO_OPTOUT")
            actions.append("法人契約ZDRプランへ移行・個人情報投入禁止")
        if cls["risk_tier"] in {"prohibited", "high_risk"}:
            flags.append(f"EU_AI_{cls['risk_tier'].upper()}")
            actions.append("利用停止またはHITL人間審査・影響評価を実施")
        elif cls["risk_tier"] == "transparency":
            flags.append("EU_AI_TRANSPARENCY")
            actions.append("利用者向けAI応答・合成明記を付与")
        if art30_4_flag:
            flags.append("COPYRIGHT_ART30_4_ENJOYMENT")
            actions.append("特定作風・既存表現模倣を禁止し類似性調査を実施")
        if cls["license_status"] == "restricted_non_commercial":
            flags.append("NON_COMMERCIAL_LICENSE")
            actions.append("Apache-2.0/MITまたは商用許諾APIへ切替")

        if (
            cls["risk_tier"] == "prohibited"
            or (shadow_flag and has_sensitive)
            or art30_4_flag
            or cls["license_status"] == "restricted_non_commercial"
            or cls["risk_tier"] == "high_risk"
        ):
            risk_level = "high_risk"
            high_risk_count += 1
        elif flags or not opt_out_enabled:
            risk_level = "medium_risk"
        else:
            risk_level = "approved"

        out_rows.append(
            {
                "tool_name": tool_name,
                "department": department,
                "risk_level": risk_level,
                "shadow_ai": "YES" if shadow_flag else "NO",
                "eu_ai_tier": cls["risk_tier"],
                "license_status": cls["license_status"],
                "art30_4_risk": "YES" if art30_4_flag else "NO",
                "flags": ",".join(flags) if flags else "NONE",
                "recommended_action": " ／ ".join(actions) if actions else "現行統制で継続可（定期年次確認）",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tool_name",
        "department",
        "risk_level",
        "shadow_ai",
        "eu_ai_tier",
        "license_status",
        "art30_4_risk",
        "flags",
        "recommended_action",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "org_name": org_name,
        "total_tools": len(out_rows),
        "shadow_ai_count": shadow_ai_count,
        "copyright_risk_count": copyright_risk_count,
        "license_risk_count": license_risk_count,
        "high_risk_count": high_risk_count,
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
        description="Offline Shadow AI Inventory & Copyright Art. 30-4 Risk Register"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--org-name", default="organization")
    args = parser.parse_args()
    res = audit_ai_inventory_csv(
        args.input_csv,
        args.output_csv,
        args.output_json,
        org_name=args.org_name,
    )
    print(
        f"Audited {res['total_tools']} AI tools offline. "
        f"HighRisk={res['high_risk_count']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
