from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

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


def analyze_frame(raw_purchase: pd.DataFrame, label: str) -> Dict[str, object]:
    catalog = pd.read_csv(APP_DIR / "data" / "sourceclub_catalog_sample.csv")
    mapping = detect_column_mapping(raw_purchase.columns, PURCHASE_SCHEMA, PURCHASE_ALIASES)
    normalized_purchase = normalize_purchase_history(raw_purchase, mapping)
    normalized_catalog = normalize_catalog(catalog)
    results = analyze_savings(normalized_purchase, normalized_catalog, AnalysisSettings())
    summary = summarize_results(results)
    coverage = summarize_coverage(results)
    workbook = make_excel_workbook(
        results,
        summary,
        coverage=coverage,
        metadata={"demo file used": label, "catalog used": "sourceclub_catalog_sample.csv"},
    )
    return {
        "label": label,
        "results": results,
        "summary": summary,
        "coverage": coverage,
        "workbook": workbook,
    }


def analyze_csv(path: Path) -> Dict[str, object]:
    return analyze_frame(pd.read_csv(path), path.name)


def assert_demo_thresholds(analysis: Dict[str, object], min_auto_confirmed: int = 5) -> None:
    summary = analysis["summary"]
    coverage = analysis["coverage"]
    workbook = analysis["workbook"]

    assert coverage["rows_analyzed"] >= 10, analysis["label"]
    assert summary["confirmed_savings"] > 0, analysis["label"]
    assert summary["potential_review_savings"] > 0, analysis["label"]
    assert coverage["catalog_coverage_percent"] >= 0.70, analysis["label"]
    assert coverage["rows_auto_confirmed"] >= min_auto_confirmed, analysis["label"]
    assert coverage["rows_needing_review"] >= 2, analysis["label"]
    assert coverage["rows_no_match_higher_price"] >= 1, analysis["label"]
    assert len(workbook) > 0, analysis["label"]


def print_summary(analysis: Dict[str, object]) -> None:
    summary = analysis["summary"]
    coverage = analysis["coverage"]
    print(
        f"{analysis['label']}: rows={coverage['rows_analyzed']}, "
        f"coverage={coverage['catalog_coverage_percent']:.1%}, "
        f"confirmed=${summary['confirmed_savings']:.2f}, "
        f"review=${summary['potential_review_savings']:.2f}, "
        f"auto={coverage['rows_auto_confirmed']}, "
        f"review_rows={coverage['rows_needing_review']}, "
        f"no_match_higher={coverage['rows_no_match_higher_price']}"
    )


def non_overlap_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Product Name": "Office printer toner cartridge black",
                "Supplier": "Demo Vendor",
                "Dist. Item #": "OFF-001",
                "Mfg": "OfficeCo",
                "Manufacturer SKU": "TONER-1",
                "Qty": 2,
                "UOM": "each",
                "Unit Price": 80,
                "Total Spend": 160,
                "Category": "Office Supplies",
            },
            {
                "Product Name": "Waiting room magazine subscription",
                "Supplier": "Demo Vendor",
                "Dist. Item #": "OFF-002",
                "Mfg": "ReadCo",
                "Manufacturer SKU": "MAG-2",
                "Qty": 1,
                "UOM": "each",
                "Unit Price": 40,
                "Total Spend": 40,
                "Category": "Office Supplies",
            },
            {
                "Product Name": "Front desk stapler heavy duty",
                "Supplier": "Demo Vendor",
                "Dist. Item #": "OFF-003",
                "Mfg": "DeskCo",
                "Manufacturer SKU": "STAP-3",
                "Qty": 3,
                "UOM": "each",
                "Unit Price": 12,
                "Total Spend": 36,
                "Category": "Office Supplies",
            },
        ]
    )


def main() -> None:
    scenarios = [
        analyze_csv(APP_DIR / "data" / "sample_purchase_history.csv"),
        analyze_csv(APP_DIR / "data" / "demo_uploads" / "Benco_Family_Dentistry_Purchase_Analysis.csv"),
        analyze_csv(APP_DIR / "data" / "demo_uploads" / "HenrySchein_Smile_Center_Items_Purchased.csv"),
    ]

    for scenario in scenarios:
        assert_demo_thresholds(scenario)
        print_summary(scenario)

    non_overlap = analyze_frame(non_overlap_frame(), "non-overlap synthetic upload")
    non_overlap_summary = non_overlap["summary"]
    non_overlap_coverage = non_overlap["coverage"]
    assert non_overlap_coverage["catalog_coverage_percent"] < 0.30
    assert non_overlap_coverage["rows_no_match_higher_price"] == non_overlap_coverage["rows_analyzed"]
    assert non_overlap_summary["confirmed_savings"] == 0
    assert non_overlap_summary["potential_review_savings"] == 0
    assert len(non_overlap["workbook"]) > 0
    print_summary(non_overlap)
    print("Low coverage warning condition: true")
    print("Demo upload test passed")


if __name__ == "__main__":
    main()
