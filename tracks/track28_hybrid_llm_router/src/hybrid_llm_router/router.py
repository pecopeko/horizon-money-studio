"""3-Tier Complexity & Privacy-Aware Hybrid LLM Router."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import httpx

from .vault import MaskReport, ReversibleEntityVault


class Tier(str, Enum):
    """Execution tier selected by the Hybrid Router."""

    LOCAL_ONLY = "local_only"
    SMALL_FAST = "small_fast"
    CLOUD_FRONTIER = "cloud_frontier"


@dataclass
class RouteDecision:
    """Transparent routing decision & telemetry record."""

    tier: Tier
    complexity_score: float
    reasons: list[str]
    mask_report: MaskReport
    mask_latency_ms: float


@dataclass
class RouterResponse:
    """End-to-end response after routing, execution, and local rehydration."""

    final_text: str
    raw_llm_text: str
    outbound_prompt: str
    decision: RouteDecision
    model_used: str
    total_latency_ms: float
    prompt_tokens: int
    completion_tokens: int


HIGH_COMPLEXITY_CUES: tuple[str, ...] = (
    "比較",
    "差額",
    "矛盾",
    "優先順位",
    "原因",
    "設計",
    "トレードオフ",
    "段階控除",
    "経過措置",
    "整合性",
    "監査",
    "複数",
    "どちらの会社",
    "再計算",
)

SIMPLE_EXTRACTION_CUES: tuple[str, ...] = (
    "抽出",
    "一行で",
    "JSONに変換",
    "分類",
    "フォーマット",
    "敬語に直して",
    "要約して",
)


def score_task_complexity(masked_prompt: str, mask_report: MaskReport) -> tuple[float, list[str]]:
    """Compute [0.0, 1.0] task complexity score on pseudonymized prompt."""
    score = 0.20
    reasons: list[str] = ["base=0.20"]

    high_hits = [kw for kw in HIGH_COMPLEXITY_CUES if kw in masked_prompt]
    if high_hits:
        bump = min(0.45, 0.15 * len(high_hits))
        score += bump
        reasons.append(f"reasoning_cues({len(high_hits)}:+{bump:.2f})")

    simple_hits = [kw for kw in SIMPLE_EXTRACTION_CUES if kw in masked_prompt]
    if simple_hits and not high_hits:
        score -= 0.12
        reasons.append("simple_extraction(-0.12)")

    # Multiple distinct typed entities (e.g. <<CORP_JP_01>> vs <<CORP_JP_02>>) require relational tracking
    distinct_corps = len(set(re.findall(r"<<CORP_JP_\d+>>", masked_prompt)))
    if distinct_corps >= 2:
        score += 0.25
        reasons.append(f"multi_entity_coref({distinct_corps}:+0.25)")

    numbers_count = len(re.findall(r"\b\d[\d,]*\b", masked_prompt))
    if numbers_count >= 4:
        score += 0.15
        reasons.append(f"numeric_density({numbers_count}:+0.15)")

    if len(masked_prompt) > 600:
        score += 0.10
        reasons.append("long_context(+0.10)")

    bounded = round(max(0.0, min(1.0, score)), 3)
    return bounded, reasons


class HybridLLMRouter:
    """Routes tasks across Local Deterministic/SLM, Small Fast Cloud, and Frontier Reasoning Cloud."""

    def __init__(
        self,
        *,
        openrouter_api_key: str | None = None,
        local_base_url: str | None = None,
        local_model: str = "qwen/qwen3.5-9b",
        fast_cloud_models: list[str] | None = None,
        frontier_cloud_models: list[str] | None = None,
        complexity_threshold: float = 0.45,
        local_fallback_fn: Callable[[str, MaskReport], str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = (openrouter_api_key if openrouter_api_key is not None else os.getenv("OPENROUTER_API_KEY", "")).strip()
        self.local_base_url = (local_base_url or os.getenv("LOCAL_LLM_BASE_URL", "")).strip()
        self.local_model = local_model
        self.fast_cloud_models = fast_cloud_models or [
            "nvidia/nemotron-3.5-lightning:free",
            "dots-studio/dots-3-note-preview:free",
        ]
        self.frontier_cloud_models = frontier_cloud_models or [
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "dots-studio/dots-3-note-preview:free",
            "nvidia/nemotron-3.5-super-vl:free",
        ]
        self.complexity_threshold = complexity_threshold
        self.local_fallback_fn = local_fallback_fn
        self._client = http_client

    def decide_route(self, raw_prompt: str, vault: ReversibleEntityVault) -> RouteDecision:
        """Pseudonymize prompt locally and select optimal execution tier."""
        t0 = time.perf_counter()
        report = vault.pseudonymize(raw_prompt)
        mask_ms = (time.perf_counter() - t0) * 1000.0

        complexity, reasons = score_task_complexity(report.masked_text, report)

        if report.contains_hard_local_only_secret:
            reasons.append("hard_secret_detected->force_local_only")
            return RouteDecision(
                tier=Tier.LOCAL_ONLY,
                complexity_score=complexity,
                reasons=reasons,
                mask_report=report,
                mask_latency_ms=round(mask_ms, 3),
            )

        if complexity >= self.complexity_threshold:
            reasons.append(f"complexity>={self.complexity_threshold}->cloud_frontier")
            tier = Tier.CLOUD_FRONTIER
        else:
            reasons.append(f"complexity<{self.complexity_threshold}->small_fast")
            tier = Tier.SMALL_FAST

        return RouteDecision(
            tier=tier,
            complexity_score=complexity,
            reasons=reasons,
            mask_report=report,
            mask_latency_ms=round(mask_ms, 3),
        )

    def _call_openai_compatible(
        self,
        url: str,
        headers: dict[str, str],
        models: list[str],
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, str, int, int]:
        last_err = ""
        for model in models:
            body: dict[str, Any] = {
                "model": model,
                "max_tokens": 1400,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            try:
                if self._client is not None:
                    resp = self._client.post(url, headers=headers, json=body, timeout=45.0)
                else:
                    with httpx.Client(timeout=45.0) as client:
                        resp = client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                last_err = f"{model}: {exc}"
                continue

            if resp.status_code >= 400:
                last_err = f"{model} HTTP {resp.status_code}: {resp.text[:160]}"
                continue

            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                last_err = f"{model}: empty choices"
                continue
            msg = choices[0].get("message") or {}
            text = str(msg.get("content") or "").strip()
            if not text and msg.get("reasoning"):
                text = str(msg.get("reasoning") or "").strip()
            if not text:
                last_err = f"{model}: empty content"
                continue
            usage = data.get("usage") or {}
            p_tok = int(usage.get("prompt_tokens") or 0)
            c_tok = int(usage.get("completion_tokens") or 0)
            return text, model, p_tok, c_tok

        raise RuntimeError(f"All candidate models failed: {last_err}")

    def execute(
        self,
        raw_prompt: str,
        *,
        system_prompt: str = (
            "あなたは企業実務アシスタントです。入力内の <<CORP_JP_01>> のような仮名トークンは"
            "絶対に書き換えたり省略したりせず、そのまま回答内に維持して出力してください。"
        ),
    ) -> RouterResponse:
        """Execute full local-mask -> tier-route -> LLM -> local-rehydrate pipeline."""
        t_start = time.perf_counter()
        vault = ReversibleEntityVault()
        decision = self.decide_route(raw_prompt, vault)
        outbound = decision.mask_report.masked_text

        if decision.tier == Tier.LOCAL_ONLY:
            if self.local_base_url:
                raw_out, used_model, p_tok, c_tok = self._call_openai_compatible(
                    f"{self.local_base_url.rstrip('/')}/chat/completions",
                    {"Content-Type": "application/json"},
                    [self.local_model],
                    system_prompt,
                    raw_prompt,  # Safe: never leaves localhost
                )
                outbound = "<LOCALHOST_ONLY_NO_CLOUD_EGRESS>"
                final_txt = raw_out
            elif self.local_fallback_fn is not None:
                raw_out = self.local_fallback_fn(raw_prompt, decision.mask_report)
                used_model = "local_deterministic_guard"
                p_tok, c_tok = 0, 0
                outbound = "<LOCAL_DETERMINISTIC_NO_CLOUD_EGRESS>"
                final_txt = raw_out
            else:
                raw_out = (
                    f"[LOCAL_ONLY_GATE] 機密シークレット（{list(decision.mask_report.entity_counts.keys())}）を"
                    "検出したためクラウド送信を遮断し、端末内で安全に処理しました。"
                )
                used_model = "local_deterministic_guard"
                p_tok, c_tok = 0, 0
                outbound = "<LOCAL_DETERMINISTIC_NO_CLOUD_EGRESS>"
                final_txt = raw_out
        else:
            if not self.api_key:
                raise RuntimeError("Cloud tier selected but OPENROUTER_API_KEY is not set.")
            models = (
                self.frontier_cloud_models
                if decision.tier == Tier.CLOUD_FRONTIER
                else self.fast_cloud_models
            )
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/pecopeko/hybrid-llm-reversible-router",
                "X-Title": "Hybrid LLM Reversible Router Benchmark",
            }
            raw_out, used_model, p_tok, c_tok = self._call_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions",
                headers,
                models,
                system_prompt,
                outbound,
            )
            final_txt = vault.rehydrate(raw_out)

        total_ms = (time.perf_counter() - t_start) * 1000.0
        return RouterResponse(
            final_text=final_txt,
            raw_llm_text=raw_out,
            outbound_prompt=outbound,
            decision=decision,
            model_used=used_model,
            total_latency_ms=round(total_ms, 2),
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
        )
