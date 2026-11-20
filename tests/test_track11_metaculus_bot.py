"""End-to-end verification suite for Track 11 — Metaculus FutureEval Quant Bot."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import httpx
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACK11_DIR = REPO_ROOT / "tracks" / "track11_metaculus_futureeval_bot"
TRACK11_SRC = TRACK11_DIR / "src"

if str(TRACK11_SRC) not in sys.path:
    sys.path.insert(0, str(TRACK11_SRC))

from metaculus_quant_bot.backtest import (  # noqa: E402
    brier_score,
    evaluate_predictions,
    metaculus_binary_baseline_scores,
    transform_calibrated_log_odds,
)
from metaculus_quant_bot.forecaster import (  # noqa: E402
    HybridQuantForecaster,
    build_metaculus_cdf,
    extremize_log_odds,
    normalize_multiple_choice_probs,
    pool_binary_signals,
    trimmed_log_odds_mean,
)
from metaculus_quant_bot.market_anchor import (  # noqa: E402
    MarketAnchorMatcher,
    detect_polarity_inversion,
    has_mutually_exclusive_action_conflict,
    score_candidate_match,
    score_date_alignment,
)
from metaculus_quant_bot.metaculus_client import (  # noqa: E402
    MetaculusAuthError,
    MetaculusClient,
    create_forecast_payload,
    parse_post_to_questions,
    validate_forecast_payload,
)
from metaculus_quant_bot.models import (  # noqa: E402
    MarketAnchorMatch,
    MetaculusQuestion,
    NumericScaling,
)


def test_track11_deliverables_and_workflow_exist() -> None:
    required_files = [
        "pyproject.toml",
        "LICENSE",
        "README.md",
        ".env.example",
        "SETUP_AND_FREE_CREDITS_GUIDE.md",
        "BACKTEST_REPORT.md",
        "data/backtest_2026_results.json",
        ".github/workflows/metaculus_futureeval_bot.yml",
        "src/metaculus_quant_bot/__init__.py",
        "src/metaculus_quant_bot/models.py",
        "src/metaculus_quant_bot/metaculus_client.py",
        "src/metaculus_quant_bot/market_anchor.py",
        "src/metaculus_quant_bot/evidence_retriever.py",
        "src/metaculus_quant_bot/forecaster.py",
        "src/metaculus_quant_bot/backtest.py",
        "src/metaculus_quant_bot/cli.py",
        "tests/test_metaculus_bot.py",
    ]
    for rel in required_files:
        path = TRACK11_DIR / rel
        assert path.exists(), f"Missing Track 11 deliverable: {rel}"

    workflow = (TRACK11_DIR / ".github/workflows/metaculus_futureeval_bot.yml").read_text(encoding="utf-8")
    assert "cron:" in workflow
    assert "--dry-run" in workflow
    assert "METACULUS_TOKEN" in workflow

    guide = (TRACK11_DIR / "SETUP_AND_FREE_CREDITS_GUIDE.md").read_text(encoding="utf-8")
    assert "https://www.metaculus.com/futureeval/participate/" in guide
    assert "https://forms.gle/aQdYMq9Pisrf1v7d8" in guide
    assert "33121" in guide


def test_real_empirical_2026_backtest_artifacts_provenance() -> None:
    results = json.loads((TRACK11_DIR / "data/backtest_2026_results.json").read_text(encoding="utf-8"))
    assert results["provenance"]["dataset"] == "forecastingresearch/forecastbench-datasets"
    assert len(results["provenance"]["snapshots_loaded"]) >= 20
    assert results["total_unique_records"] >= 1000
    assert len(results["cohorts"]) == 2

    metac_cohort = results["cohorts"][0]
    assert "Metaculus" in metac_cohort["cohort"]
    assert metac_cohort["train_n"] >= 80
    assert metac_cohort["test_n"] >= 40

    metrics_by_name = {m["strategy"]: m for m in metac_cohort["oos_metrics"]}
    uniform_m = metrics_by_name["1. Uniform 50% Baseline"]
    assert uniform_m["brier_score"] == 0.25
    assert uniform_m["metaculus_baseline_score"] == 0.0

    # OOS calibrated strategy must dramatically beat uniform baseline on real 2026 Metaculus data
    cal_rows = [m for m in metac_cohort["oos_metrics"] if "Calibrated Shrinkage+Extremizing" in m["strategy"]]
    assert len(cal_rows) == 1
    assert cal_rows[0]["brier_score"] < 0.20
    assert cal_rows[0]["metaculus_baseline_score"] > 20.0

    report_md = (TRACK11_DIR / "BACKTEST_REPORT.md").read_text(encoding="utf-8")
    assert "Metaculus Resolved Binary Questions (2026)" in report_md
    assert "Multi-Platform Prediction Markets" in report_md


def test_binary_log_odds_pooling_and_extremizing_calibration() -> None:
    # Trimmed log-odds mean rejects a single hallucinated extreme
    trimmed = trimmed_log_odds_mean([0.62, 0.64, 0.61, 0.63, 0.99], trim_fraction=0.20)
    assert 0.61 <= trimmed <= 0.65

    # Extremizing directionality + strict [0.01, 0.99] log-loss protection
    assert extremize_log_odds(0.75, d=1.25, prior=0.50) > 0.75
    assert extremize_log_odds(0.75, d=0.75, prior=0.50) < 0.75
    assert extremize_log_odds(0.9999, d=2.0, prior=0.50) == 0.99
    assert extremize_log_odds(0.0001, d=2.0, prior=0.50) == 0.01

    anchor = MarketAnchorMatch(
        platform="polymarket",
        market_id="pm-recession",
        question="US recession by end of 2026?",
        url="https://polymarket.com/event/us-recession",
        raw_probability=0.03,
        aligned_probability=0.03,
        similarity_score=0.98,
        liquidity_usd=75_000.0,
        volume_usd=250_000.0,
        date_alignment_score=1.0,
        quality_weight=0.98,
    )
    pooled, diag = pool_binary_signals(
        base_rate_prior=0.35,
        market_anchors=[anchor],
        llm_probabilities=[0.06, 0.08, 0.05],
        extremize_d=1.05,
    )
    assert 0.01 <= pooled <= 0.15
    assert diag["weights"]["market"] > 0.35
    assert diag["weights"]["llm"] > 0.25


@pytest.mark.parametrize(
    ("open_lo", "open_hi", "zero_point", "cdf_size"),
    [
        (False, False, None, 201),
        (True, True, None, 201),
        (True, False, 0.0, 201),
        (False, True, None, 201),
        (False, False, None, 21),
    ],
)
def test_numeric_201_point_strictly_monotonic_cdf_validation(
    open_lo: bool,
    open_hi: bool,
    zero_point: float | None,
    cdf_size: int,
) -> None:
    qtype = "discrete" if cdf_size != 201 else "numeric"
    q = MetaculusQuestion(
        question_id=777,
        post_id=777,
        title="Numeric test",
        question_type=qtype,
        open_lower_bound=open_lo,
        open_upper_bound=open_hi,
        scaling=NumericScaling(
            range_min=1.0,
            range_max=10.0,
            zero_point=zero_point,
            inbound_outcome_count=(cdf_size - 1) if qtype == "discrete" else None,
        ),
    )
    cdf = build_metaculus_cdf(
        percentiles={10: 3.4, 25: 3.7, 50: 3.9, 75: 4.1, 90: 4.4},
        range_min=1.0,
        range_max=10.0,
        open_lower_bound=open_lo,
        open_upper_bound=open_hi,
        zero_point=zero_point,
        cdf_size=cdf_size,
    )
    assert len(cdf) == cdf_size
    payload = create_forecast_payload(qtype, continuous_cdf=cdf)
    assert validate_forecast_payload(q, payload) == []
    diffs = np.diff(cdf)
    assert float(np.min(diffs)) >= 5e-5 - 1e-12
    assert float(np.max(diffs)) <= 0.2 * (200.0 / (cdf_size - 1)) + 1e-6


def test_multiple_choice_simplex_normalization() -> None:
    opts = ["Alpha", "Beta", "Gamma", "Delta"]
    probs = normalize_multiple_choice_probs(
        {"Alpha": 0.95, "Beta": 0.05, "Gamma": 0.0, "Delta": 0.0},
        options=opts,
        dirichlet_alpha=0.35,
    )
    assert set(probs.keys()) == set(opts)
    assert abs(sum(probs.values()) - 1.0) < 1e-6
    assert all(0.005 <= v <= 0.995 for v in probs.values())
    q = MetaculusQuestion(
        question_id=888,
        post_id=888,
        title="MC test",
        question_type="multiple_choice",
        options=opts,
    )
    assert validate_forecast_payload(q, create_forecast_payload("multiple_choice", multiple_choice_probabilities=probs)) == []


def test_polymarket_manifold_matcher_polarity_date_and_guards() -> None:
    inv, _ = detect_polarity_inversion(
        "Will inflation stay above 3% in 2026?",
        "Will inflation stay below 3% in 2026?",
    )
    assert inv is True

    assert has_mutually_exclusive_action_conflict(
        "Will the Fed decrease rates by 25 bps in December 2026?",
        "Will the Fed increase rates by 25 bps in December 2026?",
    )

    q = MetaculusQuestion(
        question_id=10,
        post_id=10,
        title="Will the US Federal Reserve decrease interest rates by 25 bps at the December 2026 meeting?",
        question_type="binary",
        scheduled_resolve_time="2026-12-31",
    )
    matched = score_candidate_match(
        question=q,
        platform="polymarket",
        market_id="pm-fed-dec",
        market_question="Will the Fed decrease interest rates by 25 bps after the December 2026 meeting?",
        market_url="https://polymarket.com/event/fed-dec",
        raw_probability=0.04,
        liquidity_usd=700_000.0,
        volume_usd=2_000_000.0,
        close_date="2026-12-18",
    )
    assert matched is not None
    assert matched.similarity_score >= 0.90
    assert matched.polarity_inverted is False

    # Date mismatch 2026 vs 2028 penalized
    d_score, _ = score_date_alignment(
        "Will US GDP exceed 3% in 2026?",
        "2026-12-31",
        "Will US GDP exceed 3% in 2028?",
        "2028-12-31",
    )
    assert d_score <= 0.15


def test_metaculus_client_api_contract_and_scoring_rules() -> None:
    post = {
        "id": 50001,
        "title": "Binary Q",
        "status": "open",
        "question": {
            "id": 50002,
            "title": "Will event Z occur in 2026?",
            "type": "binary",
            "status": "open",
            "my_forecasts": {"latest": None},
        },
    }
    qs = parse_post_to_questions(post)
    assert len(qs) == 1
    fc = HybridQuantForecaster().forecast(qs[0], enable_network=False)
    receipt = MetaculusClient(token="").submit_forecast(qs[0], fc, dry_run=True)
    assert receipt.validation_errors == []
    assert receipt.dry_run is True

    # Verify HTTP 403 raises MetaculusAuthError explicitly
    mock_http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(403, text="Auth required"))
    )
    with pytest.raises(MetaculusAuthError):
        MetaculusClient(token="", http_client=mock_http).list_open_tournament_questions()

    # Exact Metaculus baseline scoring math check
    assert math.isclose(metaculus_binary_baseline_scores(np.array([0.5]), np.array([1.0]))[0], 0.0, abs_tol=1e-6)
    assert math.isclose(metaculus_binary_baseline_scores(np.array([0.01]), np.array([1.0]))[0], -564.39, abs_tol=0.05)
    assert math.isclose(brier_score(np.array([0.2, 0.8]), np.array([0.0, 1.0])), 0.04)
    ev = evaluate_predictions("unit", [0.85, 0.15], [1.0, 0.0])
    assert ev.metaculus_baseline_score > 70.0
    t_cal = transform_calibrated_log_odds(np.array([0.8]), np.array([0.5]), 0.84, 0.93)
    assert 0.5 < t_cal[0] < 0.8


def test_cli_dry_run_and_zero_key_live_smoke_check() -> None:
    env = {**os.environ, "PYTHONPATH": str(TRACK11_SRC)}
    # Strip any API keys to guarantee pure $0 zero-key dry-run execution
    for key in ("METACULUS_TOKEN", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        env.pop(key, None)

    proc = subprocess.run(
        [sys.executable, "-m", "metaculus_quant_bot.cli", "forecast", "--sample", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, f"Live dry-run CLI failed: {proc.stderr}"
    payload = json.loads(proc.stdout)
    assert payload["sample_mode"] is True
    assert payload["submit_live"] is False
    assert payload["processed_count"] == 3

    by_type = {row["type"]: row for row in payload["forecasts"]}
    assert set(by_type.keys()) == {"binary", "multiple_choice", "numeric"}
    for row in payload["forecasts"]:
        assert row["dry_run"] is True
        assert row["submitted"] is False
        assert row["validation_errors"] == []
        assert row["mode"] == "zero_key_statistical_anchor"

    # Live smoke verification: binary recession question matched live Polymarket/Manifold,
    # numeric FEDFUNDS question produced 201-point CDF and queried FRED!
    assert by_type["numeric"]["cdf_points"] == 201
    assert by_type["binary"]["market_anchors_matched"] >= 1
    assert 0.01 <= by_type["binary"]["binary_probability"] <= 0.50
    assert "fred:FEDFUNDS" in by_type["numeric"]["evidence_status"]
