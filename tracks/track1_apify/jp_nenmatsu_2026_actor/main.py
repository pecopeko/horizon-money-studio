"""Apify Pay-Per-Event Actor: Japan 2026 (Reiwa 8) Year-End Tax Adjustment & Payroll CSV Auditor.

Statutorily verifies Japanese employee payroll records against National Tax Agency (`nta.go.jp`)
Reiwa 8 (2026-12-01 effective) Year-End Tax Adjustment tables:
- 740,000 JPY minimum employment income deduction + 219.1M-220M JPY adjustment notches + 別表第五 4,000 JPY steps
- 1,040,000 JPY basic deduction up to 4,890,000 JPY total income (670,000 JPY up to 6,550,000 JPY; 620,000 JPY up to 23,500,000 JPY)
- 620,000 JPY (1,360,000 JPY salary) dependent & spouse deduction threshold
- 9-step Special Relative Deduction (`特定親族特別控除`, ages 19-22, 620,001-1,230,000 JPY total income / 1,360,001-1,970,000 JPY salary)

Charges `$0.002` per `employee_audited` ($2.00 per 1,000 employees). Malformed rows are not charged.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

try:
    from apify import Actor
except ImportError:  # Allow local unit testing without Apify cloud runtime installed.
    Actor = None  # type: ignore[assignment]

try:
    from .calculator_core import (
        DependentInput,
        HouseholdTaxInput,
        NenmatsuInputError,
        STATUTORY_EFFECTIVE_DATE_R8,
        simulate_wall_checkpoints,
    )
    from .csv_auditor_core import (
        audit_employee_dict,
        decode_payroll_csv_bytes,
    )
except ImportError:
    from calculator_core import (  # type: ignore[no-redef]
        DependentInput,
        HouseholdTaxInput,
        NenmatsuInputError,
        STATUTORY_EFFECTIVE_DATE_R8,
        simulate_wall_checkpoints,
    )
    from csv_auditor_core import (  # type: ignore[no-redef]
        audit_employee_dict,
        decode_payroll_csv_bytes,
    )

CHARGE_EVENT_NAME = "employee_audited"


class ActorInputModel(BaseModel):
    """Pydantic v2 input contract for `jp-nenmatsu-2026-tax-payroll-auditor`."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    employees: list[Any] = Field(default_factory=list)
    csv_text: str | None = Field(default=None, alias="csvText")
    csv_base64: str | None = Field(default=None, alias="csvBase64")
    include_wall_simulation: bool = Field(default=False, alias="includeWallSimulation")


def _extract_csv_rows(csv_text: str) -> list[dict[str, Any]]:
    stripped = csv_text.lstrip("\ufeff").strip()
    if not stripped:
        return []
    reader = csv.DictReader(io.StringIO(stripped))
    if not reader.fieldnames:
        raise NenmatsuInputError("CSV header row is missing.")
    return [
        dict(r)
        for r in reader
        if any(v is not None and str(v).strip() != "" for v in r.values())
    ]


def _error_dataset_item(*, row_number: int, employee_id: str, error: str) -> dict[str, Any]:
    return {
        "row_number": row_number,
        "employee_id": employee_id,
        "employee_name": employee_id,
        "department": "未設定",
        "status": "parse_error",
        "statutory_effective_date": STATUTORY_EFFECTIVE_DATE_R8,
        "salary_yen": None,
        "statutory_annual_tax_r8_yen": None,
        "tax_overpayment_yen": 0,
        "tax_underpayment_yen": 0,
        "findings_count": 0,
        "findings": [],
        "error": error,
    }


def audit_actor_payload(raw_input: dict[str, Any]) -> list[tuple[dict[str, Any], bool]]:
    """Validate and audit all input employee dicts + inline/Base64 CSV rows.

    Returns a list of `(dataset_item_dict, is_billable)` tuples.
    """
    parsed_input = ActorInputModel.model_validate(raw_input or {})
    combined_rows: list[Any] = list(parsed_input.employees)
    detected_encoding = "json"

    if parsed_input.csv_text and parsed_input.csv_text.strip():
        try:
            combined_rows.extend(_extract_csv_rows(parsed_input.csv_text))
            detected_encoding = "utf-8"
        except NenmatsuInputError as exc:
            return [(_error_dataset_item(row_number=1, employee_id="CSV-TEXT", error=str(exc)), False)]

    if parsed_input.csv_base64 and parsed_input.csv_base64.strip():
        try:
            raw_bytes = base64.b64decode(parsed_input.csv_base64.strip(), validate=True)
            decoded_text, detected_encoding = decode_payroll_csv_bytes(raw_bytes)
            combined_rows.extend(_extract_csv_rows(decoded_text))
        except Exception as exc:
            return [(_error_dataset_item(row_number=1, employee_id="CSV-BASE64", error=str(exc)), False)]

    results: list[tuple[dict[str, Any], bool]] = []
    for idx, entry in enumerate(combined_rows, start=1):
        if not isinstance(entry, dict):
            results.append(
                (
                    _error_dataset_item(
                        row_number=idx,
                        employee_id=f"EMP-{idx:04d}",
                        error=f"Expected JSON object row, got {type(entry).__name__}.",
                    ),
                    False,
                )
            )
            continue

        try:
            rec = audit_employee_dict(entry, row_number=idx)
            item = rec.to_dict()
            item["statutory_effective_date"] = STATUTORY_EFFECTIVE_DATE_R8
            item["detected_encoding"] = detected_encoding
            item["findings_count"] = len(rec.findings)

            if parsed_input.include_wall_simulation:
                sim_inp = HouseholdTaxInput(
                    salary_yen=rec.salary_yen,
                    dependents=(DependentInput(name="特定親族モデル", age=20, salary_yen=1_520_000),),
                )
                item["wall_checkpoints"] = simulate_wall_checkpoints(sim_inp, target="child")

            results.append((item, True))
        except (NenmatsuInputError, ValueError) as exc:
            fallback_id = str(
                entry.get("employee_id")
                or entry.get("社員番号")
                or f"EMP-{idx:04d}"
            )
            results.append((_error_dataset_item(row_number=idx, employee_id=fallback_id, error=str(exc)), False))

    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' SDK is required to execute the Actor runtime.")

    async with Actor:
        actor_input = await Actor.get_input() or {}
        outcomes = audit_actor_payload(actor_input)
        for item, billable in outcomes:
            await Actor.push_data(item)
            if billable:
                await Actor.charge(event_name=CHARGE_EVENT_NAME, count=1)


if __name__ == "__main__":
    asyncio.run(main())
