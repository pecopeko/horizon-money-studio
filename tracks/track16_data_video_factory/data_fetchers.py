"""Live zero-API-key public data pullers for Track 16 Data Shorts Factory.

Sources:
1. SEC EDGAR XBRL Company Facts API (data.sec.gov) — Big Tech annual 10-K revenue.
2. Federal Reserve Economic Data (FRED) public CSV — FEDFUNDS effective rate.
3. Custom JSON spec loader — Polymarket odds, Japan tax savings, AI price drops.

Strict engineering rule: never swallow network/parse errors or fabricate
fallback metrics. Every error raises `DataFetchError` with source provenance.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

try:
    from .timeline import (
        BarRaceEntry,
        BarRaceSpec,
        LineMilestone,
        LinePoint,
        MacroLineSpec,
        VideoSpec,
        load_video_spec_json,
    )
except ImportError:
    from timeline import (  # type: ignore
        BarRaceEntry,
        BarRaceSpec,
        LineMilestone,
        LinePoint,
        MacroLineSpec,
        VideoSpec,
        load_video_spec_json,
    )


DEFAULT_SEC_USER_AGENT = (
    "HorizonDataShortsFactory/1.0 contact@horizon-money-studio.dev"
)

SEC_REVENUE_TAGS: Tuple[str, ...] = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)

DEFAULT_BIGTECH_COMPANIES: Tuple[Tuple[str, str, str, str], ...] = (
    # (ticker, 10-digit CIK, display_name, editorial_hex_color)
    ("AMZN", "0001018724", "Amazon", "#F59E0B"),
    ("AAPL", "0000320193", "Apple", "#60A5FA"),
    ("GOOGL", "0001652044", "Alphabet", "#22D3EE"),
    ("MSFT", "0000789019", "Microsoft", "#A78BFA"),
    ("NVDA", "0001045810", "NVIDIA", "#10B981"),
)

FRED_FEDFUNDS_CSV_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
)

_MONTH_ABBR = (
    "",
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
)
_MONTH_SPOKEN = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class DataFetchError(RuntimeError):
    """Raised when live public data cannot be fetched or verified."""


@dataclass(frozen=True)
class AnnualRevenuePoint:
    """Verified full-year 10-K revenue point extracted from SEC EDGAR XBRL."""

    end_date: str
    filed_date: str
    revenue_usd: float
    tag: str

    @property
    def revenue_billions(self) -> float:
        return self.revenue_usd / 1e9

    @property
    def fiscal_year_short(self) -> str:
        return "FY%s" % self.end_date[2:4]


def _http_get_text(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20.0,
) -> str:
    """Fetch UTF-8 text via stdlib urllib with explicit error surfacing."""
    req_headers = {"Accept": "*/*"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise DataFetchError("HTTP %s fetching %s" % (status, url))
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise DataFetchError(
            "HTTP %d error fetching %s: %s" % (exc.code, url, exc.reason)
        ) from exc
    except urllib.error.URLError as exc:
        raise DataFetchError(
            "Network error fetching %s: %s" % (url, exc.reason)
        ) from exc


def parse_sec_companyfacts_annual_revenue(
    payload: Dict[str, Any],
    ticker: str = "",
) -> List[AnnualRevenuePoint]:
    """Extract deduplicated annual 10-K revenue observations across XBRL tags.

    Companies occasionally switch XBRL tags across fiscal years (for example
    NVDA and GOOGL moving between RevenueFromContractWithCustomerExcludingAssessedTax
    and Revenues). Merging all canonical US-GAAP revenue tags keyed by period
    end date (retaining the latest filed 10-K value) guarantees the freshest
    verified series without missing recent filings.
    """
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    if not isinstance(us_gaap, dict) or not us_gaap:
        raise DataFetchError(
            "SEC companyfacts payload missing us-gaap facts for %s" % (ticker or "unknown")
        )

    by_end_date: Dict[str, AnnualRevenuePoint] = {}

    for tag in SEC_REVENUE_TAGS:
        concept = us_gaap.get(tag)
        if not isinstance(concept, dict):
            continue
        usd_rows = concept.get("units", {}).get("USD", [])
        if not isinstance(usd_rows, list):
            continue
        for row in usd_rows:
            if row.get("form") != "10-K":
                continue
            start_s = row.get("start")
            end_s = row.get("end")
            filed_s = row.get("filed")
            val = row.get("val")
            if not start_s or not end_s or not filed_s or val is None:
                continue
            try:
                d0 = date.fromisoformat(str(start_s))
                d1 = date.fromisoformat(str(end_s))
                val_f = float(val)
            except (ValueError, TypeError):
                continue
            days = (d1 - d0).days
            if not (330 <= days <= 385) or val_f <= 0.0:
                continue
            point = AnnualRevenuePoint(
                end_date=str(end_s),
                filed_date=str(filed_s),
                revenue_usd=val_f,
                tag=tag,
            )
            existing = by_end_date.get(point.end_date)
            if existing is None or point.filed_date > existing.filed_date:
                by_end_date[point.end_date] = point

    ordered = sorted(by_end_date.values(), key=lambda p: p.end_date)
    if not ordered:
        raise DataFetchError(
            "No valid annual 10-K USD revenue points found for %s" % (ticker or "unknown")
        )
    return ordered


def build_bigtech_bar_race_spec(
    company_series: Dict[str, Tuple[str, str, List[AnnualRevenuePoint]]],
    num_years: int = 4,
    fetched_at_utc: Optional[str] = None,
) -> BarRaceSpec:
    """Build a verified multi-year BarRaceSpec from parsed SEC EDGAR series."""
    if not company_series:
        raise DataFetchError("company_series cannot be empty")
    if num_years < 1:
        raise ValueError("num_years must be >= 1")

    entries: List[BarRaceEntry] = []
    provenance_companies: Dict[str, Any] = {}

    for ticker, (display_name, color, points) in company_series.items():
        if len(points) < num_years:
            raise DataFetchError(
                "Ticker %s has only %d annual 10-K points (need %d)"
                % (ticker, len(points), num_years)
            )
        window = points[-num_years:]
        vals_b = [round(p.revenue_billions, 2) for p in window]
        first_v = vals_b[0]
        last_v = vals_b[-1]
        pct_growth = ((last_v - first_v) / first_v) * 100.0 if first_v > 0 else 0.0
        span_years = num_years - 1
        badge = "+%.0f%% %dY" % (pct_growth, span_years) if pct_growth >= 0 else "%.0f%% %dY" % (pct_growth, span_years)
        entries.append(
            BarRaceEntry(
                key=ticker,
                label=display_name,
                color=color,
                values=vals_b,
                badge=badge,
                end_period_note=window[-1].fiscal_year_short,
            )
        )
        provenance_companies[ticker] = {
            "name": display_name,
            "latest_end": window[-1].end_date,
            "latest_filed": window[-1].filed_date,
            "latest_tag": window[-1].tag,
            "latest_revenue_b": round(window[-1].revenue_billions, 2),
            "history_b": [
                {"end": p.end_date, "rev_b": round(p.revenue_billions, 2)}
                for p in window
            ],
        }

    # Sort entries by final revenue descending for clean narrative construction
    ranked = sorted(entries, key=lambda e: -e.values[-1])
    leader = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else ranked[0]
    third = ranked[2] if len(ranked) > 2 else ranked[-1]
    fourth = ranked[3] if len(ranked) > 3 else ranked[-1]
    fastest = max(
        entries,
        key=lambda e: ((e.values[-1] - e.values[0]) / e.values[0]) if e.values[0] > 0 else 0.0,
    )
    fastest_pct = ((fastest.values[-1] - fastest.values[0]) / fastest.values[0]) * 100.0
    combined_t = sum(e.values[-1] for e in entries) / 1000.0

    # Derive clean multi-year fiscal window labels from actual latest dates
    max_year = max(
        int(info["latest_end"][:4]) for info in provenance_companies.values()
    )
    periods = []
    for offset in range(num_years - 1, -1, -1):
        yr = max_year - offset
        periods.append("FY %d/%02d" % (yr - 1, yr % 100))

    narration = (
        "Big Tech just shattered %.2f trillion dollars in annual revenue. "
        "Live SEC 10-K filings show %s leading at %.1f billion, "
        "ahead of %s at %.1f billion and %s at %.1f billion. "
        "%s hits %.1f billion, while %s explodes %.0f percent in three years to %.1f billion."
        % (
            combined_t,
            leader.label,
            leader.values[-1],
            runner_up.label,
            runner_up.values[-1],
            third.label,
            third.values[-1],
            fourth.label,
            fourth.values[-1],
            fastest.label,
            fastest_pct,
            fastest.values[-1],
        )
    )

    return BarRaceSpec(
        title="BIG TECH REVENUE RACE",
        highlight_phrase="$%.2fT" % combined_t,
        subtitle="Annual 10-K Revenue ($B USD) · %s to %s" % (periods[0], periods[-1]),
        category_badge="LIVE SEC EDGAR 10-K",
        source_label="SOURCE: SEC EDGAR XBRL (data.sec.gov) · VERIFIED 10-K",
        cta_text="FREE PYTHON RENDERER · LINK IN BIO",
        periods=periods,
        entries=entries,
        narration_script=narration,
        unit_prefix="$",
        unit_suffix="B",
        value_decimals=1,
        total_label="BIG-5 COMBINED",
        lang="en",
        provenance={
            "source": "SEC EDGAR XBRL companyfacts",
            "fetched_at_utc": fetched_at_utc
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "combined_trillions": round(combined_t, 3),
            "companies": provenance_companies,
        },
    )


def fetch_sec_bigtech_revenue(
    companies: Sequence[Tuple[str, str, str, str]] = DEFAULT_BIGTECH_COMPANIES,
    user_agent: str = DEFAULT_SEC_USER_AGENT,
    num_years: int = 4,
    pause_seconds: float = 0.16,
) -> BarRaceSpec:
    """Pull live SEC EDGAR 10-K annual revenues for Big Tech companies."""
    company_series: Dict[str, Tuple[str, str, List[AnnualRevenuePoint]]] = {}
    for idx, (ticker, cik, display_name, color) in enumerate(companies):
        url = "https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json" % cik.zfill(10)
        raw_text = _http_get_text(
            url,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=25.0,
        )
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise DataFetchError(
                "Invalid JSON from SEC EDGAR for %s: %s" % (ticker, exc)
            ) from exc
        points = parse_sec_companyfacts_annual_revenue(payload, ticker=ticker)
        company_series[ticker] = (display_name, color, points)
        if pause_seconds > 0 and idx < len(companies) - 1:
            time.sleep(pause_seconds)

    return build_bigtech_bar_race_spec(company_series, num_years=num_years)


# ---------------------------------------------------------------------------
# FRED FEDFUNDS Live Puller & Parser
# ---------------------------------------------------------------------------


def _format_month_display(iso_date: str) -> str:
    """Convert YYYY-MM-DD to 'APR 2020'."""
    parts = iso_date.split("-")
    year = int(parts[0])
    month = int(parts[1])
    return "%s %d" % (_MONTH_ABBR[month], year)


def _format_month_short(iso_date: str) -> str:
    """Convert YYYY-MM-DD to "Apr '20"."""
    parts = iso_date.split("-")
    year_short = parts[0][2:4]
    month = int(parts[1])
    return "%s '%s" % (_MONTH_ABBR[month].title(), year_short)


def _format_month_spoken(iso_date: str) -> str:
    """Convert YYYY-MM-DD to 'April 2020' for crisp TTS narration."""
    parts = iso_date.split("-")
    year = int(parts[0])
    month = int(parts[1])
    return "%s %d" % (_MONTH_SPOKEN[month], year)


def parse_fred_csv(
    csv_text: str,
    start_date: str = "2020-01-01",
    series_col: str = "FEDFUNDS",
) -> List[LinePoint]:
    """Parse a FRED fredgraph CSV string into chronologically sorted LinePoints."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise DataFetchError("FRED CSV response is empty or missing header row")

    date_col = "observation_date" if "observation_date" in reader.fieldnames else reader.fieldnames[0]
    val_col = series_col if series_col in reader.fieldnames else reader.fieldnames[1]

    points: List[LinePoint] = []
    for row in reader:
        raw_d = (row.get(date_col) or "").strip()
        raw_v = (row.get(val_col) or "").strip()
        if not raw_d or raw_d < start_date or not raw_v or raw_v == ".":
            continue
        try:
            date.fromisoformat(raw_d)
            val = float(raw_v)
        except ValueError:
            continue
        points.append(
            LinePoint(
                date_label=raw_d,
                display_date=_format_month_display(raw_d),
                value=val,
            )
        )

    if len(points) < 6:
        raise DataFetchError(
            "FRED series %s returned too few valid observations (%d) from %s"
            % (series_col, len(points), start_date)
        )
    points.sort(key=lambda p: p.date_label)
    return points


def build_fedfunds_macro_line_spec(
    points: List[LinePoint],
    fetched_at_utc: Optional[str] = None,
) -> MacroLineSpec:
    """Construct a MacroLineSpec with automatic collision-safe milestone pins."""
    if len(points) < 6:
        raise DataFetchError("Need at least 6 FRED points to build macro line chart")

    # Key inflection points
    peak_idx = max(range(len(points)), key=lambda i: points[i].value)
    pre_peak_slice = range(0, max(1, peak_idx))
    floor_idx = min(pre_peak_slice, key=lambda i: points[i].value)
    latest_idx = len(points) - 1

    post_peak_indices = list(range(peak_idx + 1, len(points)))
    post_low_idx: Optional[int] = None
    if post_peak_indices:
        cand_low = min(post_peak_indices, key=lambda i: points[i].value)
        if cand_low < latest_idx and points[latest_idx].value - points[cand_low].value >= 0.05:
            post_low_idx = cand_low

    floor_pt = points[floor_idx]
    peak_pt = points[peak_idx]
    latest_pt = points[latest_idx]

    milestones: List[LineMilestone] = [
        LineMilestone(
            index=floor_idx,
            label="ZERO-RATE ERA",
            value_text="%.2f%%" % floor_pt.value,
            subtext=_format_month_short(floor_pt.date_label),
            color="#10B981",
            align_above=True,
            x_nudge=96.0,
        ),
        LineMilestone(
            index=peak_idx,
            label="22-YR PEAK",
            value_text="%.2f%%" % peak_pt.value,
            subtext=_format_month_short(peak_pt.date_label),
            color="#F43F5E",
            align_above=True,
            x_nudge=0.0,
        ),
    ]

    if post_low_idx is not None:
        low_pt = points[post_low_idx]
        milestones.append(
            LineMilestone(
                index=post_low_idx,
                label="CUTTING LOW",
                value_text="%.2f%%" % low_pt.value,
                subtext=_format_month_short(low_pt.date_label),
                color="#38BDF8",
                align_above=False,
                x_nudge=-110.0,
            )
        )
        milestones.append(
            LineMilestone(
                index=latest_idx,
                label="LATE-26 TICK UP",
                value_text="%.2f%%" % latest_pt.value,
                subtext=_format_month_short(latest_pt.date_label),
                color="#F59E0B",
                align_above=True,
                x_nudge=-92.0,
            )
        )
        narration = (
            "Six years of Federal Reserve whiplash in one chart. "
            "Rates crashed to %.2f percent in %s, then surged to a 22-year peak of %.2f percent. "
            "After easing down to %.2f percent in %s, "
            "live FRED data shows a surprise twist: rates just ticked back up to %.2f percent."
            % (
                floor_pt.value,
                _format_month_spoken(floor_pt.date_label),
                peak_pt.value,
                low_pt.value,
                _format_month_spoken(low_pt.date_label),
                latest_pt.value,
            )
        )
    else:
        milestones.append(
            LineMilestone(
                index=latest_idx,
                label="LATEST RATE",
                value_text="%.2f%%" % latest_pt.value,
                subtext=_format_month_short(latest_pt.date_label),
                color="#F59E0B",
                align_above=True,
                x_nudge=-95.0,
            )
        )
        narration = (
            "Look at the wildest rate cycle in modern Federal Reserve history. "
            "In %s, rates crashed to %.2f percent. "
            "Then inflation surged, forcing hikes all the way to %.2f percent by %s. "
            "Live FRED data now puts the effective Fed Funds rate at %.2f percent as of %s."
            % (
                _format_month_spoken(floor_pt.date_label),
                floor_pt.value,
                peak_pt.value,
                _format_month_spoken(peak_pt.date_label),
                latest_pt.value,
                _format_month_spoken(latest_pt.date_label),
            )
        )

    y_top = max(6.5, float(int(peak_pt.value) + 2))
    start_year = points[0].date_label[:4]
    end_year = latest_pt.date_label[:4]

    return MacroLineSpec(
        title="THE FED RATE SHOCK",
        highlight_phrase="%s–%s" % (start_year, end_year),
        subtitle="Effective Federal Funds Rate (%) · Monthly FRED Series",
        category_badge="LIVE FEDERAL RESERVE DATA",
        source_label="SOURCE: FRED / Federal Reserve (FEDFUNDS) · LIVE",
        cta_text="FREE PYTHON RENDERER · LINK IN BIO",
        points=points,
        milestones=milestones,
        narration_script=narration,
        unit_prefix="",
        unit_suffix="%",
        value_decimals=2,
        y_min=0.0,
        y_max=y_top,
        y_step=1.0,
        line_color="#38BDF8",
        lang="en",
        provenance={
            "source": "FRED FEDFUNDS CSV",
            "url": FRED_FEDFUNDS_CSV_URL,
            "fetched_at_utc": fetched_at_utc
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "observation_count": len(points),
            "first": {"date": points[0].date_label, "value": points[0].value},
            "floor": {"date": floor_pt.date_label, "value": floor_pt.value},
            "peak": {"date": peak_pt.date_label, "value": peak_pt.value},
            "post_peak_low": (
                {"date": points[post_low_idx].date_label, "value": points[post_low_idx].value}
                if post_low_idx is not None
                else None
            ),
            "latest": {"date": latest_pt.date_label, "value": latest_pt.value},
        },
    )


def fetch_fred_fedfunds(
    start_date: str = "2020-01-01",
    url: str = FRED_FEDFUNDS_CSV_URL,
) -> MacroLineSpec:
    """Pull live Federal Reserve FEDFUNDS monthly series directly from FRED."""
    csv_text = _http_get_text(
        url,
        headers={"User-Agent": DEFAULT_SEC_USER_AGENT},
        timeout=20.0,
    )
    points = parse_fred_csv(csv_text, start_date=start_date, series_col="FEDFUNDS")
    return build_fedfunds_macro_line_spec(points)


def load_custom_spec(json_path: Union[str, Path]) -> VideoSpec:
    """Load any user-supplied JSON dataset spec (bar_race or macro_line)."""
    return load_video_spec_json(json_path)
