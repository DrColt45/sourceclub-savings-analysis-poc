from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Tuple

import pandas as pd

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - exercised only when rapidfuzz is unavailable
    fuzz = None


@dataclass
class AnalysisSettings:
    auto_confirm_threshold: int = 92
    review_threshold: int = 65
    use_normalized_unit_price: bool = True


ABBREVIATIONS = {
    "bx": "box",
    "boxs": "box",
    "pkg": "pack",
    "pk": "pack",
    "ea": "each",
    "ct": "count",
    "cnt": "count",
    "sz": "size",
    "reg": "regular",
    "univ": "universal",
    "steril": "sterilization",
    "mfg": "manufacturer",
}

UOM_EQUIVALENTS = {
    "ea": "each",
    "each": "each",
    "box": "box",
    "bx": "box",
    "pack": "pack",
    "pkg": "pack",
    "pk": "pack",
    "bag": "bag",
    "case": "case",
    "roll": "roll",
    "jar": "jar",
    "bottle": "bottle",
}


def clean_sku(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def normalize_text(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [ABBREVIATIONS.get(token, token) for token in text.split()]
    return " ".join(tokens)


def normalize_uom(value: object) -> str:
    text = normalize_text(value)
    for token in text.split():
        if token in UOM_EQUIVALENTS:
            return UOM_EQUIVALENTS[token]
    return text.split()[0] if text else ""


def infer_pack_qty(*values: object) -> float | None:
    text = " ".join(str(v or "") for v in values).lower()
    patterns = [
        r"(?:box|pack|pkg|bag|case|count|ct|pk|bx)\s*(?:of|/)?\s*(\d{1,5})",
        r"(\d{1,5})\s*/\s*(?:box|pack|pkg|bag|case|pk|bx)",
        r"(\d{1,5})\s*(?:ct|count|per box|per pack)",
        r"x\s*(\d{1,5})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            number = float(match.group(1))
            if number > 0:
                return number
    return None


def _text_score(left: object, right: object) -> float:
    a = normalize_text(left)
    b = normalize_text(right)
    if not a or not b:
        return 0.0
    if fuzz:
        return float(fuzz.token_set_ratio(a, b))
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return SequenceMatcher(None, a, b).ratio() * 100
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    sequence = SequenceMatcher(None, a, b).ratio()
    return (0.65 * overlap + 0.35 * sequence) * 100


def _uom_issue(purchase: pd.Series, candidate: pd.Series) -> Tuple[bool, str, float | None]:
    purchase_uom = normalize_uom(purchase.get("uom", ""))
    candidate_uom = normalize_uom(candidate.get("uom", ""))
    purchase_pack = infer_pack_qty(purchase.get("uom"), purchase.get("customer_product_name"))
    candidate_pack = float(candidate.get("pack_qty") or 1)

    notes: List[str] = []
    issue = False
    if purchase_uom and candidate_uom and purchase_uom != candidate_uom:
        issue = True
        notes.append(f"UOM differs: customer {purchase_uom}, SourceClub {candidate_uom}")

    if purchase_pack and candidate_pack and not math.isclose(purchase_pack, candidate_pack, rel_tol=0.10):
        issue = True
        notes.append(f"Pack quantity differs: customer {purchase_pack:g}, SourceClub {candidate_pack:g}")
    elif not purchase_pack and candidate_pack and candidate_pack != 1:
        notes.append(f"Customer pack quantity not explicit; SourceClub pack quantity {candidate_pack:g}")

    return issue, "; ".join(notes), purchase_pack


def _candidate_score(purchase: pd.Series, candidate: pd.Series) -> Tuple[float, List[str], bool, str, float | None]:
    notes: List[str] = []
    score = _text_score(purchase.get("customer_product_name"), candidate.get("best_supplier_product_name"))

    purchase_mfg = normalize_text(purchase.get("manufacturer"))
    candidate_mfg = normalize_text(candidate.get("manufacturer"))
    if purchase_mfg and candidate_mfg:
        if purchase_mfg == candidate_mfg:
            score += 12
            notes.append("Manufacturer matches")
        elif purchase_mfg in candidate_mfg or candidate_mfg in purchase_mfg:
            score += 6
            notes.append("Manufacturer appears related")
        else:
            score -= 7
            notes.append("Manufacturer differs")

    purchase_sku = clean_sku(purchase.get("manufacturer_item_number"))
    candidate_sku = clean_sku(candidate.get("manufacturer_item_number"))
    if purchase_sku and candidate_sku:
        if purchase_sku == candidate_sku:
            score = max(score, 100)
            notes.append("Exact manufacturer item number match")
        elif purchase_sku in candidate_sku or candidate_sku in purchase_sku:
            score += 8
            notes.append("Manufacturer item number partially matches")

    purchase_category = normalize_text(purchase.get("category"))
    candidate_category = normalize_text(candidate.get("product_category"))
    if purchase_category and candidate_category and purchase_category == candidate_category:
        score += 5
        notes.append("Category matches")

    uom_issue, uom_note, purchase_pack = _uom_issue(purchase, candidate)
    if uom_issue:
        score -= 12
        notes.append(uom_note)
    elif uom_note:
        notes.append(uom_note)
    elif normalize_uom(purchase.get("uom")) and normalize_uom(candidate.get("uom")):
        score += 3
        notes.append("UOM appears compatible")

    return max(0.0, min(100.0, score)), notes, uom_issue, uom_note, purchase_pack


def _top_candidates(purchase: pd.Series, catalog: pd.DataFrame, limit: int = 3) -> List[Dict[str, object]]:
    purchase_mfg_sku = clean_sku(purchase.get("manufacturer_item_number"))
    purchase_dist_sku = clean_sku(purchase.get("distributor_item_number"))

    scored: List[Dict[str, object]] = []
    for idx, candidate in catalog.iterrows():
        candidate_mfg_sku = clean_sku(candidate.get("manufacturer_item_number"))
        candidate_supplier_sku = clean_sku(candidate.get("best_supplier_product_sku"))

        score, notes, uom_issue, uom_note, purchase_pack = _candidate_score(purchase, candidate)
        if purchase_mfg_sku and candidate_mfg_sku and purchase_mfg_sku == candidate_mfg_sku:
            score = 100.0
            notes = ["Exact manufacturer item number match"] + [n for n in notes if "Exact manufacturer" not in n]
        elif purchase_dist_sku and candidate_supplier_sku and purchase_dist_sku == candidate_supplier_sku:
            score = max(score, 98.0)
            notes = ["Exact supplier SKU/cross-reference match"] + notes

        scored.append(
            {
                "catalog_index": idx,
                "score": round(score, 1),
                "uom_issue": uom_issue,
                "uom_note": uom_note,
                "purchase_pack_qty": purchase_pack,
                "notes": "; ".join(dict.fromkeys([n for n in notes if n])),
            }
        )

    return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]


def _normalized_costs(
    purchase: pd.Series,
    candidate: pd.Series,
    purchase_pack_qty: float | None,
    use_normalized_unit_price: bool,
) -> Tuple[float, float, float, str]:
    current_price = float(purchase.get("current_unit_price") or 0)
    best_price = float(candidate.get("best_price") or 0)
    candidate_pack_qty = float(candidate.get("pack_qty") or 1)
    purchase_quantity = float(purchase.get("quantity") or 0)

    if use_normalized_unit_price and candidate_pack_qty > 0:
        customer_pack = purchase_pack_qty or candidate_pack_qty
        if customer_pack > 0:
            comparison_units = purchase_quantity * customer_pack
            return (
                current_price / customer_pack,
                best_price / candidate_pack_qty,
                comparison_units,
                "Normalized by inferred/catalog pack quantity",
            )

    return current_price, best_price, purchase_quantity, "Package-level price comparison assumption"


def _ai_prompt(purchase: pd.Series, catalog: pd.DataFrame, candidates: List[Dict[str, object]]) -> str:
    candidate_lines = []
    for rank, item in enumerate(candidates, start=1):
        row = catalog.loc[item["catalog_index"]]
        candidate_lines.append(
            {
                "rank": rank,
                "score": item["score"],
                "sourceclub_product_id": row.get("sourceclub_product_id", ""),
                "supplier": row.get("best_supplier", ""),
                "sku": row.get("best_supplier_product_sku", ""),
                "name": row.get("best_supplier_product_name", ""),
                "manufacturer": row.get("manufacturer", ""),
                "manufacturer_item_number": row.get("manufacturer_item_number", ""),
                "uom": row.get("uom", ""),
                "pack_qty": row.get("pack_qty", ""),
                "price": row.get("best_price", ""),
                "clinical_sensitivity": row.get("clinical_sensitivity", ""),
                "notes": row.get("notes", ""),
            }
        )

    customer_item = {
        "name": purchase.get("customer_product_name", ""),
        "supplier": purchase.get("current_supplier", ""),
        "supplier_sku": purchase.get("distributor_item_number", ""),
        "manufacturer": purchase.get("manufacturer", ""),
        "manufacturer_item_number": purchase.get("manufacturer_item_number", ""),
        "uom": purchase.get("uom", ""),
        "current_unit_price": purchase.get("current_unit_price", ""),
        "category": purchase.get("category", ""),
    }
    return (
        "Compare this customer dental supply item against these top SourceClub candidate items. "
        "Determine if this is identical, substitute, alternative, or no match. Note UOM/pack concerns "
        "and recommend whether to include in confirmed savings or review only.\n\n"
        f"Customer item:\n{json.dumps(customer_item, indent=2, default=str)}\n\n"
        f"Candidate items:\n{json.dumps(candidate_lines, indent=2, default=str)}"
    )


def analyze_savings(purchase: pd.DataFrame, catalog: pd.DataFrame, settings: AnalysisSettings | None = None) -> pd.DataFrame:
    settings = settings or AnalysisSettings()
    rows: List[Dict[str, object]] = []

    for purchase_index, purchase_row in purchase.iterrows():
        top = _top_candidates(purchase_row, catalog, limit=3)
        best = top[0] if top else None

        base = purchase_row.to_dict()
        base["purchase_row_index"] = purchase_index
        base["training_status"] = "untrained"

        if not best or best["score"] < settings.review_threshold:
            rows.append(
                {
                    **base,
                    "sourceclub_product_id": "",
                    "best_supplier": "",
                    "best_supplier_product_sku": "",
                    "best_supplier_product_name": "",
                    "best_price": pd.NA,
                    "pack_qty": pd.NA,
                    "match_status": "NO_MATCH",
                    "match_type": "no_match",
                    "similarity_score": best["score"] if best else 0,
                    "current_normalized_unit_cost": pd.NA,
                    "sourceclub_normalized_unit_cost": pd.NA,
                    "sourceclub_new_spend": 0,
                    "estimated_savings": 0,
                    "estimated_savings_percent": 0,
                    "savings_bucket": "excluded_or_no_savings",
                    "match_notes": "No candidate met review threshold",
                    "top_candidates": json.dumps([], default=str),
                    "ai_review_prompt": _ai_prompt(purchase_row, catalog, top),
                }
            )
            continue

        candidate = catalog.loc[best["catalog_index"]]
        current_cost, sourceclub_cost, comparison_quantity, cost_note = _normalized_costs(
            purchase_row,
            candidate,
            best.get("purchase_pack_qty"),
            settings.use_normalized_unit_price,
        )
        old_spend = float(purchase_row.get("old_spend") or 0)
        new_spend = sourceclub_cost * comparison_quantity
        savings = old_spend - new_spend
        savings_pct = savings / old_spend if old_spend else 0

        if sourceclub_cost > current_cost:
            status = "HIGHER_PRICE"
            match_type = "identical" if best["score"] >= settings.auto_confirm_threshold else "substitute"
        elif best["uom_issue"]:
            status = "UOM_REVIEW"
            match_type = "identical" if best["score"] >= settings.auto_confirm_threshold else "substitute"
        elif best["score"] >= settings.auto_confirm_threshold:
            status = "AUTO_CONFIRMED"
            match_type = "identical"
        elif best["score"] >= 80:
            status = "REVIEW_SUBSTITUTE"
            match_type = "substitute"
        else:
            status = "REVIEW_ALTERNATIVE"
            match_type = "alternative"

        if status == "AUTO_CONFIRMED" and savings > 0:
            bucket = "confirmed_savings"
        elif status in {"REVIEW_SUBSTITUTE", "REVIEW_ALTERNATIVE", "UOM_REVIEW"} and savings > 0:
            bucket = "potential_review_savings"
        else:
            bucket = "excluded_or_no_savings"

        candidate_summaries = []
        for item in top:
            row = catalog.loc[item["catalog_index"]]
            candidate_summaries.append(
                {
                    "rank": len(candidate_summaries) + 1,
                    "score": item["score"],
                    "product_id": row.get("sourceclub_product_id", ""),
                    "supplier": row.get("best_supplier", ""),
                    "sku": row.get("best_supplier_product_sku", ""),
                    "name": row.get("best_supplier_product_name", ""),
                    "price": row.get("best_price", ""),
                    "notes": item.get("notes", ""),
                }
            )

        rows.append(
            {
                **base,
                "sourceclub_product_id": candidate.get("sourceclub_product_id", ""),
                "best_supplier": candidate.get("best_supplier", ""),
                "best_supplier_product_sku": candidate.get("best_supplier_product_sku", ""),
                "best_supplier_product_name": candidate.get("best_supplier_product_name", ""),
                "best_price": candidate.get("best_price", pd.NA),
                "pack_qty": candidate.get("pack_qty", pd.NA),
                "product_category": candidate.get("product_category", ""),
                "clinical_sensitivity": candidate.get("clinical_sensitivity", ""),
                "match_status": status,
                "match_type": match_type,
                "similarity_score": best["score"],
                "current_normalized_unit_cost": current_cost,
                "sourceclub_normalized_unit_cost": sourceclub_cost,
                "sourceclub_new_spend": new_spend,
                "estimated_savings": savings,
                "estimated_savings_percent": savings_pct,
                "savings_bucket": bucket,
                "match_notes": "; ".join([n for n in [best.get("notes"), cost_note, candidate.get("notes", "")] if n]),
                "top_candidates": json.dumps(candidate_summaries, default=str),
                "ai_review_prompt": _ai_prompt(purchase_row, catalog, top),
            }
        )

    return pd.DataFrame(rows)
