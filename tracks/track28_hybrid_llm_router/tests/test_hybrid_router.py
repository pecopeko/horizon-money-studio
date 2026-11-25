"""Unit tests for Track 28 Reversible Pseudonymizing Hybrid-LLM Router."""

from __future__ import annotations

import httpx

from hybrid_llm_router.router import HybridLLMRouter, Tier
from hybrid_llm_router.vault import (
    ReversibleEntityVault,
    is_valid_mynumber_12,
    is_valid_nta_t_number,
)


def _valid_mynumber_from_11(base11: str) -> str:
    s = 0
    for idx in range(11):
        n = 11 - idx
        p = int(base11[idx])
        q = (n + 1) if n <= 6 else (n - 5)
        s += p * q
    rem = s % 11
    cd = 0 if rem <= 1 else (11 - rem)
    return f"{base11}{cd}"


def test_statutory_checksum_validators() -> None:
    assert is_valid_nta_t_number("T7000012050002") is True  # National Tax Agency
    assert is_valid_nta_t_number("T1180301018771") is True  # Toyota
    assert is_valid_nta_t_number("T2180301018771") is False

    valid_mn = _valid_mynumber_from_11("12345678901")
    assert is_valid_mynumber_12(valid_mn) is True
    bad_last = "0" if valid_mn[-1] != "0" else "1"
    assert is_valid_mynumber_12(valid_mn[:-1] + bad_last) is False


def test_reversible_vault_preserves_entity_coreference_and_rehydrates() -> None:
    vault = ReversibleEntityVault()
    src = (
        "株式会社アルファ（T7000012050002、担当: tanaka@alpha.co.jp）への支払は税込110,000円、"
        "株式会社ベータ（T1180301018771）への支払は税込220,000円です。"
        "なお株式会社アルファは免税事業者です。"
    )
    rep = vault.pseudonymize(src)
    assert "株式会社アルファ" not in rep.masked_text
    assert "株式会社ベータ" not in rep.masked_text
    assert "T7000012050002" not in rep.masked_text
    assert "tanaka@alpha.co.jp" not in rep.masked_text
    # Same entity gets identical token twice, distinct entity gets distinct token
    assert rep.masked_text.count("<<CORP_JP_01>>") == 2
    assert rep.masked_text.count("<<CORP_JP_02>>") == 1

    # Baseline naive redact destroys co-reference
    naive = vault.naive_redact(src)
    assert naive.count("[REDACTED]") >= 5

    # Rehydrate restores exact original names
    llm_reply = "免税対象で負担が増えるのは <<CORP_JP_01>>（連絡先 <<EMAIL_01>>）です。"
    restored = vault.rehydrate(llm_reply)
    assert restored == "免税対象で負担が増えるのは 株式会社アルファ（連絡先 tanaka@alpha.co.jp）です。"


def test_three_tier_routing_and_zero_secret_egress() -> None:
    seen_payloads: list[dict[str, object]] = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(req.content.decode("utf-8"))
        seen_payloads.append(body)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "優先対応先は <<CORP_JP_02>> です。"}}],
                "usage": {"prompt_tokens": 95, "completion_tokens": 18},
            },
        )

    router = HybridLLMRouter(
        openrouter_api_key="sk-or-mock-token-value",
        http_client=httpx.Client(transport=httpx.MockTransport(mock_handler)),
    )

    # 1. Hard secret (API key or MyNumber) -> forced LOCAL_ONLY, zero HTTP calls
    valid_mn = _valid_mynumber_from_11("12345678901")
    r_local = router.execute(f"従業員マイナンバー {valid_mn} と sk-proj-1234567890abcdefghij を確認して")
    assert r_local.decision.tier == Tier.LOCAL_ONLY
    assert len(seen_payloads) == 0

    # 2. Simple formatting -> SMALL_FAST
    r_fast = router.execute("株式会社アルファ宛の挨拶文を一行で敬語に直して")
    assert r_fast.decision.tier == Tier.SMALL_FAST
    assert len(seen_payloads) == 1
    sent_fast = str(seen_payloads[-1])
    assert "株式会社アルファ" not in sent_fast

    # 3. Multi-entity comparison & tax reasoning -> CLOUD_FRONTIER + local rehydration
    r_front = router.execute(
        "株式会社アルファ（税込110,000円・インボイス有）と株式会社ベータ（税込220,000円・インボイス無）の"
        "2026年10月経過措置50%移行後の消費税負担差額を比較し、どちらの会社の契約見直し優先順位が高いか答えてください。"
    )
    assert r_front.decision.tier == Tier.CLOUD_FRONTIER
    assert "株式会社ベータ" not in r_front.outbound_prompt
    assert "株式会社ベータ" in r_front.final_text
