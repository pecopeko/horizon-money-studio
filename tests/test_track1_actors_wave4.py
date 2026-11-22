"""Comprehensive offline unit tests for Wave 4 Apify PPE Actors (Actors #11-#12)."""

from __future__ import annotations

import httpx
import pytest

from tracks.track1_apify.jp_tokusho_ec_actor.main import audit_tokusho_batch
from tracks.track1_apify.oss_security_txt_actor.main import (
    audit_domain_security_posture,
    evaluate_security_headers,
    parse_security_txt,
    validate_public_origin,
)


def test_jp_tokusho_ec_actor_screens_disclosures_and_dark_patterns() -> None:
    bad = {
        "tokusho_text": "販売業者：A商店 返品：いかなる理由であっても一切返金いたしません。解約は電話のみ。",
        "checkout_text": "初回500円でお試し！",
        "is_subscription": True,
    }
    good = {
        "tokusho_text": (
            "販売業者：株式会社サンプル 運営統括責任者：山田太郎 "
            "所在地：請求があったら遅滞なく開示いたします 電話番号：請求があったら遅滞なく開示いたします "
            "メールアドレス：support@example.co.jp 販売価格：月額2,980円 商品代金以外の必要料金：通信料 "
            "支払方法：クレカ（支払時期：毎月課金） 提供時期：即時 返品・解約条件：瑕疵時返金・管理画面解約 "
            "動作環境：Chrome最新版"
        ),
        "checkout_text": "初回500円、2回目以降は月額2,980円。最低契約期間の定めなし・12ヶ月総額33,280円。",
        "is_subscription": True,
    }
    res = audit_tokusho_batch([bad, good])
    assert res[0]["underwriting_status"] == "high_rejection_risk"
    assert {"SUB-TEASER-TRAP", "SUB-CANCEL-OBSTRUCTION", "NO-REFUND-ABSOLUTE"} <= set(res[0]["rule_ids"])
    assert res[1]["compliance_score"] == 100
    assert res[1]["missing_count"] == 0
    assert res[1]["underwriting_status"] == "pass"


def test_oss_security_txt_actor_ssrf_and_posture_scoring() -> None:
    with pytest.raises(ValueError):
        validate_public_origin("http://127.0.0.1/admin")
    with pytest.raises(ValueError):
        validate_public_origin("http://169.254.169.254/latest/meta-data")

    sec_txt = (
        "# Security disclosures\n"
        "Contact: mailto:security@example.org\n"
        "Expires: 2027-11-01T00:00:00.000Z\n"
        "Encryption: https://8.8.8.8/pgp-key.txt\n"
        "Canonical: https://8.8.8.8/.well-known/security.txt\n"
        "Policy: https://8.8.8.8/security-policy\n"
    )
    parsed = parse_security_txt(sec_txt)
    assert parsed["has_required_fields"] is True
    assert parsed["contacts"] == ["mailto:security@example.org"]

    hdrs = evaluate_security_headers(
        {
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
    )
    assert all(hdrs.values())

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/.well-known/security.txt":
            return httpx.Response(200, text=sec_txt)
        return httpx.Response(
            200,
            text="ok",
            headers={
                "Strict-Transport-Security": "max-age=63072000",
                "Content-Security-Policy": "default-src 'self'",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        audit = audit_domain_security_posture("https://8.8.8.8", client=client)

    assert audit["has_security_txt"] is True
    assert audit["security_posture_score"] == 100
    assert audit["security_txt"]["expires"] == "2027-11-01T00:00:00.000Z"
