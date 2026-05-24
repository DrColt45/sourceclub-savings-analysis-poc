from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from core.matching import AnalysisSettings, analyze_savings
from core.normalization import (
    CATALOG_ALIASES,
    CATALOG_SCHEMA,
    PURCHASE_ALIASES,
    PURCHASE_SCHEMA,
    aggregate_duplicate_purchase_items,
    detect_column_mapping,
    mapping_frame,
    mapping_from_frame,
    normalize_catalog,
    normalize_purchase_history,
)
from core.reporting import make_excel_workbook, split_result_tables, summarize_coverage, summarize_results


APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
SAMPLE_PURCHASE_PATH = DATA_DIR / "sample_purchase_history.csv"
SAMPLE_CATALOG_PATH = DATA_DIR / "sourceclub_catalog_sample.csv"


st.set_page_config(page_title="SourceClub Savings Analysis POC", layout="wide")


def read_uploaded_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Please upload a CSV or Excel file.")


def read_local_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def compact_label(value: object, max_length: int = 72) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


st.title("SourceClub Savings Analysis POC")
st.caption(
    "Upload a supplier purchase analysis, match it against SourceClub's best-pricing catalog, "
    "review uncertain items, and export a savings-ready workbook."
)
st.info(
    "This public POC uses synthetic demo data. For best demonstration results, leave the sample purchase "
    "history and built-in sample catalog enabled, then click Run Savings Analysis."
)

workflow_columns = st.columns(4)
workflow_steps = [
    ("1", "Upload purchase history"),
    ("2", "Match against catalog"),
    ("3", "Review exceptions"),
    ("4", "Export savings workbook"),
]
for column, (number, label) in zip(workflow_columns, workflow_steps):
    with column:
        st.markdown(f"**{number}. {label}**")

with st.sidebar:
    st.header("Inputs")
    purchase_upload = st.file_uploader("Upload purchase history", type=["csv", "xlsx", "xls"])
    use_sample_purchase = st.checkbox("Use sample purchase history", value=purchase_upload is None)

    st.divider()
    use_builtin_catalog = st.checkbox("Use built-in sample catalog", value=True)
    catalog_upload = st.file_uploader("Optional replacement SourceClub catalog", type=["csv", "xlsx", "xls"])

    st.divider()
    st.header("Analysis settings")
    auto_confirm_threshold = st.slider("Auto-confirm threshold", min_value=80, max_value=100, value=92, step=1)
    review_threshold = st.slider("Review threshold", min_value=45, max_value=90, value=65, step=1)
    aggregate_duplicates = st.toggle("Aggregate duplicate items", value=True)
    use_normalized_unit_price = st.toggle("Use normalized unit price when possible", value=True)


try:
    if purchase_upload is not None:
        raw_purchase = read_uploaded_table(purchase_upload)
        purchase_source = purchase_upload.name
    elif use_sample_purchase:
        raw_purchase = read_local_table(SAMPLE_PURCHASE_PATH)
        purchase_source = SAMPLE_PURCHASE_PATH.name
    else:
        raw_purchase = None
        purchase_source = ""

    if catalog_upload is not None:
        raw_catalog = read_uploaded_table(catalog_upload)
        catalog_source = catalog_upload.name
    elif use_builtin_catalog:
        raw_catalog = read_local_table(SAMPLE_CATALOG_PATH)
        catalog_source = SAMPLE_CATALOG_PATH.name
    else:
        raw_catalog = None
        catalog_source = ""
except Exception as exc:
    st.error(f"Could not load input file: {exc}")
    st.stop()


if raw_purchase is None:
    st.info("Upload a purchase-history CSV/XLSX or enable the sample purchase history.")
    st.stop()

if raw_catalog is None:
    st.info("Enable the built-in catalog or upload a replacement SourceClub catalog.")
    st.stop()


st.caption(f"Purchase history: {purchase_source} | Catalog: {catalog_source}")

purchase_mapping = detect_column_mapping(raw_purchase.columns, PURCHASE_SCHEMA, PURCHASE_ALIASES)
catalog_mapping = detect_column_mapping(raw_catalog.columns, CATALOG_SCHEMA, CATALOG_ALIASES)

st.subheader("1. Column Mapping")
st.write("Review the detected purchase-history mapping before running the analysis.")

mapping_options = [""] + [str(column) for column in raw_purchase.columns]
edited_mapping = st.data_editor(
    mapping_frame(purchase_mapping),
    use_container_width=True,
    hide_index=True,
    column_config={
        "standard_column": st.column_config.TextColumn("SourceClub field", disabled=True),
        "mapped_source_column": st.column_config.SelectboxColumn("Mapped input column", options=mapping_options),
    },
)

purchase_mapping = mapping_from_frame(edited_mapping)
normalized_purchase = normalize_purchase_history(raw_purchase, purchase_mapping)
if aggregate_duplicates:
    normalized_purchase = aggregate_duplicate_purchase_items(normalized_purchase)

normalized_catalog = normalize_catalog(raw_catalog, catalog_mapping)

with st.expander("Preview normalized purchase history", expanded=False):
    st.dataframe(normalized_purchase.head(25), use_container_width=True)

with st.expander("Preview normalized SourceClub catalog", expanded=False):
    st.dataframe(normalized_catalog.head(25), use_container_width=True)


st.subheader("2. Run Savings Analysis")
run_analysis = st.button("Run Savings Analysis", type="primary")

if run_analysis:
    settings = AnalysisSettings(
        auto_confirm_threshold=auto_confirm_threshold,
        review_threshold=review_threshold,
        use_normalized_unit_price=use_normalized_unit_price,
    )
    st.session_state["analysis_results"] = analyze_savings(normalized_purchase, normalized_catalog, settings)


results = st.session_state.get("analysis_results")
if results is None:
    st.stop()

summary = summarize_results(results)
coverage = summarize_coverage(results)

st.subheader("3. Summary")
metric_columns = st.columns(7)
metric_columns[0].metric("Total old spend analyzed", money(summary["total_old_spend_analyzed"]))
metric_columns[1].metric("Confirmed savings", money(summary["confirmed_savings"]))
metric_columns[2].metric("Potential review savings", money(summary["potential_review_savings"]))
metric_columns[3].metric("Confirmed savings %", pct(summary["confirmed_savings_percent"]))
metric_columns[4].metric("Rows auto-confirmed", f"{summary['rows_auto_confirmed']:,}")
metric_columns[5].metric("Rows needing review", f"{summary['rows_needing_review']:,}")
metric_columns[6].metric("No match / higher price", f"{summary['no_match_higher_price_rows']:,}")

st.caption(f"Matched spend: {money(summary['matched_spend'])}")

st.subheader("Coverage Diagnostic")
coverage_columns = st.columns(6)
coverage_columns[0].metric("Rows analyzed", f"{coverage['rows_analyzed']:,}")
coverage_columns[1].metric("Rows with candidate", f"{coverage['rows_with_any_candidate_match']:,}")
coverage_columns[2].metric("Rows auto-confirmed", f"{coverage['rows_auto_confirmed']:,}")
coverage_columns[3].metric("Rows needing review", f"{coverage['rows_needing_review']:,}")
coverage_columns[4].metric("No match / higher price", f"{coverage['rows_no_match_higher_price']:,}")
coverage_columns[5].metric("Catalog coverage", pct(coverage["catalog_coverage_percent"]))

if coverage["catalog_coverage_percent"] < 0.65:
    st.warning(
        "Low catalog coverage: many uploaded purchase-history items do not exist in the current demo catalog. "
        "Upload a matching SourceClub catalog or use the built-in demo files to see the full workflow."
    )

status_counts = results["match_status"].value_counts().to_dict()
status_order = [
    "AUTO_CONFIRMED",
    "REVIEW_SUBSTITUTE",
    "REVIEW_ALTERNATIVE",
    "UOM_REVIEW",
    "HIGHER_PRICE",
    "NO_MATCH",
]
status_colors = {
    "AUTO_CONFIRMED": "#DDF6E8",
    "REVIEW_SUBSTITUTE": "#FFF0C2",
    "REVIEW_ALTERNATIVE": "#FFE2C7",
    "UOM_REVIEW": "#DCEBFF",
    "HIGHER_PRICE": "#FAD7D7",
    "NO_MATCH": "#E7EAF0",
}
chips = []
for status in status_order:
    count = status_counts.get(status, 0)
    if count:
        chips.append(
            f"<span style='display:inline-block;margin:0 8px 8px 0;padding:5px 10px;"
            f"border-radius:16px;background:{status_colors[status]};font-size:0.85rem;"
            f"font-weight:600;color:#1F2933;'>{status}: {count}</span>"
        )
if chips:
    st.markdown("".join(chips), unsafe_allow_html=True)

tables = split_result_tables(results)
workbook = make_excel_workbook(results, summary)

quick_export_columns = st.columns([1, 3])
with quick_export_columns[0]:
    st.download_button(
        "Download Savings Workbook",
        data=workbook,
        file_name="SourceClub_Savings_Analysis_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key="summary_download_workbook",
    )
with quick_export_columns[1]:
    st.caption("The same export is also available in the Export tab.")

display_columns = [
    "customer_product_name",
    "current_supplier",
    "manufacturer",
    "manufacturer_item_number",
    "quantity",
    "uom",
    "old_spend",
    "best_supplier",
    "best_supplier_product_name",
    "best_price",
    "match_status",
    "match_type",
    "similarity_score",
    "sourceclub_new_spend",
    "estimated_savings",
    "estimated_savings_percent",
    "savings_bucket",
    "match_notes",
]

tabs = st.tabs(
    [
        "Savings Analysis",
        "Review Queue",
        "No Match / Higher Price",
        "Match Candidates / AI Prompts",
        "Export",
    ]
)

with tabs[0]:
    st.dataframe(results[[column for column in display_columns if column in results.columns]], use_container_width=True)

with tabs[1]:
    review_queue = tables["review_queue"].copy()
    if review_queue.empty:
        st.success("No uncertain rows are waiting for review.")
    else:
        review_queue["review_status"] = "pending"
        review_queue["reviewer_notes"] = ""
        review_columns = [
            "review_status",
            "reviewer_notes",
            "customer_product_name",
            "best_supplier_product_name",
            "similarity_score",
            "match_status",
            "match_type",
            "estimated_savings",
            "match_notes",
            "ai_review_prompt",
        ]
        st.data_editor(
            review_queue[[column for column in review_columns if column in review_queue.columns]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "review_status": st.column_config.SelectboxColumn(
                    "Review status",
                    options=["pending", "confirmed", "exclude", "needs more data"],
                ),
                "ai_review_prompt": st.column_config.TextColumn("AI review prompt", width="large"),
            },
        )

with tabs[2]:
    no_match = tables["no_match_higher_price"]
    if no_match.empty:
        st.success("No no-match or higher-price rows.")
    else:
        st.dataframe(no_match[[column for column in display_columns if column in no_match.columns]], use_container_width=True)

with tabs[3]:
    prompt_statuses = {
        "REVIEW_SUBSTITUTE",
        "REVIEW_ALTERNATIVE",
        "UOM_REVIEW",
        "HIGHER_PRICE",
        "NO_MATCH",
    }
    prompt_rows = results[results["match_status"].isin(prompt_statuses)].copy()

    if prompt_rows.empty:
        st.success("No review prompts are needed for this analysis.")
    else:
        prompt_rows = prompt_rows.reset_index(drop=True)
        prompt_rows.insert(0, "review_row", prompt_rows.index + 1)

        prompt_table_columns = [
            "review_row",
            "customer_product_name",
            "match_status",
            "similarity_score",
            "best_supplier_product_name",
            "estimated_savings",
            "match_notes",
        ]
        st.dataframe(
            prompt_rows[[column for column in prompt_table_columns if column in prompt_rows.columns]],
            use_container_width=True,
            hide_index=True,
        )

        radio_options = list(prompt_rows.index)
        selected_prompt = st.radio(
            "Select review row",
            options=radio_options,
            format_func=lambda idx: (
                f"Row {prompt_rows.loc[idx, 'review_row']}: "
                f"{compact_label(prompt_rows.loc[idx, 'customer_product_name'])}"
            ),
            key="ai_prompt_review_row",
        )

        selected_row = prompt_rows.loc[selected_prompt]
        st.text_area(
            "AI Review Prompt",
            value=selected_row["ai_review_prompt"],
            height=300,
            key=f"ai_review_prompt_text_{selected_row['review_row']}",
        )
        with st.expander("Top candidate details", expanded=False):
            st.code(selected_row["top_candidates"], language="json")

with tabs[4]:
    st.download_button(
        "Download Savings Workbook",
        data=workbook,
        file_name="SourceClub_Savings_Analysis_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key="tab_download_workbook",
    )
    st.write("Workbook sheets: Summary, Savings Analysis, Review Queue, No Match Higher Price, Match Library Updates.")
