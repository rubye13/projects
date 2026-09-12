"""Список признаков. Один и тот же набор в ноутбуке и в сервисе"""

import re

NUM_COLS = [
    "sqft",
    "baths_n",
    "beds_n",
    "stories_n",
    "year_built",
    "lotsize",
    "school_rating",
    "school_dist",
    "pool",
    "fireplace_flg",
    "remodeled",
    "has_heating",
    "has_cooling",
    "has_parking",
]

CAT_COLS = ["type_grp", "status_grp", "state"]
CB_CAT_COLS = ["type_grp", "status_grp", "state", "city", "zip_code"]

ZIP_RE = re.compile(r"\D")


def normalize_zip(value):
    """Индекс к пяти цифрам, как при очистке"""
    if value is None:
        return "unknown"
    digits = ZIP_RE.sub("", str(value))
    if len(digits) >= 5:
        return digits[:5]
    if len(digits) == 4:
        return digits.zfill(5)
    return "unknown"


def fill_sqft_by_type(frame, medians, fallback):
    """Дырки в площади заполняю медианой того же типа дома (медианы с обучения)"""
    out = frame.copy()
    mapped = out["type_grp"].map(medians)
    out["sqft"] = out["sqft"].fillna(mapped)
    if fallback is not None:
        out["sqft"] = out["sqft"].fillna(fallback)
    return out


def fold_category(series, keep, other="other"):
    """Редкие значения заменяю на other, список частых только с обучения"""
    return series.where(series.isin(keep), other)


def prepare_frame(
    frame, state_keep, city_keep, zip_keep, sqft_medians, sqft_fallback
):
    """Готовлю строку к прогнозу: штат, город, индекс, площадь как при обучении"""
    out = frame.copy()
    if "city" not in out.columns:
        out["city"] = "other"
    out["city"] = out["city"].fillna("unknown").astype(str).str.strip()
    out["city"] = fold_category(out["city"], city_keep)
    if "state" in out.columns:
        out["state"] = (
            out["state"].fillna("unknown").astype(str).str.strip().str.upper()
        )
        out["state"] = fold_category(out["state"], state_keep)
    if "zip_code" not in out.columns:
        out["zip_code"] = out["zipcode"] if "zipcode" in out.columns else "unknown"
    out["zip_code"] = out["zip_code"].map(normalize_zip)
    out["zip_code"] = fold_category(out["zip_code"], zip_keep)
    out = fill_sqft_by_type(out, sqft_medians, sqft_fallback)
    for col in CB_CAT_COLS:
        out[col] = out[col].fillna("unknown").astype(str)
    return out
