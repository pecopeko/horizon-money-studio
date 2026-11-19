"""Apify Pay-Per-Event Actor: Japan METI ★3/★4 Supply Chain Security, PPC SLA & Email Auth Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "mfa_privileged",
        "title": "Privileged Account & MFA Enforcement",
        "criterion": "METI Star-3/Star-4 Account Security",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:mfa|多要素認証|二要素|2fa|fido2|webauthn|パスキー|特権id|最小権限|pam)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:mfa未導入|多要素認証なし|パスワードのみ|id共有|特権共有)",
            re.I,
        ),
    },
    {
        "id": "edr_vuln_patch",
        "title": "EDR Deployment & Critical CVE Patch SLA",
        "criterion": "METI Star-3/Star-4 Endpoint & Vulnerability Mgmt",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:edr|epp|マルウェア|脆弱性|cve|セキュリティパッチ|sbom|waf|csirt|自動更新)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:edr未導入|パッチ適用なし|サポート切れ|eol放置)",
            re.I,
        ),
    },
    {
        "id": "backup_321_drill",
        "title": "Offline/Immutable 3-2-1 Backup & Restore Drills",
        "criterion": "METI Star-3/Star-4 Ransomware Resilience",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:バックアップ|backup|3-2-1|オフライン保管|immutable|イミュータブル|暗号化バックアップ|復旧訓練|bcp)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:バックアップ未実施|バックアップなし|復旧テストなし)",
            re.I,
        ),
    },
    {
        "id": "incident_ppc_sla",
        "title": "Incident Escalation & PPC Breach Reporting (3-5d / 30d)",
        "criterion": "Revised APPI Art. 26 / METI Star-4 CSIRT",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:速報|確報|個人情報保護委員会|ppc|3.{0,3}5日|30日|60日|24時間|72時間|初動対応|緊急連絡)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:報告期限なし|連絡体制なし|通知義務なし)",
            re.I,
        ),
    },
    {
        "id": "trade_secret_3req",
        "title": "Unfair Competition Prevention Act Trade Secret Controls",
        "criterion": "Trade Secret Confidentiality Marking & Access Control",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:営業秘密|秘密管理性|マル秘|アクセス制御|nda|秘密保持|持ち出し制限|dlp|usb禁止|生成ai入力禁止)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:全社員閲覧可|持ち出し自由|usb制限なし|パブリック共有)",
            re.I,
        ),
    },
    {
        "id": "subprocessor_control",
        "title": "Subprocessor Approval & Back-to-Back Contracts",
        "criterion": "METI Supply-Chain Subcontractor Governance",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:再委託|委託先|サプライヤー|事前承諾|書面承諾|契約書|同等水準|年次点検|監査)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:無断再委託|委託先チェックなし)",
            re.I,
        ),
    },
    {
        "id": "log_encryption",
        "title": "TLS 1.2+/AES-256 Encryption & Audit Log Retention",
        "criterion": "METI Encryption & Tamper-Resistant Forensics",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:tls\s*1\.[23]|https|aes-?256|暗号化|監査ログ|syslog|siem|改ざん|1年以上|90日以上)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:平文保存|http利用|ログ未取得|ログ保存なし)",
            re.I,
        ),
    },
)

_SPF_LOOKUP_RE = re.compile(
    r"(?:^|\s)(?:include:|redirect=|exists:|(?:[+\-~?])?(?:a|mx|ptr)(?=[:/\s]|$))",
    re.I,
)


def parse_email_auth_posture(spf_record: str = "", dmarc_record: str = "") -> dict[str, Any]:
    """Validate SPF v=spf1 qualifier/lookup count (<=10) and DMARC v=DMARC1 policy posture."""
    spf = str(spf_record or "").strip()
    dmarc = str(dmarc_record or "").strip()
    warnings: list[str] = []

    spf_valid = bool(re.search(r"\bv=spf1\b", spf, re.I))
    spf_qualifier = "missing"
    spf_lookups = 0

    if not spf:
        warnings.append("Missing SPF TXT record.")
    elif not spf_valid:
        spf_qualifier = "invalid"
        warnings.append("Invalid SPF record: must start with v=spf1.")
    else:
        if re.search(r"(?:^|\s)-all(?:\s|$)", spf, re.I):
            spf_qualifier = "-all"
        elif re.search(r"(?:^|\s)~all(?:\s|$)", spf, re.I):
            spf_qualifier = "~all"
            warnings.append("SPF softfail (~all); prefer hardfail (-all) for Star-4.")
        elif re.search(r"(?:^|\s)\+all(?:\s|$)", spf, re.I):
            spf_qualifier = "+all"
            warnings.append("Critical insecure SPF +all allows arbitrary spoofing.")
        elif re.search(r"(?:^|\s)\?all(?:\s|$)", spf, re.I):
            spf_qualifier = "?all"
            warnings.append("Neutral SPF (?all) provides weak spoofing protection.")
        else:
            spf_qualifier = "none"
            warnings.append("SPF missing terminating all mechanism (-all / ~all).")

        spf_lookups = len(_SPF_LOOKUP_RE.findall(spf))
        if spf_lookups > 10:
            warnings.append(f"SPF DNS lookup overflow: {spf_lookups} lookups (>10 RFC 7208 limit).")

    dmarc_valid = bool(re.search(r"\bv=DMARC1\b", dmarc, re.I))
    dmarc_policy = "missing"
    pct = 100
    rua_configured = False

    if not dmarc:
        warnings.append("Missing DMARC _dmarc TXT record.")
    elif not dmarc_valid:
        dmarc_policy = "invalid"
        warnings.append("Invalid DMARC record: must contain v=DMARC1.")
    else:
        pm = re.search(r"(?:^|[;\s])p\s*=\s*(reject|quarantine|none)\b", dmarc, re.I)
        dmarc_policy = pm.group(1).lower() if pm else "missing"
        if dmarc_policy == "missing":
            warnings.append("DMARC missing p=reject|quarantine|none policy.")
        elif dmarc_policy == "none":
            warnings.append("DMARC monitoring-only p=none does not block spoofed mail.")
        elif dmarc_policy == "quarantine":
            warnings.append("DMARC p=quarantine meets Star-3; p=reject recommended for Star-4.")

        pct_m = re.search(r"(?:^|[;\s])pct\s*=\s*(\d{1,3})\b", dmarc, re.I)
        if pct_m:
            pct = int(pct_m.group(1))
            if pct < 100:
                warnings.append(f"DMARC pct={pct} is partial enforcement; set pct=100.")

        rua_configured = bool(re.search(r"(?:^|[;\s])rua\s*=\s*mailto:", dmarc, re.I))
        if not rua_configured:
            warnings.append("DMARC rua=mailto:... reporting address recommended.")

    score = 0
    if spf_valid:
        score += 20
        if spf_qualifier == "-all":
            score += 20
        elif spf_qualifier == "~all":
            score += 12
        elif spf_qualifier == "?all":
            score += 4
        if spf_lookups <= 10:
            score += 10
    if dmarc_valid:
        score += 20
        if dmarc_policy == "reject":
            score += 20
        elif dmarc_policy == "quarantine":
            score += 14
        elif dmarc_policy == "none":
            score += 4
        if pct < 100 and dmarc_policy not in ("none", "missing"):
            score = max(0, score - 5)
        if rua_configured:
            score += 10
    score = min(100, max(0, score))

    return {
        "spf_valid": spf_valid,
        "spf_qualifier": spf_qualifier,
        "spf_lookups": spf_lookups,
        "dmarc_valid": dmarc_valid,
        "dmarc_policy": dmarc_policy,
        "pct": pct,
        "rua_configured": rua_configured,
        "score": score,
        "warnings": warnings,
    }


def audit_meti_security_item(
    checksheet_text: str,
    *,
    spf_record: str = "",
    dmarc_record: str = "",
    org_name: str = "organization",
) -> dict[str, Any]:
    """Audit Japanese supply-chain security policy text and SPF/DMARC posture."""
    normalized = str(checksheet_text or "").replace("\u3000", " ").strip()
    email_auth = parse_email_auth_posture(spf_record, dmarc_record)

    findings: list[dict[str, Any]] = []
    passed_pillars: list[str] = []
    raw_score = 0

    for pillar in _PILLARS:
        matched = bool(pillar["pattern"].search(normalized))
        negated = bool(pillar["anti_pattern"].search(normalized))
        if matched and not negated:
            raw_score += int(pillar["weight"])
            passed_pillars.append(str(pillar["id"]))
        else:
            findings.append(
                {
                    "rule_id": f"METI-{pillar['id'].upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    email_pts = round((int(email_auth["score"]) / 100.0) * 10)
    raw_score += email_pts
    if (
        email_auth["spf_valid"]
        and email_auth["dmarc_valid"]
        and email_auth["dmarc_policy"] in {"reject", "quarantine"}
        and int(email_auth["spf_lookups"]) <= 10
    ):
        passed_pillars.append("email_auth_dmarc")
    else:
        sev = "high" if email_auth["spf_qualifier"] == "+all" or not email_auth["dmarc_valid"] else "medium"
        findings.append(
            {
                "rule_id": "METI-EMAIL_AUTH_DMARC",
                "title": "Email Spoofing Defense (SPF / DMARC)",
                "severity": sev,
                "warnings": email_auth["warnings"],
            }
        )

    score = min(100, max(0, raw_score))
    if (
        score >= 88
        and email_auth["dmarc_policy"] == "reject"
        and email_auth["spf_valid"]
        and int(email_auth["spf_lookups"]) <= 10
    ):
        star_rating = "★4相当"
        status = "pass"
    elif score >= 70:
        star_rating = "★3相当"
        status = "warn"
    else:
        star_rating = "★3未満（要是正）"
        status = "fail"

    return {
        "org_name": org_name,
        "score": score,
        "star_rating": star_rating,
        "status": status,
        "passed_count": len(passed_pillars),
        "total_pillars": len(_PILLARS) + 1,
        "passed_pillars": passed_pillars,
        "findings_count": len(findings),
        "findings": findings,
        "email_auth": email_auth,
    }


def audit_meti_security_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of supply-chain security policy & DNS records."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_meti_security_item(
            checksheet_text=str(entry.get("checksheet_text") or entry.get("policy_text") or ""),
            spf_record=str(entry.get("spf_record") or ""),
            dmarc_record=str(entry.get("dmarc_record") or ""),
            org_name=str(entry.get("org_name") or f"org-{idx}"),
        )
        results.append({"index": idx, **res})
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        items = actor_input.get("items") or []
        if not isinstance(items, list):
            raise ValueError("'items' input must be a list of objects.")
        for rec in audit_meti_security_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="checksheet_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
