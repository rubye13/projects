"""Разбор грязных полей датасета объявлений

Парсеры нужны и в ноутбуке, и потом в сервисе: одно и то же правило
на обучении и на новых данных
"""

from __future__ import annotations

import ast
import re
from typing import Any

import numpy as np
import pandas as pd

PRICE_RE = re.compile(r"[^\d.]")
SQFT_RE = re.compile(r"[\d,]+")
NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def parse_price(value: Any) -> float:
    """Достаю цену из строки вроде $418,000, мусор ставлю как пропуск"""
    if pd.isna(value):
        return np.nan
    text = str(value).replace("\xa0", " ").strip().lower()
    if text in {"", "nan", "none", "price/sqft"}:
        return np.nan
    if "/mo" in text or "month" in text:
        return np.nan
    cleaned = PRICE_RE.sub("", text)
    if cleaned in {"", "."}:
        return np.nan
    try:
        price = float(cleaned)
    except ValueError:
        return np.nan
    if price <= 0:
        return np.nan
    return price


def parse_sqft(value: Any) -> float:
    """Достаю площадь в квадратных футах, участки в акрах и явный мусор отбрасываю"""
    if pd.isna(value):
        return np.nan
    text = str(value).replace("\xa0", " ").lower()
    if "acre" in text:
        return np.nan
    match = SQFT_RE.search(text.replace(" ", ""))
    if match is None:
        match = SQFT_RE.search(text)
    if match is None:
        return np.nan
    try:
        sqft = float(match.group(0).replace(",", ""))
    except ValueError:
        return np.nan
    if sqft < 120 or sqft > 20000:
        return np.nan
    return sqft


def parse_baths(value: Any) -> float:
    """Число ванных, значения больше 20 считаю ошибкой ввода"""
    if pd.isna(value):
        return np.nan
    text = str(value).replace("\xa0", " ").lower().replace(",", "")
    if "sqft" in text or "acre" in text:
        return np.nan
    match = NUM_RE.search(text)
    if match is None:
        return np.nan
    baths = float(match.group(0))
    if baths <= 0 or baths > 20:
        return np.nan
    return baths


def parse_beds(value: Any) -> float:
    """Число спален, если в поле попала площадь участка или ванная - выкидываю"""
    if pd.isna(value):
        return np.nan
    text = str(value).replace("\xa0", " ").strip().lower()
    if "acre" in text or "sqft" in text or "bath" in text:
        return np.nan
    if text in {"", "--", "-- bd", "nan"}:
        return np.nan
    match = NUM_RE.search(text)
    if match is None:
        return np.nan
    beds = float(match.group(0))
    if beds < 0 or beds > 20:
        return np.nan
    return beds


def parse_stories(value: Any) -> float:
    """Этажность, английские one, two, three перевожу в 1, 2, 3"""
    if pd.isna(value):
        return np.nan
    text = str(value).strip().lower()
    words = {
        "one": 1.0,
        "two": 2.0,
        "three": 3.0,
        "one level": 1.0,
        "one story": 1.0,
        "two story": 2.0,
        "three story": 3.0,
    }
    if text in words:
        return words[text]
    match = NUM_RE.search(text.replace(",", ""))
    if match is None:
        return np.nan
    stories = float(match.group(0))
    if stories < 0 or stories > 100:
        return np.nan
    return stories


def has_pool(row: pd.Series) -> int:
    """Склеиваю два столбца про бассейн: есть или нет"""
    left = str(row.get("private pool", "")).strip().lower()
    right = str(row.get("PrivatePool", "")).strip().lower()
    return int(left == "yes" or right == "yes")


def has_fireplace(value: Any) -> int:
    """Есть ли камин. Пусто, нет и ноль это 0, всё остальное 1"""
    if pd.isna(value):
        return 0
    text = str(value).strip().lower()
    if text in {"", "0", "no", "none", "not applicable", "n/a", "nan"}:
        return 0
    return 1


def _literal(value: Any) -> Any:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text in {"", "nan", "none"}:
        return None
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def parse_home_facts(value: Any) -> dict[str, Any]:
    """Год постройки, размер участка и флаги: отопление, кондиционер, парковка

    Названия вроде gas / central слишком пёстрые, оставляю только есть или нет
    Цену за фут не беру: это та же цена, только поделённая на площадь
    """
    blob = _literal(value)
    facts: dict[str, Any] = {
        "year_built": np.nan,
        "lotsize": np.nan,
        "remodeled": 0,
        "has_heating": 0,
        "has_cooling": 0,
        "has_parking": 0,
    }
    if not isinstance(blob, dict):
        return facts
    items = blob.get("atAGlanceFacts", [])
    if not isinstance(items, list):
        return facts
    mapping = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("factLabel", "")).strip().lower()
        mapping[label] = item.get("factValue")

    year = mapping.get("year built")
    if year not in (None, "", "no data"):
        match = NUM_RE.search(str(year))
        if match:
            year_num = float(match.group(0))
            if 1700 <= year_num <= 2025:
                facts["year_built"] = year_num

    remodel = mapping.get("remodeled year")
    if remodel not in (None, "", "no data"):
        facts["remodeled"] = 1

    for key, label in (
        ("has_heating", "heating"),
        ("has_cooling", "cooling"),
        ("has_parking", "parking"),
    ):
        raw = mapping.get(label)
        if raw not in (None, "", "no data", "none"):
            facts[key] = 1

    lot = mapping.get("lotsize")
    if lot not in (None, "", "no data"):
        text = str(lot).lower().replace(",", "")
        match = NUM_RE.search(text)
        if match:
            num = float(match.group(0))
            if "acre" in text:
                num *= 43560
            if 200 <= num <= 5_000_000:
                facts["lotsize"] = num
    return facts


def parse_zip(value: Any) -> str:
    """Пятизначный индекс. ZIP+4 обрезаю, короткий дополняю нулём слева"""
    if pd.isna(value):
        return "unknown"
    digits = re.sub(r"\D", "", str(value))
    if len(digits) >= 5:
        return digits[:5]
    if len(digits) == 4:
        return digits.zfill(5)
    return "unknown"


def parse_schools(value: Any) -> dict[str, float]:
    """Средний рейтинг школ и минимальное расстояние в милях"""
    blob = _literal(value)
    result = {"school_rating": np.nan, "school_dist": np.nan, "n_schools": 0.0}
    if not isinstance(blob, list) or not blob:
        return result
    ratings: list[float] = []
    dists: list[float] = []
    for school in blob:
        if not isinstance(school, dict):
            continue
        for rating in school.get("rating", []) or []:
            match = NUM_RE.search(str(rating))
            if match:
                num = float(match.group(0))
                if 0 <= num <= 10:
                    ratings.append(num)
        data = school.get("data") or {}
        for dist in data.get("Distance", []) or []:
            match = NUM_RE.search(str(dist))
            if match:
                num = float(match.group(0))
                if 0 <= num <= 100:
                    dists.append(num)
        names = school.get("name") or []
        result["n_schools"] = float(len(names) if names else 0)
    if ratings:
        result["school_rating"] = float(np.mean(ratings))
    if dists:
        result["school_dist"] = float(np.min(dists))
    return result


def normalize_status(value: Any) -> str:
    """Свожу статусы объявления к нескольким группам"""
    if pd.isna(value):
        return "unknown"
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    if "for sale" in text or text in {"active", "new", "new construction", "p"}:
        return "for_sale"
    if "pending" in text or "under contract" in text or "contingent" in text:
        return "pending"
    if "foreclos" in text:
        return "foreclosure"
    if "auction" in text:
        return "auction"
    if "sold" in text or "closed" in text:
        return "sold"
    return "other"


def normalize_property_type(value: Any) -> str:
    """Свожу тип дома к коротким группам: отдельно стоящий, кондо, таунхаус"""
    if pd.isna(value):
        return "unknown"
    text = str(value).strip().lower()
    if "land" in text or "lot" in text:
        return "land"
    if "condo" in text or "coop" in text or "co-op" in text:
        return "condo"
    if "town" in text:
        return "townhouse"
    if "multi" in text:
        return "multi_family"
    if "single" in text or "traditional" in text or "ranch" in text:
        return "single_family"
    if "mobile" in text or "manufactured" in text:
        return "mobile"
    return "other"


def clean_listings(df: pd.DataFrame) -> pd.DataFrame:
    """Чищу таблицу: дубли, участки без дома и объявления без нормальной цены"""
    out = df.copy()
    out = out.drop_duplicates()
    out["price"] = out["target"].map(parse_price)
    out["sqft"] = out["sqft"].map(parse_sqft)
    out["baths_n"] = out["baths"].map(parse_baths)
    out["beds_n"] = out["beds"].map(parse_beds)
    out["stories_n"] = out["stories"].map(parse_stories)
    out["pool"] = out.apply(has_pool, axis=1)
    out["fireplace_flg"] = out["fireplace"].map(has_fireplace)
    facts = out["homeFacts"].map(parse_home_facts).apply(pd.Series)
    schools = out["schools"].map(parse_schools).apply(pd.Series)
    out = pd.concat([out, facts, schools], axis=1)
    out["status_grp"] = out["status"].map(normalize_status)
    out["type_grp"] = out["propertyType"].map(normalize_property_type)
    out["city"] = out["city"].fillna("unknown").str.strip()
    out["state"] = out["state"].fillna("unknown").str.strip().str.upper()
    out["zip_code"] = out["zipcode"].map(parse_zip)

    out = out.loc[out["price"].notna()]
    out = out.loc[out["type_grp"] != "land"]
    out = out.loc[out["price"].between(10_000, 5_000_000)]
    out = out.drop(
        columns=[
            "private pool",
            "PrivatePool",
            "mls-id",
            "MlsId",
            "target",
            "homeFacts",
            "schools",
            "fireplace",
            "street",
            "zipcode",
        ],
        errors="ignore",
    )
    return out.reset_index(drop=True)
