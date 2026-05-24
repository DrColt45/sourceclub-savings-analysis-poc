from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from core.matching import AnalysisSettings, analyze_savings
from core.normalization import (
    PURCHASE_ALIASES,
    PURCHASE_SCHEMA,
    detect_column_mapping,
    normalize_catalog,
    normalize_purchase_history,
)
from core.reporting import make_excel_workbook, summarize_coverage, summarize_results


def main() -> None:
    purchase = pd.read_csv(APP_DIR / "data" / "sample_purchase_history.csv")
    catalog = pd.read_csv(APP_DIR / "data" / "sourceclub_catalog_sample.csv")

    mapping = detect_column_mapping(purchase.columns, PURCHASE_SCHEMA, PURCHASE_ALIASES)
    normalized_purchase = normalize_purchase_history(purchase, mapping)
    normalized_catalog = normalize_catalog(catalog)
    results = analyze_savings(normalized_purchase, normalized_catalog, AnalysisSettings())
    summary = summarize_results(results)
    coverage = summarize_coverage(results)
    workbook = make_excel_workbook(results, summary)

    output_path = APP_DIR / "scripts" / "smoke_output.xlsx"
    output_path.write_bytes(workbook)

    assert not results.empty
    assert summary["total_old_spend_analyzed"] > 0
    assert summary["confirmed_savings"] > 0
    assert summary["potential_review_savings"] > 0
    assert results["match_status"].eq("AUTO_CONFIRMED").any()
    assert results["match_status"].isin(["REVIEW_SUBSTITUTE", "REVIEW_ALTERNATIVE", "UOM_REVIEW"]).any()
    assert results["match_status"].eq("NO_MATCH").any()
    assert results["match_status"].eq("HIGHER_PRICE").any()
    assert coverage["catalog_coverage_percent"] > 0
    assert output_path.exists() and output_path.stat().st_size > 0

    print("Smoke test passed")
    print(f"Rows analyzed: {len(results)}")
    print(f"Confirmed savings: {summary['confirmed_savings']:.2f}")
    print(f"Potential review savings: {summary['potential_review_savings']:.2f}")
    print(f"Catalog coverage: {coverage['catalog_coverage_percent']:.1%}")
    print(f"Workbook: {output_path}")


if __name__ == "__main__":
    main()
