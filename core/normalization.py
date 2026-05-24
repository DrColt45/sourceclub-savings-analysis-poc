from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Mapping, Tuple

import pandas as pd


PURCHASE_SCHEMA = [
    "customer_product_name",
    "current_supplier",
    "distributor_item_number",
    "manufacturer",
    "manufacturer_item_number",
    "quantity",
    "uom",
    "current_unit_price",
    "old_spend",
    "last_order_date",
    "category",
]

CATALOG_SCHEMA = [
    "sourceclub_product_id",
    "best_supplier",
    "best_supplier_product_sku",
    "best_supplier_product_name",
    "manufacturer",
    "manufacturer_item_number",
    "uom",
    "pack_qty",
    "best_price",
    "product_category",
    "clinical_sensitivity",
    "notes",
]

PURCHASE_ALIASES: Mapping[str, Iterable[str]] = {
    "customer_product_name": [
        "product name",
        "item description",
        "description",
        "short description",
        "product description",
        "item name",
    ],
    "current_supplier": ["supplier", "supplier name", "vendor", "current supplier", "distributor"],
    "distributor_item_number": [
        "dist item #",
        "dist. item #",
        "supplier sku",
        "item code",
        "product code",
        "distributor item number",
        "item #",
        "sku",
    ],
    "manufacturer": ["mfg", "manufacturer", "brand", "maker", "mfr", "vendor brand"],
    "manufacturer_item_number": [
        "mfg item #",
        "manufacturer sku",
        "manufacturer item number",
        "manufacturer item #",
        "mfg sku",
        "mfr item",
        "mfr item #",
        "mfr part",
        "mfg number",
        "manufacturer number",
    ],
    "quantity": ["qty", "quantity", "order qty", "units purchased", "qty purchased", "purchase qty", "ordered quantity"],
    "uom": ["uom", "unit", "unit of measure", "pack", "package", "packaging", "pkg"],
    "current_unit_price": [
        "unit price",
        "price",
        "current unit price",
        "each price",
        "average unit cost",
        "avg unit cost",
        "net price",
    ],
    "old_spend": ["total spend", "amount", "extended price", "old spend", "spend", "ext price", "total paid", "extended amount"],
    "last_order_date": ["last purchase date", "last order date", "purchase date", "date", "last purchase"],
    "category": ["category", "category tree", "product category", "class"],
}

CATALOG_ALIASES: Mapping[str, Iterable[str]] = {
    "sourceclub_product_id": ["sourceclub product id", "product id", "sc product id", "id"],
    "best_supplier": ["best supplier", "supplier", "vendor"],
    "best_supplier_product_sku": ["best supplier product sku", "supplier sku", "sku", "item number"],
    "best_supplier_product_name": [
        "best supplier product name",
        "product name",
        "item description",
        "description",
    ],
    "manufacturer": ["manufacturer", "mfg", "brand"],
    "manufacturer_item_number": ["manufacturer item number", "mfg item #", "manufacturer sku", "mfg sku"],
    "uom": ["uom", "unit", "unit of measure", "pack"],
    "pack_qty": ["pack qty", "pack quantity", "package quantity", "qty per pack", "count"],
    "best_price": ["best price", "price", "unit price", "sourceclub price"],
    "product_category": ["product category", "category", "category tree"],
    "clinical_sensitivity": ["clinical sensitivity", "sensitivity", "clinical risk"],
    "notes": ["notes", "comments", "description notes"],
}


def _column_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _alias_lookup(aliases: Mapping[str, Iterable[str]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for standard, names in aliases.items():
        lookup[_column_key(standard)] = standard
        for name in names:
            lookup[_column_key(name)] = standard
    return lookup


def detect_column_mapping(
    columns: Iterable[str],
    schema: List[str],
    aliases: Mapping[str, Iterable[str]],
    minimum_similarity: float = 0.76,
) -> Dict[str, str | None]:
    """Map source columns to the standard schema using aliases and light fuzzy matching."""
    source_columns = [str(c) for c in columns]
    keyed_sources = {_column_key(c): c for c in source_columns}
    alias_lookup = _alias_lookup(aliases)
    mapping: Dict[str, str | None] = {standard: None for standard in schema}

    for source_key, source_name in keyed_sources.items():
        standard = alias_lookup.get(source_key)
        if standard in mapping and mapping[standard] is None:
            mapping[standard] = source_name

    for standard in schema:
        if mapping[standard]:
            continue
        alias_keys = [_column_key(standard)] + [_column_key(a) for a in aliases.get(standard, [])]
        best_source: Tuple[float, str | None] = (0.0, None)
        for source_key, source_name in keyed_sources.items():
            score = max(SequenceMatcher(None, source_key, alias_key).ratio() for alias_key in alias_keys)
            if score > best_source[0]:
                best_source = (score, source_name)
        if best_source[0] >= minimum_similarity:
            mapping[standard] = best_source[1]

    return mapping


def mapping_frame(mapping: Mapping[str, str | None]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"standard_column": key, "mapped_source_column": value or ""} for key, value in mapping.items()]
    )


def mapping_from_frame(frame: pd.DataFrame) -> Dict[str, str | None]:
    output: Dict[str, str | None] = {}
    for _, row in frame.iterrows():
        standard = str(row.get("standard_column", "")).strip()
        mapped = str(row.get("mapped_source_column", "")).strip()
        if standard:
            output[standard] = mapped or None
    return output


def _money_to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype("string")
        .str.replace(r"[\$,]", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _text_or_blank(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip()


def normalize_purchase_history(raw: pd.DataFrame, mapping: Mapping[str, str | None]) -> pd.DataFrame:
    normalized = pd.DataFrame(index=raw.index)
    for standard in PURCHASE_SCHEMA:
        source = mapping.get(standard)
        normalized[standard] = raw[source] if source in raw.columns else pd.NA

    for column in [
        "customer_product_name",
        "current_supplier",
        "distributor_item_number",
        "manufacturer",
        "manufacturer_item_number",
        "uom",
        "last_order_date",
        "category",
    ]:
        normalized[column] = _text_or_blank(normalized[column])

    normalized["quantity"] = _money_to_number(normalized["quantity"]).fillna(1)
    normalized["current_unit_price"] = _money_to_number(normalized["current_unit_price"])
    normalized["old_spend"] = _money_to_number(normalized["old_spend"])

    can_derive_unit = normalized["current_unit_price"].isna() & normalized["old_spend"].notna() & (normalized["quantity"] != 0)
    normalized.loc[can_derive_unit, "current_unit_price"] = (
        normalized.loc[can_derive_unit, "old_spend"] / normalized.loc[can_derive_unit, "quantity"]
    )

    can_derive_spend = normalized["old_spend"].isna() & normalized["current_unit_price"].notna()
    normalized.loc[can_derive_spend, "old_spend"] = (
        normalized.loc[can_derive_spend, "current_unit_price"] * normalized.loc[can_derive_spend, "quantity"]
    )

    normalized["row_quality_status"] = "OK"
    normalized["row_quality_notes"] = ""
    bad_spend = normalized["old_spend"].fillna(0) <= 0
    normalized.loc[bad_spend, "row_quality_status"] = "REVIEW"
    normalized.loc[bad_spend, "row_quality_notes"] = "Zero or missing old spend"

    missing_name = normalized["customer_product_name"].eq("")
    normalized.loc[missing_name, "row_quality_status"] = "REVIEW"
    normalized.loc[missing_name, "row_quality_notes"] = (
        normalized.loc[missing_name, "row_quality_notes"].str.cat(pd.Series(["Missing product name"] * missing_name.sum(), index=normalized.index[missing_name]), sep="; ").str.strip("; ")
    )

    return normalized.reset_index(drop=True)


def normalize_catalog(raw: pd.DataFrame, mapping: Mapping[str, str | None] | None = None) -> pd.DataFrame:
    if mapping is None:
        mapping = detect_column_mapping(raw.columns, CATALOG_SCHEMA, CATALOG_ALIASES)

    normalized = pd.DataFrame(index=raw.index)
    for standard in CATALOG_SCHEMA:
        source = mapping.get(standard)
        normalized[standard] = raw[source] if source in raw.columns else pd.NA

    text_columns = [
        "sourceclub_product_id",
        "best_supplier",
        "best_supplier_product_sku",
        "best_supplier_product_name",
        "manufacturer",
        "manufacturer_item_number",
        "uom",
        "product_category",
        "clinical_sensitivity",
        "notes",
    ]
    for column in text_columns:
        normalized[column] = _text_or_blank(normalized[column])

    normalized["pack_qty"] = _money_to_number(normalized["pack_qty"]).fillna(1)
    normalized["best_price"] = _money_to_number(normalized["best_price"])

    return normalized.reset_index(drop=True)


def aggregate_duplicate_purchase_items(purchase: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "customer_product_name",
        "current_supplier",
        "distributor_item_number",
        "manufacturer",
        "manufacturer_item_number",
        "uom",
        "category",
    ]
    frame = purchase.copy()
    frame["_source_row_count"] = 1
    aggregated = (
        frame.groupby(group_columns, dropna=False, as_index=False)
        .agg(
            quantity=("quantity", "sum"),
            old_spend=("old_spend", "sum"),
            current_unit_price=("current_unit_price", "mean"),
            last_order_date=("last_order_date", "max"),
            row_quality_status=("row_quality_status", "first"),
            row_quality_notes=("row_quality_notes", lambda values: "; ".join(sorted({v for v in values if v}))),
            source_row_count=("_source_row_count", "sum"),
        )
        .reset_index(drop=True)
    )
    has_qty = aggregated["quantity"].fillna(0) != 0
    aggregated.loc[has_qty, "current_unit_price"] = aggregated.loc[has_qty, "old_spend"] / aggregated.loc[has_qty, "quantity"]
    return aggregated
