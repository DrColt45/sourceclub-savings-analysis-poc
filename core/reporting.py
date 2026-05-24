from __future__ import annotations

from io import BytesIO
from typing import Dict

import pandas as pd


REVIEW_STATUSES = {"REVIEW_SUBSTITUTE", "REVIEW_ALTERNATIVE", "UOM_REVIEW"}
NO_MATCH_STATUSES = {"NO_MATCH", "HIGHER_PRICE"}


def summarize_results(results: pd.DataFrame) -> Dict[str, float | int]:
    old_spend = float(results["old_spend"].fillna(0).sum()) if "old_spend" in results else 0.0
    matched_spend = float(results.loc[~results["match_status"].eq("NO_MATCH"), "old_spend"].fillna(0).sum())
    confirmed = float(results.loc[results["savings_bucket"].eq("confirmed_savings"), "estimated_savings"].fillna(0).sum())
    potential = float(
        results.loc[results["savings_bucket"].eq("potential_review_savings"), "estimated_savings"].fillna(0).sum()
    )
    auto_confirmed_rows = int(results["match_status"].eq("AUTO_CONFIRMED").sum())
    review_rows = int(results["match_status"].isin(REVIEW_STATUSES).sum())
    no_match_or_higher = int(results["match_status"].isin(NO_MATCH_STATUSES).sum())
    return {
        "total_old_spend_analyzed": old_spend,
        "matched_spend": matched_spend,
        "confirmed_savings": confirmed,
        "potential_review_savings": potential,
        "confirmed_savings_percent": confirmed / old_spend if old_spend else 0,
        "rows_auto_confirmed": auto_confirmed_rows,
        "rows_needing_review": review_rows,
        "no_match_higher_price_rows": no_match_or_higher,
    }


def summarize_coverage(results: pd.DataFrame) -> Dict[str, float | int]:
    rows_analyzed = int(len(results))
    rows_with_candidate = int(results["sourceclub_product_id"].astype("string").fillna("").ne("").sum())
    rows_auto_confirmed = int(results["match_status"].eq("AUTO_CONFIRMED").sum())
    rows_needing_review = int(results["match_status"].isin(REVIEW_STATUSES).sum())
    rows_no_match_higher = int(results["match_status"].isin(NO_MATCH_STATUSES).sum())

    return {
        "rows_analyzed": rows_analyzed,
        "rows_with_any_candidate_match": rows_with_candidate,
        "rows_auto_confirmed": rows_auto_confirmed,
        "rows_needing_review": rows_needing_review,
        "rows_no_match_higher_price": rows_no_match_higher,
        "catalog_coverage_percent": rows_with_candidate / rows_analyzed if rows_analyzed else 0,
    }


def summary_frame(summary: Dict[str, float | int]) -> pd.DataFrame:
    labels = {
        "total_old_spend_analyzed": "Total old spend analyzed",
        "matched_spend": "Matched spend",
        "confirmed_savings": "Confirmed savings",
        "potential_review_savings": "Potential/review savings",
        "confirmed_savings_percent": "Confirmed savings %",
        "rows_auto_confirmed": "Rows auto-confirmed",
        "rows_needing_review": "Rows needing review",
        "no_match_higher_price_rows": "No-match / higher-price rows",
    }
    return pd.DataFrame([{"metric": labels.get(key, key), "value": value} for key, value in summary.items()])


def split_result_tables(results: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    review_queue = results[results["match_status"].isin(REVIEW_STATUSES)].copy()
    no_match = results[results["match_status"].isin(NO_MATCH_STATUSES)].copy()
    auto_confirmed = results[results["match_status"].eq("AUTO_CONFIRMED")].copy()
    library_updates = auto_confirmed[
        [
            "customer_product_name",
            "current_supplier",
            "distributor_item_number",
            "manufacturer",
            "manufacturer_item_number",
            "sourceclub_product_id",
            "best_supplier",
            "best_supplier_product_sku",
            "best_supplier_product_name",
            "similarity_score",
        ]
    ].copy()
    library_updates["training_status"] = "candidate_for_training"
    library_updates["reviewer_decision"] = ""
    return {
        "review_queue": review_queue,
        "no_match_higher_price": no_match,
        "match_library_updates": library_updates,
    }


def make_excel_workbook(results: pd.DataFrame, summary: Dict[str, float | int]) -> bytes:
    tables = split_result_tables(results)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_frame(summary).to_excel(writer, index=False, sheet_name="Summary")
        results.to_excel(writer, index=False, sheet_name="Savings Analysis")
        tables["review_queue"].to_excel(writer, index=False, sheet_name="Review Queue")
        tables["no_match_higher_price"].to_excel(writer, index=False, sheet_name="No Match Higher Price")
        tables["match_library_updates"].to_excel(writer, index=False, sheet_name="Match Library Updates")

        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                header = str(column_cells[0].value or "")
                width = min(max(len(header) + 2, 12), 42)
                sheet.column_dimensions[column_cells[0].column_letter].width = width

    return output.getvalue()
