"""Чтение сырых файлов RetailRocket.

Повторяет подготовку из ноутбука недели 2: без дублей, время в datetime,
сессии по паузе больше 30 минут, из свойств только категория, доступность
и `790` (цена), из дерева категорий корень и глубина.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

EVENT_TYPES = ["view", "addtocart", "transaction"]
SESSION_GAP_MS = 30 * 60 * 1000
KEEP_PROPS = {"categoryid": "category", "available": "available", "790": "price"}


@dataclass
class Catalog:
    """Всё о товарах, что нужно для факторов: история свойств и дерево."""

    prop_hist: pd.DataFrame
    cat_root: pd.Series
    cat_depth: pd.Series


def load_events(raw_dir):
    events = pd.read_csv(Path(raw_dir) / "events.csv")
    events = events.drop_duplicates().reset_index(drop=True)
    events["dt"] = pd.to_datetime(events["timestamp"], unit="ms")
    events["day"] = events["dt"].dt.normalize()

    events = events.sort_values(["visitorid", "timestamp"]).reset_index(drop=True)
    gap = events.groupby("visitorid")["timestamp"].diff()
    events["session"] = (gap.isna() | (gap > SESSION_GAP_MS)).cumsum()
    return events


def load_properties(raw_dir, chunksize=5_000_000):
    """История трёх читаемых свойств. Файлы большие, читаю кусками."""
    parts = []
    for i in (1, 2):
        path = Path(raw_dir) / f"item_properties_part{i}.csv"
        for chunk in pd.read_csv(path, chunksize=chunksize):
            parts.append(chunk[chunk["property"].isin(KEEP_PROPS)])
    prop_hist = pd.concat(parts, ignore_index=True)
    prop_hist["dt"] = pd.to_datetime(prop_hist["timestamp"], unit="ms")
    prop_hist["property"] = prop_hist["property"].map(KEEP_PROPS)
    prop_hist["value"] = prop_hist["value"].str.lstrip("n").astype(float)
    prop_hist = prop_hist[["itemid", "property", "value", "dt"]]
    return prop_hist.sort_values("dt", kind="stable").reset_index(drop=True)


def load_category_tree(raw_dir):
    tree = pd.read_csv(Path(raw_dir) / "category_tree.csv")
    parent = tree.set_index("categoryid")["parentid"].to_dict()

    def category_path(cat_id):
        path = [cat_id]
        while pd.notna(parent.get(path[-1], np.nan)):
            path.append(int(parent[path[-1]]))
        return path

    tree["depth"] = tree["categoryid"].map(lambda c: len(category_path(c)) - 1)
    tree["root"] = tree["categoryid"].map(lambda c: category_path(c)[-1])
    tree = tree.set_index("categoryid")
    return tree["root"], tree["depth"]


def load_catalog(raw_dir):
    cat_root, cat_depth = load_category_tree(raw_dir)
    return Catalog(load_properties(raw_dir), cat_root, cat_depth)
