"""Unit & parity tests for Track 25: NENMATSUGATE (`nenmatsu-2026-csv-auditor`).

Tests exact 1-yen National Tax Agency (`nta.go.jp`) statutory boundaries for Reiwa 8 (2026)
vs Reiwa 7 (2025), Shift-JIS (`cp932`) & UTF-8-BOM CSV roundtrips, CLI exit codes,
Python-vs-JS exact yen parity, and Apify Pay-Per-Event (`$0.002` / `employee_audited`) schemas.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess
import pytest

from tracks.track1_apify.jp_nenmatsu_2026_actor import main as actor_mod
from tracks.track25_nenmatsu_2026 import (
    DependentInput,
    HouseholdTaxInput,
    NenmatsuInputError,
    audit_employee_dict,
    audit_payroll_csv_bytes,
    audit_payroll_csv_text,
    build_sample_audit_csv,
    calculate_household_year_tax,
    compare_r8_vs_r7,
    compute_basic_deduction,
    compute_employment_income,
    compute_income_adjustment_deduction,
    compute_national_income_tax,
    evaluate_dependent,
    evaluate_spouse_deduction,
    export_audit_report_bytes,
    simulate_wall_checkpoints,
)
from tracks.track25_nenmatsu_2026.cli import main as cli_main


@pytest.mark.parametrize(
    ("salary_yen", "expected_r8", "expected_r7"),
    [
        (0, 0, 0),
        (650_999, 0, 0),
        (651_000, 0, 1_000),
        (740_999, 0, 90_999),
        (741_000, 1_000, 91_000),
        (1_030_000, 290_000, 380_000),
        (1_230_000, 490_000, 580_000),
        (1_230_001, 490_001, 580_001),
        (1_360_000, 620_000, 710_000),
        (1_360_001, 620_001, 710_001),
        (1_590_000, 850_000, 940_000),
        (1_780_000, 1_040_000, 1_130_000),
        (1_880_000, 1_140_000, 1_230_000),
        (1_899_999, 1_159_999, 1_249_999),
        (1_900_000, 1_160_000, 1_250_000),
        (1_970_000, 1_230_000, 1_297_600),
        (2_015_999, 1_275_999, 1_328_400),
        (2_016_000, 1_276_000, 1_331_200),
        (2_060_000, 1_320_000, 1_362_000),
        (2_070_000, 1_330_000, 1_367_600),
        (2_190_999, 1_450_999, 1_451_600),
        (2_191_000, 1_451_000, 1_451_600),
        (2_192_999, 1_451_000, 1_454_400),
        (2_193_000, 1_453_000, 1_454_400),
        (2_195_999, 1_453_000, 1_454_400),
        (2_196_000, 1_456_000, 1_457_200),
        (2_199_999, 1_456_000, 1_457_200),
        (2_200_000, 1_460_000, 1_460_000),
        (3_599_999, 2_437_200, 2_437_200),
        (3_600_000, 2_440_000, 2_440_000),
        (4_000_000, 2_760_000, 2_760_000),
        (4_751_999, 3_358_400, 3_358_400),
        (4_752_000, 3_361_600, 3_361_600),
        (6_599_999, 4_836_800, 4_836_800),
        (6_600_000, 4_840_000, 4_840_000),
        (6_655_556, 4_890_000, 4_890_000),
        (6_655_557, 4_890_001, 4_890_001),
        (8_500_000, 6_550_000, 6_550_000),
        (10_000_000, 8_050_000, 8_050_000),
    ],
)
def test_nta_no1410_employment_income_exact_1yen_boundaries(
    salary_yen: int,
    expected_r8: int,
    expected_r7: int,
) -> None:
    assert compute_employment_income(salary_yen, tax_year=2026) == expected_r8
    assert compute_employment_income(salary_yen, tax_year=2025) == expected_r7


@pytest.mark.parametrize(
    ("total_income", "expected_r8", "expected_r7"),
    [
        (0, 1_040_000, 950_000),
        (1_320_000, 1_040_000, 950_000),
        (1_320_001, 1_040_000, 880_000),
        (3_360_000, 1_040_000, 880_000),
        (3_360_001, 1_040_000, 680_000),
        (4_890_000, 1_040_000, 680_000),
        (4_890_001, 670_000, 630_000),
        (6_550_000, 670_000, 630_000),
        (6_550_001, 620_000, 580_000),
        (23_500_000, 620_000, 580_000),
        (23_500_001, 480_000, 480_000),
        (24_000_000, 480_000, 480_000),
        (24_000_001, 320_000, 320_000),
        (24_500_000, 320_000, 320_000),
        (24_500_001, 160_000, 160_000),
        (25_000_000, 160_000, 160_000),
        (25_000_001, 0, 0),
    ],
)
def test_nta_no1199_basic_deduction_exact_boundaries_and_nonresident(
    total_income: int,
    expected_r8: int,
    expected_r7: int,
) -> None:
    amt_r8, _ = compute_basic_deduction(total_income, tax_year=2026, is_resident=True)
    amt_r7, _ = compute_basic_deduction(total_income, tax_year=2025, is_resident=True)
    assert amt_r8 == expected_r8
    assert amt_r7 == expected_r7

    # NTA Q&A Q6-4 non-resident cap: 620,000 in R8 vs 580,000 in R7 up to 23.5M
    nonres_r8, _ = compute_basic_deduction(1_000_000, tax_year=2026, is_resident=False)
    nonres_r7, _ = compute_basic_deduction(1_000_000, tax_year=2025, is_resident=False)
    assert nonres_r8 == 620_000
    assert nonres_r7 == 580_000


@pytest.mark.parametrize(
    ("salary_yen", "expected_cat", "expected_deduction", "expected_fuyo"),
    [
        (0, "tokutei_fuyo", 630_000, True),
        (1_230_000, "tokutei_fuyo", 630_000, True),
        (1_360_000, "tokutei_fuyo", 630_000, True),
        (1_360_001, "tokutei_shinzoku_tokubetsu", 630_000, False),
        (1_590_000, "tokutei_shinzoku_tokubetsu", 630_000, False),
        (1_590_001, "tokutei_shinzoku_tokubetsu", 610_000, False),
        (1_640_000, "tokutei_shinzoku_tokubetsu", 610_000, False),
        (1_640_001, "tokutei_shinzoku_tokubetsu", 510_000, False),
        (1_690_000, "tokutei_shinzoku_tokubetsu", 510_000, False),
        (1_690_001, "tokutei_shinzoku_tokubetsu", 410_000, False),
        (1_740_000, "tokutei_shinzoku_tokubetsu", 410_000, False),
        (1_740_001, "tokutei_shinzoku_tokubetsu", 310_000, False),
        (1_790_000, "tokutei_shinzoku_tokubetsu", 310_000, False),
        (1_790_001, "tokutei_shinzoku_tokubetsu", 210_000, False),
        (1_840_000, "tokutei_shinzoku_tokubetsu", 210_000, False),
        (1_840_001, "tokutei_shinzoku_tokubetsu", 110_000, False),
        (1_890_000, "tokutei_shinzoku_tokubetsu", 110_000, False),
        (1_890_001, "tokutei_shinzoku_tokubetsu", 60_000, False),
        (1_940_000, "tokutei_shinzoku_tokubetsu", 60_000, False),
        (1_940_001, "tokutei_shinzoku_tokubetsu", 30_000, False),
        (1_970_000, "tokutei_shinzoku_tokubetsu", 30_000, False),
        (1_970_001, "ineligible_over_1230k", 0, False),
    ],
)
def test_nta_no1177_all_9_steps_tokutei_shinzoku_1yen_boundaries(
    salary_yen: int,
    expected_cat: str,
    expected_deduction: int,
    expected_fuyo: bool,
) -> None:
    res = evaluate_dependent(DependentInput(name="大学生", age=20, salary_yen=salary_yen), tax_year=2026)
    assert res.category == expected_cat
    assert res.deduction_yen == expected_deduction
    assert res.is_fuyo_shinzoku is expected_fuyo


def test_fuyo_and_spouse_deduction_r8_tiers_and_178m_wall() -> None:
    # General (17yo -> 380k), elderly non-cohabiting (72yo -> 480k), elderly cohabiting (75yo -> 580k)
    assert evaluate_dependent(DependentInput(age=17, salary_yen=1_360_000), 2026).deduction_yen == 380_000
    assert evaluate_dependent(DependentInput(age=17, salary_yen=1_360_001), 2026).deduction_yen == 0
    assert (
        evaluate_dependent(DependentInput(age=72, salary_yen=1_360_000, is_cohabiting_ascendant=False), 2026).deduction_yen
        == 480_000
    )
    assert (
        evaluate_dependent(DependentInput(age=75, salary_yen=1_360_000, is_cohabiting_ascendant=True), 2026).deduction_yen
        == 580_000
    )

    # Spouse deduction & Special Spouse Deduction across taxpayer bands
    sp_elderly = evaluate_spouse_deduction(
        has_spouse=True,
        taxpayer_total_income_yen=8_000_000,
        spouse_salary_yen=1_360_000,
        spouse_age=71,
        tax_year=2026,
    )
    assert sp_elderly.category == "haigusha_kojo_elderly"
    assert sp_elderly.deduction_yen == 480_000

    sp_special_top = evaluate_spouse_deduction(
        has_spouse=True,
        taxpayer_total_income_yen=9_200_000,
        spouse_salary_yen=1_690_000,
        spouse_age=45,
        tax_year=2026,
    )
    assert sp_special_top.deduction_yen == 260_000

    sp_special_edge = evaluate_spouse_deduction(
        has_spouse=True,
        taxpayer_total_income_yen=9_800_000,
        spouse_salary_yen=2_070_000,
        spouse_age=45,
        tax_year=2026,
    )
    assert sp_special_edge.deduction_yen == 10_000

    sp_over = evaluate_spouse_deduction(
        has_spouse=True,
        taxpayer_total_income_yen=8_000_000,
        spouse_salary_yen=2_070_001,
        spouse_age=45,
        tax_year=2026,
    )
    assert sp_over.deduction_yen == 0

    sp_tp_over = evaluate_spouse_deduction(
        has_spouse=True,
        taxpayer_total_income_yen=10_000_001,
        spouse_salary_yen=1_000_000,
        spouse_age=45,
        tax_year=2026,
    )
    assert sp_tp_over.deduction_yen == 0
    assert sp_tp_over.is_doitsu_seikei_spouse is True

    # 178万円の壁: 74万 + 104万 = 178万円 -> 0 yen tax even with 0 social insurance
    wall_178 = calculate_household_year_tax(HouseholdTaxInput(salary_yen=1_780_000, social_insurance_yen=0), 2026)
    assert wall_178.annual_tax_yen == 0
    assert compute_income_adjustment_deduction(9_250_003, is_eligible=True) == 75_001
    _, _, base_t, _, _, ann_t = compute_national_income_tax(7_000_000, 0)
    assert base_t == 974_000
    assert ann_t == 994_400  # 974,000 * 1.021 = 994,454 -> 100円未満切捨て = 994,400


def test_csv_batch_auditor_shift_jis_utf8_bom_roundtrip_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sample_csv = build_sample_audit_csv()
    summary = audit_payroll_csv_text(sample_csv)
    assert summary.total_employees == 8
    assert summary.clean_employees == 2
    assert summary.flagged_employees == 6
    assert summary.critical_findings_count == 3
    assert summary.finding_counts_by_code["MISSED_TOKUTEI_SHINZOKU"] == 1
    assert summary.finding_counts_by_code["LEGACY_R7_THRESHOLD_APPLIED"] == 2
    assert summary.finding_counts_by_code["WRONG_BASIC_DEDUCTION_TIER"] == 1
    assert summary.finding_counts_by_code["PRE_DEC1_ENFORCEMENT_INELIGIBLE"] == 1

    # Shift-JIS (cp932) input roundtrip
    sjis_path = tmp_path / "payroll_sjis.csv"
    sjis_path.write_bytes(sample_csv.encode("cp932"))
    sjis_summary = audit_payroll_csv_bytes(sjis_path.read_bytes())
    assert sjis_summary.detected_encoding == "cp932"
    assert sjis_summary.total_tax_overpayment_yen == summary.total_tax_overpayment_yen

    # Export both UTF-8 BOM and cp932 audit reports and verify CSV headers
    bom_out = tmp_path / "audit_bom.csv"
    cp932_out = tmp_path / "audit_cp932.csv"
    rc_crit = cli_main(
        [
            str(sjis_path),
            "--export-csv",
            str(bom_out),
            "--export-encoding",
            "utf-8-sig",
            "--fail-on",
            "critical",
        ]
    )
    assert rc_crit == 2
    _ = capsys.readouterr()
    raw_bom = bom_out.read_bytes()
    assert raw_bom.startswith(b"\xef\xbb\xbf")
    parsed_rows = list(csv.DictReader(io.StringIO(raw_bom.decode("utf-8-sig"))))
    assert len(parsed_rows) == 8
    assert parsed_rows[0]["社員番号"] == "EMP-2601"
    assert parsed_rows[0]["検算ステータス"] == "要是正（重大）"

    cp932_bytes = export_audit_report_bytes(summary, encoding="cp932")
    cp932_out.write_bytes(cp932_bytes)
    cp932_rows = list(csv.DictReader(io.StringIO(cp932_out.read_bytes().decode("cp932"))))
    assert len(cp932_rows) == 8
    assert cp932_rows[6]["検算ステータス"] == "適正"

    # CLI --simulate JSON mode
    rc_sim = cli_main(
        [
            "--simulate",
            "--salary",
            "6200000",
            "--spouse-salary",
            "1320000",
            "--child-age",
            "20",
            "--child-salary",
            "1520000",
            "--format",
            "json",
        ]
    )
    assert rc_sim == 0
    sim_payload = json.loads(capsys.readouterr().out)
    assert sim_payload["comparison"]["r8_2026"]["tokutei_shinzoku_deduction_total_yen"] == 630_000
    assert len(sim_payload["wall_checkpoints"]) == 10

    # Validation error on negative salary
    with pytest.raises(NenmatsuInputError):
        audit_employee_dict({"employee_id": "BAD-1", "salary_yen": "-100"})


def test_python_and_js_engines_have_exact_1yen_parity_and_ui_contracts() -> None:
    node_bin = shutil.which("node")
    if not node_bin:
        nvm_candidates = sorted((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"))
        assert nvm_candidates, "Node.js binary required for JS parity verification"
        node_bin = str(nvm_candidates[-1])

    web_dir = Path(__file__).resolve().parent.parent / "tracks" / "track25_nenmatsu_2026" / "web"

    # 1. Run `node --test`
    test_proc = subprocess.run(
        [node_bin, "--test", "./test/engine.test.mjs"],
        cwd=str(web_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "fail 0" in test_proc.stdout

    # 2. Verify exact 1-yen parity across household comparison, 10 checkpoints, and 8-row CSV batch audit
    js_eval = (
        "import { compareR8VsR7, simulateWallCheckpoints, auditPayrollCsvText, buildSampleAuditCsv } from './engine.js';"
        "const hh = { salary_yen: 9200000, has_spouse: true, spouse_age: 45, spouse_salary_yen: 1760000,"
        "  dependents: [{ name: '子1', age: 20, salary_yen: 1680000 }, { name: '子2', age: 17, salary_yen: 1300000 }] };"
        "const out = {"
        "  comp: compareR8VsR7(hh),"
        "  walls: simulateWallCheckpoints(hh, 'child'),"
        "  batch: auditPayrollCsvText(buildSampleAuditCsv(), 'utf-8')"
        "};"
        "console.log(JSON.stringify(out));"
    )
    proc = subprocess.run(
        [node_bin, "--input-type=module", "-e", js_eval],
        cwd=str(web_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    js_out = json.loads(proc.stdout)

    py_hh = HouseholdTaxInput(
        salary_yen=9_200_000,
        has_spouse=True,
        spouse_age=45,
        spouse_salary_yen=1_760_000,
        dependents=(
            DependentInput(name="子1", age=20, salary_yen=1_680_000),
            DependentInput(name="子2", age=17, salary_yen=1_300_000),
        ),
    )
    py_comp = compare_r8_vs_r7(py_hh)
    py_walls = simulate_wall_checkpoints(py_hh, target="child")
    py_batch = audit_payroll_csv_text(build_sample_audit_csv(), detected_encoding="utf-8").to_dict()

    assert py_comp == js_out["comp"]
    assert py_walls == js_out["walls"]
    assert py_batch == js_out["batch"]

    # 3. Verify strict zero-network CSP and BOOTH/Zenn conversion links in index.html
    html = (web_dir / "index.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in html
    assert "https://pecopeko1011.booth.pm/items/9179705" in html
    assert "https://zenn.dev/pecopeko/books/afml-quant-and-local-ai-guard" in html
    assert "Crafted by peco" in html


def test_apify_ppe_actor_schemas_billing_and_banned_terms() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    actor_dir = root_dir / "tracks" / "track1_apify" / "jp_nenmatsu_2026_actor"
    track_dir = root_dir / "tracks" / "track25_nenmatsu_2026"

    actor_json = json.loads((actor_dir / ".actor" / "actor.json").read_text(encoding="utf-8"))
    assert actor_json["name"] == "jp-nenmatsu-2026-tax-payroll-auditor"
    assert actor_json["input"] == "./input_schema.json"
    assert actor_json["output"] == "./output_schema.json"
    assert actor_json["storages"] == {"dataset": "./dataset_schema.json"}

    ppe_json = json.loads((actor_dir / ".actor" / "pay_per_event.json").read_text(encoding="utf-8"))
    events = ppe_json["pricingPerEvent"]["actorChargeEvents"]
    assert "employee_audited" in events
    assert events["employee_audited"]["eventPriceUsd"] == 0.002

    req_txt = (actor_dir / "requirements.txt").read_text(encoding="utf-8")
    assert "apify>=2.0.0" in req_txt
    assert "pydantic>=2.7.0" in req_txt

    banned_word = "cap" + "tcha"
    for scan_dir in (actor_dir, track_dir):
        for p in scan_dir.rglob("*"):
            if p.is_file() and p.suffix in {".md", ".py", ".json", ".js", ".mjs", ".html", ".css"}:
                assert banned_word not in p.read_text(encoding="utf-8").lower(), f"Banned term found in {p}"

    # Verify Shift-JIS Base64 + inline employee + malformed unbilled row execution
    sjis_b64 = base64.b64encode(build_sample_audit_csv().encode("cp932")).decode("ascii")
    outcomes = actor_mod.audit_actor_payload(
        {
            "employees": [
                {"employee_id": "INLINE-1", "salary_yen": 1_780_000, "social_insurance_yen": 0},
                {"employee_id": "BROKEN-ROW", "salary_yen": "not-a-number"},
            ],
            "csvBase64": sjis_b64,
            "includeWallSimulation": True,
        }
    )
    assert len(outcomes) == 10  # 2 inline + 8 from Shift-JIS CSV
    billable_items = [item for item, billable in outcomes if billable]
    unbilled_items = [item for item, billable in outcomes if not billable]
    assert len(billable_items) == 9
    assert len(unbilled_items) == 1
    assert unbilled_items[0]["employee_id"] == "BROKEN-ROW"
    assert unbilled_items[0]["status"] == "parse_error"
    assert billable_items[0]["statutory_annual_tax_r8_yen"] == 0
    assert len(billable_items[0]["wall_checkpoints"]) == 10
