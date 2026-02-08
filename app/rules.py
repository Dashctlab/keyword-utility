import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class RuleResult:
    bucket_id: str
    intent: str
    stage: str
    paid_activation: str
    seo_asset: str
    is_negative: str
    negative_type: str
    negative_theme: str
    confidence: float
    notes: str

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _has_any(text: str, terms: List[str]) -> bool:
    t = _norm(text)
    return any(term.lower() in t for term in terms)

def classify_keyword(kw: str, lists: Dict[str, List[str]]) -> RuleResult:
    t = _norm(kw)

    # quick detectors
    has_ka = _has_any(t, lists["ka_tokens"])
    has_comp = _has_any(t, lists["competitor_brands"])
    has_prop = _has_any(t, lists["proprietary_products"])
    has_form = _has_any(t, lists["classical_formulations"])
    has_cat  = _has_any(t, lists["categories_formats"])
    has_need = _has_any(t, lists["need_states"])
    has_sup  = _has_any(t, lists["support_terms"])
    has_serv = _has_any(t, lists["services_terms"])
    has_corp = _has_any(t, lists["corporate_terms"])
    has_geo  = _has_any(t, lists["geo_other_terms"])

    has_eval = _has_any(t, lists["eval_terms"])
    has_txn  = _has_any(t, lists["txn_terms"])
    has_how  = _has_any(t, lists["howto_terms"])
    has_trust= _has_any(t, lists["trust_terms"])

    # --- Buckets (precedence) ---
    bucket = "UNCLASSIFIED"
    notes = ""

    # Comparisons (non-brand or brand) as priority when explicit evaluation exists
    if has_eval:
        # If explicit vs + brands -> CMP-1 or CMP-2
        if "vs" in t or "versus" in t or "comparison" in t:
            if has_form and (has_ka or has_comp):
                bucket = "CMP-2"
            else:
                bucket = "CMP-1" if (has_ka or has_comp) else "CMP-3"
        else:
            bucket = "CMP-3"

    # Brand-led
    elif has_ka:
        if has_corp:
            bucket = "KA-NF2"
        elif has_serv:
            bucket = "KA-NF1"
        elif has_geo:
            bucket = "KA-NF3"
        elif has_prop:
            bucket = "KA-3"
        elif has_form:
            bucket = "KA-4"
        elif has_need:
            bucket = "KA-NS"
        elif has_cat:
            bucket = "KA-6"
        elif has_sup:
            bucket = "KA-7"
        else:
            bucket = "KA-1"

    # Competitor-led
    elif has_comp:
        if has_need:
            bucket = "COMP-NS"
        elif has_form or has_cat or has_txn or has_how:
            bucket = "COMP-2"
        else:
            bucket = "COMP-1"

    # Owned proprietary (no KA token)
    elif has_prop:
        bucket = "OWN-1"

    # Non-brand
    else:
        if has_trust:
            bucket = "NB-6"
        elif has_how:
            bucket = "NB-5"
        elif has_form:
            bucket = "NB-1"
        elif has_need:
            bucket = "NB-2"
        elif has_cat:
            bucket = "NB-4"
        else:
            bucket = "UNCLASSIFIED"

    # --- Intent ---
    intent = "LEARN"
    if has_txn:
        intent = "TXN"
    elif has_eval:
        intent = "EVAL"
    elif bucket in ("KA-1", "COMP-1") and not (has_form or has_need or has_cat):
        intent = "NAV"
    elif has_sup and has_ka:
        intent = "SUPPORT"
    elif bucket in ("NB-5", "NB-6"):
        intent = "LEARN"

    # --- Stage ---
    stage = {"TXN": "BOF", "EVAL": "MOF", "SUPPORT": "RET", "NAV": "TOF", "LEARN": "TOF"}[intent]

    # --- Suggested paid activation ---
    if intent == "TXN":
        paid = "Search/Shopping"
    elif intent == "EVAL":
        paid = "Search (tight)"
    else:
        paid = "Exclude"

    # --- SEO asset ---
    seo = "Hub/Guide"
    if bucket in ("KA-3", "KA-4", "OWN-1", "NB-1"):
        seo = "PDP"
    elif bucket in ("KA-6", "NB-4"):
        seo = "PLP"
    elif bucket in ("NB-5",):
        seo = "Usage/FAQ"
    elif bucket in ("CMP-1", "CMP-2", "CMP-3"):
        seo = "Comparison"
    elif bucket in ("KA-7",):
        seo = "Policy"
    elif bucket.startswith("KA-NF"):
        seo = "Review needed"

    # --- Negatives ---
    is_neg = "N"
    neg_type = "None"
    neg_theme = "None"
    if bucket.startswith("KA-NF"):
        is_neg = "Y"
        neg_type = "Route"
        neg_theme = "Services" if bucket == "KA-NF1" else ("Corporate/Investor" if bucket == "KA-NF2" else "Geo mismatch")
        paid = "Exclude"

    # --- Confidence ---
    # simple heuristic: unclassified or conflict -> low
    confidence = 0.85
    if bucket == "UNCLASSIFIED":
        confidence = 0.2
        notes = "Unclassified by rules"
    # multi-signal can be ambiguous
    conflict = sum([has_form, has_need, has_cat, has_how, has_trust]) >= 3
    if conflict and bucket not in ("KA-NF1","KA-NF2","KA-NF3"):
        confidence = min(confidence, 0.55)
        notes = (notes + "; " if notes else "") + "Multi-signal ambiguity"

    return RuleResult(bucket, intent, stage, paid, seo, is_neg, neg_type, neg_theme, confidence, notes)
