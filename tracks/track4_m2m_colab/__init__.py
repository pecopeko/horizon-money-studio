"""Non-invasive Google Colab GPU offload & AFML audit kit for macroTomicro."""

from .afml_colab_auditor import (
    DayBlockBaggingRegressor,
    FeatureAuditRow,
    FixedCapitalReport,
    OrthogonalityAuditReport,
    evaluate_jp_daily_fixed_capital,
    evaluate_us_daily_fixed_capital,
    run_afml_orthogonality_audit,
)

__all__ = [
    "DayBlockBaggingRegressor",
    "FeatureAuditRow",
    "FixedCapitalReport",
    "OrthogonalityAuditReport",
    "evaluate_jp_daily_fixed_capital",
    "evaluate_us_daily_fixed_capital",
    "run_afml_orthogonality_audit",
]
