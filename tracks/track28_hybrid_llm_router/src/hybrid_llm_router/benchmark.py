"""Live empirical benchmark comparing Naive [REDACTED], Always-Frontier, and 3-Tier Hybrid Router."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .router import HybridLLMRouter, Tier
from .vault import ReversibleEntityVault


BENCHMARK_CASES: list[dict[str, Any]] = [
    {
        "id": "C1_MULTI_CORP_INVOICE_50PCT",
        "expected_tier": Tier.CLOUD_FRONTIER.value,
        "prompt": (
            "以下の3社の外注支払データを比較してください。\n"
            "・株式会社アオイ商事（登録番号: T7000012050002、適格請求書あり、月額税込330,000円）\n"
            "・株式会社ベータ企画（免税事業者、月額税込220,000円）\n"
            "・合同会社シグマ制作（免税事業者、月額税込110,000円）\n"
            "なお、株式会社ベータ企画は来月から月額税込110,000円へ減額合意済みですが、合同会社シグマ制作は来月から月額税込330,000円へ増額予定です。"
            "2026年10月のインボイス経過措置50%控除適用下において、『来月』の発注側消費税負担増（インボイス有りと比較した控除不能額）が"
            "最も大きくなる会社名を1社だけ特定し、その控除不能額（円）を答えてください。"
        ),
        "must_contain_after_rehydrate": ["合同会社シグマ制作", "15,000"],
        "alt_accept": ["15000"],
        "secrets": ["株式会社アオイ商事", "株式会社ベータ企画", "合同会社シグマ制作", "T7000012050002"],
    },
    {
        "id": "C2_MULTI_HOST_SLA_ROOT_CAUSE",
        "expected_tier": Tier.CLOUD_FRONTIER.value,
        "prompt": (
            "障害ログの整合性を監査し、根本原因のホストと通知すべき取引先社名を特定してください。\n"
            "1) auth-gw.internal（10.24.8.11）と pay-db.internal（10.24.9.40）でタイムアウトが発生。\n"
            "2) 株式会社デルタ物流向けのWebhookは auth-gw.internal 経由、サクラ電機株式会社向けのWebhookは pay-db.internal 経由です。\n"
            "3) 調査の結果、auth-gw.internal の遅延は 10.24.9.40 のコネクション枯渇からの連鎖であり、"
            "株式会社デルタ物流側は自動リトライで復旧済み、サクラ電機株式会社側のみ欠損が確定しました。\n"
            "最優先でコネクション上限を引き上げるべき内部IPアドレスと、欠損連絡が必要な取引先社名を答えてください。"
        ),
        "must_contain_after_rehydrate": ["10.24.9.40", "サクラ電機株式会社"],
        "alt_accept": [],
        "secrets": ["auth-gw.internal", "pay-db.internal", "10.24.8.11", "10.24.9.40", "株式会社デルタ物流", "サクラ電機株式会社"],
    },
    {
        "id": "C3_SIMPLE_POLITE_REWRITE",
        "expected_tier": Tier.SMALL_FAST.value,
        "prompt": (
            "株式会社ミナト工業の佐藤様（sato@minato-ind.co.jp）宛に、"
            "『請求書受領しました。来週水曜に振り込みます』を丁寧なビジネス敬語の一行メール文に直してください。"
            "宛先の会社名も文頭に残してください。"
        ),
        "must_contain_after_rehydrate": ["株式会社ミナト工業"],
        "alt_accept": [],
        "secrets": ["株式会社ミナト工業", "sato@minato-ind.co.jp"],
    },
    {
        "id": "C4_SIMPLE_JSON_EXTRACT",
        "expected_tier": Tier.SMALL_FAST.value,
        "prompt": (
            "次の文から取引先名と連絡先メールを抽出しJSONに変換してください："
            "『発注先：オリオン情報システム株式会社、窓口メール：billing@orion-sys.jp、納期：12月15日』"
        ),
        "must_contain_after_rehydrate": ["オリオン情報システム株式会社", "billing@orion-sys.jp"],
        "alt_accept": [],
        "secrets": ["オリオン情報システム株式会社", "billing@orion-sys.jp"],
    },
    {
        "id": "C5_HARD_SECRET_MYNUMBER",
        "expected_tier": Tier.LOCAL_ONLY.value,
        "prompt": "年末調整チェック：従業員マイナンバー 123456789018 の扶養控除等申告書は端末内のみで保管確認してください。",
        "must_contain_after_rehydrate": ["端末内"],
        "alt_accept": ["ローカル"],
        "secrets": ["123456789018"],
    },
    {
        "id": "C6_HARD_SECRET_API_KEY",
        "expected_tier": Tier.LOCAL_ONLY.value,
        "prompt": ".envファイルに sk-live-9876543210abcdefghijklm と ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234 が残っていないか確認して",
        "must_contain_after_rehydrate": ["端末内"],
        "alt_accept": ["遮断"],
        "secrets": ["sk-live-9876543210abcdefghijklm", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"],
    },
]


def _check_answer(text: str, required: list[str], alt: list[str]) -> bool:
    for item in required:
        if item in text:
            continue
        if item == "15,000" and any(a in text for a in alt):
            continue
        if alt and any(a in text for a in alt):
            continue
        return False
    return True


def run_live_benchmark(output_path: Path | None = None) -> dict[str, Any]:
    api_key = os.environ["OPENROUTER_API_KEY"].strip()
    router = HybridLLMRouter(openrouter_api_key=api_key)

    results: dict[str, list[dict[str, Any]]] = {
        "naive_redacted_frontier": [],
        "always_frontier_reversible": [],
        "hybrid_3tier_reversible": [],
    }

    sys_prompt = (
        "あなたは正確な企業実務AIです。入力内の <<CORP_JP_01>> や <<PRIVATE_HOST_01>> のような"
        "仮名トークンは絶対に書き換えたり省略したりせず、そのまま回答内に維持してください。簡潔に結論を述べてください。"
    )

    for case in BENCHMARK_CASES:
        cid = case["id"]
        prompt = case["prompt"]
        secrets = case["secrets"]

        # 1. Hybrid 3-Tier Reversible Router
        h_resp = router.execute(prompt, system_prompt=sys_prompt)
        leaked_h = [s for s in secrets if s in h_resp.outbound_prompt]
        ok_h = _check_answer(h_resp.final_text, case["must_contain_after_rehydrate"], case["alt_accept"])
        results["hybrid_3tier_reversible"].append(
            {
                "case_id": cid,
                "tier": h_resp.decision.tier.value,
                "complexity": h_resp.decision.complexity_score,
                "model_used": h_resp.model_used,
                "latency_ms": h_resp.total_latency_ms,
                "mask_latency_ms": h_resp.decision.mask_latency_ms,
                "prompt_tokens": h_resp.prompt_tokens,
                "completion_tokens": h_resp.completion_tokens,
                "leaked_secrets": len(leaked_h),
                "correct": ok_h,
                "answer_preview": h_resp.final_text[:220],
            }
        )

        # 2. Naive [REDACTED] + Frontier (for cloud-eligible comparison cases C1-C4)
        vault_naive = ReversibleEntityVault()
        naive_prompt = vault_naive.naive_redact(prompt)
        t0 = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        raw_n, mod_n, pt_n, ct_n = router._call_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            headers,
            router.frontier_cloud_models,
            "あなたは正確な企業実務AIです。簡潔に結論を述べてください。",
            naive_prompt,
        )
        lat_n = round((time.perf_counter() - t0) * 1000.0, 2)
        leaked_n = [s for s in secrets if s in naive_prompt]
        ok_n = _check_answer(raw_n, case["must_contain_after_rehydrate"], case["alt_accept"])
        results["naive_redacted_frontier"].append(
            {
                "case_id": cid,
                "model_used": mod_n,
                "latency_ms": lat_n,
                "prompt_tokens": pt_n,
                "completion_tokens": ct_n,
                "leaked_secrets": len(leaked_n),
                "correct": ok_n,
                "answer_preview": raw_n[:220],
            }
        )

        # 3. Always-Frontier + Reversible Vault (all 6 sent to frontier after pseudonymize)
        vault_f = ReversibleEntityVault()
        rep_f = vault_f.pseudonymize(prompt)
        t1 = time.perf_counter()
        raw_f, mod_f, pt_f, ct_f = router._call_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            headers,
            router.frontier_cloud_models,
            sys_prompt,
            rep_f.masked_text,
        )
        final_f = vault_f.rehydrate(raw_f)
        lat_f = round((time.perf_counter() - t1) * 1000.0, 2)
        leaked_f = [s for s in secrets if s in rep_f.masked_text]
        ok_f = _check_answer(final_f, case["must_contain_after_rehydrate"], case["alt_accept"])
        results["always_frontier_reversible"].append(
            {
                "case_id": cid,
                "model_used": mod_f,
                "latency_ms": lat_f,
                "prompt_tokens": pt_f,
                "completion_tokens": ct_f,
                "leaked_secrets": len(leaked_f),
                "correct": ok_f,
                "answer_preview": final_f[:220],
            }
        )

    summary: dict[str, Any] = {}
    for method, rows in results.items():
        n = len(rows)
        summary[method] = {
            "cases": n,
            "accuracy_count": sum(1 for r in rows if r["correct"]),
            "accuracy_pct": round(100.0 * sum(1 for r in rows if r["correct"]) / n, 1),
            "mean_latency_ms": round(sum(r["latency_ms"] for r in rows) / n, 1),
            "total_tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows),
            "frontier_calls": sum(
                1 for r in rows if "550b" in r["model_used"] or "super" in r["model_used"]
            ),
            "total_leaked_secrets": sum(r["leaked_secrets"] for r in rows),
        }

    payload = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "details": results,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "data" / "benchmark_results.json"
    res = run_live_benchmark(output_path=out)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
